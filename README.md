# LLa - your personal assistant on Telegram

LLa chats with you on Telegram, reads your Google Calendar and Gmail, keeps a task list,
and sends you a plan every morning. Claude is the brain; this program is the hands.

What it can do now:
- Calendar: list events, create events (you approve each one with a button)
- Gmail: read your inbox and emails, save reply drafts (it can NOT send email)
- Tasks: add, list and complete to-dos
- Morning plan: sent automatically at MORNING_PLAN_TIME, or send /plan any time

Two ways to use it: Telegram (phone) and a web page (browser, with voice). Only your Telegram
account can talk to the bot, and the web page needs your password.

## Setup

### 1. Telegram bot
1. In Telegram, message @BotFather, send /newbot, and copy the bot token.
2. Message @userinfobot to get your numeric user id.

### 2. Anthropic API key
Create a key in the Claude Console (console.anthropic.com) and add credit to the account.

### 3. Google access (one time)
1. Go to console.cloud.google.com and create a project.
2. Enable the "Gmail API" and the "Google Calendar API".
3. Open "OAuth consent screen" (Google Auth platform), choose External, and add your own
   Gmail address as a test user.
4. Create credentials: "OAuth client ID", type "Desktop app". Download the JSON file and save it
   as `data/credentials.json`.
5. On your own computer (not the server):
       pip install -r requirements.txt
       python authorize_google.py
   Log in and allow access. This creates `data/token.json`.

Important: while the Google app is in "Testing" status, Google expires the login every 7 days.
To stop that, set the app's publishing status to "In production" on the consent screen. It is
only for your own account, so you can ignore Google's verification warning screen when you log in.

### 4. Settings
    cp .env.example .env
Edit `.env` with your keys, your Telegram id, your timezone and your plan time.

### 5. Deploy on the server
Copy this whole folder (including `data/token.json`) to your server, then:
    docker compose up -d --build
    docker compose logs -f

Message your bot on Telegram. Try: "What is on my calendar today?" or "Any important unread emails?"

## Web interface

Besides Telegram, LLa has a web page: chat window, today's calendar and open tasks, Approve/Cancel
buttons, a microphone button (speak to LLa) and an optional "Speak replies" switch.
Voice uses your browser's built-in speech tools, so it works best in Chrome, Edge or Safari.

It starts with `docker compose up` (the `web` service). Set `WEB_PASSWORD` in `.env` first.
For safety it listens only on the server itself (127.0.0.1:8000). Pick one way to open it:

Option A, quick and private (SSH tunnel from your computer):
    ssh -L 8000:127.0.0.1:8000 youruser@your-server
Then open http://localhost:8000 in your browser.

Option B, a real address with HTTPS (needs a domain pointing to your server). Install Caddy
and use this Caddyfile:
    lla.yourdomain.com {
        reverse_proxy 127.0.0.1:8000
    }
Then open https://lla.yourdomain.com. Voice input needs HTTPS (or localhost) to work.

The web chat and the Telegram chat are separate conversations, but they share the same
task list, calendar and email.

## Safety notes
- Email text comes from strangers, so LLa is told to treat it as untrusted. Keep email on
  read/draft only until you trust it.
- Calendar changes always need your Approve button.
- Never open the web port to the whole internet without HTTPS and a strong WEB_PASSWORD.
- Keep `.env` and `data/token.json` private. Anyone with them can use your accounts.

## Next steps
1. Sending email, with an Approve button like events.
2. Voice notes (speech-to-text in, text-to-speech out).
3. Evening check-in and weekly review.
4. More tools: notes, web search, your company's tools.
