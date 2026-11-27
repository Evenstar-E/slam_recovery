#include "VioFeatureExchange.h"

#include <array>
#include <cstddef>
#include <cstring>

namespace ORB_SLAM3 {
namespace {

struct PacketHeader {
    std::uint64_t signature;
    std::uint32_t keypoints;
    std::int32_t mono;
};
struct KeypointFields {
    float x, y, size, angle, response;
    int octave, class_id;
};
constexpr std::size_t bytes_per_key = sizeof(KeypointFields) + 32;
constexpr std::uint32_t max_keys = 4096;

struct FrameExchange {
    bool capture = false;
    bool consume = false;
    // Each extraction thread writes only its own slot, joined before reply.
    std::array<std::vector<char>, 2> packets;
    std::array<unsigned, 2> hits;
};

FrameExchange exchange;
thread_local int camera = -1;

void mix(std::uint64_t& hash, const void* data, std::size_t size) {
    const auto* bytes = static_cast<const std::uint8_t*>(data);
    for (std::size_t n = 0; n < size; ++n) {
        hash ^= bytes[n];
        hash *= 1099511628211ULL;
    }
}

}  // namespace

void VioFeatureRequest(bool capture, const std::vector<char>& packet) {
    exchange.capture = capture;
    exchange.consume = false;
    exchange.hits.fill(0);
    for (auto& side : exchange.packets)
        side.clear();
    std::size_t offset = 0;
    for (auto& side : exchange.packets) {
        if (packet.size() - offset < sizeof(PacketHeader))
            return;
        PacketHeader header;
        std::memcpy(&header, packet.data() + offset, sizeof(header));
        if (header.keypoints > max_keys || header.mono < 0
            || static_cast<std::uint32_t>(header.mono) > header.keypoints)
            return;
        const std::size_t bytes = sizeof(header) + header.keypoints * bytes_per_key;
        if (packet.size() - offset < bytes)
            return;
        side.assign(packet.begin() + offset, packet.begin() + offset + bytes);
        offset += bytes;
    }
    exchange.consume = offset == packet.size();
}

std::vector<char> VioFeatureReply() {
    if (!exchange.capture || exchange.packets[0].empty() || exchange.packets[1].empty())
        return {};
    std::vector<char> reply = exchange.packets[0];
    reply.insert(reply.end(), exchange.packets[1].begin(), exchange.packets[1].end());
    return reply;
}

unsigned VioFeatureHits() {
    return exchange.hits[0] + exchange.hits[1];
}

void VioFeatureCamera(int side) {
    camera = side;
}

std::uint64_t VioFeatureSignature(const cv::Mat& image, const int config[], int size, double scale) {
    if (camera < 0 || (!exchange.capture && !exchange.consume))
        return 0;
    std::uint64_t hash = 14695981039346656037ULL;
    mix(hash, &image.rows, sizeof(image.rows));
    mix(hash, &image.cols, sizeof(image.cols));
    mix(hash, config, size * sizeof(int));
    mix(hash, &scale, sizeof(scale));
    for (int row = 0; row < image.rows; ++row)
        mix(hash, image.ptr(row), image.cols);
    return hash;
}

bool VioReadFeatures(std::uint64_t signature, std::vector<cv::KeyPoint>& keys,
                     cv::OutputArray descriptors, int& mono) {
    if (!exchange.consume || camera < 0 || !signature)
        return false;
    const auto& side = exchange.packets[camera];
    PacketHeader header;
    std::memcpy(&header, side.data(), sizeof(header));
    if (header.signature != signature)
        return false;
    keys.resize(header.keypoints);
    if (header.keypoints) {
        const auto* data = side.data() + sizeof(header);
        const auto bytes = keys.size() * sizeof(KeypointFields);
        for (std::size_t i = 0; i < keys.size(); ++i) {
            KeypointFields fields;
            std::memcpy(&fields, data + i * sizeof(fields), sizeof(fields));
            keys[i] = cv::KeyPoint(fields.x, fields.y, fields.size, fields.angle,
                                   fields.response, fields.octave, fields.class_id);
        }
        descriptors.create(header.keypoints, 32, CV_8U);
        std::memcpy(descriptors.getMat().data, data + bytes, header.keypoints * 32);
    } else {
        descriptors.release();
    }
    mono = header.mono;
    exchange.hits[camera] = 1;
    return true;
}

void VioWriteFeatures(std::uint64_t signature, const std::vector<cv::KeyPoint>& keys,
                      const cv::Mat& descriptors, int mono) {
    if (!exchange.capture || camera < 0 || !signature || keys.size() > max_keys)
        return;
    const PacketHeader header{signature, static_cast<std::uint32_t>(keys.size()), mono};
    auto& side = exchange.packets[camera];
    side.resize(sizeof(header) + keys.size() * bytes_per_key);
    std::memcpy(side.data(), &header, sizeof(header));
    if (!keys.empty()) {
        auto* data = side.data() + sizeof(header);
        const auto bytes = keys.size() * sizeof(KeypointFields);
        for (std::size_t i = 0; i < keys.size(); ++i) {
            const auto& key = keys[i];
            const KeypointFields fields{key.pt.x, key.pt.y, key.size, key.angle,
                                        key.response, key.octave, key.class_id};
            std::memcpy(data + i * sizeof(fields), &fields, sizeof(fields));
        }
        std::memcpy(data + bytes, descriptors.data, keys.size() * 32);
    }
}

}  // namespace ORB_SLAM3
