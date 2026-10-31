# ProofSight evaluation

From the repository root:

```powershell
.\.venv\Scripts\python.exe evaluation/scripts/run_benchmark.py
.\.venv\Scripts\python.exe evaluation/scripts/run_benchmark.py --live --scenario correct-order --max-live-requests 1
```

The default validates the five original synthetic scenes and makes **zero** Meta requests. `--live` uses a new temporary database per scene, uploads real image bytes, invokes the existing Muse Spark 1.3 and SAM 3.1 workflow, and may invoke the investigation agent. One inspection attempt is allowed by default; the hard cap is six. Results go to the ignored `evaluation/results/` directory; use `--output-dir data/evaluation-results` for local private artifacts.

The scenario manifest is `evaluation/manifests/synthetic.json`. New rights-cleared evidence can be added with a matching case record; `PHYSICAL_CAPTURE` must never point to a synthetic fixture. The current five scenes cover a correct order, visible shortfall, extra product, unreadable label, and unidentified object. Other requested scenarios require eligible evidence or a separate policy test and are not counted as live benchmark cases.

To combine already recorded live results without another paid request:

```powershell
.\.venv\Scripts\python.exe evaluation/scripts/summarize_results.py <first-live-result.json> <second-live-result.json>
```

Rates with no valid denominator are `null`. Uncertain cases are excluded from binary discrepancy precision and recall, and region-level identification accuracy remains unmeasured until independent SKU annotations exist. Synthetic before/after evidence can test software state transitions but cannot prove a physical correction.
