"""
scripts/local_llm/ollama_client.py
Processing LLM client — OpenAI-compatible API (LiteLLM / Ollama).
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


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if PROC_LLM_API_KEY:
        h["Authorization"] = f"Bearer {PROC_LLM_API_KEY}"
    return h


def generate(prompt: str, model: str = None, temperature: float = 0.1,
             json_mode: bool = False, num_predict: int = 512) -> str:
    """
    Send a prompt to the processing LLM and return the response text.
    Uses low temperature by default — we want consistent structured output.
    Set json_mode=True to force JSON output (recommended for scoring/parsing).
    num_predict: max tokens. 512 for scoring; 2048+ for profile parsing.
    """
    model = model or PROC_LLM_MODEL
    url   = f"{PROC_LLM_BASE_URL}/v1/chat/completions"

    payload: dict = {
        "model":       model,
        "messages":    [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens":  num_predict,
    }

    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=_headers(),
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"].strip()
    except urllib.error.URLError as e:
        raise OllamaError(
            f"Cannot reach processing LLM at {PROC_LLM_BASE_URL}. "
            f"Is it running? Error: {e}"
        ) from e


def is_available() -> bool:
    """Quick health check — GET /v1/models."""
    try:
        req = urllib.request.Request(
            f"{PROC_LLM_BASE_URL}/v1/models",
            headers=_headers(),
        )
        with urllib.request.urlopen(req, timeout=5):
            return True
    except Exception:
        return False


def model_is_pulled(model: str = None) -> bool:
    """Check if a specific model is available via /v1/models."""
    model = model or PROC_LLM_MODEL
    try:
        req = urllib.request.Request(
            f"{PROC_LLM_BASE_URL}/v1/models",
            headers=_headers(),
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            names = [m["id"] for m in data.get("data", [])]
            return any(model in name for name in names)
    except Exception:
        return False
