"""Copy-on-Write Spatial Map Mutation Journal & Redo Image (Section 2.2 of FAST_LIVO2_SHARED_CORE_EXTRACTION.md).

Provides O(|Dirty Set|) rollback and zero-full-copy dual-branch trial execution for voxel/submap stores:
  - First-write before-image cloning (`before_images`): clones an existing voxel/submap node only the FIRST time
    it is touched within a transaction generation; subsequent mutations in the same generation incur zero copy cost.
  - Zero-copy new key logging (`inserted_keys`): newly created voxels/nodes only record their key.
  - `MutationRedoImage`: captures the post-mutation state of ONLY the dirty keys before rolling back to try a
    candidate repair branch, allowing O(|Dirty Set|) restoration of the incumbent live branch if the candidate is rejected.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Dict, Generic, Hashable, Optional, Set, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


@dataclass
class MutationRedoImage(Generic[K, V]):
    generation_id: int
    after_images: Dict[K, V] = field(default_factory=dict)
    inserted_after_images: Dict[K, V] = field(default_factory=dict)
    removed_keys: Set[K] = field(default_factory=set)


class SpatialMutationLog(Generic[K, V]):
    """
    Generic Copy-on-Write transaction log over a persistent spatial map store `map_store: Dict[K, V]`.
    Supports:
      - VoxelOctoTree / VoxelHashMap (`K = Tuple[int, int, int]`, `V = VoxelNode`)
      - KeyFrame subcloud maps (`K = int`, `V = np.ndarray`)
      - Covisibility / landmark graphs (`K = int`, `V = LandmarkState`)
    """

    def __init__(self, map_store: Optional[Dict[K, V]] = None) -> None:
        self.store: Dict[K, V] = {} if map_store is None else map_store
        self.generation_id: int = 0
        self.active_journal: bool = False
        self.before_images: Dict[K, V] = {}
        self.inserted_keys: Set[K] = set()

    def begin_generation(self) -> int:
        self.generation_id += 1
        self.active_journal = True
        self.before_images.clear()
        self.inserted_keys.clear()
        return self.generation_id

    def put(self, key: K, value: V) -> None:
        """
        Insert or update `key` in the spatial map while recording a minimal first-write before-image
        if a transaction generation is active.
        """
        if self.active_journal:
            if key in self.store:
                if key not in self.before_images and key not in self.inserted_keys:
                    self.before_images[key] = deepcopy(self.store[key])
            else:
                self.inserted_keys.add(key)
        self.store[key] = value

    def remove(self, key: K) -> None:
        if key not in self.store:
            return
        if self.active_journal:
            if key in self.inserted_keys:
                self.inserted_keys.remove(key)
            elif key not in self.before_images:
                self.before_images[key] = deepcopy(self.store[key])
        del self.store[key]

    @property
    def dirty_set_size(self) -> int:
        return len(self.before_images) + len(self.inserted_keys)

    def capture_mutation_redo(self) -> MutationRedoImage[K, V]:
        """
        Capture the post-mutation state (After-Image) of ONLY the dirty keys in O(|Dirty Set|)
        so that if a candidate branch fails validation after rollback, the incumbent live map can be
        restored without having cloned the entire map.
        """
        redo = MutationRedoImage[K, V](generation_id=self.generation_id)
        for k in self.before_images:
            if k in self.store:
                redo.after_images[k] = deepcopy(self.store[k])
            else:
                redo.removed_keys.add(k)
        for k in self.inserted_keys:
            if k in self.store:
                redo.inserted_after_images[k] = deepcopy(self.store[k])
        return redo

    def rollback_mutation_journal(self) -> int:
        """
        Roll back all mutations in the current generation in O(|Dirty Set|) time.
        Returns the number of reverted keys.
        """
        reverted = 0
        for k in list(self.inserted_keys):
            if k in self.store:
                del self.store[k]
                reverted += 1
        for k, before_val in self.before_images.items():
            self.store[k] = deepcopy(before_val)
            reverted += 1
        self.before_images.clear()
        self.inserted_keys.clear()
        self.active_journal = False
        return reverted

    def consume_mutation_redo(self, redo: MutationRedoImage[K, V]) -> int:
        """
        Restore the incumbent branch's post-mutation state from `redo` in O(|Dirty Set|) time.
        """
        restored = 0
        for k in redo.removed_keys:
            if k in self.store:
                del self.store[k]
                restored += 1
        for k, val in redo.after_images.items():
            self.store[k] = deepcopy(val)
            restored += 1
        for k, val in redo.inserted_after_images.items():
            self.store[k] = deepcopy(val)
            restored += 1
        return restored

    def commit_generation(self) -> None:
        """Discard before-images and make current generation permanent in O(1) time."""
        self.before_images.clear()
        self.inserted_keys.clear()
        self.active_journal = False
