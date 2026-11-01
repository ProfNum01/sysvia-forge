# Ten synthetic whole-order scenarios

`manifest.json` contains ten independent order cases. Each `orders/TEN-ORDER-XX.json` is an order manifest and points to one whole-order PNG in `images/`. Six scenes match their orders. Four conflict: missing red can, extra green cube, red-to-yellow substitution, and one missing blue box.

All images are deterministic Pillow drawings made for this project using the four fictional SKU names in the existing Claude-labeled reference set. They are synthetic illustrations, not camera captures. `ground_truth_quantities` describes what the generator drew; it is not a Meta observation or a verified inspection result. The project must still use real perception and its evidence policy before marking an order verified.

Regenerate with `python evaluation/scripts/create_ten_orders.py`. Validate offline with `python evaluation/scripts/run_benchmark.py --dataset evaluation/datasets/ten-orders/manifest.json`. Register these orders in the local application database with `python scripts/register_ten_orders.py` after the four Claude-labeled synthetic products are registered. Registration is idempotent and creates no inspections or verification results.
