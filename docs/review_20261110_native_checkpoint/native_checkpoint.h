/*
 * Minimal native checkpoint for the recovery mainline.
 *
 * The host keeps its map as an unordered_map<VOXEL_LOCATION, VoxelOctoTree*> of raw pointers, so
 * "restore the map" can only mean "have a second, independent copy of that tree". This file is
 * only that copy: deep clone, free, and count. It deliberately does not define a serialisation
 * format, a second estimator, or an index sidecar -- those would each be a separate decision, and
 * the first thing the recovery loop needs is to know whether the copy itself is possible.
 */

#ifndef NATIVE_CHECKPOINT_H_
#define NATIVE_CHECKPOINT_H_

#include "voxel_map.h"

namespace native_checkpoint
{

// Deep copy of one octo tree. The default constructor of VoxelOctoTree leaves plane_ptr_ and
// leaves_[] uninitialised, so every field is written explicitly here rather than relying on it.
VoxelOctoTree *cloneTree(const VoxelOctoTree *src);

void freeTree(VoxelOctoTree *tree);

std::unordered_map<VOXEL_LOCATION, VoxelOctoTree *> cloneMap(
    const std::unordered_map<VOXEL_LOCATION, VoxelOctoTree *> &src);

// Frees every tree in the map and leaves the map empty.
void freeMap(std::unordered_map<VOXEL_LOCATION, VoxelOctoTree *> &map);

// Points held in temp_points_ across the whole map -- the quantity that says whether a "restore"
// actually rolled the map back, rather than only swapping an empty container.
size_t countPoints(const std::unordered_map<VOXEL_LOCATION, VoxelOctoTree *> &map);

// Number of octo tree nodes (root nodes plus every leaf below them).
size_t countNodes(const std::unordered_map<VOXEL_LOCATION, VoxelOctoTree *> &map);

} // namespace native_checkpoint

#endif
