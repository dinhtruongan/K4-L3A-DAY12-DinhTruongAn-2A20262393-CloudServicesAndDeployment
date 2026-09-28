# Checkpoint verification record

Verification run on the user's Windows workstation with Python 3.13.15 and Docker Desktop Linux Engine 29.8.0 (Docker Compose v5.5.1). Test output and JUnit reports are under `evidence/`.

| Checkpoint | Expected | Latest actual result | Status/evidence |
|---|---|---|---|
| CP1 — config, health, logging | All checkpoint tests pass | 13 passed; one Starlette deprecation warning | PASS — `evidence/cp1.txt`, `evidence/cp1.xml` |
| CP2 — Docker | Static checks pass; build succeeds; image below 500 MB | 16 passed, including both Docker build/size tests. Image is 271 MB; configured user is `10001:10001`; container became healthy. | PASS — `evidence/cp2.txt`, `evidence/cp2.xml`, `evidence/docker-runtime.txt` |
| CP3 — API security | Auth, rate limit, monthly budget and request order pass | 22 passed | PASS (unit tests) — `evidence/cp3.txt`, `evidence/cp3.xml`; real-container smoke details in `evidence/docker-runtime.txt` |
| CP4 — scale and reliability | Shared Redis history, readiness, TTL/limit, and signal forwarding | 19 passed. Three separate containers returned history lengths 0, 2, 4; after restarting one agent, that agent continued at 6. During a Redis outage, `/health` returned 200 and `/ready` returned 503; readiness returned 200 after Redis restarted. | PASS (unit and Docker runtime) — `evidence/cp4.txt`, `evidence/cp4.xml`, `evidence/docker-runtime.txt` |
| CP5 — Render deployment | Public HTTPS URL, ready Redis, authenticated API and deployment details | Live at `https://day12-agent-7l68.onrender.com`; latest SHA `68e265a` is Live as deploy `dep-dat64qbbc2fs73bbcop0`. `/health` 200, `/ready` 200 with Redis, unauthenticated `/ask` 401. CP5: 8 passed, 5 skipped; the valid-key test was skipped because the Render-generated key was not exposed to local tests. | DEPLOYED, PUBLIC PATHS VERIFIED — `evidence/cp5-render.txt`, `evidence/cp5-render.xml`, `evidence/render-smoke.txt`, `DEPLOYMENT.md` |
| Root landing page | Opening the service root returns a Vietnamese HTML guide with API Docs, health/readiness links and API-key usage guidance; it never embeds the key | Added after user reported root URL returned `{"detail":"Not Found"}`; CP1 test validates root response | Pending deploy; CP1 now 14 passed |
| Bonus — GitHub Actions | Test/build gate, main-only Render hook and passing badge | Run `36424280082` passed test, Docker build and deploy hook for SHA `68e265a`; Render dashboard shows the same SHA as Live. The earlier run failed before tests due to transient PyPI metadata timeouts; increasing pip retries/timeouts fixed the rerun. | CI/BADGE/HOOK PASS — `evidence/bonus-final.txt`, `evidence/bonus-final.xml`, `evidence/workflow-36423898814.txt`, `evidence/github-actions-36424280082.json`, [successful run](https://github.com/dinhtruongan/K4-L3A-DAY12-DinhTruongAn-2A20262393-CloudServicesAndDeployment/actions/runs/36424280082) |

Local pre-deploy CI test command: **68 passed, 2 deselected**; the deselections were tests marked for Docker. The separate CP2 run used Docker and passed all 16 tests. The bonus test file passed all 13 checks after the repo became public and the badge started reporting passing.

`python grade.py` after the public deploy reported **95/100 including the 10-point bonus**: CP1 15/15, CP2 15/15, CP3 20/20, CP4 20/20, CP5 15/15, exercises 0/15, bonus 10/10. The grader skipped two Docker-marked CP2 tests in that aggregate run; the separate Docker-enabled CP2 run passed all 16. CP5's five skips include the authenticated request because `DEPLOY_API_KEY` was intentionally not exposed to the test process. The grader excludes skipped tests from its denominator, so its CP5 score does not prove that authenticated request succeeds.

## Runtime observations

- `docker compose ps` showed the agent healthy and Redis healthy.
- `/health` returned 200; `/ready` returned 200 with `redis: true`; `/ask` without an API key returned 401; authenticated requests returned 200 and shared history.
- A fresh test user received ten 200 responses followed by two 429 responses.
- The scaled three-agent test used an isolated Compose project and test Redis volume. Those temporary containers and that volume were removed after the test. The user's existing Redis container was left running; the test agent was stopped.
- Docker image metadata reported 271,011,307 bytes (about 271 MB), UID/GID `10001:10001`, and a `/health` healthcheck.
- Render created a Free Docker Web Service and Free Key Value instance in Oregon. The first commit `e8fd6b4` and the CI-gated commit `68e265a` both returned public HTTPS health and readiness responses; the latter was triggered through the GitHub secret-backed Render deploy hook.

## Limits

- The authenticated `/ask` success case has not been tested against the Render-generated secret; the public endpoint was verified to reject missing credentials with 401.
- The test Redis used for scale/outage/restart checks was isolated and removed after testing.
- CP3 rate and budget checks use separate read/write operations, so the tests do not establish strict enforcement under concurrent requests.
- Render Free Key Value can lose its data when it restarts; the tested persistence guarantee covers agent restarts while Redis stays up.
