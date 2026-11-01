# Owner physical packing capture

The five Claude AI generated PNGs supplied on 2026-11-01 were moved unchanged to `../synthetic-claude-labeled/`. They are not physical captures. Physical validation remains blocked until genuine camera photographs are supplied.

Print [the A4 labels](../../../submission/physical-product-labels.html) at 100% scale. Attach each label only to the corresponding owner-confirmed physical product. Use genuine camera photos with the whole packing surface and readable labels. Keep captures private; this folder ignores photographs and `manifest.json` in Git.

Copy six genuine files here using these exact names:

| File | Required capture |
| --- | --- |
| `reference-blue.png`, `reference-red.png`, `reference-yellow.png`, `reference-green.png` | One clear photo of each labeled product |
| `missing-before.png` | Entire scene: 2 BLUE-BOX, 1 RED-CAN, 0 YELLOW-POUCH |
| `missing-after.png` | New photo after physical correction: 2 BLUE-BOX, 1 RED-CAN, 1 YELLOW-POUCH |

The scene quantities above are operator setup instructions, not AI observations. A green cube reference is required for the catalog, but no green cube is ordered. Do not use screenshots, generated images, or copies of the same capture for before and after. Retain camera originals and capture time privately.

Copy `manifest.template.json` to `manifest.json`. Fill the actual dataset ID, unique order reference, stock quantities and location; set `rights_confirmed` true only after confirming rights. The template deliberately fails validation until these fields and genuine reference/before photos exist. Leave `after_image` empty until correction; then set it to `missing-after.png`.

From the project root, validate and register the isolated physical products and order:

```powershell
Copy-Item evaluation/datasets/physical-packing/manifest.template.json evaluation/datasets/physical-packing/manifest.json
.\.venv\Scripts\python.exe scripts/register_physical_dataset.py evaluation/datasets/physical-packing/manifest.json
.\.venv\Scripts\python.exe scripts/register_physical_dataset.py evaluation/datasets/physical-packing/manifest.json --register
```

Registration only adds a separate physical catalog and order. It does not infer photo contents or verify the order. Upload `missing-before.png` through the authenticated inspection workflow, review its evidence and proposed action, approve as supervisor, execute the controlled action, physically add the missing product, then upload `missing-after.png` for a new inspection. Keep both inspection/photo IDs. Verification requires actual after-image evidence and deterministic reconciliation. Never treat task completion or an absent detection alone as proof of correction.
