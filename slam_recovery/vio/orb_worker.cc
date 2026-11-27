// A single native ORB-SLAM3 instance. The supervisor owns the input and output streams.
#include "System.h"
#include "VioFeatureExchange.h"
#include "VioVocabulary.h"

#include <array>
#include <cstdint>
#include <cstdio>
#include <iomanip>
#include <limits>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <unistd.h>

namespace ORB_SLAM3 {
void WriteVioReplaySnapshot(System& system, std::ostream& out);
bool WriteVioBoundarySnapshot(System& system, std::ostream& out);
}

template<class T>
void read_value(T& value) {
    if (!std::cin.read(reinterpret_cast<char*>(&value), sizeof(value)))
        throw std::runtime_error("truncated worker request");
}

namespace {
constexpr std::size_t feature_capacity = 512 * 1024;
constexpr auto save_checkpoint = std::numeric_limits<std::int64_t>::min();
constexpr auto async_frame = save_checkpoint + 1;
constexpr auto read_boundary = save_checkpoint + 2;
struct FeatureSlot {
    std::uint64_t generation;
    std::uint64_t size;
};

off_t feature_offset(std::uint64_t generation, std::uint64_t slots) {
    return (generation % slots) * (sizeof(FeatureSlot) + feature_capacity);
}

std::vector<char> load_features(int fd, std::uint64_t generation, std::uint64_t slots) {
    const auto offset = feature_offset(generation, slots);
    FeatureSlot header{}, current{};
    if (pread(fd, &header, sizeof(header), offset) != sizeof(header)
        || header.generation != generation || header.size > feature_capacity)
        return {};
    std::vector<char> packet(header.size);
    if (pread(fd, packet.data(), packet.size(), offset + sizeof(header))
            != static_cast<ssize_t>(packet.size())
        || pread(fd, &current, sizeof(current), offset) != sizeof(current)
        || current.generation != generation)
        return {};
    return packet;
}

void save_features(int fd, std::uint64_t generation, std::uint64_t slots, const std::vector<char>& packet) {
    const auto offset = feature_offset(generation, slots);
    const FeatureSlot empty{};
    const FeatureSlot header{generation, packet.size()};
    if (packet.size() > feature_capacity
        || pwrite(fd, &empty, sizeof(empty), offset) != sizeof(empty)
        || pwrite(fd, packet.data(), packet.size(), offset + sizeof(header))
            != static_cast<ssize_t>(packet.size())
        || pwrite(fd, &header, sizeof(header), offset) != sizeof(header))
        throw std::runtime_error("cannot save shared ORB features");
}
}  // namespace

int main(int argc, char* argv[]) try {
    if (argc == 4 && std::string(argv[1]) == "--cache-vocabulary") {
        ORB_SLAM3::WriteVioVocabulary(argv[2], argv[3]);
        return 0;
    }
    if (argc != 4)
        throw std::runtime_error("orb_worker VOCABULARY SETTINGS RESPONSE_FD");
    FILE* responses = fdopen(std::stoi(argv[3]), "w");
    if (!responses)
        throw std::runtime_error("cannot open response pipe");

    cv::setNumThreads(1);
    ORB_SLAM3::System slam(argv[1], argv[2], ORB_SLAM3::System::IMU_STEREO, false);
    const bool boundaries = std::getenv("ORB_VIO_BOUNDARY_PROTOCOL");
    if (std::getenv("ORB_VIO_REPORT_READY")) {
        const char* ready = boundaries ? "READY BOUNDARY_V1\n" : "READY\n";
        if (std::fputs(ready, responses) == EOF || std::fflush(responses))
            throw std::runtime_error("cannot report worker readiness");
    }
    const bool feature_protocol = std::getenv("ORB_VIO_FEATURE_PROTOCOL") != nullptr;
    const char* feature_fd_env = std::getenv("ORB_VIO_FEATURE_FD");
    const int feature_fd = feature_fd_env ? std::stoi(feature_fd_env) : -1;
    const char* slots_env = std::getenv("ORB_VIO_FEATURE_SLOTS");
    const auto slots = slots_env ? std::stoull(slots_env) : 16;
    if (slots == 0)
        throw std::runtime_error("shared ORB feature ring has no slots");
    std::int64_t last_frame = 0;
    for (std::uint32_t width; std::cin.peek() != EOF;) {
        std::int64_t timestamp;
        std::uint32_t height, samples;
        read_value(timestamp);
        if (timestamp == save_checkpoint) {
            std::uint32_t length;
            read_value(length);
            if (length == 0 || length > 4096)
                throw std::runtime_error("invalid checkpoint path length");
            std::string path(length, '\0');
            if (!std::cin.read(&path[0], length))
                throw std::runtime_error("missing checkpoint path");
            const char* acknowledgement = "BUSY\n";
            try {
                if (slam.SaveVioCheckpoint(path))
                    acknowledgement = "SAVED\n";
            } catch (const std::exception& error) {
                std::cerr << "cannot save checkpoint: " << error.what() << std::endl;
                acknowledgement = "SAVEERROR\n";
            }
            if (std::fputs(acknowledgement, responses) == EOF || std::fflush(responses))
                throw std::runtime_error("cannot acknowledge native checkpoint");
            continue;
        }
        if (boundaries && timestamp == read_boundary) {
            std::ostringstream row;
            row.imbue(std::locale::classic());
            row << std::setprecision(10) << last_frame;
            const auto reply = last_frame && ORB_SLAM3::WriteVioBoundarySnapshot(slam, row)
                ? row.str() : "BOUNDARY_BUSY";
            if (std::fprintf(responses, "%s\n", reply.c_str()) < 0 || std::fflush(responses))
                throw std::runtime_error("cannot acknowledge native boundary");
            continue;
        }
        const bool asynchronous = boundaries && timestamp == async_frame;
        if (asynchronous)
            read_value(timestamp);
        read_value(width);
        read_value(height);
        read_value(samples);
        std::int32_t feature_size = 0;
        if (feature_protocol)
            read_value(feature_size);
        const bool shared = feature_size == -2 || feature_size == -3;
        std::uint64_t generation = 0;
        if (shared) {
            if (feature_fd < 0)
                throw std::runtime_error("shared ORB feature descriptor missing");
            read_value(generation);
        }
        if (feature_size < -3 || feature_size > static_cast<std::int32_t>(feature_capacity))
            throw std::runtime_error("invalid ORB feature payload width");
        if (!width || !height || width > 4096 || height > 4096 || samples > 10000)
            throw std::runtime_error("invalid frame dimensions or IMU count");

        cv::Mat left(height, width, CV_8UC1), right(height, width, CV_8UC1);
        for (auto* image : {&left, &right})
            if (!std::cin.read(reinterpret_cast<char*>(image->data),
                               static_cast<std::streamsize>(width) * height))
                throw std::runtime_error("truncated stereo pair");

        std::vector<ORB_SLAM3::IMU::Point> imu;
        imu.reserve(samples);
        for (std::uint32_t i = 0; i < samples; ++i) {
            std::int64_t time;
            std::array<float, 6> values;  // ax ay az gx gy gz
            read_value(time);
            read_value(values);
            imu.emplace_back(values[0], values[1], values[2], values[3], values[4], values[5],
                             static_cast<double>(time) * 1e-9);
        }

        if (feature_protocol) {
            std::vector<char> feature_packet(feature_size > 0 ? feature_size : 0);
            if (!feature_packet.empty() && !std::cin.read(feature_packet.data(), feature_packet.size()))
                throw std::runtime_error("truncated ORB feature payload");
            if (feature_size == -3)
                feature_packet = load_features(feature_fd, generation, slots);
            ORB_SLAM3::VioFeatureRequest(feature_size == -1 || feature_size == -2, feature_packet);
        }
        const auto Tcw = slam.TrackStereo(left, right, static_cast<double>(timestamp) * 1e-9, imu);
        const auto translation = Tcw.translation();
        const auto rotation = Tcw.unit_quaternion();
        std::ostringstream row;
        row.imbue(std::locale::classic());
        row << std::setprecision(10) << timestamp << ' ' << slam.GetTrackingState()
            << ' ' << translation.x() << ' ' << translation.y() << ' ' << translation.z()
            << ' ' << rotation.x() << ' ' << rotation.y() << ' ' << rotation.z() << ' ' << rotation.w();
        if (asynchronous)
            ORB_SLAM3::WriteVioReplaySnapshot(slam, row);
        else
            slam.WriteVioSnapshot(row);
        last_frame = timestamp;
        if (std::fprintf(responses, "%s\n", row.str().c_str()) < 0 || std::fflush(responses))
            throw std::runtime_error("cannot write worker response");
        if (feature_protocol) {
            const auto reply = ORB_SLAM3::VioFeatureReply();
            if (feature_size == -2)
                save_features(feature_fd, generation, slots, reply);
            if (std::fprintf(responses, "%u %zu\n", ORB_SLAM3::VioFeatureHits(), reply.size()) < 0
                || (!shared && !reply.empty() && std::fwrite(reply.data(), 1, reply.size(), responses) != reply.size())
                || std::fflush(responses))
                throw std::runtime_error("cannot write ORB feature response");
        }
    }
    slam.Shutdown();
    std::fclose(responses);
    return 0;
} catch (const std::exception& error) {
    std::cerr << "orb_worker: " << error.what() << std::endl;
    return 1;
}
