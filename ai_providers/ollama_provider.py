"""Ollama local model provider — zero cost, runs on your machine.

Requires Ollama to be installed and running: https://ollama.com/download
"""
import json
import os
import platform
import shutil
import subprocess
import tempfile
import time
import urllib.request
import urllib.error
from typing import Optional

from ai_providers.base import AIProvider, GenerationResult

OLLAMA_BASE = "http://localhost:11434"

_INSTALL_URLS = {
    "Windows": "https://ollama.com/download/OllamaSetup.exe",
    "Darwin":  "https://ollama.com/download/Ollama-darwin.zip",
    "Linux":   "https://ollama.com/install.sh",
}


def _system() -> str:
    return platform.system()  # "Windows", "Darwin", "Linux"


def is_ollama_installed() -> bool:
    """Return True if the ollama binary/executable is found on PATH."""
    return shutil.which("ollama") is not None


def install_ollama(on_status=None) -> bool:
    """Download and silently install Ollama. Returns True on success.
    on_status(msg) is called with progress strings."""
    sys = _system()
    url = _INSTALL_URLS.get(sys)
    if not url:
        if on_status:
            on_status(f"Unsupported platform: {sys}")
        return False

    try:
        if on_status:
            on_status("Downloading Ollama installer…")

        if sys == "Windows":
            tmp = os.path.join(tempfile.gettempdir(), "OllamaSetup.exe")
            urllib.request.urlretrieve(url, tmp)
            if on_status:
                on_status("Running installer (silent)…")
            # /S = silent NSIS install; waits for completion
            subprocess.run([tmp, "/S"], check=True, timeout=300)
            if on_status:
                on_status("Installed! Starting Ollama…")
            # Ollama on Windows auto-starts after install, but give it a moment
            time.sleep(3)
            return True

        elif sys == "Darwin":
            tmp = os.path.join(tempfile.gettempdir(), "Ollama-darwin.zip")
            urllib.request.urlretrieve(url, tmp)
            if on_status:
                on_status("Extracting…")
            apps = "/Applications"
            subprocess.run(["unzip", "-o", tmp, "-d", apps], check=True, timeout=60)
            if on_status:
                on_status("Installed! Starting Ollama…")
            subprocess.Popen(["open", f"{apps}/Ollama.app"])
            time.sleep(3)
            return True

        else:  # Linux
            tmp = os.path.join(tempfile.gettempdir(), "ollama_install.sh")
            urllib.request.urlretrieve(url, tmp)
            os.chmod(tmp, 0o755)
            if on_status:
                on_status("Running install script (may need sudo)…")
            subprocess.run(["bash", tmp], check=True, timeout=300)
            if on_status:
                on_status("Installed! Starting Ollama…")
            return start_ollama(on_status=None)

    except Exception as exc:
        if on_status:
            on_status(f"Install failed: {exc}")
        return False


def start_ollama(on_status=None) -> bool:
    """Start the Ollama server in the background. Returns True if it becomes reachable."""
    sys = _system()
    try:
        if sys == "Windows":
            # On Windows, launch the Ollama app (it auto-starts serve)
            ollama_exe = shutil.which("ollama")
            if not ollama_exe:
                # Try default install path
                candidate = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
                if os.path.isfile(candidate):
                    ollama_exe = candidate
            if ollama_exe:
                subprocess.Popen(
                    [ollama_exe, "serve"],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        elif sys == "Darwin":
            subprocess.Popen(["open", "-a", "Ollama"])
        else:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass

    # Wait up to 10 s for the server to come up
    if on_status:
        on_status("Waiting for Ollama to start…")
    for _ in range(20):
        time.sleep(0.5)
        if is_ollama_running():
            return True
    return False


def _ollama_request(path: str, payload: Optional[dict] = None, timeout: int = 120) -> dict:
    """Make a JSON request to the local Ollama server."""
    url = f"{OLLAMA_BASE}{path}"
    if payload is not None:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def is_ollama_running() -> bool:
    """Return True if the Ollama daemon is reachable."""
    try:
        _ollama_request("/api/tags", timeout=3)
        return True
    except Exception:
        return False


def list_installed_models() -> list[dict]:
    """Return list of installed model dicts with name/size keys."""
    try:
        data = _ollama_request("/api/tags", timeout=5)
        return data.get("models", [])
    except Exception:
        return []


def pull_model(model_name: str, on_progress=None) -> bool:
    """Pull (download) a model. on_progress(status_str) called during download.
    Returns True on success."""
    url = f"{OLLAMA_BASE}/api/pull"
    payload = json.dumps({"name": model_name, "stream": True}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            while True:
                line = resp.readline()
                if not line:
                    break
                try:
                    obj = json.loads(line.decode())
                    status = obj.get("status", "")
                    completed = obj.get("completed", 0)
                    total = obj.get("total", 0)
                    if on_progress:
                        if total:
                            pct = int(completed / total * 100)
                            on_progress(f"{status} — {pct}%")
                        else:
                            on_progress(status)
                    if obj.get("error"):
                        return False
                except json.JSONDecodeError:
                    pass
        return True
    except Exception:
        return False


def delete_model(model_name: str) -> bool:
    """Delete a locally installed model."""
    url = f"{OLLAMA_BASE}/api/delete"
    payload = json.dumps({"name": model_name}).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(req, timeout=15):
            return True
    except Exception:
        return False


class OllamaProvider(AIProvider):
    """Flet app provider wrapping the local Ollama server."""

    provider_name = "ollama"

    def is_configured(self) -> bool:
        """Configured when Ollama is running AND at least one model is installed."""
        return is_ollama_running() and bool(list_installed_models())

    def list_models(self) -> list[str]:
        return [m["name"] for m in list_installed_models()]

    def generate(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: int = 2048,
    ) -> GenerationResult:
        if not is_ollama_running():
            return GenerationResult(
                content="",
                model=model or "",
                provider=self.provider_name,
                error=(
                    "Ollama is not running. Start it with: ollama serve\n"
                    "Download from https://ollama.com/download"
                ),
            )
        available = self.list_models()
        if not available:
            return GenerationResult(
                content="",
                model=model or "",
                provider=self.provider_name,
                error="No local models installed. Go to Settings → Local Models to download one.",
            )
        model = model or available[0]
        try:
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"num_predict": max_tokens},
            }
            data = _ollama_request("/api/chat", payload, timeout=180)
            content = data.get("message", {}).get("content", "")
            usage = data.get("eval_count", 0)
            prompt_eval = data.get("prompt_eval_count", 0)
            return GenerationResult(
                content=content,
                model=model,
                provider=self.provider_name,
                tokens_input=prompt_eval,
                tokens_output=usage,
                cost=0.0,
            )
        except Exception as exc:
            return GenerationResult(
                content="",
                model=model,
                provider=self.provider_name,
                error=f"Ollama error: {exc}",
            )

    def estimate_cost(self, prompt_tokens: int, model: Optional[str] = None) -> float:
        return 0.0  # Always free
