# SYSVIA ProofSight

**The AI That Verifies Reality.** Local operations console with real Meta perception,
conservative reconciliation, read-only AI investigation, supervisor approval, and
new-photo reinspection.

## Run locally

From the repository root in PowerShell:

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/setup_local.py
.\.venv\Scripts\python.exe scripts/seed_demo.py
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
~~~

In a second terminal:

~~~powershell
cd frontend
npm.cmd ci
npm.cmd run dev
~~~

Open http://127.0.0.1:5173. API docs: http://127.0.0.1:8000/docs.
Alternatively, with the local servers stopped, run:

~~~powershell
docker compose up --build -d
~~~

Docker uses the same URLs and persists SQLite and evidence in the ignored data/ folder.

## Configuration and use

- Set MODEL_API_KEY locally in the root .env. An existing file can be selected
  with PROOFSIGHT_ENV_FILE; existing process variables take precedence.
- setup_local.py creates a separate, secure OPERATOR_TOKEN if absent. In
  **Settings**, enter that local token for uploads, analysis, investigation, and
  supervisor actions. It stays in browser memory. Never enter a model API key in the UI.
- The explicit seed creates four synthetic products, five orders, and inventory.
  It does not create inspection results or reset existing orders.
- Select a ready order, upload rights-cleared evidence, and explicitly analyze.
  A run makes one Muse image request and up to four SAM requests for distinct
  observed catalog products. Investigation is a separate paid operation using
  bounded, order-scoped read tools.
- In **AI Operations**, start an investigation, inspect its recorded tools and
  evidence, then approve or reject each validated proposal. Execution is a
  separate authorized step. Supported actions hold shipment, create a picking
  task, request reinspection, or escalate to human review.
- A picking task reserves availability without deducting physical inventory.
  It cannot verify an order: upload a genuinely different image and reanalyze.
  Both photo IDs remain. Shipping transitions require current verified evidence.
- Optional original synthetic image: python scripts/create_synthetic_image.py.
  This produces data/synthetic-preparation.png, not a warehouse photograph.

## Checks

~~~powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
cd frontend
npm.cmd test
npm.cmd run build
~~~

Running python scripts/test_meta_api.py makes one live ping; adding --image
also makes one SAM request. Live diagnostics never fall back to mocks. Normal
unit tests use isolated databases and mocked provider transport.

The backend is deliberately a single-worker local development service. Geometry
does not prove SKU, and “not observed” does not prove absence. See
[connection evidence](docs/meta-api-connection-report.md) and
[original contributions](docs/hackathon-contributions.md).
