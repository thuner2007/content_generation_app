"""
PyInstaller spec for packaging AI Ads Studio as a Windows .exe

Usage:
    pip install pyinstaller
    pyinstaller build.spec

Output: dist/AI Ads Studio/AI Ads Studio.exe
"""
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all flet assets
datas = []
datas += collect_data_files("flet")
datas += [("assets", "assets")]

hiddenimports = (
    collect_submodules("flet")
    + collect_submodules("openai")
    + collect_submodules("anthropic")
    + collect_submodules("google.generativeai")
    + [
        "storage.db",
        "storage.models",
        "storage.project_repo",
        "storage.chat_repo",
        "storage.asset_repo",
        "core.app_state",
        "core.dispatcher",
        "core.prompt_builder",
        "core.cost_tracker",
        "ai_providers.openai_provider",
        "ai_providers.claude_provider",
        "ai_providers.gemini_provider",
        "ai_providers.router",
        "services.file_parser",
        "services.cost_estimator",
        "ui.layout",
        "ui.sidebar",
        "ui.chat_view",
        "ui.project_view",
        "ui.asset_view",
        "ui.settings_view",
        "ui.theme",
    ]
)

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AI Ads Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,            # Hide console window on Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico",   # Add your icon here
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AI Ads Studio",
)
