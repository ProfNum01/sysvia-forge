# Meta Global AI Developer Hackathon 2026 — Official Submission Document

**Track:** Startups  
**Theme:** Push the Frontier  
**Deadline:** November 4, 2026 at 9:00 PM Eastern Time  

---

### Project Name
**SYSVIA ProofSight**

### Tagline
**The AI That Verifies Reality**

### One-Line Description
An evidence-grounded autonomous operations agent that connects visual observations with digital business workflows and verifies corrective actions.

---

### Project Description

#### 1. The Real-World Problem
Modern supply chains, distribution centers, and manufacturing plants operate under the dangerous assumption that digital records reflect physical reality. When an operator scans an item barcode or marks an order "packed" in an Enterprise Resource Planning (ERP) or Warehouse Management System (WMS), the software assumes the carton contains exactly what was ordered. 

In reality, packing discrepancies, mispicks, part substitutions, and count errors frequently escape detection. Standard automated systems rely either on barcode scans (which only verify what was scanned, not what was placed in the box) or weight scales (which fail when substitutes have similar weight). When incorrect shipments leave the loading dock, companies suffer costly returns, customer chargebacks, regulatory penalties, and significant waste.

#### 2. The Proposed Solution
**SYSVIA ProofSight** is an evidence-grounded operations platform that bridges physical visual evidence with digital order records. Rather than replacing existing warehouse systems, ProofSight acts as an autonomous, accountable verification layer.

When a parcel is packed, high-resolution visual evidence is captured. ProofSight uses Meta’s Muse Spark 1.3 multimodal model and Segment Anything Model (SAM 3.1) to observe, segment, and ground physical objects. A deterministic reconciliation engine compares observed evidence against authoritative order manifests. 

When discrepancies occur (such as a missing canister or an unauthorized product), an autonomous Meta agent investigates the operational context using bounded, read-only tools. It analyzes whether the error was caused by inventory stockouts, label misreads, or physical occlusion. The agent proposes validated corrective actions (e.g., requesting a physical reinspection, issuing a picking task, or escalating to human management). Every action requires certified human supervisor authorization before execution, and verification requires fresh physical evidence—ensuring a closed-loop audit trail.

#### 3. What Makes ProofSight Technically Interesting
ProofSight is built on the philosophy of **"Evidence before Confidence."** Most AI vision applications suffer from hallucinations: models confidently guess counts or hallucinate brand names from partial visual cues. ProofSight enforces two strict mathematical safety principles:
1. **Geometry does not prove identity:** Segmenting a polygon via SAM establishes that an object exists at specific pixel coordinates, but cannot verify its SKU.
2. **"Not observed" does not prove "absent":** If an item is occluded or outside the camera frame, ProofSight labels it `UNCERTAIN` or `NOT_OBSERVED` rather than declaring it missing.

#### 4. How Meta AI Models Are Essential
ProofSight leverages two distinct Meta AI models in a unified multimodal pipeline:
- **Meta Muse Spark 1.3:** Powers both the initial perception layer (analyzing visual scenes, extracting alphanumeric label text, and identifying visible object categories) and the autonomous investigation agent (reasoning over discrepancies, choosing bounded read tools, and synthesizing structured action recommendations).
- **Meta Segment Anything Model (SAM 3.1):** Operates over streaming response endpoints to generate exact pixel-level masks and polygon coordinates in source-image resolution, grounding the high-level semantic observations in physical geometry.

#### 5. How Autonomous Investigation Works
When visual evidence reveals an anomaly, ProofSight initiates an autonomous investigation:
- The agent is equipped with strictly read-only database tools (`get_order_details`, `get_inventory_levels`, `get_inspection_evidence`, `get_pending_actions`, `get_verification_history`).
- It autonomously formulates a reasoning trace, queries the necessary facts, and evaluates root causes without any human prompting.
- It operates under strict resource bounds (enforced timeouts and call limits) to prevent runaway loops.
- All model reasoning and tool events are logged to an immutable SQLite audit log.

#### 6. Why Deterministic Verification and Human Approval Matter
LLMs should never execute consequential operational mutations directly. In ProofSight:
- **No Unilateral Mutations:** The Meta agent can only *propose* actions. All mutations are validated by a deterministic server-side policy engine.
- **Supervisor Approval Gate:** Consequential actions (holding an order, creating a warehouse picking task, initiating reinspection) require a Bearer-authenticated supervisor signature with an idempotency key.
- **Closed-Loop Verification:** ProofSight rejects "self-certification." Merely marking a picking task "completed" does not verify the order; a fresh physical photograph with a distinct photo ID must be uploaded and re-inspected.
- **Strict Shipping Safety:** An order's shipping status cannot advance to `READY_TO_SHIP` or `SHIPPED` while open discrepancies or required reinspections exist.

#### 7. What Was Actually Implemented
During the hackathon window (October 26 – November 4, 2026), the following was built from scratch:
- Complete FastAPI backend with SQLite schema, triggers, and migrations.
- React 19 / TypeScript / Vite operations console with dark-mode operations dashboard, visual inspection evidence viewer, before/after reinspection comparison, and AI operations workspace.
- Meta Model API integration clients for Muse Spark 1.3 and SAM 3.1 streaming responses.
- Bounded autonomous investigation engine with six read-only database tools.
- Idempotent action execution engine with supervisor authorization.
- Authenticated evidence endpoints utilizing secure, short-lived Blob URLs without URL credential leakage.
- Five procedural, rights-cleared synthetic test scenes and an offline reproducible benchmark runner.
- Playwright Chromium end-to-end browser test suite.

#### 8. Which Capabilities Were Verified
- **135 backend tests** passed (0 failures) covering security, concurrency, edge cases, action policies, and schema migrations.
- **23 frontend unit tests** passed (0 failures).
- **Playwright browser E2E validation** passed across all 9 workflow phases.
- **Protected image endpoints** confirmed: 403 Forbidden without token, 200 OK with Bearer token.
- **Live Meta requests:** Muse Spark 1.3 ping, live image analysis, and SAM 3.1 streaming inference previously executed and confirmed live.
- **Shipping safety:** Zero unauthorized shipping transitions across all test scenarios.

#### 9. What Remains Unverified (Transparent Limitations)
- **Physical Camera Capture:** Validation was performed using original rights-cleared synthetic scenes and local test fixtures. Physical warehouse camera feeds and real-world warehouse lighting conditions remain to be validated.
- **Live Correction Cycle:** Due to the absence of a physical packing line, the complete live correction cycle (physical item picked from a real shelf and re-photographed) was validated using procedural before/after evidence rather than physical warehouse items.
- **Benchmark Sample Size:** The live benchmark was evaluated on two synthetic scenarios; the remaining three cases were validated via the offline benchmark suite.

---

### Technical Innovation

ProofSight demonstrates that the future of enterprise AI lies in **controlled autonomy backed by deterministic guardrails**:
1. **Multimodal Perception Fusion:** Combining Muse Spark’s semantic scene understanding with SAM 3.1’s geometric segmentation prevents single-model hallucinations.
2. **Evidence-Grounded Reasoning:** The model is constrained to facts observable in the photo or retrieved via database read tools.
3. **Deterministic State Machine:** The AI proposes; deterministic software validates and dispatches. The model cannot alter order versions or clear holds on its own authority.
4. **Order Revision Protection:** Database triggers automatically bump order versions when line items change, instantly invalidating stale visual evidence.
5. **Immutable Evidence Chains:** Every inspection retains immutable photo UUIDs, preventing old evidence from being passed off as fresh corrections.

---

### Meta AI Usage Details

- **Meta Muse Spark 1.3 (`muse-spark-1.3`):**
  - Endpoint: `https://api.meta.ai/v1/chat/completions`
  - Function Calling: Operates with 6 tool declarations (`get_order_details`, `get_inventory_levels`, `get_inspection_evidence`, `get_pending_actions`, `get_verification_history`, `escalate_to_human`).
  - Output: Enforces strict structured JSON schema for findings, recommendations, and evidence references.
- **Meta SAM 3.1 (`sam-3.1`):**
  - Endpoint: `https://api.meta.ai/v1/chat/completions` (Streaming Responses API)
  - Output: Streams binary/polygon segmentations converted into SVG overlay coordinates mapped to original image dimensions.

---

### Target Industry Impact

- **E-Commerce & Warehouse Fulfillment:** Autonomous secondary inspection for high-value orders (electronics, pharmaceuticals, luxury goods) to eliminate wrong-item chargebacks.
- **Industrial Order Staging:** Verifying kitting and assembly parts before delivery to manufacturing lines.
- **Outbound Quality Assurance:** Providing an indisputable visual record to defend against false damage or missing-item claims.

---

### Repository and Links

- **GitHub Repository:** `https://github.com/ProfNum01/sysvia-forge.git`
- **Demo Video URL:** *[DEMO VIDEO PLACEHOLDER — To be populated with public YouTube/Loom URL upon upload]*
- **Documentation:** `README.md`, `docs/hackathon-contributions.md`, `submission/DEMO_SCRIPT.md`

---

### Team Information

- **Team:** SYSVIA Team (`ProfNum01`)
- **Track:** Startups · Push the Frontier
- **Development Window:** October 26, 2026 – November 4, 2026

