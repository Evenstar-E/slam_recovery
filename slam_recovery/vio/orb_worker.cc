// A single native ORB-SLAM3 instance. The supervisor owns the input and output streams.
#include "System.h"
#include "VioFeatureExchange.h"

#include <array>
#include <cstdint>
#include <cstdio>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

template<class T>
void read_value(T& value) {
    if (!std::cin.read(reinterpret_cast<char*>(&value), sizeof(value)))
        throw std::runtime_error("truncated worker request");
}

int main(int argc, char* argv[]) try {
    if (argc != 4)
        throw std::runtime_error("orb_worker VOCABULARY SETTINGS RESPONSE_FD");
    FILE* responses = fdopen(std::stoi(argv[3]), "w");
    if (!responses)
        throw std::runtime_error("cannot open response pipe");

    cv::setNumThreads(1);
    ORB_SLAM3::System slam(argv[1], argv[2], ORB_SLAM3::System::IMU_STEREO, false);
    if (std::getenv("ORB_VIO_REPORT_READY")) {
        if (std::fputs("READY\n", responses) == EOF || std::fflush(responses))
            throw std::runtime_error("cannot report worker readiness");
    }
    const bool feature_protocol = std::getenv("ORB_VIO_FEATURE_PROTOCOL") != nullptr;
    for (std::uint32_t width; std::cin.peek() != EOF;) {
        std::int64_t timestamp;
        std::uint32_t height, samples;
        read_value(timestamp);
        read_value(width);
        read_value(height);
        read_value(samples);
        std::int32_t feature_size = 0;
        if (feature_protocol)
            read_value(feature_size);
        if (feature_size < -1 || feature_size > 512 * 1024)
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
            ORB_SLAM3::VioFeatureRequest(feature_size == -1, feature_packet);
        }
        const auto Tcw = slam.TrackStereo(left, right, static_cast<double>(timestamp) * 1e-9, imu);
        const auto translation = Tcw.translation();
        const auto rotation = Tcw.unit_quaternion();
        std::ostringstream row;
        row.imbue(std::locale::classic());
        row << std::setprecision(10) << timestamp << ' ' << slam.GetTrackingState()
            << ' ' << translation.x() << ' ' << translation.y() << ' ' << translation.z()
            << ' ' << rotation.x() << ' ' << rotation.y() << ' ' << rotation.z() << ' ' << rotation.w();
        slam.WriteVioSnapshot(row);
        if (std::fprintf(responses, "%s\n", row.str().c_str()) < 0 || std::fflush(responses))
            throw std::runtime_error("cannot write worker response");
        if (feature_protocol) {
            const auto reply = ORB_SLAM3::VioFeatureReply();
            if (std::fprintf(responses, "%u %zu\n", ORB_SLAM3::VioFeatureHits(), reply.size()) < 0
                || (!reply.empty() && std::fwrite(reply.data(), 1, reply.size(), responses) != reply.size())
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
