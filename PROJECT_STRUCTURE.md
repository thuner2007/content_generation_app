ai_ads_studio/
│
├── README.md
├── PROJECT_SPEC.md
├── ARCHITECTURE.md
├── DATA_MODEL.md
├── MVP_SCOPE.md
├── .env.example
├── requirements.txt
│
├── main.py
│
├── app_bootstrap.py
│
├── ui/
│   ├── __init__.py
│   ├── layout.py
│   ├── sidebar.py
│   ├── chat_view.py
│   ├── project_view.py
│   └── asset_view.py
│
├── core/
│   ├── __init__.py
│   ├── app_state.py
│   ├── prompt_builder.py
│   ├── cost_tracker.py
│   └── dispatcher.py
│
├── ai_providers/
│   ├── __init__.py
│   ├── base.py
│   ├── openai_provider.py
│   ├── claude_provider.py
│   ├── gemini_provider.py
│   └── router.py
│
├── storage/
│   ├── __init__.py
│   ├── db.py
│   ├── models.py
│   ├── project_repo.py
│   ├── chat_repo.py
│   └── asset_repo.py
│
├── services/
│   ├── __init__.py
│   ├── file_parser.py
│   ├── speech_to_text.py
│   └── cost_estimator.py
│
└── assets/
    └── .gitkeep