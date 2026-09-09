import json
from pathlib import Path


DEFAULT_OVERRIDES = {
    "channels": {},
    "topic_preferences": {},
    "playlist_destinations": {},
    "unsubscribe_subscription_ids": [],
}


def load_overrides(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        return {
            key: (dict(value) if isinstance(value, dict) else list(value))
            for key, value in DEFAULT_OVERRIDES.items()
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    result = {
        key: (dict(value) if isinstance(value, dict) else list(value))
        for key, value in DEFAULT_OVERRIDES.items()
    }
    for key, default in DEFAULT_OVERRIDES.items():
        value = data.get(key)
        if isinstance(default, dict) and isinstance(value, dict):
            result[key].update(value)
        elif isinstance(default, list) and isinstance(value, list):
            result[key] = value
    return result


def save_channel_override(path: str | Path, channel_id: str, action: str) -> None:
    data = load_overrides(path)
    data["channels"][channel_id] = action
    Path(path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
