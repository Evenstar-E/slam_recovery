#include "worker_input.hpp"

#include <condition_variable>
#include <cstdlib>
#include <deque>
#include <mutex>

#include <okvis/ThreadedSlam.hpp>
#include <okvis/ViParametersReader.hpp>
#include <okvis/timing/Timer.hpp>

static double recordedSeconds(std::initializer_list<const char *> tags) {
    double seconds = 0;
    for (const char *tag : tags) seconds += okvis::timing::Timing::getTotalSeconds(tag);
    return seconds;
}

static double frontendSeconds() {
    return recordedSeconds({"1 DetectAndDescribe", "2 Match"});
}

static double optimizationSeconds() {
    return recordedSeconds({"3 Optimise", "5 Import full optimisation", "7 Marginalise"});
}

static uint64_t elapsedNs(double start, double finish) {
    return static_cast<uint64_t>(std::max(0.0, finish - start) * 1e9);
}

static okvis::Time measurementTime(uint64_t stamp) {
    return okvis::Time(stamp / 1000000000, stamp % 1000000000);
}

struct CallbackPose {
    uint64_t stamp;
    bool good;
    Eigen::Vector3d position;
    Eigen::Quaterniond orientation;
    Eigen::Vector3d velocity, accelBias, gyroBias;

    void write(std::ostream &out) const {
        emit(out, stamp, good, position, orientation, velocity, accelBias, gyroBias);
    }
};

int main(int argc, char **argv) {
    if (argc != 5) return 2;
    google::InitGoogleLogging(argv[0]);
    cv::setNumThreads(1);
    okvis::ViParameters parameters;
    okvis::ViParametersReader(argv[1]).getParameters(parameters);
    std::mutex poseMutex;
    std::condition_variable callbackReady;
    std::deque<CallbackPose> mailbox;
    CallbackPose latest{};
    uint64_t lastVisual = 0;
    const bool pipelined = std::getenv("VIO_BLOCKING_CALLBACK") == nullptr;
    okvis::ThreadedSlam estimator(parameters, argv[2]);
    estimator.setBlocking(true);
    std::ofstream output(std::string("/proc/self/fd/") + argv[3]);
    if (!output) return 3;
    estimator.setOptimisedGraphCallback(
        [&](const okvis::State &state, const okvis::TrackingState &tracking, auto, auto) {
            std::lock_guard<std::mutex> guard(poseMutex);
            latest = {state.timestamp.toNSec(), tracking.trackingQuality != okvis::TrackingQuality::Lost,
                      state.T_WS.r(), state.T_WS.q(), state.v_W, state.b_a, state.b_g};
            if (pipelined) mailbox.push_back(latest);
            callbackReady.notify_one();
        });
    output << (pipelined ? "ready callback" : "ready") << std::endl;
    Request request;
    while (request.read()) {
        const auto received = nowNs();
        const double front = pipelined ? 0.0 : frontendSeconds();
        const double optimization = pipelined ? 0.0 : optimizationSeconds();
        for (const auto &imu : request.imu) {
            if (!estimator.addImuMeasurement(measurementTime(imu.stamp), imu.acceleration, imu.rotation))
                throw std::runtime_error("OKVIS2 refused IMU input");
        }
        if (!request.left.empty()) {
            lastVisual = request.stamp;
            if (!estimator.addImages(measurementTime(request.stamp),
                                     {{0, request.left}, {1, request.right}}))
                throw std::runtime_error("OKVIS2 refused stereo input");
        }
        const bool boundary = request.stamp == 0;
        if (boundary || !pipelined) {
            // The native empty-queue iteration joins the in-flight optimisation.
            while (estimator.processFrame()) {}
        } else if (!request.left.empty()) {
            // A single call lets next-frame detection overlap this optimisation.
            estimator.processFrame();
        }
        if (pipelined) {
            std::deque<CallbackPose> ready;
            {
                std::unique_lock<std::mutex> guard(poseMutex);
                if (boundary) {
                    callbackReady.wait_for(guard, std::chrono::milliseconds(10),
                                           [&] { return latest.stamp >= lastVisual; });
                }
                ready.swap(mailbox);
            }
            output << "batch " << request.stamp << ' ' << received << ' ' << nowNs()
                   << ' ' << ready.size() << '\n';
            for (const auto &state : ready) state.write(output);
            output.flush();
        } else {
            std::lock_guard<std::mutex> guard(poseMutex);
            emitTiming(output, request.stamp, received, elapsedNs(front, frontendSeconds()),
                       elapsedNs(optimization, optimizationSeconds()));
            if (latest.good && latest.stamp == request.stamp) {
                latest.write(output);
            } else {
                emit(output, request.stamp, false);
            }
        }
    }
    estimator.stopThreading();
}
