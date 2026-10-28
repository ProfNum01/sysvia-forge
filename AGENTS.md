# AGENTS.md — SYSVIA ProofSight / Mandatory Codex Guardrails

## Goal and provenance
Build a NEW, standalone Meta Global AI Developer Hackathon 2026 Startup Track / Push the Frontier project during Oct 26–Nov 4, 2026. It is NOT an ERP, NOT a basic image analyzer, and must NOT import proprietary MK ERP, Tawajod/SuiteCRM, or unrelated code. Work must be original to this event; log actual changes in `docs/hackathon-contributions.md`. Public repository is mandatory for final submission, but never publish without owner approval. Work offline/local-first on Windows/WSL2/Docker; use synthetic or rights-cleared imagery only.

## Non-negotiable safety and truthfulness
- `META_API_KEY` is not the official environment variable here; use `MODEL_API_KEY` from environment. Never commit, print, or ask user to paste keys into chat. No implicit credentials or mock production state.
- Meta API endpoint: `https://api.meta.ai/v1`. Muse Spark `muse-spark-1.3`. SAM segmentation `sam-3.1` over Responses API. Verify with official docs; do not invent JSON response schema for SAM or blindly assume it is normal Chat Completions JSON.
- Model may recommend actions, NEVER execute arbitrary operations. All mutations are validated by deterministic server policy; supervisor approval on consequential actions; idempotency and audit required.
- `Not observed` does NOT prove `absent`. Never assert exact SKU or counts based on ambiguous photo; insufficient visual evidence => NEEDS_REVIEW or HELD, NEVER VERIFIED.
- Do not treat completed picking task as proof corrected. Require new photo, real re-inspection and evidence-backed reconciliation. Preserve both photo IDs.
- No fabricated successful tests, synthetic metrics presented as live performance, fake streamed agent thoughts, fake vendor capabilities, placeholder API calls presented as working, or pretend demo video.
- Never put secrets, customer data, copyrighted assets, or personal images into a public repository without rights and approval. Do not manipulate the user's existing business systems.

## Build discipline
Plan smallest working end-to-end flow: order -> image -> real perception -> deterministic reconciliation -> read-tool AI investigation -> proposal -> approved action -> new image -> reinspection. Prefer code over decorative UI. Small reviewable commits; docs, type checks and tests per phase. Stop and clearly report BLOCKED if credentials, input media, services or tests are unavailable. Do not over-engineer auth, hosting, robotics, multi-tenant, or video until core workflow proven.

## Status protocol
At end of every prompt report: (1) files modified, (2) commands executed, (3) ACTUAL test results, (4) live Meta requests made vs mocks, (5) security/quality defects, (6) PASS/BLOCKED/FAIL, (7) what owner must provide next. Never silently continue to next numbered prompt without owner review.
