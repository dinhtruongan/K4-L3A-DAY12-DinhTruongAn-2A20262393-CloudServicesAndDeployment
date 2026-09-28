# Checkpoint verification record

Verification run on the user's Windows workstation with Python 3.13.15 and Docker Desktop Linux Engine 29.8.0 (Docker Compose v5.5.1). Test output and JUnit reports are under `evidence/`.

| Checkpoint | Expected | Latest actual result | Status/evidence |
|---|---|---|---|
| CP1 — config, health, logging | All checkpoint tests pass | 13 passed; one Starlette deprecation warning | PASS — `evidence/cp1.txt`, `evidence/cp1.xml` |
| CP2 — Docker | Static checks pass; build succeeds; image below 500 MB | 16 passed, including both Docker build/size tests. Image is 271 MB; configured user is `10001:10001`; container became healthy. | PASS — `evidence/cp2.txt`, `evidence/cp2.xml`, `evidence/docker-runtime.txt` |
| CP3 — API security | Auth, rate limit, monthly budget and request order pass | 22 passed | PASS (unit tests) — `evidence/cp3.txt`, `evidence/cp3.xml`; real-container smoke details in `evidence/docker-runtime.txt` |
| CP4 — scale and reliability | Shared Redis history, readiness, TTL/limit, and signal forwarding | 19 passed. Three separate containers returned history lengths 0, 2, 4; after restarting one agent, that agent continued at 6. During a Redis outage, `/health` returned 200 and `/ready` returned 503; readiness returned 200 after Redis restarted. | PASS (unit and Docker runtime) — `evidence/cp4.txt`, `evidence/cp4.xml`, `evidence/docker-runtime.txt` |
| CP5 — Render deployment | Public HTTPS URL, ready Redis, auth and deployment details | Not deployed; URL and deployment details are still placeholders. Tests: 4 failed, 5 errors, 4 skipped because no URL/configuration is available. | NOT COMPLETE — latest console output in the conversation; see `DEPLOYMENT.md` |
| Bonus — GitHub Actions | 13 tests pass and public badge reports passing | 12 passed, 1 failed: badge endpoint returns HTTP 404 because no successful workflow run is available yet. | PARTIAL — `evidence/bonus.txt`, `evidence/bonus.xml` |

`python grade.py --no-bonus` most recently reported 70/100 before Docker became available. Recalculate after final deployment and exercises. The Docker skips from that earlier run are superseded by the latest CP2 run of 16/16.

## Runtime observations

- `docker compose ps` showed the agent healthy and Redis healthy.
- `/health` returned 200; `/ready` returned 200 with `redis: true`; `/ask` without an API key returned 401; authenticated requests returned 200 and shared history.
- A fresh test user received ten 200 responses followed by two 429 responses.
- The scaled three-agent test used an isolated Compose project and test Redis volume. Those temporary containers and that volume were removed after the test. The user's existing Redis container was left running; the test agent was stopped.
- Docker image metadata reported 271,011,307 bytes (about 271 MB), UID/GID `10001:10001`, and a `/health` healthcheck.

## Limits

- Local Docker integration proves this workstation can build and run the stack; it does not prove that a public Render deployment is live.
- The test Redis used for scale/outage/restart checks was isolated and removed after testing.
- CP3 rate and budget checks use separate read/write operations, so the tests do not establish strict enforcement under concurrent requests.
- No cloud URL, live CI passing badge, or deployment incident is claimed.
