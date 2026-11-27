// Differential verification of the native feature-only path.
#include "ORBextractor.h"
#include "VioFeatureExchange.h"

#include <opencv2/imgcodecs.hpp>
#include <algorithm>
#include <chrono>
#include <iostream>
#include <stdexcept>
#include <vector>

using namespace ORB_SLAM3;

namespace {

struct Features {
    std::vector<cv::KeyPoint> keys;
    cv::Mat descriptors;
    int mono;
};

Features extract(ORBextractor& orb, int side, const cv::Mat& image) {
    Features result;
    std::vector<int> overlap{0, 0};
    VioFeatureCamera(side);
    result.mono = orb(image, cv::Mat(), result.keys, result.descriptors, overlap);
    VioFeatureCamera(-1);
    return result;
}

void compare(const Features& original, const Features& received) {
    const auto same = [](const cv::KeyPoint& a, const cv::KeyPoint& b) {
        return a.pt == b.pt && a.size == b.size && a.angle == b.angle
            && a.response == b.response && a.octave == b.octave && a.class_id == b.class_id;
    };
    if (original.mono != received.mono || original.keys.size() != received.keys.size()
        || !std::equal(original.keys.begin(), original.keys.end(), received.keys.begin(), same)
        || original.descriptors.size() != received.descriptors.size()
        || cv::norm(original.descriptors, received.descriptors, cv::NORM_INF) != 0)
        throw std::runtime_error("cached and native ORB features differ");
}

double time(ORBextractor& orb, const cv::Mat& image, const std::vector<char>& packet) {
    std::vector<double> samples;
    using Clock = std::chrono::steady_clock;
    for (int i = 0; i < 30; ++i) {
        const auto start = Clock::now();
        VioFeatureRequest(false, packet);
        extract(orb, 0, image);
        samples.push_back(std::chrono::duration<double, std::milli>(Clock::now() - start).count());
    }
    std::nth_element(samples.begin(), samples.begin() + samples.size()/2, samples.end());
    return samples[samples.size()/2];
}

}  // namespace

int main(int argc, char* argv[]) {
    if (argc != 3)
        throw std::runtime_error("test_feature_exchange LEFT.png RIGHT.png");
    cv::setNumThreads(1);
    const auto left = cv::imread(argv[1], cv::IMREAD_GRAYSCALE);
    const auto right = cv::imread(argv[2], cv::IMREAD_GRAYSCALE);
    if (left.empty() || right.empty())
        throw std::runtime_error("missing stereo test input");
    ORBextractor primary(1200, 1.2f, 8, 20, 7), mirror(1200, 1.2f, 8, 20, 7);
    VioFeatureRequest(true, {});
    const auto original_left = extract(primary, 0, left);
    const auto original_right = extract(primary, 1, right);
    const auto packet = VioFeatureReply();
    VioFeatureRequest(false, packet);
    compare(original_left, extract(mirror, 0, left));
    compare(original_right, extract(mirror, 1, right));
    if (VioFeatureHits() != 2)
        throw std::runtime_error("exact stereo did not hit twice");
    for (std::size_t level = 0; level < primary.mvImagePyramid.size(); ++level)
        if (cv::norm(primary.mvImagePyramid[level], mirror.mvImagePyramid[level], cv::NORM_INF) != 0)
            throw std::runtime_error("native image pyramid changed");
    auto changed = left.clone();
    changed.at<unsigned char>(10,10) ^= 1;
    VioFeatureRequest(false, packet);
    const auto fallback = extract(mirror, 0, changed);
    if (VioFeatureHits() != 0)
        throw std::runtime_error("other image accepted stale features");
    VioFeatureRequest(false, {});
    compare(fallback, extract(primary, 0, changed));
    auto truncated = packet;
    truncated.pop_back();
    VioFeatureRequest(false, truncated);
    compare(original_left, extract(mirror, 0, left));
    if (VioFeatureHits() != 0)
        throw std::runtime_error("incomplete stereo packet reused");
    std::cout << "left_keys=" << original_left.keys.size() << " right_keys=" << original_right.keys.size()
              << " packet_bytes=" << packet.size() << " native_left_median_ms=" << time(primary,left,{})
              << " shared_left_median_ms=" << time(mirror,left,packet) << '\n';
}
