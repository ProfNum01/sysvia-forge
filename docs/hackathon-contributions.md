# Hackathon contributions

## 2026-11-01 — Operations Investigation Layout & Cross-App Action Button Differentiation

- Repaired `ActiveInvestigationProgress` layout and animation performance on `/operations`:
  - Re-architected `.investigation-stepper-grid` from 4-column blowout to a contained 2x2 grid (`grid-template-columns: repeat(2, minmax(0, 1fr))`, mobile `1fr`), eliminating horizontal overflow into adjacent card columns.
  - Added CSS containment (`contain: paint; overflow: hidden; box-sizing: border-box; max-width: 100%`) on `.active-investigation-container` and `.investigation-card`.
  - Stabilized animation loops (`@keyframes radar-pulse`, `shimmerSweep`, `.spin`) with `will-change: transform` and throttled the investigation progress timer from 100ms to 500ms intervals, eliminating layout thrashing and stutter.
- Comprehensive semantic button differentiation:
  - Table and workspace action buttons across `/orders`, `/operations`, and `InspectionTable` (Ledger and Overview) are now strictly styled with distinct high-contrast semantic palettes:
    - `action-inspect` (Luminous Sky/Cyan gradient) for pending inspections.
    - `action-review` (Warm Amber gradient) for discrepancy investigations.
    - `action-hold` (Rose Crimson gradient) for held orders and quarantines.
    - `action-verified` (Emerald Green gradient) for verified proof.
    - `action-view` (Slate Outline) for evidence records.
  - Updated Docker container `sysvia-proofsight-frontend-1` with the fresh compiled production build (`index-RATNp3O0.js` & `index-r8WOXJna.css`).
- Verification: 24 frontend vitest tests passed; 158 backend pytest tests passed; Vite TypeScript production build succeeded with 0 errors.

## 2026-11-01 — Comprehensive semantic button differentiation across entire interface

- Redesigned visual button hierarchy across the application to eliminate indistinguishable dark/outline buttons.
- Orders workspace:
  - Differentiated the filter bar (`.orders-filter-bar`) by introducing unique semantic chromatic styles, glowing active states, and distinct SVG icons (`Layers` for All Orders in electric blue, `Clock` for Awaiting Inspection in luminous cyan, `ShieldAlert` for On Hold in crimson, and `CheckCircle2` for Verified Reality in emerald).
  - Re-engineered table row action buttons with high-contrast dedicated variant styles: `Inspect Now` (`action-inspect`, cyan gradient), `Review Issues` (`action-review`, warm amber gradient), `Investigate Hold` (`action-hold`, crimson gradient), and `Verified Match` (`action-verified`, emerald gradient).
  - Styled `Synthetic seed data` as an informational metadata pill rather than looking like an interactive or disabled button.
- Demo Workspace:
  - Differentiated action buttons so they are no longer all identical outline variants: "Open inspection evidence" (`variant="primary"`), "Use in inspection" (`variant="inspect"`), and "Set token to use" (`variant="warning"`).
- Evidence Viewer & Operations:
  - Enhanced viewer zoom controls with distinct tactile button borders, and transformed the Overlays toggle into an active cyan button (`variant="inspect"`) when active.
  - Added semantic styling to timeline filter pills (`data-category`) across ALL, TOOL, LIFECYCLE, and ACTION.
  - Differentiated shipping transition buttons (`READY_TO_SHIP` in success emerald, `SHIPPED` in primary blue).
- Verification: 24 frontend tests passed; 158 backend tests passed; Vite TypeScript production build succeeded with 0 errors.

## 2026-11-01 — Claude synthetic live inspection and review agent

- Diagnosed the Claude catalog's SAM prompt as a provenance sentence rather than a short object phrase. Added a failing provider test, then sent the registered product's noun phrase to SAM for this catalog. No SKU, count, expected quantity, or discrepancy was injected into model results.
- Analyzed saved inspection `b038207d-7287-454a-a9c3-4adb9fdfe729` using 1 live Muse Spark 1.3 and 2 live SAM 3.1 requests. The saved evidence grounds two BLUE-BOX and one RED-CAN observations to three actual SAM regions. YELLOW-POUCH is `NOT_OBSERVED`, not confirmed absent; inspection remains `NEEDS_REVIEW`, shipping `HELD`.
- Ran the live read-tool agent using 4 Muse requests and 6 read tools. It returned `HUMAN_REVIEW_REQUIRED` and proposed `REQUEST_REINSPECTION` and `ESCALATE_TO_HUMAN`, both pending approval. No picking task, approval, execution, or verification was claimed. Private per-request ledger: `data/experiments/ledger.json`; 7/30 paid calls, estimated Standard-mode upper-bound cost $0.069571 using published token and SAM image prices; actual billed amount unavailable.
- Expanded the browser check to reopen saved Claude evidence, compare expected and observed quantities, show SAM regions and the pending review action. Labeled synthetic investigation and action cards so their text cannot be mistaken for physical validation. Older unlabeled cases remain separate; no additional paid secondary validation was warranted by the `NOT_OBSERVED` limitation.

## 2026-11-01 — Task 010 physical identity preparation

- Added strict local registration for owner-supplied `PHYSICAL_CAPTURE` product references and distinct before/after images. Registration requires explicit rights, visible SKU labels, owner-provided inventory, and a matching order; it creates no inspection or inferred result. Added a private physical dataset import location and validation-only CLI mode.
- Separated visual catalog candidates from confirmed SKU identity in Muse observations. A candidate can guide a SAM prompt, but deterministic grounding still requires an exact readable scene SKU and matching SAM region. Added an authenticated on-demand crop endpoint using only saved SAM geometry. Physical catalog references now require operator authorization.
- Added physical order selection in the existing Demo Workspace without serving physical photos as public demo assets. The inspection page displays reference provenance, visual candidate evidence, and guidance to capture readable labels. No owner physical images were present, so no new live Meta call or physical correction was performed.

## 2026-11-01 — Visual accuracy recovery

- Reviewed both prior live packing benchmark records before making new provider calls. Their comparisons contained no grounded SKU quantities; the raw Muse and SAM outputs had not been retained. Confirmed all four source scenes pass local quality checks and the isolated packing catalog does not reuse incompatible original references.
- Calibrated the blur warning with a controlled Gaussian blur of an existing packing image: measured edge variance fell from 402.0 to 36.2, while a mild brightness change remained acceptable. The warning threshold is now configurable. Added tests for the original, mild dimming, severe low light, blur, and obstruction without claiming occlusion detection.
- Added a per-run SAM request cap and benchmark option to skip agent calls, plus bounded parsed Muse observation retention for diagnostic traces. Tested a generic SAM fallback prompt in one live extra-product inspection, then reverted it after SAM returned zero boxes. That validation used 2 paid requests, no mocks: Muse located five objects but identified no exact SKUs; status remained NEEDS_REVIEW and shipping HELD. No repeat live attempt was made to seek a favorable result.

- 2026-10-30 — Task 002: added original synthetic catalog references and five labeled test scenes, source-image coordinates, official SAM mask overlays, conservative SKU/region association, deterministic comparison tables, actual processing events, retry-safe upload, and additive database migration. Verified 86 Python tests and 17 frontend tests in that task. Four additional live requests (ping, image analysis, two SAM streams) returned HTTP 200. The blue package had a supported region; red had no SAM corroboration, so the new inspection correctly remained NEEDS_REVIEW. No physical photograph or completed correction cycle was claimed.
- 2026-10-29 — Initial Meta integration foundation: SDK clients, diagnostics, streaming SAM parser, and unit tests. This first pass was blocked by configuration; subsequent work below resolved it.
- 2026-10-29 — Built the original React/TypeScript operations console and FastAPI/SQLite backend, with explicit synthetic product/order/inventory seed and no seeded perception results. Added image validation, deterministic evidence reconciliation, controlled read-tool AI investigation, server-authorized approval/execution, idempotency, audit events, and distinct-photo reinspection preserving evidence chains.
- 2026-10-29 — Corrected local dotenv loading and SAM parser/annotation defects; added security/concurrency/provider regression tests and local Docker builds. Three actual Meta requests succeeded: one ping, one Muse image request, and one SAM stream. Visual input was an original procedural synthetic fixture, not customer media or a warehouse benchmark; the real output remained NEEDS_REVIEW for a shortfall.

- 2026-10-30 ? Task 003: extended the original application with bounded Muse tool investigation, persisted decisions/events, deterministic four-action policy, approval/rejection, transactional picking records, shipping guards, and preserved-evidence reinspection. Verified 115 Python and 22 frontend tests. Eight actual Muse calls across two attempts: first decision rejected safely, retry produced a validated human-review proposal; authenticated API approval/execution of its reinspection request succeeded exactly once. Order remains HELD; no live picking or corrected-photo success fabricated. Browser and full live correction-cycle verification remain blocked.

## 2026-10-31 — Task 004 partial closed-loop verification

- Added a deterministic gate so a matching reinspection cannot verify an order while prior corrective actions remain unexecuted or a picking task remains open. Blocked cases retain the shipping hold and emit a persisted `VERIFICATION_BLOCKED` audit event.
- Added authenticated evidence-chain, comparison, verification-status, and verification-history read endpoints, plus an authenticated, idempotent physical picking-completion report that does not imply visual verification.
- Added a before/after inspection panel using saved images and reconciliation rows. Added regression tests for unapproved actions, evidence history, and picking-completion authorization.
- Local tests: 117 backend tests passed; 22 frontend tests passed; frontend production build passed. Backend health and frontend HTTP checks passed. No live Meta requests were made in this task; existing model responses in tests were mocked.
- Remaining gaps: no authoritative order-version snapshot or stale-order invalidation, and the full approved correction-to-verified live workflow has not been demonstrated.

## 2026-10-31 — Task 004 finalization

- Added a saved order version and requirements digest to each inspection. SQLite triggers advance the order version and hold shipping when required lines or relevant product SKUs change. Analysis, investigation, action approval/execution, and shipping reject stale evidence. Verification claims the current order version through a conditional update.
- Reinspection now rejects unexecuted agent actions and open picking tasks. A mocked integration test completes approval, execution, reported pick completion, new-photo analysis, and verification without dispatching the order. Added stale order and in-flight change regression tests.
- The before/after interface now shows persisted discrepancies, corrective actions, picking status, order revision state, and final decision. The verification status API returns those backend facts.
- Real Meta calls on original synthetic fixtures: three before/after runs, each with one Muse call and two SAM calls per image (18 visual requests); an additional isolated live agent investigation completed using Muse read tools. The final isolated synthetic workflow reached VERIFIED and left shipping NOT_READY. It did not involve a physical warehouse pick; the live agent recommended human review, reinspection, and escalation rather than a picking task.
- Final checks: 122 backend tests passed, 22 frontend tests passed, frontend build passed, local API health and frontend HTTP 200, SQLite integrity check OK, zero foreign-key violations. Browser interaction could not be checked because the in-app browser backend was unavailable.

## 2026-10-31 — Task 005 multi-scenario intelligence

- Added a server-validated CREATE_REMOVAL_TASK for supported EXCESS and EXTRA_PRODUCT discrepancies. It creates an approved, idempotent physical task without changing inventory. Task completion is separately operator reported, and new photo verification remains mandatory. Uncertain required items cannot create guessed picking tasks.
- Added a bounded get_verification_history read tool, removal task context in pending actions and audit history, and configurable agent timeout/tool-call limits. The agent may dynamically choose six database read tools; all proposed writes still pass deterministic policy.
- Updated the operations and before/after interfaces with detected issue types, current verification status, open picking/removal tasks, and operator task completion controls. Automatic hold proposals superseded by newer evidence are audited while the order stays held until verification.
- Mocked integration tests cover wrong product, multiple discrepancies, excess quantity, removal approval/concurrency/completion, and reinspection. Final local checks: 126 backend tests passed, 22 frontend tests passed, frontend production build passed; backend health/database and frontend HTTP 200; local SQLite integrity OK with zero foreign-key violations.
- One isolated live run used the rights-cleared synthetic extra-product image. Muse/SAM analysis returned UNCERTAIN, and four real Muse investigation calls completed five read tools. The agent chose HUMAN_REVIEW_REQUIRED and escalation; no removal was proposed or executed. This is safe uncertainty handling, not real-world physical validation.
- In a wrong-product fixture, the removal task records required products needing operator review without claiming that an unobserved product is absent. The operator must confirm any replacement; the subsequent photo is still the verification source.

## 2026-10-31 — Task 006 product experience and controlled demo

- Extended the existing dashboard with backend-calculated hold and human-review counts and linked attention rows from current inspection records. Kept the established navy interface and added responsive layouts.
- Added a Demo Workspace that lists only synthetic seed orders and backend-served original synthetic fixture images. Selecting an asset preloads the actual inspection upload form; saving, analysis, investigation, and approval still require their existing explicit actions and authorization. No simulated model events or inspection outcomes were added.
- Added frontend rendering/data-binding coverage and backend allowlist/dashboard tests. Verified 128 Python tests, 23 frontend tests, and production build. Chromium visited all seven major routes, loaded five synthetic scenes, opened a scene in inspection, and found no console errors or mobile horizontal overflow. Browser screenshots were kept in the local temp directory, outside the repository.
- This task made zero live Meta requests. The browser walkthrough stopped at the existing operator credential gate; it does not establish a live physical correction or complete paid inference.

## 2026-10-31 — Task 007 reproducible evaluation

- Added a five-case manifest for existing original synthetic scenes, a default-offline benchmark runner, safe live mode using temporary seeded databases, a results summarizer, authenticated read-only Chromium walkthrough, and manifest/metric tests. The manifest leaves unreadable SKU identity unknown and never labels fixture imagery as physical evidence.
- Two actual live benchmark cases used Muse Spark 1.3 and SAM 3.1: the correct-order scene reached VERIFIED with shipping NOT_READY; the additional-product scene remained NEEDS_REVIEW/HELD because green product identity was not sufficiently grounded. One real agent investigation returned HUMAN_REVIEW_REQUIRED; three read tools were called and completed. No corrective action was approved or executed. The inspection metadata records two Muse visual requests and five SAM requests; the earlier benchmark artifact did not retain the additional agent request count, so that count is not claimed.
- The two-sample combined results report zero false verifications and zero shipping safety violations, four supported product-quantity pairs agreeing with the procedural scene manifest, and one valid backend-accepted agent decision. These small synthetic samples do not measure real-world performance, region-level identification accuracy, physical correction, or live removal planning. One uncertain case is excluded from binary discrepancy precision/recall.
- The local authenticated browser read returned HTTP 200, all seven routes loaded, five synthetic assets appeared, and Chromium reported zero console errors or mobile overflow. The walkthrough was read-only and did not exercise approval or a complete inspection through the UI.

## 2026-10-31 — Task 007 continuation: security hardening and test regression fix

- Applied server-side authorization gate to `GET /api/inspections/{id}/image` and `GET /api/inspections/{id}/annotation` — uploaded evidence bytes now require a valid Bearer operator token (same `supervisor` dependency used on all mutation endpoints). Confirmed by `test_uploaded_evidence_requires_operator_authorization`.
- Identified 11 test regressions introduced by the security hardening: tests that relied on httpx TestClient replacing default headers when passing `headers={}` or `headers={"X-Role": ...}` (httpx 0.28 merges, not replaces). Fixed all 11 by:
  - Replacing empty-dict / role-only header dicts with explicit `{"Authorization": ""}` to simulate a missing/invalid token.
  - Restoring `self.auth` headers on TestClient instances recreated after SQLite schema-migration in the legacy-upgrade test.
  - Adding auth headers to standalone `TestClient` blocks in the additive-upgrade test that were not descended from the `setUp` client.
- Final verified test counts: **134 backend tests passed, 41 subtests passed, 0 failures**; **23 frontend tests passed**; frontend production build passed.
- Offline benchmark runner: 5 manifest cases validated, 0 live attempts, machine-readable JSON saved to `evaluation/results/`.
- No live Meta requests were made in this continuation task. Physical correction validation remains BLOCKED (no owner-provided before/after physical photo pair). Authorized browser authentication walkthrough remains partially blocked by the operator credential gate in CI, but authenticated API tests prove the security model is enforced.

## 2026-10-31 — Task 008 final release hardening & browser E2E validation

- Integrated authenticated image loading in the React console (`useProtectedImage` and `ProtectedEvidenceImage`) using authenticated `fetch` and safe, short-lived Blob URLs with automatic `URL.revokeObjectURL` cleanup. Protected images are never accessible via raw unauthenticated URLs and operator tokens are never exposed in image query parameters.
- Verified protected endpoints `GET /api/inspections/{id}/image` and `GET /api/inspections/{id}/annotation`: unauthenticated access is strictly rejected with 403 Forbidden; authenticated access with valid Bearer token returns 200 OK with `nosniff` and `no-store` headers.
- Built and validated Playwright Chromium Authenticated Browser E2E suite (`e2e/run_workflow_e2e.cjs` and `e2e/workflow.spec.ts`) executing complete workflow:
  1. Authorize local operator session via Settings form (token stored in sessionStorage).
  2. Demo Workspace presentation with 5 synthetic scenarios clearly marked TEST FIXTURE.
  3. Session persistence verified across browser reload.
  4. Order selection and authoritative manifest verification.
  5. Protected evidence loading verified via safe `blob:` URL without credential leakage.
  6. Display of real observations and deterministic discrepancy (Shortfall).
  7. Reinspection before-and-after comparison table listing catalog items and prior photo IDs.
  8. AI operations investigation inspection with persisted decision and real read-tool execution events.
  9. Proposed corrective actions review (reinspection / human review).
  10. Shipping safety enforcement: unverified/held orders remain strictly HELD.
- Regression testing:
  - Backend: 135 backend tests passed (0 failures).
  - Frontend: 23 vitest unit tests passed (0 failures).
  - Production build: TypeScript checking and Vite production bundling passed cleanly.
  - Authenticated Browser E2E: Playwright Chromium tests passed (2 of 2 spec tests passed; all 9 phases in E2E runner passed).
  - SQLite integrity check: `[('ok',)]`, foreign key check: 0 violations.
  - Offline benchmark runner: 5 procedural synthetic cases validated, output recorded.
- Zero live Meta requests made in Task 008. Physical correction validation remains BLOCKED without physical warehouse imagery.

## 2026-10-31 — Task 009 final hackathon submission, release packaging & demo preparation

- Audited repository for sensitive data: verified zero exposed API keys, operator tokens, passwords, or customer data in git history or tracked files; `.env` is gitignored; `.env.example` contains only empty template keys.
- Rewrote `README.md` into an extensive, developer/judge-grade manual covering the reality-gap problem, evidence-first solution, operational value, Meta Muse Spark 1.3 & SAM 3.1 architecture, model reasoning vs. deterministic policy matrix, agentic 7-stage lifecycle, technology versions, Windows/Linux/Docker installation instructions, exact test execution commands, benchmark summary, hackathon contributions, and honest limitations.
- Created `submission/SUBMISSION.md` with complete, form-ready copy for the Meta Global AI Developer Hackathon submission portal (Startup Track / Push the Frontier).
- Created `submission/DEMO_SCRIPT.md` (timed precisely to 180 seconds across 7 narrative segments) and `submission/DEMO_SHOT_LIST.md` (15 structured shots with timecodes, on-screen text, visual actions, and recording guidelines).
- Created `submission/demo-assets/` and `MANIFEST.md`: captured 5 clean high-resolution application screenshots via Chromium (zero credentials in URLs or inputs) and organized the five original rights-cleared procedural synthetic test scenes.
- Created `submission/FINAL_CHECKLIST.md` tracking all 14 submission criteria, clearly distinguishing COMPLETE items from PENDING owner actions (public repository toggle, video upload, license selection, platform form submission).
- Executed 1 live Meta API diagnostic ping to verify active status of credentials and `muse-spark-1.3` endpoint (HTTP 200, 2124ms latency). Verified 135 backend tests, 23 frontend unit tests, production build, Playwright browser E2E (2/2 spec tests, 9/9 phases), SQLite integrity, and offline benchmark runner with zero defects.


## 2026-11-01 — Final AI intelligence sprint (partial)

- Inspected the four existing synthetic packing images and preserved them unchanged. Created a separate `PACK-*` product catalog and two synthetic orders because the existing `PS-*` reference drawings represent different objects. Added a linked before/after manifest; original benchmark manifest and fixtures remain intact.
- Added local image-quality measurements and a conservative gate before paid inference. Low resolution, severe low light, or severe overexposure blocks analysis and holds shipping; uncertain glare or texture is a review warning. The four supplied packing images passed this local gate. Added quality display in Visual Inspection.
- Ran two live Meta inspections, one per packing-before scenario. Both returned `NEEDS_REVIEW` with five completed read-tool calls each. Records show 2 Muse, 2 SAM, and 8 agent model starts in total: 12 paid model requests. Inspection latencies were 19,253 ms and 18,743 ms. Both cases remained unverified; no shipping safety violation was observed. The after images received no live inference.
- Added reproducible JSON/CSV aggregation, adjusted the browser walkthrough to distinguish expected anonymous 403 responses from authenticated console errors, and updated the demo script/shot list to remove unsupported physical and certainty claims. Backend tests: 142 passed, 45 subtests; frontend tests: 23 passed; production build and Playwright (2/2) passed. Existing read-only browser E2E: nine phases passed. Physical correction, full approval/reinspection for the new pairs, and a final video remain unvalidated.
# 2026-11-01 — Task 011 physical capture preparation

- Added printable A4 labels and a private physical dataset import template with exact reference/before filenames. Template deliberately lacks rights confirmation, stock values, and captures; registration cannot proceed without owner evidence.
- Allowed registration before correction when `after_image` is empty; if supplied, before and after images must have different contents. No physical photographs were created or imported, and no live Meta requests were made in this task.
- Physical registration, SKU recognition, missing-product detection, approval, and before/after verification remain blocked by owner camera captures and actual inventory details.
# 2026-11-01 — Claude synthetic provenance correction

- Moved five owner-confirmed Claude AI generated PNGs unchanged from the physical capture staging folder to `evaluation/datasets/synthetic-claude-labeled/`; SHA-256 hashes were preserved. Added an explicit `SYNTHETIC` manifest with fictional inventory of 10 per SKU and a separate order.
- Added isolated synthetic registration, references, and a Demo Workspace scene entry. Registered four products with fictional test inventory of 10 each and uploaded the before image as an `UPLOADED` inspection; no model analysis was run. Physical registration rules were preserved. No new paid Meta inference was authorized; existing live records did not match the new before-image hash. Physical validation remains blocked.

## 2026-11-01 — Full operational UI/UX overhaul & live progress trackers

- Re-engineered the application interface to provide distinct visual identities and active operational progress for every workflow:
  - Added distinct color accents and micro-badges to all routes in navigation and headers: Overview (blue / `SYSTEM OVERVIEW`), Orders (teal / `AUTHORITATIVE MANIFESTS`), Visual Inspection (cyan / `PERCEPTION WORKSPACE`), AI Operations (purple / `HUMAN SUPERVISOR GATE`), Verification History (amber / `AUDITABLE LEDGER`), Demo Workspace (rose / `SANDBOX DEMO`), Settings (slate / `GATEWAYS & TOKENS`).
  - Implemented `ActiveInspectionProgress` with a 4-stage pipeline (Image Ingestion -> Muse Spark 1.3 -> SAM 3.1 -> Policy Reconciliation), elapsed timer, pulsing radar dot, and shimmering progress bar.
  - Implemented `ActiveInvestigationProgress` in AI Operations with a 4-stage tool pipeline (Order Manifest -> Meta Muse Spark -> Read-Tool Check -> Proposal Synthesizer), elapsed timer, and live stage status message.
  - Upgraded physical warehouse task display in `CorrectiveActionCard` into a dedicated `.warehouse-task-box` with status indicators (`OPEN` vs `COMPLETED`), clear operator reporting controls, and explicit notice that physical execution requires a new photo for verification.
  - Enhanced Verification Comparison to `verification-kpi-grid` with 4 KPI cards and figure caption badges.
  - Added interactive filtering chips to `Orders()` with real-time count badges ("All Orders", "Awaiting Inspection", "On Hold", "Verified Reality").
  - Added Photo ID custody column and `.photo-id-pill` badges to the Verification History ledger table.
  - Resolved legacy inspection `order_version` handling in `backend/app/api/routes.py` to prevent false conflict errors during reinspection.
- Tests & Verification:
  - Backend: 154/154 tests passed in 15.4s.
  - Frontend: 24/24 Vitest tests passed across 5 test suites.
  - Production build: `tsc -b && vite build` passed cleanly in 3.41s.
  - Backend and frontend daemons active and responding (HTTP 200).

## 2026-11-01 — Interactive result pop-up modal, discrepancy highlighting & semantic button system

- Created a unified `ResultModalProvider` and `ResultModalDialog` in `frontend/src/components/result-modal.tsx`:
  - Automatically pops up immediately upon inspection completion, AI investigation completion, or corrective action state changes.
  - Formulates a detailed, bilingual diagnosis ("تشخيص نتيجة الفحص") explaining the exact operational and visual reasons behind `NEEDS_REVIEW` (shortfall, unobserved products under strict policy, unconfirmed SKU labels) or `VERIFIED`.
  - Embeds interactive before/after or manifest comparison with row-level discrepancy highlighting (`row-highlight-error`).
  - Provides direct one-click action to launch AI investigation or authorize shipping directly from the pop-up.
- System-Wide Semantic Button Palette:
  - Expanded `frontend/src/components/ui/button.tsx` and `frontend/src/index.css` with 9 distinct, purpose-driven button variants:
    - `inspect` (Luminous Cyan gradient) for perception/inspection actions ("Inspect Now", "Start AI Inspection").
    - `warning` (Warm Amber tint & glow) for issue review ("Review Issues", "Show Diagnosis Pop-up").
    - `destructive` (Rose/Crimson gradient) for hold investigation and rejections ("Investigate Hold", "Reject", "Clear Token").
    - `success` (Emerald Green gradient) for deterministic verifications and approvals ("Verified Match", "Approve", "Authorize Shipping").
    - `agent` (Majestic Purple gradient) for AI operations ("Start AI Investigation").
    - `primary` (Electric Blue) for standard system mutations ("Execute Approved Action", "Save Inspection Image").
    - `outline`, `ghost`, and `subtle` for contextual low-emphasis actions.
  - Upgraded Orders table action column so every row features a distinct, color-coded, icon-backed button corresponding directly to its status.
- Resolved Visual Overlap:
  - Removed duplicate `nav-dot` from sidebar to prevent collision with `VISION` tag.
  - Removed heavy left border from `.page-heading` and added proper spacing to prevent line congestion.
  - Enabled smooth vertical scrolling on the sidebar.


