# SYSVIA ProofSight — Demo Video Shot List & Production Guide

**Target Duration:** 180 seconds (03:00)  
**Resolution:** 1080p (1920 × 1080) or 1440p (2560 × 1440) @ 60fps  
**Audio:** Clear spoken voiceover, subtle UI sound design, no background music or low non-distracting ambient drone.

---

## Shot-by-Shot Timing and Visual Guide

| Shot # | Timecode | Screen / View | Action / Visual Elements | On-Screen Graphic / Text | Audio Cue / Voiceover Point |
|---|---|---|---|---|---|
| **01** | `00:00–00:10` | Title & Problem Context | Title card transitions into split screen: Warehouse packing bench vs ERP status "Packed". | *The Physical-Digital Reality Gap* | "Modern supply chains run on digital records..." |
| **02** | `00:10–00:20` | Real Discrepancy Graphic | Callout showing packing error: physical box has 1 canister; manifest lists 2. | *Digital Scanners Don't Verify Physical Contents* | "Barcodes lie, packing slips miss reality..." |
| **03** | `00:20–00:35` | Operations Dashboard | Live browser at `http://127.0.0.1:5173/`. Cursor points to Attention cards (Held, Needs Review) and Orders list. | **SYSVIA ProofSight**<br>*The AI That Verifies Reality* | "Meet SYSVIA ProofSight..." |
| **04** | `00:35–00:45` | Architecture Transition | Animated or high-level banner showing: Observe → Investigate → Propose → Approve → Reinspect → Verify. | *Evidence-Grounded Autonomous Operations* | "Bridge visual evidence with backend order data..." |
| **05** | `00:45–01:00` | Visual Inspection & Evidence | Live browser at `/inspection`. Select order `PS-1001`. Image loads with pixel coordinates. | *Meta Muse Spark 1.3 & SAM 3.1 Streaming* | "Let's inspect order PS-1001..." |
| **06** | `01:00–01:10` | SAM Overlays & Mask Toggle | Toggle SAM mask geometry. Show exact bounding boxes and pixel polygons around items. | *Source-Coordinate Geometry Grounding* | "SAM 3.1 streams precise pixel coordinate masks..." |
| **07** | `01:10–01:20` | Discrepancy Table | Scroll to Evidence & Reconciliation table: Red Canister Shortfall (Expected 2, Observed 1). | *Conservative Policy: Not Observed ≠ Absent* | "Geometry does not prove SKU; unobserved ≠ absent..." |
| **08** | `01:20–01:35` | AI Operations Console | Live browser at `/operations`. Select investigation card for order `PS-1001`. Show model badge (Muse Spark 1.3). | *Meta Autonomous Agent Investigation* | "In AI Operations, the agent investigates root cause..." |
| **09** | `01:35–01:45` | Agent Tool Execution Trace | Expand the Agent Tool Activity `<details>`. Scroll through tool calls: `get_order_details`, `get_inventory_levels`. | *Strictly Bounded Read Tools Only* | "Queries database for manifests and inventory..." |
| **10** | `01:45–01:55` | Audit Log & Tool Findings | Highlight immutable audit events. Findings: Shortfall confirmed, inventory stock available. | *Immutable Audit Trail* | "Every tool invocation is logged to an immutable ledger..." |
| **11** | `01:55–02:10` | Action Proposals | Scroll to Proposed Actions: `REQUEST_REINSPECTION` (Requires Approval). | *Autonomous Proposals · Deterministic Policy* | "Agent recommends actions—never unilateral mutation..." |
| **12** | `02:10–02:25` | Supervisor Authorization | Operator clicks **Approve**. Modal confirmation with operator signature. State changes to `AWAITING_NEW_PHOTO`. | *Human-in-the-Loop Supervisor Approval* | "A certified human operator explicitly approves..." |
| **13** | `02:25–02:35` | Before & After Reinspection | Navigate to Before & After view. Show side-by-side comparison with original and new photo IDs. | *Closed-Loop Physical Verification* | "ProofSight requires fresh physical evidence..." |
| **14** | `02:35–02:45` | Shipping Safety Enforcement | Highlight Shipping Authorization box: `Held`. Button to ship is locked until physical reconciliation passes. | *100% Shipping Safety Enforcement* | "Only when deterministic policy confirms full evidence..." |
| **15** | `02:45–03:00` | Summary & Close | Final recap card: 135 backend tests, 23 frontend tests, 100% safety, Meta Muse Spark + SAM 3.1. | **SYSVIA ProofSight**<br>*The AI That Verifies Reality*<br>Meta Global AI Hackathon 2026 | "SYSVIA ProofSight: The AI That Verifies Reality." |

---

## Technical Recording Checklist

1. **Resolution:** 1440p (2560 × 1440) recommended for sharp font rendering in browser tables.
2. **Theme:** Use the application's native dark navy interface (`#070B14`).
3. **Cursor:** Set cursor scaling to 1.25x or enable subtle click rings for visibility.
4. **Token Security:** Ensure the settings page is pre-authorized before recording; never expose the operator token or model keys on screen.
5. **No Jump Cuts in UI:** Keep mouse movements smooth and purposeful.

