#ifndef VIO_FEATURE_EXCHANGE_H
#define VIO_FEATURE_EXCHANGE_H

#include <opencv2/core.hpp>
#include <cstdint>
#include <vector>

namespace ORB_SLAM3 {

// Called by the synchronous worker around one TrackStereo request.
void VioFeatureRequest(bool capture, const std::vector<char>& packet);
std::vector<char> VioFeatureReply();
unsigned VioFeatureHits();
void VioFeatureCamera(int side);
std::uint64_t VioFeatureSignature(const cv::Mat& image, const int config[], int size, double scale);
bool VioReadFeatures(std::uint64_t signature, std::vector<cv::KeyPoint>& keys,
                     cv::OutputArray descriptors, int& mono);
void VioWriteFeatures(std::uint64_t signature, const std::vector<cv::KeyPoint>& keys,
                      const cv::Mat& descriptors, int mono);

}  // namespace ORB_SLAM3
#endif
