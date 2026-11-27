#include "worker_input.hpp"

#include <dlfcn.h>

#include "estimator/estimator.h"
#include "estimator/parameters.h"
#include "utility/visualization.h"

namespace {
uint64_t frontendNs = 0;
uint64_t optimizationNs = 0;

template <typename Function>
Function hostFunction(const char *symbol) {
    auto address = reinterpret_cast<Function>(dlsym(RTLD_NEXT, symbol));
    if (!address) throw std::runtime_error(std::string("missing VINS profiling symbol: ") + symbol);
    return address;
}
}  // namespace

// Interpose the two synchronous calls in the pinned shared library. Both
// bodies still execute the original host functions with unchanged arguments.
std::map<int, std::vector<std::pair<int, Eigen::Matrix<double, 7, 1>>>>
FeatureTracker::trackImage(double time, const cv::Mat &left, const cv::Mat &right) {
    using Tracks = std::map<int, std::vector<std::pair<int, Eigen::Matrix<double, 7, 1>>>>;
    using Native = Tracks (*)(FeatureTracker *, double, const cv::Mat &, const cv::Mat &);
    static const Native native = hostFunction<Native>("_ZN14FeatureTracker10trackImageEdRKN2cv3MatES3_");
    const auto start = nowNs();
    auto result = native(this, time, left, right);
    frontendNs += nowNs() - start;
    return result;
}

void Estimator::optimization() {
    using Native = void (*)(Estimator *);
    static const Native native = hostFunction<Native>("_ZN9Estimator12optimizationEv");
    const auto start = nowNs();
    native(this);
    optimizationNs += nowNs() - start;
}

int main(int argc, char **argv) {
    if (argc != 5) return 2;
    int rosArgc = 1;
    ros::init(rosArgc, argv, argv[4], ros::init_options::NoSigintHandler);
    ros::NodeHandle privateNode("~");
    cv::setNumThreads(1);
    readParameters(argv[1]);
    if (MULTIPLE_THREAD || SHOW_TRACK || !USE_IMU || NUM_OF_CAM != 2) return 3;
    registerPub(privateNode);
    // Match the native entry point: clearState reads pointers zeroed by static storage.
    static Estimator estimator;
    estimator.setParameter();
    std::ofstream output(std::string("/proc/self/fd/") + argv[3]);
    if (!output) return 4;
    output << "ready" << std::endl;
    Request request;
    constexpr double nano = 1.0 / 1000000000;
    while (request.read()) {
        const auto received = nowNs();
        frontendNs = optimizationNs = 0;
        for (const auto &imu : request.imu) {
            estimator.inputIMU(imu.stamp * nano, imu.acceleration, imu.rotation);
        }
        const double time = request.stamp * nano;
        if (!request.left.empty()) estimator.inputImage(time, request.left, request.right);
        const bool exact = !request.left.empty() && estimator.prevTime == time + estimator.td
                        && estimator.solver_flag == Estimator::NON_LINEAR;
        emitTiming(output, request.stamp, received, frontendNs, optimizationNs);
        emit(output, request.stamp, exact, estimator.Ps[WINDOW_SIZE],
             Eigen::Quaterniond(estimator.Rs[WINDOW_SIZE]),
             estimator.Vs[WINDOW_SIZE], estimator.Bas[WINDOW_SIZE], estimator.Bgs[WINDOW_SIZE]);
    }
}
