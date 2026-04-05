"""
scripts/local_llm/ollama_client.py
Processing LLM client (LiteLLM / Ollama compatible).
All local inference goes through this module.
"""
import os
import json
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()

PROC_LLM_BASE_URL = os.environ.get("PROC_LLM_BASE_URL", "http://localhost:11434")
PROC_LLM_MODEL    = os.environ.get("PROC_LLM_MODEL", "qwen2.5:7b")
PROC_LLM_API_KEY  = os.environ.get("PROC_LLM_API_KEY", "")


class OllamaError(Exception):
    pass


def generate(prompt: str, model: str = None, temperature: float = 0.1,
             json_mode: bool = False, num_predict: int = 512) -> str:
    """
    Send a prompt to the processing LLM and return the response text.
    Uses low temperature by default — we want consistent structured output.
    Set json_mode=True to force the model to return valid JSON (recommended for
    scoring and parsing prompts).
    num_predict: max tokens to generate. 512 is fine for scoring; use 2048+
    for longer structured outputs like profile parsing.
    """
    model = model or PROC_LLM_MODEL
    url   = f"{PROC_LLM_BASE_URL}/api/generate"

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

    headers = {"Content-Type": "application/json"}
    if PROC_LLM_API_KEY:
        headers["Authorization"] = f"Bearer {PROC_LLM_API_KEY}"

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data.get("response", "").strip()
    except urllib.error.URLError as e:
        raise OllamaError(
            f"Cannot reach processing LLM at {PROC_LLM_BASE_URL}. "
            f"Is it running? Error: {e}"
        ) from e


def is_available() -> bool:
    """Quick health check — tries /health (LiteLLM) then /api/tags (Ollama)."""
    headers = {}
    if PROC_LLM_API_KEY:
        headers["Authorization"] = f"Bearer {PROC_LLM_API_KEY}"
    for path in ("/health", "/api/tags"):
        try:
            req = urllib.request.Request(f"{PROC_LLM_BASE_URL}{path}", headers=headers)
            with urllib.request.urlopen(req, timeout=5):
                return True
        except Exception:
            continue
    return False


def model_is_pulled(model: str = None) -> bool:
    """Check if a specific model is available."""
    model = model or PROC_LLM_MODEL
    try:
        url = f"{PROC_LLM_BASE_URL}/api/tags"
        headers = {}
        if PROC_LLM_API_KEY:
            headers["Authorization"] = f"Bearer {PROC_LLM_API_KEY}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            names = [m["name"] for m in data.get("models", [])]
            return any(model in name for name in names)
    except Exception:
        return False
