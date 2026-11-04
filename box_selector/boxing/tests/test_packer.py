"""Pure unit tests for the packer (no database needed)."""
import random
import unittest

from boxing.packer import EPS, Item, check_fit, pack, rotations


def item(name, l, w, h, weight=0.1):
    return Item(name, l, w, h, weight)


def assert_valid_packing(test, placements, dims, items):
    """Independent validator: in bounds, right shape, and no two items overlap."""
    test.assertEqual(len(placements), len(items))
    by_name = {i.name: i for i in items}
    for p in placements:
        test.assertGreaterEqual(p.x, -EPS)
        test.assertGreaterEqual(p.y, -EPS)
        test.assertGreaterEqual(p.z, -EPS)
        test.assertLessEqual(p.x + p.length, dims[0] + 1e-6)
        test.assertLessEqual(p.y + p.width, dims[1] + 1e-6)
        test.assertLessEqual(p.z + p.height, dims[2] + 1e-6)
        test.assertEqual(sorted((p.length, p.width, p.height)), sorted(by_name[p.name].dims))
    for i, a in enumerate(placements):
        for b in placements[i + 1:]:
            overlap = (
                a.x < b.x + b.length - 1e-6 and b.x < a.x + a.length - 1e-6
                and a.y < b.y + b.width - 1e-6 and b.y < a.y + a.width - 1e-6
                and a.z < b.z + b.height - 1e-6 and b.z < a.z + a.height - 1e-6
            )
            test.assertFalse(overlap, f"{a} overlaps {b}")


class RotationTests(unittest.TestCase):
    def test_cube_has_one_orientation(self):
        self.assertEqual(len(rotations(item("c", 5, 5, 5))), 1)

    def test_brick_has_six_orientations(self):
        self.assertEqual(len(rotations(item("b", 1, 2, 3))), 6)


class CheckFitTests(unittest.TestCase):
    def test_exact_fit(self):
        r = check_fit([item("a", 10, 10, 10)], (10, 10, 10), 5)
        self.assertTrue(r.fits)

    def test_fits_only_when_rotated(self):
        r = check_fit([item("long", 30, 10, 5)], (10, 5, 30), 5)
        self.assertTrue(r.fits)
        assert_valid_packing(self, list(r.placements), (10, 5, 30), [item("long", 30, 10, 5)])

    def test_item_too_large_in_every_orientation(self):
        r = check_fit([item("big", 31, 1, 1)], (30, 30, 30), 5)
        self.assertFalse(r.fits)
        self.assertIn("too large", r.reason)

    def test_weight_limit_exceeded(self):
        r = check_fit([item("heavy", 1, 1, 1, weight=6)], (10, 10, 10), 5)
        self.assertFalse(r.fits)
        self.assertIn("weight", r.reason)

    def test_weight_exactly_at_limit_is_ok(self):
        r = check_fit([item("a", 1, 1, 1, 2.5), item("b", 1, 1, 1, 2.5)], (10, 10, 10), 5)
        self.assertTrue(r.fits)

    def test_total_volume_exceeded(self):
        items = [item(f"c{n}", 5, 5, 5) for n in range(9)]  # 1125 > 1000
        r = check_fit(items, (10, 10, 10), 100)
        self.assertFalse(r.fits)
        self.assertIn("volume", r.reason)

    def test_eight_cubes_fill_box_exactly(self):
        items = [item(f"c{n}", 5, 5, 5) for n in range(8)]
        r = check_fit(items, (10, 10, 10), 100)
        self.assertTrue(r.fits)
        assert_valid_packing(self, list(r.placements), (10, 10, 10), items)

    def test_volume_ok_but_geometry_impossible(self):
        # 2 x 216 = 432 cm3 < 1000 cm3, but two 6 cm cubes cannot share a 10 cm box.
        items = [item("a", 6, 6, 6), item("b", 6, 6, 6)]
        r = check_fit(items, (10, 10, 10), 100)
        self.assertFalse(r.fits)
        self.assertIn("arrangement", r.reason)

    def test_empty_item_list_fits(self):
        self.assertEqual(pack([], (1, 1, 1)), [])


class RandomizedValidityTests(unittest.TestCase):
    def test_any_returned_packing_is_valid(self):
        rng = random.Random(1234)  # fixed seed -> reproducible
        produced = 0
        for _ in range(300):
            dims = (rng.randint(8, 30), rng.randint(8, 30), rng.randint(8, 30))
            items = [
                item(f"i{n}", rng.randint(1, 12), rng.randint(1, 12), rng.randint(1, 12))
                for n in range(rng.randint(1, 9))
            ]
            placements = pack(items, dims)
            if placements is not None:
                produced += 1
                assert_valid_packing(self, placements, dims, items)
        self.assertGreater(produced, 50)  # make sure the test actually exercised packings


if __name__ == "__main__":
    unittest.main()
