# Architecture

## Frontend (Flet)
- sidebar navigation
- chat screen
- project screen
- asset library

---

## Core Layer
- app_state.py → global state
- prompt_builder.py → inject brand context
- dispatcher.py → routes AI calls
- cost_tracker.py → usage tracking

---

## AI Providers
Interface:
- generate(prompt)
- estimate_cost()
- model_info()

All providers must implement base class.

---

## Storage
SQLite database:
- projects
- chats
- messages
- assets
- usage logs

---

## Rules
- No backend server
- Fully local app
- API calls only from provider layer