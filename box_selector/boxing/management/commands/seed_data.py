from django.core.management.base import BaseCommand

from boxing.models import Box, Order, OrderItem, Product

BOXES = [
    # name, L, W, H (inner cm), max kg, cost
    ("Small Mailer", 20, 15, 10, 2, "0.45"),
    ("Medium Box", 30, 25, 20, 8, "0.90"),
    ("Large Box", 45, 35, 30, 20, "1.80"),
    ("XL Box", 60, 45, 40, 30, "3.20"),
    ("Heavy-Duty Compact", 25, 20, 20, 25, "2.40"),
]

PRODUCTS = [
    # sku, name, L, W, H (cm), kg
    ("CABLE-01", "USB Cable", 15, 10, 3, "0.100"),
    ("MUG-01", "Ceramic Mug", 8, 8, 9, "0.400"),
    ("BOOK-01", "Hardcover Book", 24, 17, 3, "0.600"),
    ("STAND-01", "Laptop Stand", 35, 25, 6, "1.200"),
    ("DUMB-05", "5 kg Dumbbell", 20, 10, 10, "5.000"),
    ("LAMP-01", "Desk Lamp", 40, 15, 15, "1.500"),
]


class Command(BaseCommand):
    help = "Load sample boxes, products and orders (idempotent)."

    def handle(self, *args, **options):
        for name, l, w, h, kg, cost in BOXES:
            Box.objects.update_or_create(
                name=name,
                defaults=dict(inner_length_cm=l, inner_width_cm=w, inner_height_cm=h, max_weight_kg=kg, cost=cost),
            )
        for sku, name, l, w, h, kg in PRODUCTS:
            Product.objects.update_or_create(
                sku=sku, defaults=dict(name=name, length_cm=l, width_cm=w, height_cm=h, weight_kg=kg)
            )

        samples = {
            "ORD-1001": {"CABLE-01": 2, "MUG-01": 1},
            "ORD-1002": {"DUMB-05": 3},
            "ORD-1003": {"STAND-01": 1, "BOOK-01": 2, "LAMP-01": 1},
        }
        for reference, lines in samples.items():
            order, _ = Order.objects.get_or_create(reference=reference)
            for sku, qty in lines.items():
                OrderItem.objects.update_or_create(
                    order=order, product=Product.objects.get(sku=sku), defaults={"quantity": qty}
                )
        self.stdout.write(self.style.SUCCESS("Sample data loaded."))
