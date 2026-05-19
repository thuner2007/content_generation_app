# Database Schema

## projects
- id TEXT
- name TEXT
- slogan TEXT
- brand_colors TEXT
- fonts TEXT
- created_at DATETIME

---

## chats
- id TEXT
- project_id TEXT
- created_at DATETIME

---

## messages
- id TEXT
- chat_id TEXT
- role TEXT (user/assistant)
- content TEXT
- created_at DATETIME

---

## assets
- id TEXT
- project_id TEXT
- type TEXT (image/text/prompt)
- content TEXT
- tags TEXT
- created_at DATETIME

---

## api_keys
- provider TEXT
- key TEXT

---

## usage_logs
- id TEXT
- provider TEXT
- cost FLOAT
- tokens INT
- created_at DATETIME