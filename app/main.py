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
    main { width: min(780px, 100%); padding: clamp(24px, 5vw, 44px); border: 1px solid #2c4057; border-radius: 24px; background: #142235ef; box-shadow: 0 24px 80px #0006; }
    .tag { display: inline-block; padding: 7px 11px; border: 1px solid #275e55; border-radius: 999px; color: #7ee7bd; background: #12352e; font-size: 13px; }
    h1 { margin: 22px 0 12px; font-size: clamp(34px, 7vw, 56px); letter-spacing: -.04em; line-height: 1.03; }
    p { color: #adbed2; font-size: 17px; line-height: 1.65; }
    nav { display: flex; flex-wrap: wrap; gap: 12px; margin: 28px 0; }
    a { padding: 12px 16px; border: 1px solid #39536f; border-radius: 11px; color: #dff3ff; text-decoration: none; background: #1b3047; }
    a.primary { border-color: #62d7b0; color: #09251e; background: #71e4bc; font-weight: 700; }
    a:hover { filter: brightness(1.12); }
    code { color: #9fe6cd; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
    .hint { padding: 14px 16px; border-left: 3px solid #71e4bc; border-radius: 4px 10px 10px 4px; background: #1a2c40; font-size: 14px; }
    .chat { margin-top: 28px; padding: 20px; border: 1px solid #2c4057; border-radius: 16px; background: #101c2b; }
    .chat h2 { margin: 0 0 6px; font-size: 20px; }
    .chat p { margin: 0 0 16px; font-size: 14px; }
    label { display: block; margin: 14px 0 7px; color: #c1d0e1; font-size: 13px; }
    input, textarea { width: 100%; padding: 12px 13px; border: 1px solid #39536f; border-radius: 10px; outline: none; color: #e5edf8; background: #142235; font: inherit; }
    input:focus, textarea:focus { border-color: #71e4bc; }
    textarea { min-height: 84px; resize: vertical; }
    .chat-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 12px; }
    button { padding: 12px 17px; border: 0; border-radius: 10px; color: #09251e; background: #71e4bc; font: inherit; font-weight: 700; cursor: pointer; }
    button:disabled { opacity: .6; cursor: wait; }
    #status { color: #a9bdd2; font-size: 13px; }
    #answer { display: none; white-space: pre-wrap; margin-top: 16px; padding: 15px; border-radius: 10px; color: #dce8f5; background: #1a2c40; line-height: 1.6; }
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
    <section class="chat" aria-labelledby="chat-title">
      <h2 id="chat-title">Trò chuyện với AI Agent</h2>
      <p>Agent demo chạy mock LLM offline. API key chỉ được giữ trong bộ nhớ trang này và gửi trực tiếp tới API của dịch vụ.</p>
      <form id="chat-form">
        <label for="api-key">API key</label>
        <input id="api-key" type="password" autocomplete="off" placeholder="Nhập AGENT_API_KEY của bạn" required>
        <label for="question">Câu hỏi</label>
        <textarea id="question" maxlength="2000" placeholder="Ví dụ: Hãy giới thiệu về bạn" required></textarea>
        <div class="chat-actions"><button id="send" type="submit">Gửi câu hỏi</button><span id="status" role="status">Key không được lưu trên trình duyệt.</span></div>
      </form>
      <div id="answer" aria-live="polite"></div>
    </section>
    <p class="hint">Bạn cũng có thể tích hợp trực tiếp qua <code>POST /ask</code>, header <code>X-API-Key</code> và JSON <code>{"question":"..."}</code>. API Docs ở nút phía trên.</p>
    <footer>Day 12 · Cloud Services and Deployment · FastAPI + Redis</footer>
  </main>
  <script>
    const form = document.querySelector('#chat-form');
    const send = document.querySelector('#send');
    const status = document.querySelector('#status');
    const answer = document.querySelector('#answer');
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      send.disabled = true;
      status.textContent = 'Đang xử lý…';
      answer.style.display = 'none';
      try {
        const response = await fetch('/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-API-Key': document.querySelector('#api-key').value, 'X-User-Id': 'web-demo' },
          body: JSON.stringify({ question: document.querySelector('#question').value })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
        answer.textContent = `${data.answer}\n\nLịch sử: ${data.history_length} tin nhắn · Chi phí mô phỏng: $${Number(data.cost_usd).toFixed(4)}`;
        answer.style.display = 'block';
        status.textContent = 'Đã nhận phản hồi.';
      } catch (error) {
        status.textContent = error.message === 'Invalid API key' ? 'API key không hợp lệ.' : error.message;
      } finally {
        send.disabled = false;
      }
    });
  </script>
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
