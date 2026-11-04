"""Box selection logic on plain dataclasses (no Django, no database)."""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Optional, Sequence

from .packer import Item, Placement, check_fit

MAX_UNITS = 200  # safety cap: packing cost grows quickly with unit count


@dataclass(frozen=True)
class BoxSpec:
    name: str
    length: float
    width: float
    height: float
    max_weight: float
    cost: Decimal

    @property
    def dims(self) -> tuple[float, float, float]:
        return (self.length, self.width, self.height)

    @property
    def volume(self) -> float:
        return self.length * self.width * self.height


@dataclass(frozen=True)
class BoxEvaluation:
    box: BoxSpec
    fits: bool
    reason: str
    placements: tuple[Placement, ...] = ()


@dataclass(frozen=True)
class Recommendation:
    recommended: Optional[BoxEvaluation]
    alternatives: tuple[BoxEvaluation, ...]  # other boxes that also fit, best first
    rejected: tuple[BoxEvaluation, ...]  # boxes that do not fit, with reasons
    total_weight: float
    total_volume: float
    unit_count: int


def expand_items(lines: Sequence[tuple[Item, int]]) -> list[Item]:
    """Turn (item, quantity) lines into one Item per physical unit."""
    if not lines:
        raise ValueError("order has no items")
    expanded: list[Item] = []
    for item, qty in lines:
        if qty < 1:
            raise ValueError(f"quantity for '{item.name}' must be at least 1")
        for n in range(1, qty + 1):
            expanded.append(replace(item, name=f"{item.name} ({n}/{qty})") if qty > 1 else item)
        if len(expanded) > MAX_UNITS:
            raise ValueError(f"orders with more than {MAX_UNITS} units are not supported")
    return expanded


def recommend(items: Sequence[Item], boxes: Sequence[BoxSpec]) -> Recommendation:
    """Pick the cheapest box that fits.

    Tie-breakers: smaller box volume (less void fill / cheaper to ship), then name
    so the result is deterministic.
    """
    fitting: list[BoxEvaluation] = []
    rejected: list[BoxEvaluation] = []
    for box in boxes:
        result = check_fit(items, box.dims, box.max_weight)
        evaluation = BoxEvaluation(box, result.fits, result.reason, result.placements)
        (fitting if result.fits else rejected).append(evaluation)

    fitting.sort(key=lambda e: (e.box.cost, e.box.volume, e.box.name))
    rejected.sort(key=lambda e: (e.box.cost, e.box.name))

    return Recommendation(
        recommended=fitting[0] if fitting else None,
        alternatives=tuple(fitting[1:]),
        rejected=tuple(rejected),
        total_weight=sum(i.weight for i in items),
        total_volume=sum(i.volume for i in items),
        unit_count=len(items),
    )
