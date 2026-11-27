#pragma once
#include "ORBVocabulary.h"

namespace ORB_SLAM3 {
ORBVocabulary* ReadVioVocabulary(const std::string& text, const std::string& path);
void WriteVioVocabulary(const std::string& text, const std::string& path);
}
