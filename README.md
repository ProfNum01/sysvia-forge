# SYSVIA ProofSight

**The AI That Verifies Reality.**

> An evidence-grounded autonomous operations agent that connects visual observations with digital business workflows, enforces deterministic verification policies, and audits corrective actions.

Built for the **Meta Global AI Developer Hackathon 2026** (Startups Track · Push the Frontier).

---

## The Problem

Enterprise supply chains and warehouse operations suffer from a dangerous gap: **the disconnect between digital systems and physical reality.**

When an order is picked and packed in a modern warehouse, an operator scans a barcode or taps a screen to mark the order "completed." The Enterprise Resource Planning (ERP) and Warehouse Management System (WMS) assume this digital action guarantees the parcel's contents are correct.

In high-throughput environments, this assumption regularly breaks down:
- Items placed into the wrong carton after scanning.
- Missing units due to inventory stockouts or picker fatigue.
- Part substitutions where an unauthorized or incompatible SKU is packed.
- Ambiguous labels or occlusion preventing quality assurance.

Digital barcodes verify only what was scanned, not what was actually placed in the box. Weight scales fail when products have similar weights. When errors escape to customers, the result is costly returns, chargebacks, wasted freight, and broken customer trust.

---

## Our Solution

**SYSVIA ProofSight** is an accountable, evidence-grounded operations platform. It does not replace existing warehouse software; instead, it acts as an autonomous physical verification layer.

ProofSight captures visual evidence of packed orders and subjects them to an end-to-end perception and reasoning loop:
1. **Multimodal Perception:** Uses **Meta Muse Spark 1.3** to identify visible products and alphanumeric labels, combined with **Meta SAM 3.1** to segment exact pixel masks in source-image resolution.
2. **Deterministic Reconciliation:** Compares observed items against the authoritative digital manifest using conservative policies: *geometry does not prove SKU identity*, and *unobserved does not prove absent*.
3. **Autonomous Investigation:** When discrepancies exist, an autonomous Meta agent investigates root causes using bounded, strictly read-only database tools.
4. **Governed Action Proposals:** The agent proposes corrective actions (e.g., hold order, request reinspection, escalate to supervisor). The model is strictly prohibited from mutating production state unilaterally.
5. **Human Supervisor Authorization:** Consequential actions require an authenticated human supervisor approval with idempotency protection.
6. **Closed-Loop Physical Verification:** ProofSight rejects self-certification. Re-inspection requires fresh photographic evidence with an immutable, distinct photo ID before shipping holds can ever be released.

---

## Why It Matters

- **Eliminates False Verifications:** Prevents AI hallucinations from certifying incomplete shipments.
- **Reduces Returns & Chargebacks:** Catches missing, wrong, or extra products before cartons reach shipping carriers.
- **Auditable Chain of Custody:** Maintains an immutable historical ledger connecting physical photo UUIDs, tool execution traces, supervisor signatures, and state transitions.
- **Human-Governed Autonomy:** Combines the speed of multimodal AI investigation with the safety of deterministic code gates and certified human authorization.

---

## Meta AI Integration

ProofSight integrates two flagship Meta AI models running over official Meta API endpoints (`https://api.meta.ai/v1`):

### 1. Meta Muse Spark 1.3 (`muse-spark-1.3`)
- **Visual Analysis:** Evaluates high-resolution scene evidence, extracting product geometry, visible SKU labels, and packaging characteristics.
- **Autonomous Investigation Agent:** When anomalies are detected, Muse Spark acts as the reasoning engine. It dynamically invokes declared function tools (`get_order_details`, `get_inventory_levels`, `get_inspection_evidence`, `get_pending_actions`, `get_verification_history`) to gather context.
- **Structured Outputs:** Returns structured JSON findings, recommendations, and evidence references.

### 2. Meta Segment Anything Model 3.1 (`sam-3.1`)
- **Pixel-Level Geometry:** Streams binary segmentation masks and polygonal coordinates over the Meta Responses API.
- **Coordinate Grounding:** Directly maps segmentation boundaries to original image dimensions, providing visual evidence regions rendered as SVG overlays in the operator console.

### Model-Driven Reasoning vs. Deterministic Policy
| Capability | Meta AI Responsibility | Deterministic Backend Policy Responsibility |
|---|---|---|
| **Scene Perception** | Identifies shapes, visible labels, and confidence | Converts observations to candidate items; flags uncertain observations |
| **Discrepancy Analysis** | Synthesizes findings across manifest and stock | Calculates exact quantity shortfalls, excesses, and unobserved items |
| **Operational Proposals** | Recommends actions based on context | Validates that proposed actions conform to state machine rules |
| **Action Execution** | *None (Strictly prohibited)* | Enforces supervisor authentication, idempotency, and audit logging |
| **Shipping Authorization** | *None (Strictly prohibited)* | Locks shipping in `HELD` until full physical evidence reconciliation succeeds |

---

## Agentic Architecture

ProofSight follows a 7-stage governed autonomous lifecycle:

```
┌─────────┐     ┌─────────────┐     ┌─────────┐     ┌─────────┐
│ Observe │ ──> │ Investigate │ ──> │ Propose │ ──> │ Approve │
└─────────┘     └─────────────┘     └─────────┘     └─────────┘
 (Meta AI)         (Meta AI)         (Meta AI)       (Human)
                                                        │
┌─────────┐     ┌─────────────┐     ┌─────────┐         │
│ Verify  │ <── │  Reinspect  │ <── │ Execute │ <───────┘
└─────────┘     └─────────────┘     └─────────┘
(Backend)         (Operator)         (Backend)
```

1. **Observe (Autonomous):** Muse Spark 1.3 and SAM 3.1 analyze the physical image.
2. **Reconcile (Deterministic):** Backend compares observations against digital order items.
3. **Investigate (Autonomous):** Muse agent queries order, inventory, and action history using bounded read-only tools.
4. **Propose (Autonomous):** Agent synthesizes findings and suggests validated actions.
5. **Approve (Human Intervention Required):** Certified supervisor evaluates and explicitly authorizes the action.
6. **Execute (Deterministic):** Backend records action, creates tasks, and updates order revision state.
7. **Reinspect & Verify (Closed Loop):** Physical operator uploads fresh evidence. Deterministic verification verifies the order and authorizes shipping.

---

## Technology Stack

- **Backend:** Python 3.13, FastAPI 0.115, SQLAlchemy 2.0, SQLite 3 (with triggers and foreign keys), Pillow, HTTPX.
- **Frontend:** React 19.2, TypeScript 5.9, Vite 7.1, TanStack Query v5, Lucide Icons, Recharts, Tailwind CSS v4.
- **AI & Perception:** Meta Muse Spark 1.3, Meta SAM 3.1 over `https://api.meta.ai/v1`.
- **Testing & E2E:** Python `unittest`, Playwright 1.64 (Chromium), Vitest 5.0.
- **Deployment:** Windows PowerShell native, Linux/WSL2, Docker & Docker Compose.

---

## Installation

### Prerequisites
- Python 3.11+ (Python 3.13 tested)
- Node.js 20+ (Node.js 24 tested)
- Git

### 1. Windows (PowerShell)
```powershell
# Clone repository
git clone https://github.com/ProfNum01/sysvia-forge.git
cd sysvia-forge

# Create Python virtual environment
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Initialize local configuration and seed database
.\.venv\Scripts\python.exe scripts/setup_local.py
.\.venv\Scripts\python.exe scripts/seed_demo.py

# Install frontend dependencies
cd frontend
npm.cmd ci
cd ..
```

### 2. Linux / WSL2 (Bash)
```bash
git clone https://github.com/ProfNum01/sysvia-forge.git
cd sysvia-forge

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/setup_local.py
python scripts/seed_demo.py

cd frontend
npm ci
cd ..
```

### 3. Docker Compose
```bash
docker compose up --build -d
```
*Docker maps backend to `http://127.0.0.1:8000` and frontend to `http://127.0.0.1:5173`, persisting SQLite data in the `./data` directory.*

---

## Environment Configuration

Configuration is managed via `.env` in the project root. Copy `.env.example` to start:

```ini
# Meta Model API Key (leave empty for offline/benchmark mode)
MODEL_API_KEY=

# Local Supervisor Bearer Token (generated automatically by setup_local.py)
OPERATOR_TOKEN=

# Bounded Agent Limits (optional)
PROOFSIGHT_AGENT_TIMEOUT_SECONDS=45
PROOFSIGHT_AGENT_MAX_TOOL_CALLS=8

# Optional Storage and Network Paths
# PROOFSIGHT_DATA_DIR=data
# DATABASE_URL=sqlite:///data/proofsight.db
```

> **Security Note:** Never commit `.env` or paste model API keys into the frontend console. Operator authentication uses Bearer tokens stored in browser session memory.

---

## Running the Application

### 1. Start the Backend API
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
*Swagger API Documentation: `http://127.0.0.1:8000/docs`*

### 2. Start the Frontend Console
```powershell
cd frontend
npm.cmd run dev
```
*Open `http://127.0.0.1:5173` in your browser.*

---

## Running Tests

### 1. Backend Test Suite (135 Tests)
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### 2. Frontend Unit Tests (23 Tests)
```powershell
npm --prefix frontend test
```

### 3. Frontend Production Build
```powershell
npm --prefix frontend run build
```

### 4. Authenticated Browser E2E Tests (Playwright Chromium)
```powershell
# Run Playwright test runner
cd frontend
npx playwright test

# Or execute the complete standalone 9-phase E2E workflow script
node e2e/run_workflow_e2e.cjs
```

### 5. Offline Benchmark Suite (Zero API Cost)
```powershell
.\.venv\Scripts\python.exe evaluation/scripts/run_benchmark.py
```

### 6. Live Meta Diagnostic Ping (1 Live Request)
```powershell
.\.venv\Scripts\python.exe scripts/test_meta_api.py
```

---

## Benchmark Results

Evaluation was conducted against five original, procedurally defined synthetic test scenarios documented in `evaluation/manifests/synthetic.json`:

| Scenario ID | Test Case | Target Discrepancy | Live Evaluation Result | Safety Policy Compliance |
|---|---|---|---|---|
| `correct-order` | Exactly 2x Red Canister, 1x Blue Box | None (Matching manifest) | **VERIFIED** (Shipping `NOT_READY`) | **100% PASS** |
| `visible-shortfall` | 1x Red Canister observed (2 required) | Shortfall (1 missing) | Tested offline; Shortfall flagged | **100% PASS** |
| `additional-product` | 2x Red, 1x Blue + 1x Green Canister | Extra Product | **NEEDS_REVIEW / HELD** (Uncertain grounded identity) | **100% PASS** |
| `unreadable-label` | Deliberately degraded label text | Uncertain SKU | Tested offline; Needs Review flagged | **100% PASS** |
| `unidentified-shape` | Non-catalog purple object | Unidentified Object | Tested offline; Needs Review flagged | **100% PASS** |

### Verified Summary Statistics
- **False Verification Rate:** 0.0% (Zero unverified or held orders incorrectly advanced to shipping).
- **Shipping Safety Enforcement:** 100% (Orders with discrepancies strictly blocked from shipping).
- **Agent Decision Validity:** 100% (All model recommendations complied with deterministic policy and schema).

---

## Hackathon Contributions

All code in this repository was built from scratch specifically for the **Meta Global AI Developer Hackathon 2026** during **October 26 – November 4, 2026**:
- **Oct 26–29:** Core domain models, SQLite schema, FastAPI backend, React operations console, initial Meta client wrappers.
- **Oct 30:** Streaming SAM 3.1 parser, source-coordinate overlays, deterministic reconciliation tables, bounded agent tool engine.
- **Oct 31:** Closed-loop reinspection verification, order revision triggers, removal task handling, security hardening with Bearer-protected evidence endpoints, Playwright Chromium E2E suite, and release packaging.

Detailed chronological commit logs are maintained in [`docs/hackathon-contributions.md`](docs/hackathon-contributions.md).

---

## Limitations and Disclosure

1. **Synthetic Imagery Baseline:** All benchmarks and demonstrations utilize original rights-cleared procedural scenes and test fixtures. Real-world warehouse camera hardware, varying focal lengths, and dynamic facility lighting remain unvalidated.
2. **Physical Correction Cycle:** The end-to-end physical picking and removal loop was verified using before/after digital evidence pairs. Physical warehouse item replenishment has not been evaluated with a live warehouse picking crew.
3. **Live Meta Inference Sample Size:** Two scenarios were evaluated with live Meta API calls; the remaining three scenarios were evaluated through the offline fixture suite to avoid uncontrolled API usage.

---

## License

This project was built during the Meta Global AI Developer Hackathon 2026. A formal open-source license will be selected by the project owner prior to public distribution.
