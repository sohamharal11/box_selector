"""Django tests: models, services and the JSON API (need a database)."""
import json
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from boxing.models import Box, Order, OrderItem, Product
from boxing.services import recommend_for_order


def make_box(name, l, w, h, max_w, cost, active=True):
    return Box.objects.create(
        name=name, inner_length_cm=l, inner_width_cm=w, inner_height_cm=h,
        max_weight_kg=max_w, cost=cost, is_active=active,
    )


def make_product(sku, l, w, h, kg):
    return Product.objects.create(sku=sku, name=sku.title(), length_cm=l, width_cm=w, height_cm=h, weight_kg=kg)


class BaseData(TestCase):
    def setUp(self):
        self.small = make_box("Small", 20, 15, 10, 2, "0.50")
        self.medium = make_box("Medium", 30, 25, 20, 8, "1.00")
        self.large = make_box("Large", 45, 35, 30, 20, "2.00")
        self.mug = make_product("MUG", 8, 8, 9, "0.4")
        self.dumbbell = make_product("DUMB", 20, 10, 10, "5")

    def post(self, payload):
        return self.client.post(reverse("recommend-box"), data=json.dumps(payload), content_type="application/json")


class ModelConstraintTests(BaseData):
    def test_non_positive_dimension_rejected_by_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_product("BAD", 0, 5, 5, 1)

    def test_duplicate_product_in_order_rejected(self):
        order = Order.objects.create(reference="O1")
        OrderItem.objects.create(order=order, product=self.mug, quantity=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrderItem.objects.create(order=order, product=self.mug, quantity=2)


class ServiceTests(BaseData):
    def test_inactive_boxes_are_ignored(self):
        self.small.is_active = False
        self.small.save()
        order = Order.objects.create(reference="O1")
        OrderItem.objects.create(order=order, product=self.mug, quantity=1)
        self.assertEqual(recommend_for_order(order).recommended.box.name, "Medium")

    def test_order_quantity_is_respected(self):
        order = Order.objects.create(reference="O2")
        OrderItem.objects.create(order=order, product=self.dumbbell, quantity=2)  # 10 kg
        self.assertEqual(recommend_for_order(order).recommended.box.name, "Large")


class AdhocApiTests(BaseData):
    def test_recommends_cheapest_fitting_box(self):
        resp = self.post({"items": [{"sku": "MUG", "quantity": 1}]})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["recommended_box"]["name"], "Small")
        self.assertEqual(body["recommended_box"]["cost"], "0.50")
        self.assertEqual(len(body["recommended_box"]["placements"]), 1)
        self.assertEqual(body["summary"]["unit_count"], 1)

    def test_weight_pushes_order_to_larger_box(self):
        body = self.post({"items": [{"sku": "DUMB", "quantity": 1}]}).json()
        self.assertEqual(body["recommended_box"]["name"], "Medium")
        self.assertEqual(body["rejected"][0]["box"], "Small")

    def test_duplicate_skus_are_merged(self):
        body = self.post({"items": [{"sku": "MUG"}, {"sku": "MUG", "quantity": 2}]}).json()
        self.assertEqual(body["summary"]["unit_count"], 3)

    def test_no_fit_returns_200_with_status_no_fit(self):
        make_product("HUGE", 100, 100, 100, "1")
        resp = self.post({"items": [{"sku": "HUGE"}]})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "no_fit")
        self.assertIsNone(body["recommended_box"])
        self.assertEqual(len(body["rejected"]), 3)

    def test_unknown_sku_is_400(self):
        resp = self.post({"items": [{"sku": "NOPE"}]})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["unknown_skus"], ["NOPE"])

    def test_invalid_json_is_400(self):
        resp = self.client.post(reverse("recommend-box"), data="{oops", content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_bad_quantities_are_400(self):
        for qty in (0, -1, "2", 1.5, True):
            with self.subTest(qty=qty):
                self.assertEqual(self.post({"items": [{"sku": "MUG", "quantity": qty}]}).status_code, 400)

    def test_empty_or_malformed_items_are_400(self):
        for payload in ({}, {"items": []}, {"items": "MUG"}, {"items": ["MUG"]}, [1, 2]):
            with self.subTest(payload=payload):
                self.assertEqual(self.post(payload).status_code, 400)

    def test_too_many_units_is_400(self):
        self.assertEqual(self.post({"items": [{"sku": "MUG", "quantity": 5000}]}).status_code, 400)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(reverse("recommend-box")).status_code, 405)


class OrderApiTests(BaseData):
    def test_order_endpoint(self):
        order = Order.objects.create(reference="ORD-1")
        OrderItem.objects.create(order=order, product=self.mug, quantity=2)
        resp = self.client.get(reverse("order-recommend-box", args=["ORD-1"]))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["order"], "ORD-1")
        self.assertEqual(body["recommended_box"]["name"], "Small")  # two mugs side by side in 20x15x10

    def test_unknown_order_is_404(self):
        self.assertEqual(self.client.get(reverse("order-recommend-box", args=["missing"])).status_code, 404)

    def test_order_without_items_is_400(self):
        Order.objects.create(reference="EMPTY")
        self.assertEqual(self.client.get(reverse("order-recommend-box", args=["EMPTY"])).status_code, 400)
