"""Run this ONCE on your own computer (it opens a browser) to log in to Google.

    python authorize_google.py

It needs data/credentials.json (OAuth client, type "Desktop app") and creates
data/token.json. Then copy data/token.json to the same folder on your server.
"""

from google_auth_oauthlib.flow import InstalledAppFlow

from google_auth import CLIENT_SECRET_FILE, SCOPES, TOKEN_FILE

if not CLIENT_SECRET_FILE.exists():
    raise SystemExit(f"Put your Google OAuth client file at {CLIENT_SECRET_FILE} first.")

flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
creds = flow.run_local_server(port=0)
TOKEN_FILE.write_text(creds.to_json())
print(f"Done. Saved {TOKEN_FILE}. Copy it to your server's data/ folder.")
