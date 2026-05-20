# AI Ads & Content Generation Studio

Local-first AI desktop app for ecommerce and marketing teams. Multi-provider AI chat, ad copy generation, asset library, cost tracking — all stored in a local SQLite database.

## Launch (WSL → Windows)

Edit in WSL, run on Windows. One command syncs and starts the app:

```bash
bash run.sh
```

This copies your WSL source to `C:\projects\studio` and launches the Windows Python venv.

## First-time setup

**1. Create the Windows venv** (one-time, from WSL):
```bash
powershell.exe -Command "python -m venv C:\\projects\\studio\\.venv-win"
powershell.exe -Command "& 'C:\\projects\\studio\\.venv-win\\Scripts\\python.exe' -m pip install flet==0.28.3 openai anthropic google-generativeai python-dotenv"
```

**2. Add an API key** — open the app, go to **Settings**, paste an OpenAI / Claude / Gemini key.

**3. Local models (free)** — go to **Settings → Local Models**, click **Install Ollama** then download any model. No API key needed.

## Data

All data lives at `C:\Users\<you>\AppData\Local\ai_ads_studio\studio.db` (Windows) or `~/.ai_ads_studio/studio.db` (Linux/Mac).

Reset the DB:
```bash
# Windows PowerShell
Remove-Item "$env:LOCALAPPDATA\ai_ads_studio\studio.db"
```

## Project structure

```
main.py          Entry point
app_bootstrap.py DB init
storage/         SQLite CRUD
ai_providers/    OpenAI, Claude, Gemini, Ollama + router
core/            AppState, dispatcher, prompt builder, cost tracker
ui/              Flet views (sidebar, chat, panels, settings)
run.sh           WSL → Windows launch script
```

