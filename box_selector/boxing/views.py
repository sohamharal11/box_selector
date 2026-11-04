import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import Order, Product
from .selector import BoxEvaluation, Recommendation
from .services import recommend_for_lines, recommend_for_order


def _r(value, digits=2):
    return round(float(value), digits)


def _box_payload(ev: BoxEvaluation) -> dict:
    box = ev.box
    return {
        "name": box.name,
        "cost": str(box.cost),
        "inner_dimensions_cm": [_r(box.length), _r(box.width), _r(box.height)],
        "max_weight_kg": _r(box.max_weight, 3),
    }


def _recommendation_payload(rec: Recommendation) -> dict:
    payload = {
        "summary": {
            "unit_count": rec.unit_count,
            "total_weight_kg": _r(rec.total_weight, 3),
            "total_volume_cm3": _r(rec.total_volume, 1),
        },
        "alternatives": [_box_payload(ev) for ev in rec.alternatives],
        "rejected": [{"box": ev.box.name, "reason": ev.reason} for ev in rec.rejected],
    }
    if rec.recommended is None:
        payload.update(
            status="no_fit",
            recommended_box=None,
            message=(
                "No single active box can hold this order."
                if rec.rejected
                else "No active boxes are configured."
            ),
        )
        return payload

    ev = rec.recommended
    box_payload = _box_payload(ev)
    box_payload["utilization"] = {
        "volume_pct": _r(rec.total_volume / ev.box.volume * 100, 1),
        "weight_pct": _r(rec.total_weight / ev.box.max_weight * 100, 1),
    }
    box_payload["placements"] = [
        {
            "item": p.name,
            "position_cm": [_r(p.x), _r(p.y), _r(p.z)],
            "size_cm": [_r(p.length), _r(p.width), _r(p.height)],
        }
        for p in ev.placements
    ]
    payload.update(status="ok", recommended_box=box_payload)
    return payload


def _bad_request(message, **extra):
    return JsonResponse({"error": message, **extra}, status=400)


@csrf_exempt  # JSON API for internal warehouse tooling; no session auth to protect
@require_POST
def recommend_box_adhoc(request):
    """POST {"items": [{"sku": "ABC", "quantity": 2}, ...]}"""
    try:
        data = json.loads(request.body or b"")
    except json.JSONDecodeError:
        return _bad_request("request body must be valid JSON")

    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        return _bad_request("'items' must be a non-empty list")

    wanted: dict[str, int] = {}
    for entry in items:
        if not isinstance(entry, dict):
            return _bad_request("each item must be an object with 'sku' and 'quantity'")
        sku = entry.get("sku")
        qty = entry.get("quantity", 1)
        if not isinstance(sku, str) or not sku:
            return _bad_request("each item needs a non-empty string 'sku'")
        if isinstance(qty, bool) or not isinstance(qty, int) or qty < 1:
            return _bad_request(f"quantity for '{sku}' must be an integer >= 1")
        wanted[sku] = wanted.get(sku, 0) + qty

    products = Product.objects.in_bulk(list(wanted), field_name="sku")
    missing = sorted(set(wanted) - set(products))
    if missing:
        return _bad_request("unknown SKUs", unknown_skus=missing)

    try:
        rec = recommend_for_lines([(products[sku], qty) for sku, qty in wanted.items()])
    except ValueError as exc:
        return _bad_request(str(exc))
    return JsonResponse(_recommendation_payload(rec))


@require_GET
def order_recommendation(request, reference):
    order = Order.objects.filter(reference=reference).first()
    if order is None:
        return JsonResponse({"error": f"order '{reference}' not found"}, status=404)
    try:
        rec = recommend_for_order(order)
    except ValueError as exc:
        return _bad_request(str(exc))
    return JsonResponse({"order": order.reference, **_recommendation_payload(rec)})
