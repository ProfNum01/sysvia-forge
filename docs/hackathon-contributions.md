# Hackathon contributions

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

