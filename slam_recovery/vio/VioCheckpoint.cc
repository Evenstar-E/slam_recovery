// ORB-SLAM3 checkpoint at a drained, initialized rectified stereo-inertial boundary.
#include "System.h"
#include "G2oTypes.h"
#include "SerializationUtils.h"
#include <boost/archive/binary_iarchive.hpp>
#include <boost/archive/binary_oarchive.hpp>
#include <fstream>
#include <limits>

namespace ORB_SLAM3 {
namespace {
constexpr unsigned int format_version = 1;
constexpr auto absent = std::numeric_limits<unsigned long>::max();

template<class Archive, class Matrix>
void matrix(Archive& ar, Matrix& value)
{
    ar & boost::serialization::make_array(value.data(), value.size());
}

template<class Archive, class PointRange>
void imu_samples(Archive& ar, PointRange& samples)
{
    std::vector<double> flat;
    if (Archive::is_saving::value)
        for (const auto& point : samples)
            flat.insert(flat.end(), {point.a.x(), point.a.y(), point.a.z(),
                                     point.w.x(), point.w.y(), point.w.z(), point.t});
    ar & flat;
    if (Archive::is_loading::value) {
        if (flat.size() % 7)
            throw std::runtime_error("invalid checkpoint IMU samples");
        samples.clear();
        for (std::size_t i = 0; i < flat.size(); i += 7)
            samples.emplace_back(flat[i], flat[i+1], flat[i+2], flat[i+3],
                                 flat[i+4], flat[i+5], flat[i+6]);
    }
}

template<class Archive, class Object>
void optional_value(Archive& ar, Object*& value)
{
    bool present = Archive::is_saving::value && value != nullptr;
    ar & present;
    if (Archive::is_loading::value)
        value = present ? new Object() : nullptr;
    if (present)
        ar & *value;
}

template<class Archive, class Object>
void reference(Archive& ar, Object*& value, const std::map<unsigned long, Object*>& objects)
{
    unsigned long id = Archive::is_saving::value && value && objects.count(value->mnId) ? value->mnId : absent;
    ar & id;
    if (Archive::is_loading::value)
        value = id == absent ? nullptr : objects.at(id);
}

template<class Archive, class Range, class Object>
void references(Archive& ar, Range& values, const std::map<unsigned long, Object*>& objects)
{
    std::size_t count = values.size();
    ar & count;
    if (Archive::is_loading::value)
        values.resize(count, nullptr);
    for (auto*& value : values)
        reference(ar, value, objects);
}
}  // namespace

template<class Archive>
void System::ArchiveVioState(Archive& ar)
{
    auto& t = *mpTracker;
    auto& lm = *mpLocalMapper;
    auto& lc = *mpLoopCloser;
    auto version = format_version;
    ar & version;
    if (version != format_version)
        throw std::runtime_error("unsupported native VIO checkpoint format");
    auto* map = mpAtlas->GetCurrentMap();
    int changed = map->GetMapChangeIndex(), notified = map->GetLastMapChange();
    ar & changed & notified;
    if (Archive::is_loading::value) {
        map->mnMapChange = changed;
        map->SetLastMapChange(notified);
    }

    std::map<unsigned long, KeyFrame*> keys;
    std::map<unsigned long, MapPoint*> points;
    for (auto* k : map->GetAllKeyFrames())
        keys.emplace(k->mnId, k);
    for (auto* p : map->GetAllMapPoints())
        points.emplace(p->mnId, p);
    for (const auto& item : points) {
        auto& point = *item.second;
        ar & point.mnVisible & point.mnFound & point.mnLastFrameSeen
           & point.mnTrackReferenceForFrame;
    }

    ar & t.mState & t.mLastProcessedState & t.mbCreatedMap & t.mbMapUpdated
       & t.mnLastKeyFrameId & t.mnLastRelocFrameId & t.mnMatchesInliers
       & t.mnFirstFrameId & t.mnInitialFrameId & t.mnFirstImuFrameId
       & t.mbVelocity & t.mLastBias;
    serializeSophusSE3(ar, t.mVelocity, 0);
    reference(ar, t.mpLastKeyFrame, keys);
    reference(ar, t.mpReferenceKF, keys);
    references(ar, t.mvpLocalKeyFrames, keys);
    references(ar, t.mvpLocalMapPoints, points);
    imu_samples(ar, t.mlQueueImuData);
    imu_samples(ar, t.mvImuFromLastFrame);
    optional_value(ar, t.mpImuPreintegratedFromLastKF);

    ar & Frame::fx & Frame::fy & Frame::cx & Frame::cy & Frame::invfx & Frame::invfy
       & Frame::mnMinX & Frame::mnMaxX & Frame::mnMinY & Frame::mnMaxY
       & Frame::mfGridElementWidthInv & Frame::mfGridElementHeightInv
       & Frame::mbInitialComputations;

    auto frame = [&](Frame& f) {
        ar & f.mnId & f.mTimeStamp & f.N & f.mnCloseMPs & f.mbf & f.mb & f.mThDepth
           & f.Nleft & f.Nright & f.mnDataset & f.mNameFile
           & f.mnScaleLevels & f.mfScaleFactor & f.mfLogScaleFactor
           & f.mvScaleFactors & f.mvInvScaleFactors & f.mvLevelSigma2 & f.mvInvLevelSigma2
           & f.mvuRight & f.mvDepth & f.mvbOutlier & f.mBowVec & f.mFeatVec
           & f.mImuCalib & f.mImuBias & f.mPredBias
           & f.mbIsSet & f.mbImuPreintegrated & f.mbHasPose & f.mbHasVelocity;
        serializeMatrix(ar, f.mK, 0);
        matrix(ar, f.mK_);
        serializeMatrix(ar, f.mDistCoef, 0);
        serializeVectorKeyPoints(ar, f.mvKeys, 0);
        serializeVectorKeyPoints(ar, f.mvKeysUn, 0);
        serializeVectorKeyPoints(ar, f.mvKeysRight, 0);
        serializeMatrix(ar, f.mDescriptors, 0);
        serializeMatrix(ar, f.mDescriptorsRight, 0);
        serializeSophusSE3(ar, f.mTcw, 0);
        matrix(ar, f.mVw);
        reference(ar, f.mpLastKeyFrame, keys);
        reference(ar, f.mpReferenceKF, keys);
        references(ar, f.mvpMapPoints, points);
        optional_value(ar, f.mpImuPreintegratedFrame);
        if (Archive::is_loading::value) {
            f.mpORBvocabulary = mpVocabulary;
            f.mpORBextractorLeft = t.mpORBextractorLeft;
            f.mpORBextractorRight = t.mpORBextractorRight;
            f.mpCamera = t.mpCamera;
            f.mpCamera2 = nullptr;
            f.mpImuPreintegrated = t.mpImuPreintegratedFromLastKF;
            f.mpMutexImu = new std::mutex;
            f.UpdatePoseMatrices();
            f.AssignFeaturesToGrid();
        }
    };
    frame(t.mCurrentFrame);
    frame(t.mLastFrame);

    // Track() copies the current frame into the last frame at this boundary.
    // The two shallow copies share the same prior, which the next optimizer owns.
    bool prior = t.mLastFrame.mpcpi != nullptr;
    ar & prior;
    if (prior) {
        if (Archive::is_loading::value)
            t.mLastFrame.mpcpi = new ConstraintPoseImu();
        auto& constraint = *t.mLastFrame.mpcpi;
        matrix(ar, constraint.Rwb);
        matrix(ar, constraint.twb);
        matrix(ar, constraint.vwb);
        matrix(ar, constraint.bg);
        matrix(ar, constraint.ba);
        matrix(ar, constraint.H);
    }
    auto lastRelative = t.mlRelativeFramePoses.empty() ? Sophus::SE3f()
                                                      : t.mlRelativeFramePoses.back();
    serializeSophusSE3(ar, lastRelative, 0);
    if (Archive::is_loading::value) {
        if (!t.mLastFrame.mpReferenceKF || !t.mpLastKeyFrame)
            throw std::runtime_error("checkpoint lost a tracking reference keyframe");
        t.mCurrentFrame.mpcpi = t.mLastFrame.mpcpi;
        t.mCurrentFrame.mpPrevFrame = &t.mLastFrame;
        t.mlRelativeFramePoses.push_back(lastRelative);
        t.mlpReferences.push_back(t.mLastFrame.mpReferenceKF);
        t.mlFrameTimes.push_back(t.mLastFrame.mTimeStamp);
        t.mlbLost.push_back(false);
        // Public trajectory history remains with the controller.
        t.mnFirstFrameId = t.mLastFrame.mnId;
        mTrackingState = t.mState;
    }
    ar & lm.mTinit & lm.mFirstTs & lm.mbNotBA1 & lm.mbNotBA2 & lm.mIdxInit
       & lm.mInitSect & lm.mScale & lm.mnMatchesInliers;
    reference(ar, lm.mpCurrentKeyFrame, keys);
    references(ar, lm.mlpRecentAddedMapPoints, points);
    if (Archive::is_loading::value)
        lm.mlpRecentAddedMapPoints.remove(nullptr);
    ar & lc.mLastLoopKFid;
    reference(ar, lc.mpLastCurrentKF, keys);

    auto mapReferences = map->GetReferenceMapPoints();
    references(ar, mapReferences, points);
    if (Archive::is_loading::value) {
        mapReferences.erase(std::remove(mapReferences.begin(), mapReferences.end(), nullptr),
                            mapReferences.end());
        map->SetReferenceMapPoints(mapReferences);
    }
}

bool System::SaveVioCheckpoint(const std::string& path)
{
    auto& t = *mpTracker;
    if (mSensor != IMU_STEREO || t.mState != Tracking::OK || t.mbOnlyTracking
            || !t.mLastFrame.HasVelocity() || t.mLastFrame.Nleft != -1
            || !t.mLastFrame.mpcpi || !t.mpImuPreintegratedFromLastKF
            || !t.mLastFrame.mpImuPreintegratedFrame || !mpAtlas->isImuInitialized()
            || mpAtlas->GetAllMaps().size() != 1)
        return false;
    std::unique_lock<std::mutex> local(mpLocalMapper->mVioCheckpointMutex, std::defer_lock);
    std::unique_lock<std::mutex> loop(mpLoopCloser->mVioCheckpointMutex, std::defer_lock);
    // The mapper and loop closer can wait for each other. Take both only at idle.
    if (std::try_lock(local, loop) != -1 || mpLocalMapper->KeyframesInQueue()
            || mpLocalMapper->mbBadImu || mpLoopCloser->CheckNewKeyFrames()
            || mpLoopCloser->isRunningGBA() || mpLoopCloser->mnLoopNumCoincidences
            || mpLoopCloser->mnMergeNumCoincidences)
        return false;
    auto* map = mpAtlas->GetCurrentMap();
    std::unique_lock<std::mutex> update(map->mMutexMapUpdate);
    mpAtlas->PreSave(true);
    {
        std::ofstream stream(path + ".map", std::ios::binary);
        stream.exceptions(std::ios::badbit | std::ios::failbit);
        boost::archive::binary_oarchive ar(stream);
        ar << mpAtlas;
    }
    {
        std::ofstream stream(path + ".state", std::ios::binary);
        stream.exceptions(std::ios::badbit | std::ios::failbit);
        boost::archive::binary_oarchive ar(stream);
        ArchiveVioState(ar);
    }
    return true;
}

void System::LoadVioMap(const std::string& path)
{
    std::ifstream stream(path + ".map", std::ios::binary);
    stream.exceptions(std::ios::badbit | std::ios::failbit);
    boost::archive::binary_iarchive ar(stream);
    mpAtlas = nullptr;
    ar >> mpAtlas;
    mpAtlas->SetKeyFrameDababase(mpKeyFrameDatabase);
    mpAtlas->SetORBVocabulary(mpVocabulary);
    mpAtlas->PostLoad();
    const auto maps = mpAtlas->GetAllMaps();
    if (maps.size() != 1 || !maps[0]->isImuInitialized())
        throw std::runtime_error("checkpoint requires one initialized active map");
    mpAtlas->ChangeMap(maps[0]);
}

void System::LoadVioState(const std::string& path)
{
    std::ifstream stream(path + ".state", std::ios::binary);
    stream.exceptions(std::ios::badbit | std::ios::failbit);
    boost::archive::binary_iarchive ar(stream);
    ArchiveVioState(ar);
}
}  // namespace ORB_SLAM3
