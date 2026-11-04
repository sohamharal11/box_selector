from django.core.management.base import BaseCommand, CommandError

from boxing.models import Order
from boxing.services import recommend_for_order


class Command(BaseCommand):
    help = "Print the recommended box for an order reference."

    def add_arguments(self, parser):
        parser.add_argument("reference")

    def handle(self, *args, **options):
        order = Order.objects.filter(reference=options["reference"]).first()
        if order is None:
            raise CommandError(f"Order '{options['reference']}' not found")
        try:
            rec = recommend_for_order(order)
        except ValueError as exc:
            raise CommandError(str(exc))

        self.stdout.write(
            f"{rec.unit_count} unit(s), {rec.total_weight:.3f} kg, {rec.total_volume:.1f} cm3"
        )
        if rec.recommended is None:
            self.stdout.write(self.style.ERROR("No single box fits."))
        else:
            box = rec.recommended.box
            self.stdout.write(self.style.SUCCESS(f"Recommended: {box.name} (cost {box.cost})"))
        for ev in rec.alternatives:
            self.stdout.write(f"  alternative: {ev.box.name} (cost {ev.box.cost})")
        for ev in rec.rejected:
            self.stdout.write(f"  rejected: {ev.box.name} - {ev.reason}")
