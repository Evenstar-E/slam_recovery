#pragma once

#include <chrono>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <vector>

#include <Eigen/Geometry>
#include <opencv2/core.hpp>

inline uint64_t nowNs() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}

inline void emitTiming(std::ostream &out, uint64_t stamp, uint64_t received,
                       uint64_t frontend, uint64_t optimization) {
    out << "timing " << stamp << ' ' << received << ' ' << nowNs() << ' '
        << frontend << ' ' << optimization << '\n';
}

struct Sample {
    uint64_t stamp;
    Eigen::Vector3d acceleration, rotation;
};

struct Request {
    uint64_t stamp;
    std::vector<Sample> imu;
    cv::Mat left, right;

    bool read() {
        unsigned count, rows, cols;
        if (!(std::cin >> stamp >> count >> rows >> cols)) {
            return false;
        }
        if (count > 2000 || rows > 2000 || cols > 2000 || ((rows == 0) != (cols == 0))) {
            throw std::runtime_error("invalid measurement dimensions");
        }
        imu.resize(count);
        for (auto &sample : imu) {
            std::cin >> sample.stamp;
            for (int i = 0; i < 3; ++i) std::cin >> sample.acceleration[i];
            for (int i = 0; i < 3; ++i) std::cin >> sample.rotation[i];
        }
        if (!std::cin || std::cin.get() != '\n') {
            throw std::runtime_error("malformed measurement packet");
        }
        left = cv::Mat(rows, cols, CV_8UC1);
        right = cv::Mat(rows, cols, CV_8UC1);
        if (rows && (!std::cin.read(reinterpret_cast<char *>(left.data), rows * cols) ||
                     !std::cin.read(reinterpret_cast<char *>(right.data), rows * cols))) {
            throw std::runtime_error("incomplete image packet");
        }
        return true;
    }
};

inline void emit(std::ostream &output, uint64_t stamp, bool ready,
                 const Eigen::Vector3d &position = Eigen::Vector3d::Zero(),
                 const Eigen::Quaterniond &orientation = Eigen::Quaterniond::Identity(),
                 const Eigen::Vector3d &velocity = Eigen::Vector3d::Zero(),
                 const Eigen::Vector3d &accelBias = Eigen::Vector3d::Zero(),
                 const Eigen::Vector3d &gyroBias = Eigen::Vector3d::Zero()) {
    output << std::setprecision(17) << stamp << ' ' << ready;
    if (ready) {
        for (int i = 0; i < 3; ++i) output << ' ' << position[i];
        for (int i = 0; i < 4; ++i) output << ' ' << orientation.coeffs()[i];
        for (const auto &vector : {velocity, accelBias, gyroBias}) {
            for (int i = 0; i < 3; ++i) output << ' ' << vector[i];
        }
    }
    output << std::endl;
}
