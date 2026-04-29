# Email Watcher — Setup & Configuration

Polls your mailbox every 2 hours and sends a Telegram notification when an email matches any of your configured criteria (interviews, exams, schedule requests, etc.).

---

## Prerequisites

The main repo's Python dependencies are sufficient. Make sure they're installed:

```bash
pip install -r ../requirements.txt
```

If you haven't installed them yet, run the above from the `email_watcher/` directory.

---

## Step 1 — Configure Environment Variables

```bash
cp .env.example .env
```

Open `.env` and fill in the required values (details below).

---

## Step 2 — Telegram Bot Setup

You need a Telegram bot and your chat ID.

**Create a bot:**
1. Open Telegram and message `@BotFather`.
2. Send `/newbot` and follow the prompts (pick a name and username).
3. Copy the **bot token** (looks like `123456789:ABCdef...`) into `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456789:ABCdef...
   ```

**Get your chat ID:**
1. Start a conversation with your new bot (send it any message).
2. Message `@userinfobot` in Telegram — it replies with your numeric ID.
3. Copy that number into `.env`:
   ```
   TELEGRAM_CHAT_ID=123456789
   ```

---

## Step 3 — Email Provider Authentication

### Gmail

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project → enable the **Gmail API**.
3. Create **OAuth 2.0 credentials** (Desktop app type).
4. Download the JSON file and save it as `credentials/gmail_credentials.json` in the **repo root** (one level above `email_watcher/`).
5. Set in `.env`:
   ```
   EMAIL_PROVIDER=gmail
   GMAIL_CREDENTIALS_FILE=../credentials/gmail_credentials.json
   GMAIL_TOKEN_FILE=../credentials/gmail_token.json
   ```
   > If you already authenticated for the main EmailSorter app, you can reuse the existing token file — just point `GMAIL_TOKEN_FILE` to the same path.
6. **First-time login:** run the watcher once manually (see Step 5). A browser window will open for OAuth consent; after approval a token file is saved and future runs are silent.

### Outlook

1. Go to [Azure Portal](https://portal.azure.com/) → App registrations → New registration.
2. Under **Authentication**, add a **Mobile and desktop application** platform with redirect URI `https://login.microsoftonline.com/common/oauth2/nativeclient`.
3. Under **API permissions**, add `Mail.Read` (delegated).
4. Copy the **Application (client) ID** and set:
   ```
   EMAIL_PROVIDER=outlook
   OUTLOOK_CLIENT_ID=<your-client-id>
   OUTLOOK_TENANT_ID=common
   OUTLOOK_TOKEN_FILE=../credentials/outlook_token.json
   ```
5. **First-time login:** run the watcher once manually. It prints a device-flow URL and code; complete auth in a browser. The token is cached and reused silently afterward.

---

## Step 4 — Configure Alert Criteria

```bash
cp config.example.json config.json
```

Edit `config.json`. Each entry in `"criteria"` is an independent rule:

```json
{
  "criteria": [
    {
      "name": "Interview",
      "keywords": ["interview", "technical screen", "recruiter"],
      "fields": ["subject", "body", "sender"],
      "match_any": true
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Label shown in the Telegram notification |
| `keywords` | list of strings | Words/phrases to search for (case-insensitive) |
| `fields` | list | Which parts of the email to search: `subject`, `body`, `snippet`, `sender` |
| `match_any` | boolean | `true` = any keyword triggers; `false` = all keywords must be present |

Add as many criteria objects as you like.

---

## Step 5 — Test Run

From the `email_watcher/` directory:

```bash
python watcher.py
```

On first run it looks back `LOOKBACK_HOURS` (default: 2) hours. Subsequent runs automatically pick up from where the last run ended (stored in `state.json`).

Expected output:
```
[2026-04-28 10:00 UTC] Watching 'you@gmail.com' since 2026-04-28T08:00:00+00:00
  MATCH [Interview]: 'We'd love to schedule an interview' from recruiter@company.com
Done. Checked 47 emails, sent 1 alerts.
```

---

## Step 6 — Schedule as a Cron Job (every 2 hours)

### macOS / Linux (crontab)

Open the crontab editor:

```bash
crontab -e
```

Add this line (adjust paths to match your system):

```cron
0 */2 * * * /usr/bin/python3 /path/to/EmailSorter/email_watcher/watcher.py >> /path/to/EmailSorter/email_watcher/watcher.log 2>&1
```

To find your Python path:
```bash
which python3
```

**Tips:**
- `0 */2 * * *` runs at minute 0 of every even hour (00:00, 02:00, 04:00, …).
- The `>> watcher.log 2>&1` appends all output (stdout + stderr) to a log file.
- Cron runs with a minimal environment — use absolute paths for everything.

### macOS — LaunchAgent alternative (more reliable than cron)

Create `/Library/LaunchAgents/com.emailwatcher.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.emailwatcher</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/path/to/EmailSorter/email_watcher/watcher.py</string>
  </array>
  <key>StartInterval</key>
  <integer>7200</integer>
  <key>StandardOutPath</key>
  <string>/path/to/EmailSorter/email_watcher/watcher.log</string>
  <key>StandardErrorPath</key>
  <string>/path/to/EmailSorter/email_watcher/watcher.log</string>
  <key>RunAtLoad</key>
  <true/>
</dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.emailwatcher.plist
```

---

## File Reference

```
email_watcher/
├── watcher.py            ← main script (run this)
├── config.json           ← your alert criteria (create from config.example.json)
├── config.example.json   ← template with sample criteria
├── .env                  ← your secrets (create from .env.example)
├── .env.example          ← template for environment variables
├── state.json            ← auto-created; tracks last check time + notified IDs
├── watcher.log           ← auto-created by cron; tail -f to monitor
├── notifier.py           ← Telegram sender
└── email_providers/      ← read-only email adapters (Gmail + Outlook)
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must both be set` | Fill both values in `.env` |
| `Gmail credentials file not found` | Check `GMAIL_CREDENTIALS_FILE` path in `.env` |
| `OUTLOOK_CLIENT_ID is not set` | Set it in `.env` |
| Cron runs but no alerts appear | Check `watcher.log`; confirm cron can reach the internet |
| Same email alerted twice | Check `state.json` — `notified_ids` should contain the email ID |
| Want to reset and re-scan | Delete or clear `state.json` |
