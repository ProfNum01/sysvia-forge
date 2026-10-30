# Meta connection evidence — 2026-10-29

FastAPI + SQLAlchemy/SQLite backend, React/TypeScript/Vite frontend.
Installed locally: OpenAI SDK 3.40.0, meta-sam-parser 0.1.0, Pillow 13.0.0,
FastAPI 0.162.0, SQLAlchemy 2.1.6, python-dotenv 1.2.4.

Configuration: MODEL_API_KEY, optional META_API_BASE_URL, PROOFSIGHT_ENV_FILE,
OPERATOR_TOKEN, PROOFSIGHT_DATA_DIR, DATABASE_URL, CORS_ORIGINS.
Root .env is ignored and loaded without overriding process variables.
The owner-directed Codex configuration had a token-like literal in its env_key
field; its value was migrated privately to .env. The Codex file was preserved.

| Real request | Result | HTTP | Latency | Actual token usage |
| --- | --- | --- | --- | --- |
| Muse Spark ping, muse-spark-1.3 | PASS | 200 | 1,897 ms | 15 prompt + 145 completion = 160 |
| Muse Spark image, muse-spark-1.3 | PASS | 200 | 5,016 ms | 1,651 prompt + 975 completion = 2,626 |
| SAM Responses stream, sam-3.1 | PASS | 200 | 2,356 ms | Not captured |

**Three live requests total.** The two visual requests used an original locally
generated image explicitly labeled a synthetic fixture. These are real API
responses, not mocked perception, and provide no claim about warehouse accuracy.
Muse observed one red canister and one blue box. SAM returned one box and one mask;
the official parser decoded the mask and produced the annotated debug image.
Deterministic policy detected a shortfall against two required red canisters and
saved NEEDS_REVIEW. No action was automatically approved or executed.

Real read-tool investigation and the complete corrected-photo approval cycle have
not been run live. Their controlled tools, policy, authorization, idempotency, and
new-evidence rules are covered by isolated automated tests.

Validation: 48 backend/integration tests passed; 10 frontend tests passed; frontend
production build passed; Python dependency consistency check passed. Browser
verified dashboard data, all five orders, order details, and Settings. Browser
file selection was initially blocked by extension file access, then file selection
and preview passed after reconnection; actual image upload and analysis API succeeded.
Docker images built, and a container confirmed
both required secrets were present as environment variables, without printing
values or baking .env into its image. Both services run through Docker Compose.
Image paths are rebased against the active data directory at startup, preserving
the original image and SAM annotation when moving between Windows and Docker.
The mobile viewport was verified with populated database records and no document
horizontal overflow.

Files changed: frontend/, backend/, proofsight/meta_api.py, scripts/, tests/,
requirements.txt, .gitignore, .dockerignore, .env.example, docker-compose.yml,
README.md, and docs/. Local .env and data/ remain ignored.

Commands: pip install -r requirements.txt; python scripts/seed_demo.py;
python scripts/test_meta_api.py; python scripts/create_synthetic_image.py;
python -m unittest discover -s tests -v; python -m compileall -q backend proofsight scripts tests;
npm.cmd test; npm.cmd run build; npm.cmd audit; docker compose config --quiet;
docker compose build backend frontend; docker compose up --build -d; and a
container environment-presence check.

Security: secret values never printed or sent to the frontend; no secrets detected
in the repository's tracked history. .env, images, SQLite, dependency folders,
and generated files are ignored. All mutation endpoints require a server-validated
supervisor token. No commit, push, publication, or external business-system change.

Contracts verified: [Chat Completions](https://dev.meta.ai/docs/cookbook/quickstart-chat-completions),
[image input](https://dev.meta.ai/docs/image-understanding),
[structured output](https://dev.meta.ai/docs/structured-output),
[SAM](https://dev.meta.ai/docs/media-segmentation),
[parser](https://dev.meta.ai/docs/sam/client-libraries),
[read tools](https://dev.meta.ai/docs/tool-calling).


## Task 002 verification (2026-10-30)

Four additional real requests on original synthetic media: Muse ping HTTP 200,
2,344 ms, 140 tokens; Muse visual HTTP 200, 6,693 ms, 5,070 tokens;
SAM red HTTP 200, 1,626 ms, no matching region; SAM blue HTTP 200, 2,013 ms,
one actual box and mask. Total inspection latency: 12,275 ms.
The new inspection `e5852427-7de3-49fe-aa6e-8d00c05cd4d7` remained
NEEDS_REVIEW: blue observed 1, red quantity unknown. No red geometry or count
was invented. Both old and new photos remain. Seven cumulative Meta requests
through Task 002. Physical warehouse-image validation remains BLOCKED.

Added reference catalog, strict region grounding, actual mask overlays,
comparison table, real progress polling, upload idempotency, camera input,
and additive migrations. Camera hardware capture was not exercised.
Commands: `python scripts/create_inspection_fixtures.py`,
`python -m unittest discover -s tests -v` (86 passed), `npm.cmd test`
(17 passed), `npm.cmd run build`, `npm.cmd audit` (0 vulnerabilities),
`python -m pip check`, `python -m compileall -q backend proofsight scripts tests`,
`git diff --check`, `docker compose up --build -d`.
