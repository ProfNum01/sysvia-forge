# SYSVIA ProofSight — 3-Minute Video Demonstration Script

**Title:** SYSVIA ProofSight: The AI That Verifies Reality  
**Track:** Startups · Meta Global AI Developer Hackathon 2026  
**Target Duration:** Exactly 180 Seconds (03:00)  
**Presenter Tone:** Direct, authoritative, technically grounded, zero hype.

---

### Segment 1: The Problem (00:00 – 00:20 · 20s)

**Visual:**
Split screen: A warehouse packing bench with physical parcels on the left; an ERP fulfillment status saying *"Packed & Ready"* on the right.

**Voiceover:**
> "Modern supply chains run on digital records. Every warehouse management system assumes that if a barcode scanned, the physical box is correct.
> But barcodes lie, picking bins get mixed up, and packing slips don't see what actually went into the carton.
> In high-throughput operations, discrepancies slip through undetected—costing millions in returns, fines, and operational downtime.
> Digital records cannot verify physical reality."

---

### Segment 2: Meet ProofSight (00:20 – 00:45 · 25s)

**Visual:**
Switch to the live ProofSight Operations Dashboard (`01_dashboard.png`). Highlight the real-time Attention metrics (Needs Review, Held), Order Statuses, and live Meta API connection badge.

**Voiceover:**
> "Meet SYSVIA ProofSight: The AI That Verifies Reality.
> ProofSight is an evidence-grounded autonomous operations agent.
> Instead of assuming an order is correct, ProofSight bridges real visual evidence with backend order data.
> Every decision starts with what can actually be observed.
> It uses Meta’s Muse Spark 1.3 for multimodal reasoning and SAM 3.1 for exact geometric segmentation, governed by strict deterministic backend policies."

---

### Segment 3: Visual Intelligence (00:45 – 01:20 · 35s)

**Visual:**
Navigate to Visual Inspection (`03_visual_inspection.png`). Select order `PS-1001`. Display the uploaded packing scene.
Show real perception outputs:
1. Muse Spark 1.3 visual observations identifying products and text labels (`PS-RED-01`, `PS-BLUE-02`).
2. SAM 3.1 exact pixel mask overlays outlining each parcel in source coordinates.
3. The deterministic comparison table highlighting a quantity shortfall: Expected 2 units of Red Utility Canister, but evidence only supports 1 visible unit.

**Voiceover:**
> "Let’s inspect order PS-1001. The order calls for two Red Utility Canisters and one Blue Supply Box.
> When an inspection image is uploaded, ProofSight triggers real Meta inference.
> Muse Spark 1.3 analyzes the visual scene, reading SKU labels and visual geometry.
> Simultaneously, Segment Anything Model 3.1 streams precise pixel coordinate masks for every item.
> Here is ProofSight’s first core principle: geometry does not prove SKU identity, and unobserved does not prove absent.
> Our deterministic policy flags an open Shortfall discrepancy. The order is automatically placed on Hold."

---

### Segment 4: Autonomous Investigation (01:20 – 01:55 · 35s)

**Visual:**
Navigate to AI Operations (`05_ai_operations.png`). Trigger the AI investigation.
Expand the tool activity trace showing the model calling bounded read tools:
- `get_order_details`
- `get_inventory_levels`
- `get_inspection_evidence`
- `get_pending_actions`
Show the model reasoning over real database facts.

**Voiceover:**
> "Now the agent takes over. In AI Operations, the ProofSight agent investigates the root cause.
> Unlike black-box chatbots, our agent operates in an accountable loop with strictly read-only tools.
> It queries the database for manifest requirements, inspects available warehouse stock, and reviews historical actions.
> It verifies whether a second unit was in stock or if visual occlusion prevented a clean count.
> Every tool invocation is logged to an immutable audit ledger."

---

### Segment 5: Safe Operational Decisions (01:55 – 02:25 · 30s)

**Visual:**
Show the agent’s findings: Decision: `HUMAN_REVIEW_REQUIRED`.
Show proposed actions: `REQUEST_REINSPECTION` and `ESCALATE_TO_HUMAN`.
Click the supervisor **Approve** button. Enter idempotency key. Show state transition to `AWAITING_NEW_PHOTO`. Show shipping status locked at `HELD`.

**Voiceover:**
> "ProofSight’s agent recommends actions—it never executes mutations unilaterally.
> When evidence is ambiguous, the agent correctly halts and decides: Human Review Required.
> It proposes requesting physical reinspection.
> A certified human operator reviews the proposal and explicitly approves it with an idempotent signature.
> The order remains strictly locked in Held status. ProofSight enforces safety: no unverified order can ever be dispatched."

---

### Segment 6: Closed-Loop Verification (02:25 – 02:45 · 20s)

**Visual:**
Open Before & After Reinspection view (`04_before_after_reinspection.png`).
Show the two distinct photo IDs: original Photo ID `865ac95e` vs new Photo ID `4d7292d9`.
Show the comparison table comparing before/after observed quantities.
Show the shipping guard: Shipping Authorization remains Held until physical evidence completely satisfies the manifest.

**Voiceover:**
> "To close the loop, ProofSight requires fresh physical evidence.
> Merely completing a pick ticket does not verify an order. An operator must provide a new photograph.
> The before-and-after view preserves both immutable photo IDs and reconciles actual changes.
> Only when deterministic policy confirms every item is observed and accounted for does the order become eligible for shipping authorization."

---

### Segment 7: Technical Impact & Close (02:45 – 03:00 · 15s)

**Visual:**
Show the architecture overview and benchmark metrics:
- 135 backend tests, 23 frontend tests passed.
- 100% shipping safety enforcement across all test cases.
- Meta Muse Spark 1.3 + SAM 3.1 integration.
Display final logo: **SYSVIA ProofSight — The AI That Verifies Reality.**

**Voiceover:**
> "SYSVIA ProofSight transforms computer vision from a passive monitor into an accountable, evidence-grounded operations partner.
> 135 backend tests, end-to-end browser validation, zero false verifications.
> SYSVIA ProofSight: The AI That Verifies Reality. Built for the Meta Global AI Developer Hackathon 2026."

