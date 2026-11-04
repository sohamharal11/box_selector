"""Pure unit tests for box selection rules (no database needed)."""
import unittest
from decimal import Decimal

from boxing.packer import Item
from boxing.selector import MAX_UNITS, BoxSpec, expand_items, recommend


def box(name, l, w, h, max_w, cost):
    return BoxSpec(name, l, w, h, max_w, Decimal(cost))


def item(name="thing", l=10, w=10, h=10, weight=1.0):
    return Item(name, l, w, h, weight)


class RecommendTests(unittest.TestCase):
    def test_cheapest_fitting_box_wins(self):
        boxes = [box("big", 50, 50, 50, 20, "5.00"), box("small", 15, 15, 15, 20, "2.00")]
        rec = recommend([item()], boxes)
        self.assertEqual(rec.recommended.box.name, "small")
        self.assertEqual([e.box.name for e in rec.alternatives], ["big"])

    def test_skips_cheap_box_that_cannot_carry_the_weight(self):
        boxes = [box("cheap-light", 30, 30, 30, 1, "1.00"), box("sturdy", 30, 30, 30, 20, "3.00")]
        rec = recommend([item(weight=5)], boxes)
        self.assertEqual(rec.recommended.box.name, "sturdy")
        self.assertIn("weight", rec.rejected[0].reason)

    def test_skips_cheap_box_that_is_too_small(self):
        boxes = [box("tiny", 5, 5, 5, 20, "0.50"), box("ok", 20, 20, 20, 20, "2.00")]
        rec = recommend([item()], boxes)
        self.assertEqual(rec.recommended.box.name, "ok")

    def test_equal_cost_prefers_smaller_volume(self):
        boxes = [box("roomy", 40, 40, 40, 20, "2.00"), box("snug", 12, 12, 12, 20, "2.00")]
        rec = recommend([item()], boxes)
        self.assertEqual(rec.recommended.box.name, "snug")

    def test_equal_cost_and_volume_is_deterministic_by_name(self):
        boxes = [box("b", 20, 20, 20, 20, "2.00"), box("a", 20, 20, 20, 20, "2.00")]
        self.assertEqual(recommend([item()], boxes).recommended.box.name, "a")

    def test_no_box_fits(self):
        rec = recommend([item(l=100)], [box("small", 20, 20, 20, 20, "1.00")])
        self.assertIsNone(rec.recommended)
        self.assertEqual(len(rec.rejected), 1)

    def test_no_boxes_configured(self):
        rec = recommend([item()], [])
        self.assertIsNone(rec.recommended)
        self.assertEqual(rec.rejected, ())

    def test_totals(self):
        rec = recommend([item(weight=1.5), item(weight=2.0)], [box("x", 50, 50, 50, 20, "1")])
        self.assertAlmostEqual(rec.total_weight, 3.5)
        self.assertAlmostEqual(rec.total_volume, 2000)
        self.assertEqual(rec.unit_count, 2)

    def test_multiple_items_needing_a_bigger_box(self):
        items = [item(f"c{n}", 10, 10, 10, 0.5) for n in range(8)]
        boxes = [box("one-cube", 10, 10, 10, 20, "1"), box("eight-cubes", 20, 20, 20, 20, "4")]
        self.assertEqual(recommend(items, boxes).recommended.box.name, "eight-cubes")


class ExpandItemsTests(unittest.TestCase):
    def test_quantity_creates_one_item_per_unit(self):
        items = expand_items([(item("mug"), 3), (item("book"), 1)])
        self.assertEqual(len(items), 4)
        self.assertEqual(items[0].name, "mug (1/3)")
        self.assertEqual(items[-1].name, "book")

    def test_empty_order_rejected(self):
        with self.assertRaises(ValueError):
            expand_items([])

    def test_zero_quantity_rejected(self):
        with self.assertRaises(ValueError):
            expand_items([(item(), 0)])

    def test_unit_cap(self):
        with self.assertRaises(ValueError):
            expand_items([(item(), MAX_UNITS + 1)])


if __name__ == "__main__":
    unittest.main()
