"""Agent service — điểm ráp nối của cả lab (CP1, CP3, CP4).

Luồng một request tới /ask:

    client ──► verify_api_key ──► rate_limiter ──► cost_guard
                                                       │
                              store.get_history ◄──────┘
                                       │
                                    ask_llm
                                       │
                              store.append × 2 ──► cost_guard.record ──► log_event
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from utils.mock_llm import ask_llm

from .auth import verify_api_key
from .config import get_settings
from .cost_guard import CostGuard
from .lifecycle import lifecycle
from .logging_utils import log_event
from .rate_limiter import RateLimiter
from .store import ConversationStore, get_redis_client

SERVICE_NAME = "day12-agent"
SERVICE_VERSION = "1.0.0"


# ─────────────────────────────────────────────────────────────
# Providers — CHO SẴN
# Tách ra thành hàm để test có thể thay bằng Redis giả qua
# app.dependency_overrides, và để kết nối Redis chỉ tạo khi thật sự cần.
# ─────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_store() -> ConversationStore:
    return ConversationStore(get_redis_client())


@lru_cache(maxsize=1)
def get_rate_limiter() -> RateLimiter:
    return RateLimiter(get_redis_client(), get_settings().rate_limit_per_minute)


@lru_cache(maxsize=1)
def get_cost_guard() -> CostGuard:
    return CostGuard(get_redis_client(), get_settings().monthly_budget_usd)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """CHO SẴN — chạy lúc app khởi động và lúc tắt."""
    get_settings()  # Validate required config before accepting requests.
    lifecycle.shutting_down = False
    lifecycle.install()
    log_event("service_started", service=SERVICE_NAME, version=SERVICE_VERSION)
    try:
        yield
    finally:
        log_event("service_stopped", service=SERVICE_NAME)


app = FastAPI(title="Day 12 Production Agent", version=SERVICE_VERSION, lifespan=lifespan)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index():
    """Small public landing page so opening the deployed URL is useful."""
    return """<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#101827">
  <title>Day 12 AI Agent API</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, sans-serif; }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 24px; color: #e5edf8; background: radial-gradient(ellipse at 15% 10%, #183b53 0, transparent 45%), #101827; }
    main { width: min(720px, 100%); padding: clamp(28px, 6vw, 52px); border: 1px solid #2c4057; border-radius: 24px; background: #142235eF; box-shadow: 0 24px 80px #0006; }
    .tag { display: inline-block; padding: 7px 11px; border: 1px solid #275e55; border-radius: 999px; color: #7ee7bd; background: #12352e; font-size: 13px; }
    h1 { margin: 22px 0 12px; font-size: clamp(34px, 7vw, 56px); letter-spacing: -.04em; line-height: 1.03; }
    p { color: #adbed2; font-size: 17px; line-height: 1.65; }
    nav { display: flex; flex-wrap: wrap; gap: 12px; margin: 28px 0; }
    a { padding: 12px 16px; border: 1px solid #39536f; border-radius: 11px; color: #dff3ff; text-decoration: none; background: #1b3047; }
    a.primary { border-color: #62d7b0; color: #09251e; background: #71e4bc; font-weight: 700; }
    a:hover { filter: brightness(1.12); }
    code { color: #9fe6cd; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
    .hint { padding: 14px 16px; border-left: 3px solid #71e4bc; border-radius: 4px 10px 10px 4px; background: #1a2c40; font-size: 14px; }
    footer { margin-top: 28px; color: #8296ad; font-size: 13px; }
  </style>
</head>
<body>
  <main>
    <span class="tag">● API đang hoạt động</span>
    <h1>Day 12<br>AI Agent API</h1>
    <p>Dịch vụ AI Agent demo chạy mock LLM offline, có xác thực API key, giới hạn tốc độ, kiểm soát chi phí và Redis dùng chung.</p>
    <nav>
      <a class="primary" href="/docs">Mở API Docs →</a>
      <a href="/health">Health</a>
      <a href="/ready">Readiness</a>
    </nav>
    <p class="hint">Để gọi <code>POST /ask</code>, gửi header <code>X-API-Key</code> cùng câu hỏi JSON. API key được giữ bí mật trong cấu hình dịch vụ; không chia sẻ hoặc dán key lên trang web.</p>
    <footer>Day 12 · Cloud Services and Deployment · FastAPI + Redis</footer>
  </main>
</body>
</html>"""


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


# ─────────────────────────────────────────────────────────────
# Health & readiness
# ─────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """Liveness probe — process còn sống không?

    TODO (CP1 + CP4):
      - Đang tắt dần (``lifecycle.shutting_down``) → trả
        ``JSONResponse(status_code=503, content={"status": "shutting_down"})``
      - Bình thường → ``{"status": "ok", "service": SERVICE_NAME,
        "version": SERVICE_VERSION}`` (mặc định FastAPI trả 200).

    Endpoint này phải **nhẹ**: không gọi Redis, không query DB. Nó chỉ trả
    lời câu hỏi "có cần restart container này không?". Nếu nó phụ thuộc
    Redis, Redis chết một nhịp là cả cụm container bị restart theo.
    """
    if lifecycle.shutting_down:
        return JSONResponse(status_code=503, content={"status": "shutting_down"})
    return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.get("/ready")
def ready(store: ConversationStore = Depends(get_store)):
    """Readiness probe — đã sẵn sàng nhận traffic chưa?

    TODO (CP4):
      - Đang tắt dần → 503 ``{"status": "shutting_down"}``
      - ``store.ping()`` False → 503 ``{"status": "not ready", "redis": False}``
      - Ngược lại → ``{"status": "ready", "redis": True}``

    Khác /health ở chỗ: endpoint này ĐƯỢC PHÉP kiểm tra dependency. Load
    balancer dùng nó để quyết định có đẩy request vào instance này không.
    """
    if lifecycle.shutting_down:
        return JSONResponse(status_code=503, content={"status": "shutting_down"})
    if not store.ping():
        return JSONResponse(status_code=503, content={"status": "not ready", "redis": False})
    return {"status": "ready", "redis": True}


# ─────────────────────────────────────────────────────────────
# Endpoint chính
# ─────────────────────────────────────────────────────────────
@app.post("/ask")
def ask(
    payload: AskRequest,
    user_id: str = Depends(verify_api_key),
    store: ConversationStore = Depends(get_store),
    limiter: RateLimiter = Depends(get_rate_limiter),
    guard: CostGuard = Depends(get_cost_guard),
):
    """Hỏi agent một câu.

    TODO (CP3 + CP4) — làm ĐÚNG THỨ TỰ sau:
      1. ``limiter.check(user_id)``           → 429 nếu gọi quá nhanh
      2. ``guard.check(user_id)``             → 402 nếu hết ngân sách
      3. ``history = store.get_history(user_id)``
      4. ``result = ask_llm(payload.question, history)``
      5. ``store.append(user_id, "user", payload.question)`` và
         ``store.append(user_id, "assistant", result["answer"])``
      6. ``guard.record(user_id, result["cost_usd"])``
      7. ``log_event("ask_completed", user_id=user_id,
         tokens_in=result["tokens_in"], tokens_out=result["tokens_out"],
         cost_usd=result["cost_usd"])``
      8. trả về::

            {
                "answer": result["answer"],
                "user_id": user_id,
                "history_length": len(history),
                "cost_usd": result["cost_usd"],
                "tokens": {"in": result["tokens_in"], "out": result["tokens_out"]},
            }

    Vì sao check trước rồi mới gọi LLM? Vì tiền mất ở bước gọi LLM. Chặn sau
    khi đã gọi thì bạn vừa trả tiền vừa trả lỗi.

    ``user_id`` do ``verify_api_key`` trả về, nên request không có API key
    hợp lệ sẽ dừng ở 401 trước khi chạm vào bất cứ dòng nào ở đây.
    """
    limiter.check(user_id)
    guard.check(user_id)
    history = store.get_history(user_id)
    result = ask_llm(payload.question, history)
    store.append(user_id, "user", payload.question)
    store.append(user_id, "assistant", result["answer"])
    guard.record(user_id, result["cost_usd"])
    log_event("ask_completed", user_id=user_id, tokens_in=result["tokens_in"], tokens_out=result["tokens_out"], cost_usd=result["cost_usd"])
    return {"answer": result["answer"], "user_id": user_id, "history_length": len(history), "cost_usd": result["cost_usd"], "tokens": {"in": result["tokens_in"], "out": result["tokens_out"]}}


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
