"""
scripts/local_llm/ollama_client.py
Minimal Ollama API client for Qwen2.5:7b.
All local inference goes through this module.
"""
import os
import json
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")


class OllamaError(Exception):
    pass


def generate(prompt: str, model: str = None, temperature: float = 0.1,
             json_mode: bool = False, num_predict: int = 512) -> str:
    """
    Send a prompt to Ollama and return the response text.
    Uses low temperature by default — we want consistent structured output.
    Set json_mode=True to force Ollama to return valid JSON (recommended for
    scoring and parsing prompts).
    num_predict: max tokens to generate. 512 is fine for scoring; use 2048+
    for longer structured outputs like profile parsing.
    """
    model = model or OLLAMA_MODEL
    url   = f"{OLLAMA_BASE_URL}/api/generate"

    payload: dict = {
        "model":  model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
        },
    }

    if json_mode:
        payload["format"] = "json"

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data.get("response", "").strip()
    except urllib.error.URLError as e:
        raise OllamaError(
            f"Cannot reach Ollama at {OLLAMA_BASE_URL}. "
            f"Is it running? Error: {e}"
        ) from e


def is_available() -> bool:
    """Quick health check — returns True if Ollama is reachable."""
    try:
        url = f"{OLLAMA_BASE_URL}/api/tags"
        with urllib.request.urlopen(url, timeout=5):
            return True
    except Exception:
        return False


def model_is_pulled(model: str = None) -> bool:
    """Check if a specific model is already pulled."""
    model = model or OLLAMA_MODEL
    try:
        url = f"{OLLAMA_BASE_URL}/api/tags"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
            names = [m["name"] for m in data.get("models", [])]
            return any(model in name for name in names)
    except Exception:
        return False