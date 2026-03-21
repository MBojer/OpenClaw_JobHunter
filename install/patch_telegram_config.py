"""
install/patch_telegram_config.py
Safely merges Telegram settings into ~/.openclaw/openclaw.json.
Used as fallback if 'openclaw config set' is not available.
Preserves all existing config — only adds/updates telegram keys.
"""
import json
import argparse
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except json.JSONDecodeError:
            print(f"WARNING: {CONFIG_PATH} exists but is not valid JSON. "
                  "Will create a fresh config.")
    return {}


def save_config(config: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))


def deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base, recursively for nested dicts."""
    result = base.copy()
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def patch(bot_token: str, user_id: str):
    config = load_config()

    telegram_patch = {
        "channels": {
            "telegram": {
                "enabled":   True,
                "botToken":  bot_token,
                "dmPolicy":  "allowlist",
                "allowFrom": [str(user_id)],
                "streaming": "partial",
                "capabilities": {
                    "inlineButtons": "dm"
                },
            }
        }
    }

    merged = deep_merge(config, telegram_patch)
    save_config(merged)
    print(f"✓ Patched {CONFIG_PATH}")
    print(f"  dmPolicy: allowlist")
    print(f"  allowFrom: [{user_id}]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bot-token", required=True)
    parser.add_argument("--user-id",   required=True)
    args = parser.parse_args()
    patch(args.bot_token, args.user_id)
