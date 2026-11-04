# AI-Assisted Box Selection System

A small Django service that recommends the cheapest shipping box that can hold an order,
checking **weight**, **volume**, and **actual 3D geometry** (with item rotation).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations boxing     # generates boxing/migrations/ - commit it
python manage.py migrate
python manage.py seed_data                 # sample boxes, products, orders
python manage.py recommend_box ORD-1001    # CLI
python manage.py runserver                 # API + admin (create a user with createsuperuser)
python manage.py test -v 2                 # run tests
```

## Data model

| Model | Key fields |
|---|---|
| `Product` | `sku`, `length_cm`, `width_cm`, `height_cm`, `weight_kg` |
| `Box` | `name`, `inner_length/width/height_cm` (internal), `max_weight_kg`, `cost`, `is_active` |
| `Order` / `OrderItem` | `reference`; product + `quantity` (unique per order) |

DB `CheckConstraint`s enforce positive dimensions/weights and quantity >= 1.

## API

**Ad-hoc:** `POST /api/recommend-box/`
```json
{"items": [{"sku": "CABLE-01", "quantity": 2}, {"sku": "MUG-01", "quantity": 1}]}
```
**Stored order:** `GET /api/orders/ORD-1001/recommend-box/`

Response (abridged):
```json
{
  "status": "ok",
  "recommended_box": {
    "name": "Small Mailer", "cost": "0.45",
    "inner_dimensions_cm": [20.0, 15.0, 10.0], "max_weight_kg": 2.0,
    "utilization": {"volume_pct": 37.1, "weight_pct": 30.0},
    "placements": [{"item": "Ceramic Mug", "position_cm": [0, 0, 0], "size_cm": [8, 8, 9]}]
  },
  "alternatives": [{"name": "Medium Box", "cost": "0.90", "...": "..."}],
  "rejected": [],
  "summary": {"unit_count": 3, "total_weight_kg": 0.6, "total_volume_cm3": 1.0}
}
```
`status` is `"ok"` or `"no_fit"` (HTTP 200 either way - "nothing fits" is a valid answer, with a reason
for each rejected box). Bad input gives HTTP 400 (invalid JSON, unknown SKUs, bad quantity), unknown order 404.

## How a box is chosen

1. Expand quantities into individual units (cap: 200 units).
2. For each **active** box run cheap necessary checks, then a packing attempt:
   - total weight <= `max_weight_kg`
   - total item volume <= box volume
   - every item fits the box in *some* orientation (sorted-dimension comparison)
   - a **3D packing heuristic** finds a concrete valid arrangement
3. Among boxes that fit, pick the lowest `cost`; tie-break on smaller volume, then name (deterministic).

### Packing heuristic
Guillotine free-space splitting: place items (largest first) into the free cuboid that wastes the
least space, trying all axis-aligned rotations, then split the leftover into three disjoint cuboids.
Three item orderings are tried. Any packing it returns is valid (the test-suite checks bounds and
non-overlap independently).

## Assumptions
- Units are cm / kg. Box dimensions are **internal** (usable) dimensions.
- `max_weight_kg` is the limit for the **contents** (box tare weight is ignored).
- Items are rigid cuboids, axis-aligned rotation only; no "this side up" or fragile rules.
- No padding/void-fill allowance is subtracted from box space.
- Cost is per box only (no shipping-rate calculation).

## Limitations / trade-offs
- Exact 3D bin packing is NP-hard. The heuristic can **miss** an arrangement that exists, so a very
  tight order may be pushed to a larger (costlier) box. It never claims a fit that is impossible.
- Single-box only: if nothing fits, the API says `no_fit` rather than splitting into several parcels.
- The JSON endpoint is CSRF-exempt and unauthenticated (internal-tool assumption); add auth before exposing it.

## Layout
```
boxing/packer.py     pure 3D packing + fit checks (no Django)
boxing/selector.py   pure selection rules, dataclasses (no Django)
boxing/services.py   DB -> selector glue
boxing/views.py      JSON API
boxing/models.py     Product, Box, Order, OrderItem
boxing/tests/        test_packer, test_selector (pure) + test_api (Django)
```
The logic is kept free of Django so it is testable without a database.
