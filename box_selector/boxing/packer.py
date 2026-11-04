"""Pure-Python 3D packing helpers (deliberately free of Django imports).

Units: centimetres and kilograms.

The packer is a *heuristic*: guillotine free-space splitting with best-fit
placement and full axis-aligned rotation. If it returns a packing, that
packing is valid (every item inside the box, nothing overlapping). If it
returns None, an arrangement may still exist that the heuristic missed, because
exact 3D bin packing is NP-hard. See README "Limitations".
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations
from typing import Optional, Sequence

EPS = 1e-9


@dataclass(frozen=True)
class Item:
    name: str
    length: float
    width: float
    height: float
    weight: float

    @property
    def dims(self) -> tuple[float, float, float]:
        return (self.length, self.width, self.height)

    @property
    def volume(self) -> float:
        return self.length * self.width * self.height


@dataclass(frozen=True)
class Placement:
    """Where an item sits in the box, after rotation. Origin = one inner corner."""

    name: str
    x: float
    y: float
    z: float
    length: float
    width: float
    height: float


@dataclass(frozen=True)
class FitResult:
    fits: bool
    reason: str
    placements: tuple[Placement, ...] = ()


def rotations(item: Item) -> list[tuple[float, float, float]]:
    """All distinct axis-aligned orientations (a cube has 1, a brick has 6)."""
    return sorted(set(permutations(item.dims)))


# Different orderings catch cases where one greedy order paints itself into a corner.
_ORDERINGS = (
    lambda i: (-i.volume, i.name),
    lambda i: (-max(i.dims), -i.volume, i.name),
    lambda i: (-min(i.dims), -i.volume, i.name),
)


def _pack_in_order(ordered: Sequence[Item], dims) -> Optional[list[Placement]]:
    length, width, height = dims
    free = [(0.0, 0.0, 0.0, length, width, height)]  # x, y, z, l, w, h
    placements: list[Placement] = []

    for item in ordered:
        best = None
        for idx, (x, y, z, fl, fw, fh) in enumerate(free):
            space_volume = fl * fw * fh
            for a, b, c in rotations(item):
                if a <= fl + EPS and b <= fw + EPS and c <= fh + EPS:
                    # Best fit = least wasted space; prefer low/near corner for stability.
                    key = (space_volume - a * b * c, z, y, x)
                    if best is None or key < best[0]:
                        best = (key, idx, (a, b, c))
        if best is None:
            return None

        _, idx, (a, b, c) = best
        x, y, z, fl, fw, fh = free.pop(idx)
        placements.append(Placement(item.name, x, y, z, a, b, c))

        # Guillotine split of what is left into three disjoint cuboids.
        leftovers = (
            (x + a, y, z, fl - a, fw, fh),  # slab to the right (full width/height)
            (x, y + b, z, a, fw - b, fh),  # slab in front of the item
            (x, y, z + c, a, b, fh - c),  # space on top of the item
        )
        for space in leftovers:
            if space[3] > EPS and space[4] > EPS and space[5] > EPS:
                free.append(space)

    return placements


def pack(items: Sequence[Item], dims) -> Optional[list[Placement]]:
    """Return a valid packing of items into a box of inner size `dims`, or None."""
    if not items:
        return []
    for key in _ORDERINGS:
        result = _pack_in_order(sorted(items, key=key), dims)
        if result is not None:
            return result
    return None


def check_fit(items: Sequence[Item], dims, max_weight: float) -> FitResult:
    """Cheap necessary checks first, then the actual packing attempt."""
    total_weight = sum(i.weight for i in items)
    if total_weight > max_weight + EPS:
        return FitResult(
            False,
            f"total weight {total_weight:.3f} kg exceeds box limit {max_weight:.3f} kg",
        )

    box_volume = dims[0] * dims[1] * dims[2]
    total_volume = sum(i.volume for i in items)
    if total_volume > box_volume + EPS:
        return FitResult(
            False,
            f"total item volume {total_volume:.1f} cm3 exceeds box volume {box_volume:.1f} cm3",
        )

    sorted_box = sorted(dims)
    for item in items:
        if any(d > b + EPS for d, b in zip(sorted(item.dims), sorted_box)):
            return FitResult(
                False, f"item '{item.name}' is too large for the box in every orientation"
            )

    placements = pack(items, dims)
    if placements is None:
        return FitResult(False, "no valid arrangement found for these items in this box")
    return FitResult(True, "fits", tuple(placements))
