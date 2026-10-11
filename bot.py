"""Telegram front end for LLa. Run with: python bot.py"""

import asyncio
import datetime
import json
import logging
import os
import threading
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from zoneinfo import ZoneInfo

# Patch for python-telegram-bot on Python 3.12/3.14
_original_get_event_loop = asyncio.get_event_loop
def _patched_get_event_loop():
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop
asyncio.get_event_loop = _patched_get_event_loop

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from agent import run_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

PLAN_PROMPT = (
    "Make my plan for today. Check my calendar, my open tasks and my unread emails. "
    "Reply with: top 3 priorities, a time-blocked schedule around my meetings, and any emails "
    "that need a reply. Keep it short."
)

history: list = []                 # one user, one conversation
agent_lock = asyncio.Lock()        # one agent run at a time
pending: dict[str, asyncio.Future] = {}


async def send_long(bot, chat_id: int, text: str) -> None:
    for i in range(0, len(text), 4000):
        await bot.send_message(chat_id, text[i : i + 4000])


async def ask_approval(bot, chat_id: int, name: str, args: dict) -> bool:
    key = uuid.uuid4().hex[:8]
    future = asyncio.get_running_loop().create_future()
    pending[key] = future
    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Approve", callback_data=f"ok:{key}"),
          InlineKeyboardButton("Cancel", callback_data=f"no:{key}")]]
    )
    await bot.send_message(
        chat_id,
        f"LLa wants to run: {name}\n{json.dumps(args, indent=2, ensure_ascii=False)}",
        reply_markup=markup,
    )
    try:
        return await asyncio.wait_for(future, timeout=600)
    except asyncio.TimeoutError:
        return False
    finally:
        pending.pop(key, None)


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.from_user.id != config.ALLOWED_TELEGRAM_USER_ID:
        return
    action, key = query.data.split(":", 1)
    future = pending.get(key)
    if future is None or future.done():
        await query.edit_message_text(query.message.text + "\n\nExpired.")
        return
    future.set_result(action == "ok")
    await query.edit_message_text(query.message.text + ("\n\nApproved." if action == "ok" else "\n\nCancelled."))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id, "typing")
    approve = lambda name, args: ask_approval(context.bot, chat_id, name, args)
    async with agent_lock:
        try:
            reply = await run_agent(history, update.message.text, approve)
        except Exception:
            logging.exception("Agent error")
            reply = "Something went wrong. Check the server logs."
    await send_long(context.bot, chat_id, reply)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("LLa is online. Send /plan for today's plan, or just talk to me.")


async def cmd_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id, "typing")
    approve = lambda name, args: ask_approval(context.bot, chat_id, name, args)
    async with agent_lock:
        try:
            reply = await run_agent(history, PLAN_PROMPT, approve)
        except Exception:
            logging.exception("Agent error")
            reply = "Something went wrong. Check the server logs."
    await send_long(context.bot, chat_id, reply)


async def morning_plan(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = config.ALLOWED_TELEGRAM_USER_ID
    approve = lambda name, args: ask_approval(context.bot, chat_id, name, args)
    async with agent_lock:
        try:
            reply = await run_agent(history, PLAN_PROMPT, approve)
        except Exception:
            logging.exception("Morning plan error")
            reply = "I could not build your morning plan. Check the server logs."
    await send_long(context.bot, chat_id, reply)


# --- Simple health check server for Render.com (keeps the service alive) ---
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *args):
        pass  # silence logs

def _start_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    logging.info(f"Health check server on port {port}")
    server.serve_forever()


def main() -> None:
    config.check_required()

    # Write Google token from env var if present (for cloud deployment)
    if os.environ.get("GOOGLE_TOKEN_JSON") and not config.DATA_DIR.joinpath("token.json").exists():
        config.DATA_DIR.joinpath("token.json").write_text(os.environ["GOOGLE_TOKEN_JSON"])
        logging.info("Wrote token.json from GOOGLE_TOKEN_JSON env var.")

    # Fix for Python 3.12+ event loop issue
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Start health check server in background thread (for Render)
    threading.Thread(target=_start_health_server, daemon=True).start()

    # concurrent_updates is required: the Approve/Cancel button must be handled
    # while the agent is still waiting for it.
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).concurrent_updates(True).build()

    owner = filters.User(user_id=config.ALLOWED_TELEGRAM_USER_ID)  # everyone else is ignored
    app.add_handler(CommandHandler("start", cmd_start, filters=owner))
    app.add_handler(CommandHandler("plan", cmd_plan, filters=owner))
    app.add_handler(MessageHandler(owner & filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(on_button))

    hour, minute = (int(x) for x in config.MORNING_PLAN_TIME.split(":"))
    app.job_queue.run_daily(
        morning_plan, time=datetime.time(hour, minute, tzinfo=ZoneInfo(config.TIMEZONE))
    )

    logging.info("LLa is running.")
    app.run_polling()


if __name__ == "__main__":
    main()
