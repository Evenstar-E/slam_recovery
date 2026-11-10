#include "native_checkpoint.h"

namespace native_checkpoint
{

VoxelOctoTree *cloneTree(const VoxelOctoTree *src)
{
  if (src == nullptr) return nullptr;

  VoxelOctoTree *dst = new VoxelOctoTree();
  dst->temp_points_ = src->temp_points_;
  dst->layer_ = src->layer_;
  dst->octo_state_ = src->octo_state_;
  dst->voxel_center_[0] = src->voxel_center_[0];
  dst->voxel_center_[1] = src->voxel_center_[1];
  dst->voxel_center_[2] = src->voxel_center_[2];
  dst->layer_init_num_ = src->layer_init_num_;
  dst->quater_length_ = src->quater_length_;
  dst->planer_threshold_ = src->planer_threshold_;
  dst->points_size_threshold_ = src->points_size_threshold_;
  dst->update_size_threshold_ = src->update_size_threshold_;
  dst->max_points_num_ = src->max_points_num_;
  dst->max_layer_ = src->max_layer_;
  dst->new_points_ = src->new_points_;
  dst->init_octo_ = src->init_octo_;
  dst->update_enable_ = src->update_enable_;

  dst->plane_ptr_ = src->plane_ptr_ != nullptr ? new VoxelPlane(*src->plane_ptr_) : nullptr;
  for (int i = 0; i < 8; ++i)
  {
    dst->leaves_[i] = cloneTree(src->leaves_[i]);
  }
  return dst;
}

void freeTree(VoxelOctoTree *tree)
{
  // ~VoxelOctoTree deletes leaves_ and plane_ptr_ itself, so one delete frees the whole subtree.
  delete tree;
}

std::unordered_map<VOXEL_LOCATION, VoxelOctoTree *> cloneMap(
    const std::unordered_map<VOXEL_LOCATION, VoxelOctoTree *> &src)
{
  std::unordered_map<VOXEL_LOCATION, VoxelOctoTree *> dst;
  dst.reserve(src.size());
  for (const auto &kv : src)
  {
    dst.emplace(kv.first, cloneTree(kv.second));
  }
  return dst;
}

void freeMap(std::unordered_map<VOXEL_LOCATION, VoxelOctoTree *> &map)
{
  for (auto &kv : map)
  {
    freeTree(kv.second);
  }
  map.clear();
}

static size_t countPointsTree(const VoxelOctoTree *tree)
{
  if (tree == nullptr) return 0;
  size_t n = tree->temp_points_.size();
  for (int i = 0; i < 8; ++i)
  {
    n += countPointsTree(tree->leaves_[i]);
  }
  return n;
}

static size_t countNodesTree(const VoxelOctoTree *tree)
{
  if (tree == nullptr) return 0;
  size_t n = 1;
  for (int i = 0; i < 8; ++i)
  {
    n += countNodesTree(tree->leaves_[i]);
  }
  return n;
}

size_t countPoints(const std::unordered_map<VOXEL_LOCATION, VoxelOctoTree *> &map)
{
  size_t n = 0;
  for (const auto &kv : map)
  {
    n += countPointsTree(kv.second);
  }
  return n;
}

size_t countNodes(const std::unordered_map<VOXEL_LOCATION, VoxelOctoTree *> &map)
{
  size_t n = 0;
  for (const auto &kv : map)
  {
    n += countNodesTree(kv.second);
  }
  return n;
}

} // namespace native_checkpoint
