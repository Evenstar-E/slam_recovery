"""Install the feature-only exchange hooks in an isolated ORB-SLAM3 checkout."""
from pathlib import Path
import sys


def install(root):
    here = Path(__file__).parent
    for name in ("VioFeatureExchange.h", "VioFeatureExchange.inc"):
        target = root / "include" / name
        source = (here / name).read_text()
        if not target.exists() or target.read_text() != source:
            target.write_text(source)

    frame = root / "src/Frame.cc"
    source = frame.read_text()
    if '#include "VioFeatureExchange.h"' not in source:
        entry = "void Frame::ExtractORB(int flag, const cv::Mat &im, const int x0, const int x1)\n{\n"
        exit_ = "        monoRight = (*mpORBextractorRight)(im,cv::Mat(),mvKeysRight,mDescriptorsRight,vLapping);\n}"
        if source.count(entry) != 1 or source.count(exit_) != 1:
            raise ValueError("unexpected native Frame::ExtractORB")
        frame.write_text('#include "VioFeatureExchange.h"\n' + source
                         .replace(entry, entry + "    VioFeatureCamera(flag);\n")
                         .replace(exit_, exit_[:-1] + "    VioFeatureCamera(-1);\n}"))

    extractor = root / "src/ORBextractor.cc"
    source = extractor.read_text()
    if '#include "VioFeatureExchange.inc"' not in source:
        after_pyramid = "        ComputePyramid(image);\n"
        out = "        return monoIndex;"
        if source.count(after_pyramid) != 1 or source.count(out) != 1:
            raise ValueError("unexpected native ORB extractor")
        fast_path = """
        const int config[] = {nfeatures, nlevels, iniThFAST, minThFAST,
                              vLappingArea[0], vLappingArea[1]};
        const auto signature = VioFeatureSignature(image, config, 6, scaleFactor);
        int cachedMono = 0;
        if (VioReadFeatures(signature, _keypoints, _descriptors, cachedMono))
            return cachedMono;
"""
        extractor.write_text('#include "VioFeatureExchange.inc"\n' + source
                             .replace(after_pyramid, after_pyramid + fast_path)
                             .replace(out, "        VioWriteFeatures(signature, _keypoints, descriptors, monoIndex);\n" + out))


if __name__ == "__main__":
    install(Path(sys.argv[1]))
