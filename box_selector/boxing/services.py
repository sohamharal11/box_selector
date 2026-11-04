"""Glue between the database and the pure selection logic."""
from __future__ import annotations

from typing import Iterable

from .models import Box, Order, Product
from .selector import Recommendation, expand_items, recommend


def recommend_for_lines(lines: Iterable[tuple[Product, int]]) -> Recommendation:
    """lines: (Product, quantity) pairs. Raises ValueError on invalid input."""
    item_lines = [(product.to_item(), qty) for product, qty in lines]
    items = expand_items(item_lines)
    boxes = [box.to_spec() for box in Box.objects.filter(is_active=True)]
    return recommend(items, boxes)


def recommend_for_order(order: Order) -> Recommendation:
    lines = [(oi.product, oi.quantity) for oi in order.items.select_related("product")]
    return recommend_for_lines(lines)
