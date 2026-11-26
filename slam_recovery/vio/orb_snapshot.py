"""Install the diagnostic API on the pinned ORB-SLAM3 checkout."""
import sys
from pathlib import Path


HEADER = "    int GetTrackingState();"
DECLARATION = HEADER + "\n    void WriteVioSnapshot(std::ostream& out);"
METHOD = r'''
void System::WriteVioSnapshot(std::ostream& out)
{
    // In offline replay, drain pending local work before sampling a boundary.
    // This changes scheduling only. Tracking, loop detection, and Atlas stay active.
    if (std::getenv("ORB_VIO_DRAIN_LOCAL_MAPPING")) {
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(3);
        while (mpLocalMapper->KeyframesInQueue() || !mpLocalMapper->AcceptKeyFrames()
               || mpLoopCloser->isRunningGBA()) {
            if (std::chrono::steady_clock::now() >= deadline)
                throw std::runtime_error("could not drain VIO frame boundary");
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
    }
    Map* map = mpAtlas->GetCurrentMap();
    std::unique_lock<std::mutex> guard(map->mMutexMapUpdate);
    Frame& frame = mpTracker->mCurrentFrame;
    const bool initialized = map->isImuInitialized();
    const bool inertial = initialized && frame.isSet()
        && mpTracker->mState == Tracking::OK && frame.mpImuPreintegratedFrame;
    std::array<bool, 16> cells{};
    int occupied = 0;
    std::vector<float> reprojections;
    if (frame.isSet() && frame.mpCamera) {
        const auto Tcw = frame.GetPose();
        const size_t count = std::min({frame.mvKeysUn.size(), frame.mvpMapPoints.size(),
                                       frame.mvbOutlier.size()});
        const float width = frame.mnMaxX - frame.mnMinX;
        const float height = frame.mnMaxY - frame.mnMinY;
        for (size_t i = 0; i < count && width > 0 && height > 0; ++i) {
            auto* point = frame.mvpMapPoints[i];
            if (!point || frame.mvbOutlier[i] || point->isBad())
                continue;
            const Eigen::Vector3f xyz = Tcw * point->GetWorldPos();
            if (!xyz.allFinite() || xyz.z() <= 0)
                continue;
            const auto pixel = frame.mpCamera->project(xyz);
            const auto key = frame.mvKeysUn[i].pt;
            const float error = std::hypot(pixel.x() - key.x, pixel.y() - key.y);
            if (!std::isfinite(error))
                continue;
            reprojections.push_back(error);
            const int col = std::max(0, std::min(3, int(4 * (key.x - frame.mnMinX) / width)));
            const int row = std::max(0, std::min(3, int(4 * (key.y - frame.mnMinY) / height)));
            if (!cells[4 * row + col]) {
                cells[4 * row + col] = true;
                ++occupied;
            }
        }
    }
    float median = -1;
    if (!reprojections.empty()) {
        auto middle = reprojections.begin() + reprojections.size() / 2;
        std::nth_element(reprojections.begin(), middle, reprojections.end());
        median = *middle;
    }
    out << ' ' << initialized << ' ' << map->GetId()
        << ' ' << map->GetAllKeyFrames().size()
        << ' ' << mpAtlas->GetAllMaps().size()
        << ' ' << mpLocalMapper->KeyframesInQueue()
        << ' ' << reprojections.size() << ' ' << occupied << ' ' << median
        << ' ' << inertial;
    if (!inertial)
        return;

    const auto velocity = frame.GetVelocity();
    const auto bias = frame.mImuBias;
    auto* preint = frame.mpImuPreintegratedFrame;
    const auto dp = preint->GetUpdatedDeltaPosition();
    const auto dv = preint->GetUpdatedDeltaVelocity();
    const Eigen::Quaternionf dq(preint->GetUpdatedDeltaRotation());
    out << ' ' << velocity.x() << ' ' << velocity.y() << ' ' << velocity.z()
        << ' ' << bias.bax << ' ' << bias.bay << ' ' << bias.baz
        << ' ' << bias.bwx << ' ' << bias.bwy << ' ' << bias.bwz
        << ' ' << preint->dT << ' ' << dp.x() << ' ' << dp.y() << ' ' << dp.z()
        << ' ' << dv.x() << ' ' << dv.y() << ' ' << dv.z()
        << ' ' << dq.x() << ' ' << dq.y() << ' ' << dq.z() << ' ' << dq.w();
}
'''


def install(root: Path) -> None:
    header = root / "include/System.h"
    source = root / "src/System.cc"
    h, s = header.read_text(), source.read_text()
    marker = "int System::GetTrackingState()"
    if DECLARATION in h and METHOD in s:
        return
    if (h.count(HEADER), s.count(marker)) != (1, 1) or DECLARATION in h or METHOD in s:
        raise ValueError("unexpected ORB-SLAM3 source")
    header.write_text(h.replace(HEADER, DECLARATION))
    source.write_text(s.replace(marker, METHOD + "\n" + marker))


if __name__ == "__main__":
    install(Path(sys.argv[1]))
