// Store the initialized ORB vocabulary without re-parsing descriptors on restart.
#include "VioVocabulary.h"
#include <array>
#include <cstdint>
#include <fstream>
#include <memory>
#include <openssl/sha.h>
#include <stdexcept>

namespace ORB_SLAM3 {
namespace {
constexpr std::uint64_t signature = 0x56494f564f433032ULL;
constexpr std::uint32_t max_nodes = 2000000;

template<class T>
T read(std::istream& stream)
{
    T value;
    stream.read(reinterpret_cast<char*>(&value), sizeof(value));
    return value;
}

template<class T>
void write(std::ostream& stream, const T& value)
{
    stream.write(reinterpret_cast<const char*>(&value), sizeof(value));
}

using Fingerprint = std::array<unsigned char, SHA256_DIGEST_LENGTH>;

Fingerprint fingerprint(const std::string& text)
{
    std::ifstream stream(text, std::ios::binary);
    if (!stream)
        throw std::runtime_error("cannot fingerprint ORB text vocabulary");
    SHA256_CTX context;
    SHA256_Init(&context);
    std::array<char, 65536> buffer;
    while (stream) {
        stream.read(buffer.data(), buffer.size());
        SHA256_Update(&context, buffer.data(), stream.gcount());
    }
    if (!stream.eof())
        throw std::runtime_error("error reading ORB text vocabulary");
    Fingerprint hash;
    SHA256_Final(hash.data(), &context);
    return hash;
}

class BinaryVocabulary : public ORBVocabulary
{
public:
    void save(std::ostream& out, const Fingerprint& source) const
    {
        write(out, signature);
        write(out, source);
        const std::array<std::uint32_t, 6> header{
            static_cast<std::uint32_t>(m_k), static_cast<std::uint32_t>(m_L),
            static_cast<std::uint32_t>(m_scoring), static_cast<std::uint32_t>(m_weighting),
            static_cast<std::uint32_t>(m_nodes.size()), static_cast<std::uint32_t>(m_words.size())};
        write(out, header);
        for (std::size_t i = 1; i < m_nodes.size(); ++i) {
            const auto& node = m_nodes[i];
            write(out, node.parent);
            write(out, node.weight);
            out.write(reinterpret_cast<const char*>(node.descriptor.ptr()), DBoW2::FORB::L);
        }
        for (const auto* word : m_words)
            write(out, word->id);
    }

    void load(std::istream& in, const Fingerprint& source)
    {
        if (read<std::uint64_t>(in) != signature)
            throw std::runtime_error("invalid VIO vocabulary signature");
        if (read<Fingerprint>(in) != source)
            throw std::runtime_error("VIO cache does not match the configured text vocabulary");
        const auto meta = read<std::array<std::uint32_t, 6>>(in);
        if (meta[0] < 2 || meta[0] > 20 || meta[1] == 0 || meta[1] > 10
            || meta[2] > 5 || meta[3] > 3 || meta[4] < 2 || meta[4] > max_nodes
            || meta[5] == 0 || meta[5] >= meta[4])
            throw std::runtime_error("invalid VIO vocabulary dimensions");
        m_k = meta[0];
        m_L = meta[1];
        m_scoring = static_cast<DBoW2::ScoringType>(meta[2]);
        m_weighting = static_cast<DBoW2::WeightingType>(meta[3]);
        createScoringObject();

        m_nodes.resize(meta[4]);
        // Use one contiguous descriptor buffer. Row views retain its storage.
        cv::Mat descriptors(meta[4] - 1, DBoW2::FORB::L, CV_8U);
        for (std::uint32_t i = 1; i < meta[4]; ++i) {
            auto& node = m_nodes[i];
            node.id = i;
            node.parent = read<DBoW2::NodeId>(in);
            node.weight = read<DBoW2::WordValue>(in);
            if (node.parent >= i)
                throw std::runtime_error("invalid VIO vocabulary parent");
            node.descriptor = descriptors.row(i - 1);
            in.read(reinterpret_cast<char*>(node.descriptor.ptr()), DBoW2::FORB::L);
            m_nodes[node.parent].children.push_back(i);
        }
        m_words.resize(meta[5]);
        for (std::uint32_t i = 0; i < meta[5]; ++i) {
            const auto id = read<DBoW2::NodeId>(in);
            if (!id || id >= m_nodes.size() || !m_nodes[id].isLeaf())
                throw std::runtime_error("invalid VIO vocabulary word");
            m_words[i] = &m_nodes[id];
            m_words[i]->word_id = i;
        }
    }
};
}  // namespace

ORBVocabulary* ReadVioVocabulary(const std::string& text, const std::string& path)
{
    std::ifstream in(path, std::ios::binary);
    in.exceptions(std::ios::failbit | std::ios::badbit);
    auto vocabulary = std::unique_ptr<BinaryVocabulary>(new BinaryVocabulary);
    vocabulary->load(in, fingerprint(text));
    return vocabulary.release();
}

void WriteVioVocabulary(const std::string& text, const std::string& path)
{
    BinaryVocabulary vocabulary;
    if (!vocabulary.loadFromTextFile(text))
        throw std::runtime_error("ORB vocabulary could not be loaded");
    std::ofstream out(path, std::ios::binary);
    out.exceptions(std::ios::failbit | std::ios::badbit);
    vocabulary.save(out, fingerprint(text));
}
}  // namespace ORB_SLAM3
