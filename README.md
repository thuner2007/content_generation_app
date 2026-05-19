# AI Ads & Content Generation Studio

Local-first AI desktop app for ecommerce, SaaS, and marketing teams.

## Features
- **Multi-project workspace** — brand identity, chat history, and assets per project
- **AI Chat** — context-aware responses injecting your brand data automatically
- **Multi-provider** — OpenAI, Anthropic Claude, Google Gemini (plug-in architecture)
- **Generation tools** — Ad Copy, Image Prompts, Video Prompts, 10-Variation Bulk Generator
- **Asset Library** — save, tag, and search generated content
- **Cost Tracking** — per-request cost logging with provider breakdown
- **Local-first** — SQLite storage, no cloud, no subscriptions

## Quick Start

This app requires a Python virtual environment (Debian/Ubuntu block system-wide installs).

```bash
# 1. Install venv support if missing (one-time, requires sudo)
sudo apt install python3.12-venv

# 2. Create and activate the virtual environment
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python main.py
```

On first launch, go to **Settings** and add at least one API key.

## Development

**Standard run** (activate venv first):
```bash
source .venv/bin/activate
python main.py
```

**Flet dev mode** (hot-reload on file save — fastest for UI work):
```bash
source .venv/bin/activate
flet run main.py
```

**Reset the local database** (wipes all data — useful during dev):
```bash
rm ~/.ai_ads_studio/studio.db
```

The DB is recreated automatically on next launch.

## Data Location

All data is stored at `~/.ai_ads_studio/studio.db` (SQLite).

## Package as Windows .exe

```bash
pip install pyinstaller
pyinstaller build.spec
# Output: dist/AI Ads Studio/AI Ads Studio.exe
```

Or use Flet's built-in packaging:
```bash
flet pack main.py --name "AI Ads Studio"
```

## Project Structure

```
main.py                 # Entry point
app_bootstrap.py        # DB init
storage/                # SQLite CRUD (projects, chats, assets, keys)
ai_providers/           # OpenAI, Claude, Gemini + router
core/                   # AppState, dispatcher, prompt builder, cost tracker
services/               # File parser, cost estimator
ui/                     # Flet views: sidebar, chat, right panel, assets, settings
assets/                 # Static assets dir (icons, etc.)
build.spec              # PyInstaller packaging config
```

## Architecture

```
User → Flet UI → AppState → Dispatcher → AIProvider → AI API
                     ↕
                  SQLite DB (projects / chats / messages / assets / usage_logs)
```

## Extending

**Add a new AI provider:** Create `ai_providers/myprovider.py` extending `AIProvider`, 
register it in `ai_providers/router.py`. No other changes needed.

**Add a generation type:** Add an entry to `_GENERATION_TYPES` in `ui/chat_view.py` and
a system prompt in `core/prompt_builder.py`.
# content_generation_app
