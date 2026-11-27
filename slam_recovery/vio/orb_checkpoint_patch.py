"""Install the persistent stereo-inertial checkpoint into the pinned ORB source."""
import sys
from pathlib import Path


def install(root):
    files = {}

    def edit(rel, before, after):
        old = files[rel] if rel in files else (root / rel).read_text()
        if old.count(before) != 1:
            raise ValueError(f"unexpected native source {rel}: {before!r}")
        files[rel] = old.replace(before, after)

    here = Path(__file__).parent
    additions = ("src/VioCheckpoint.cc", "src/VioVocabulary.cc", "include/VioVocabulary.h")

    def copy_additions():
        for rel in additions:
            (root / rel).write_bytes((here / Path(rel).name).read_bytes())

    if all((root / rel).exists() for rel in additions):
        copy_additions()
        return

    for cls in ("Frame", "Tracking", "LocalMapping", "LoopClosing", "Map", "MapPoint"):
        edit(f"include/{cls}.h", f"class {cls}\n{{", f"class {cls}\n{{\n    friend class System;")

    edit("include/G2oTypes.h", "    ConstraintPoseImu(const Eigen::Matrix3d",
         "    ConstraintPoseImu() = default;\n\n    ConstraintPoseImu(const Eigen::Matrix3d")

    for cls, sleep in (("LocalMapping", "3000"), ("LoopClosing", "5000")):
        edit(f"include/{cls}.h", "    // Main function",
             "    std::mutex mVioCheckpointMutex;\n\n    // Main function")
        finished = "    mbFinished = false;" if cls == "LocalMapping" else "    mbFinished =false;"
        entry = finished + "\n\n    while(1)\n    {\n"
        edit(f"src/{cls}.cc", entry,
             entry + "        std::unique_lock<std::mutex> checkpoint(mVioCheckpointMutex);\n")
        edit(f"src/{cls}.cc", f"        usleep({sleep});\n    }}\n\n    SetFinish();",
             f"        checkpoint.unlock();\n        usleep({sleep});\n    }}\n\n    SetFinish();")

    edit("include/Atlas.h", "    void PreSave();", "    void PreSave(bool live = false);")
    edit("src/Atlas.cc", "void Atlas::PreSave()\n{\n    if(mpCurrentMap){",
         "void Atlas::PreSave(bool live)\n{\n    if(!live && mpCurrentMap){")
    edit("src/Atlas.cc", "    std::copy(mspMaps.begin(), mspMaps.end(), std::back_inserter(mvpBackupMaps));",
         "    mvpBackupMaps.clear();\n"
         "    std::copy(mspMaps.begin(), mspMaps.end(), std::back_inserter(mvpBackupMaps));")
    edit("src/Atlas.cc", "        pMi->PreSave(spCams);", "        pMi->PreSave(spCams, live);")
    edit("include/Map.h", "    void PreSave(std::set<GeometricCamera*> &spCams);",
         "    void PreSave(std::set<GeometricCamera*> &spCams, bool live = false);")
    edit("src/Map.cc", "void Map::PreSave(std::set<GeometricCamera*> &spCams)",
         "void Map::PreSave(std::set<GeometricCamera*> &spCams, bool live)")
    edit("src/Map.cc", "                pMPi->EraseObservation(it->first);",
         "                if (!live)\n                    pMPi->EraseObservation(it->first);")
    edit("src/Map.cc", "        pMPi->PreSave(mspKeyFrames,mspMapPoints);",
         "        pMPi->PreSave(mspKeyFrames,mspMapPoints, live);")
    before = "    mnBackupKFinitialID = -1;\n    if(mpKFinitial)"
    edit("src/Map.cc", before,
         "    if (live) {\n"
         "        std::sort(mvpBackupMapPoints.begin(), mvpBackupMapPoints.end(),\n"
         "            [](const MapPoint* a, const MapPoint* b) { return a->mnId < b->mnId; });\n"
         "        std::sort(mvpBackupKeyFrames.begin(), mvpBackupKeyFrames.end(),\n"
         "            [](const KeyFrame* a, const KeyFrame* b) { return a->mnId < b->mnId; });\n"
         "    }\n\n" + before)
    edit("include/MapPoint.h", "    void PreSave(set<KeyFrame*>& spKF,set<MapPoint*>& spMP);",
         "    void PreSave(set<KeyFrame*>& spKF,set<MapPoint*>& spMP, bool live = false);")
    edit("src/MapPoint.cc", "void MapPoint::PreSave(set<KeyFrame*>& spKF,set<MapPoint*>& spMP)",
         "void MapPoint::PreSave(set<KeyFrame*>& spKF,set<MapPoint*>& spMP, bool live)")
    edit("src/MapPoint.cc", "        else\n        {\n            EraseObservation(pKFi);\n        }",
         "        else if (!live)\n        {\n            EraseObservation(pKFi);\n        }")

    reference = """    if(spKF.find(mpRefKF) != spKF.end())
    {
        mBackupRefKFId = mpRefKF->mnId;
    }
"""
    restored_reference = """    if (live) {
        auto* reference = mpRefKF && spKF.count(mpRefKF) && !mpRefKF->isBad() ? mpRefKF : nullptr;
        if (!reference)
            for (const auto& observation : mObservations) {
                auto* candidate = observation.first;
                if (spKF.count(candidate) && !candidate->isBad()
                    && (!reference || candidate->mnId < reference->mnId))
                    reference = candidate;
            }
        if (!reference)
            throw std::runtime_error("live VIO map point has no restorable reference");
        mBackupRefKFId = reference->mnId;
    } else if(spKF.find(mpRefKF) != spKF.end()) {
        mBackupRefKFId = mpRefKF->mnId;
    }
"""
    edit("src/MapPoint.cc", reference, restored_reference)

    edit("include/System.h", "    void WriteVioSnapshot(std::ostream& out);",
         "    void WriteVioSnapshot(std::ostream& out);\n"
         "    bool SaveVioCheckpoint(const std::string& path);")
    edit("include/System.h", "    void SaveAtlas(int type);",
         "    void SaveAtlas(int type);\n"
         "    void LoadVioMap(const std::string& path);\n"
         "    void LoadVioState(const std::string& path);\n"
         "    template<class Archive> void ArchiveVioState(Archive& ar);")
    edit("src/System.cc", "    bool loadedAtlas = false;",
         "    const char* vioRestore = std::getenv(\"ORB_VIO_RESTORE_PREFIX\");\n"
         "    if (vioRestore && (mSensor != IMU_STEREO || bUseViewer || !mStrLoadAtlasFromFile.empty()))\n"
         "        throw std::runtime_error(\"incompatible native VIO restore configuration\");\n"
         "    bool loadedAtlas = false;")
    edit("src/System.cc", "        mpAtlas = new Atlas(0);",
         "        if (vioRestore)\n            LoadVioMap(vioRestore);\n"
         "        else\n            mpAtlas = new Atlas(0);")
    for thread, cls, instance, space in (
            ("mptLocalMapping", "LocalMapping", "mpLocalMapper", ""),
            ("mptLoopClosing", "LoopClosing", "mpLoopCloser", " ")):
        start = f"{thread} = new thread(&ORB_SLAM3::{cls}::Run,{space}{instance});"
        edit("src/System.cc", "    "+start, "    if (!vioRestore)\n        "+start)
    edit("src/System.cc", "    mpLoopCloser->SetLocalMapper(mpLocalMapper);",
         "    mpLoopCloser->SetLocalMapper(mpLocalMapper);\n\n"
         "    if (vioRestore) {\n"
         "        LoadVioState(vioRestore);\n"
         "        mptLocalMapping = new thread(&ORB_SLAM3::LocalMapping::Run, mpLocalMapper);\n"
         "        mptLoopClosing = new thread(&ORB_SLAM3::LoopClosing::Run, mpLoopCloser);\n"
         "    }")
    edit("src/System.cc", '#include "System.h"', '#include "System.h"\n#include "VioVocabulary.h"')
    rel = "src/System.cc"
    text_loader = ("        mpVocabulary = new ORBVocabulary();\n"
                   "        bool bVocLoad = mpVocabulary->loadFromTextFile(strVocFile);")
    cached_loader = ("        const char* vocabCache = vioRestore ? std::getenv(\"ORB_VIO_VOCABULARY_CACHE\") : nullptr;\n"
                     "        mpVocabulary = vocabCache ? ReadVioVocabulary(strVocFile, vocabCache) : new ORBVocabulary();\n"
                     "        bool bVocLoad = vocabCache || mpVocabulary->loadFromTextFile(strVocFile);")
    if files[rel].count(text_loader) != 2:
        raise ValueError("unexpected native vocabulary loader")
    files[rel] = files[rel].replace(text_loader, cached_loader, 1)
    edit("CMakeLists.txt", "src/System.cc\n", "src/System.cc\nsrc/VioCheckpoint.cc\nsrc/VioVocabulary.cc\n")
    for rel, data in files.items():
        (root / rel).write_text(data)
    copy_additions()



if __name__ == "__main__":
    install(Path(sys.argv[1]))
