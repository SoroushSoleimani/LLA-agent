"""Web interface for LLa. Run with: uvicorn web:app --host 0.0.0.0 --port 8000"""

import asyncio
import hmac
import logging
import secrets
import uuid
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

import config
import tools_google
import tools_tasks
from agent import run_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

if not config.WEB_PASSWORD:
    raise RuntimeError("Set WEB_PASSWORD in your .env file before starting the web interface.")

COOKIE = "lla_session"
INDEX_HTML = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")

LOGIN_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LLa</title>
<style>
:root{color-scheme:light dark;--bg:#faf9f7;--card:#fff;--text:#1f1e1d;--muted:#6b6a67;--line:#e4e2dd;--accent:#534ab7}
@media(prefers-color-scheme:dark){:root{--bg:#1c1b1a;--card:#262524;--text:#f1efe9;--muted:#a09e98;--line:#3a3836;--accent:#9b94ee}}
body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--text);font:16px/1.5 system-ui,sans-serif}
form{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:28px;width:min(320px,86vw);display:grid;gap:14px}
h1{margin:0;font-size:22px;font-weight:500}
p{margin:0;color:var(--muted);font-size:14px}
input,button{font:inherit;padding:10px 12px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--text)}
button{background:var(--accent);color:#fff;border-color:var(--accent);cursor:pointer}
.err{color:#c0392b;font-size:14px}
</style></head><body>
<form method="post" action="/login">
<h1>LLa</h1><p>Your personal assistant</p>
__ERROR__
<input type="password" name="password" placeholder="Password" autofocus required>
<button type="submit">Sign in</button>
</form></body></html>"""

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

sessions: set[str] = set()
history: list = []
agent_lock = asyncio.Lock()


def is_authed(token: str | None) -> bool:
    return bool(token) and token in sessions


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if not is_authed(request.cookies.get(COOKIE)):
        return HTMLResponse(LOGIN_HTML.replace("__ERROR__", ""))
    return HTMLResponse(INDEX_HTML)


@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    if not hmac.compare_digest(password.encode(), config.WEB_PASSWORD.encode()):
        await asyncio.sleep(1)  # slow down guessing
        return HTMLResponse(
            LOGIN_HTML.replace("__ERROR__", '<div class="err">Wrong password.</div>'), status_code=401
        )
    token = secrets.token_urlsafe(32)
    sessions.add(token)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        samesite="strict",
        secure=request.headers.get("x-forwarded-proto") == "https",
        max_age=60 * 60 * 24 * 30,
    )
    return response


@app.post("/logout")
async def logout(request: Request):
    sessions.discard(request.cookies.get(COOKIE, ""))
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(COOKIE)
    return response


@app.get("/api/today")
async def today(request: Request):
    if not is_authed(request.cookies.get(COOKIE)):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    async def safe(fn, *args):
        try:
            return await asyncio.to_thread(fn, *args)
        except Exception as e:
            return f"Could not load: {e}"

    return {
        "events": await safe(tools_google.list_events, 1),
        "tasks": await safe(tools_tasks.list_tasks),
    }


@app.websocket("/ws")
async def chat_socket(ws: WebSocket):
    origin = ws.headers.get("origin")
    if not is_authed(ws.cookies.get(COOKIE)) or (
        origin and urlparse(origin).netloc != ws.headers.get("host")
    ):
        await ws.close(code=1008)
        return
    await ws.accept()

    approvals: dict[str, asyncio.Future] = {}
    tasks: set[asyncio.Task] = set()

    async def approve(name: str, args: dict) -> bool:
        key = uuid.uuid4().hex[:8]
        future = asyncio.get_running_loop().create_future()
        approvals[key] = future
        await ws.send_json({"type": "approval", "id": key, "name": name, "args": args})
        try:
            return await asyncio.wait_for(future, timeout=600)
        except asyncio.TimeoutError:
            return False
        finally:
            approvals.pop(key, None)

    async def handle(text: str) -> None:
        await ws.send_json({"type": "status", "text": "LLa is thinking..."})
        async with agent_lock:
            try:
                reply = await run_agent(history, text, approve)
            except Exception:
                logging.exception("Agent error")
                reply = "Something went wrong. Check the server logs."
        await ws.send_json({"type": "reply", "text": reply})

    try:
        while True:
            data = await ws.receive_json()
            if data.get("type") == "message" and str(data.get("text", "")).strip():
                task = asyncio.create_task(handle(str(data["text"]).strip()))
                tasks.add(task)
                task.add_done_callback(tasks.discard)
            elif data.get("type") == "approval_reply":
                future = approvals.get(data.get("id"))
                if future and not future.done():
                    future.set_result(bool(data.get("approved")))
    except WebSocketDisconnect:
        pass
    finally:
        for future in approvals.values():
            if not future.done():
                future.set_result(False)
        for task in tasks:
            task.cancel()
