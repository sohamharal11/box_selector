from django.db import models
from django.db.models import Q

from .packer import Item
from .selector import BoxSpec


class Product(models.Model):
    sku = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    length_cm = models.DecimalField(max_digits=8, decimal_places=2)
    width_cm = models.DecimalField(max_digits=8, decimal_places=2)
    height_cm = models.DecimalField(max_digits=8, decimal_places=2)
    weight_kg = models.DecimalField(max_digits=8, decimal_places=3)

    class Meta:
        ordering = ["sku"]
        constraints = [
            models.CheckConstraint(
                condition=Q(length_cm__gt=0) & Q(width_cm__gt=0) & Q(height_cm__gt=0),
                name="product_dimensions_positive",
            ),
            models.CheckConstraint(condition=Q(weight_kg__gt=0), name="product_weight_positive"),
        ]

    def __str__(self):
        return f"{self.sku} - {self.name}"

    def to_item(self) -> Item:
        return Item(
            name=self.name,
            length=float(self.length_cm),
            width=float(self.width_cm),
            height=float(self.height_cm),
            weight=float(self.weight_kg),
        )


class Box(models.Model):
    """A shipping box. Dimensions are INTERNAL (usable) dimensions."""

    name = models.CharField(max_length=100, unique=True)
    inner_length_cm = models.DecimalField(max_digits=8, decimal_places=2)
    inner_width_cm = models.DecimalField(max_digits=8, decimal_places=2)
    inner_height_cm = models.DecimalField(max_digits=8, decimal_places=2)
    max_weight_kg = models.DecimalField(max_digits=8, decimal_places=3, help_text="Max weight of contents")
    cost = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["cost", "name"]
        verbose_name_plural = "boxes"
        constraints = [
            models.CheckConstraint(
                condition=Q(inner_length_cm__gt=0) & Q(inner_width_cm__gt=0) & Q(inner_height_cm__gt=0),
                name="box_dimensions_positive",
            ),
            models.CheckConstraint(condition=Q(max_weight_kg__gt=0), name="box_max_weight_positive"),
            models.CheckConstraint(condition=Q(cost__gte=0), name="box_cost_non_negative"),
        ]

    def __str__(self):
        return self.name

    def to_spec(self) -> BoxSpec:
        return BoxSpec(
            name=self.name,
            length=float(self.inner_length_cm),
            width=float(self.inner_width_cm),
            height=float(self.inner_height_cm),
            max_weight=float(self.max_weight_kg),
            cost=self.cost,
        )


class Order(models.Model):
    reference = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "product"], name="unique_product_per_order"),
            models.CheckConstraint(condition=Q(quantity__gte=1), name="order_item_quantity_min_1"),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.product.sku} ({self.order.reference})"
