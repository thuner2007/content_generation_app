# AI Ads Studio - Product Spec

## Goal
A local Windows desktop app for generating ads, managing brand projects, and using multiple AI providers.

---

## Core Features

### Projects
- Create/edit/delete projects
- Each project stores:
  - brand colors
  - fonts
  - slogan
  - logo reference
  - documents

---

### AI Chat
- Chat per project
- Persistent history
- Context-aware responses using project data

---

### Generation Tools
- ad copy generator
- image prompt generator
- bulk ad generator (10+ outputs)

---

### AI Providers
- OpenAI
- Claude
- Gemini
- pluggable system

---

## MVP
- projects
- chat
- 1 provider (OpenAI)
- SQLite storage

---

## Not MVP
- video generation
- speech-to-text
- cost optimizer