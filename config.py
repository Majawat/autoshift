# config.py
import json
from pathlib import Path
from typing import List, Dict, Any
from common import _L, DIRNAME


class Config:
    def __init__(self, config_file: str = None):
        self.config_file = (
            Path(config_file) if config_file else Path(DIRNAME) / "config.json"
        )
        self.data = self._load_config()

    def _load_config(self):
        default_config = {
            "sources": [
                {
                    "name": "ugoogalizer autoshift-codes",
                    "url": "https://raw.githubusercontent.com/ugoogalizer/autoshift-codes/main/shiftcodes.json",
                    "type": "json",
                    "enabled": True,
                },
                {
                    "name": "Majawat autoshift-codes",
                    "url": "https://raw.githubusercontent.com/Majawat/autoshift-codes/refs/heads/main/shiftcodes.json",
                    "type": "json",
                    "enabled": True,
                },
            ],
            "duplicate_detection": True,
            "retry_failed": True,
        }

        if not self.config_file.exists():
            self._save_config(default_config)
            return default_config

        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except Exception as e:
            _L.warning(f"Error loading config: {e}. Using defaults.")
            return default_config

    def _save_config(self, config):
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)

    def get_sources(self):
        return [s for s in self.data.get("sources", []) if s.get("enabled", True)]

    def add_source(self, name: str, url: str, source_type: str = "json"):
        self.data["sources"].append(
            {"name": name, "url": url, "type": source_type, "enabled": True}
        )
        self._save_config(self.data)


# Enhanced query.py functions
def parse_json_source(url_or_path: str):
    """Parse JSON from URL or local file"""
    try:
        if url_or_path.startswith(("http://", "https://")):
            resp = requests.get(url_or_path)
            resp.raise_for_status()
            data = resp.json()
        else:
            with open(url_or_path, "r") as f:
                data = json.load(f)

        # Handle both array format and object format
        if isinstance(data, list) and len(data) > 0 and "codes" in data[0]:
            codes = data[0]["codes"]
        elif isinstance(data, list):
            codes = data
        elif isinstance(data, dict) and "codes" in data:
            codes = data["codes"]
        else:
            codes = data

        return codes
    except Exception as e:
        _L.error(f"Error parsing source {url_or_path}: {e}")
        return []


def update_keys_from_sources(config: Config):
    """Update keys from all configured sources"""
    from collections import Counter

    all_keys = []
    seen_codes = set()

    for source in config.get_sources():
        _L.info(f"Checking source: {source['name']}")

        if source["type"] == "json":
            codes = parse_json_source(source["url"])

            for code_data in codes:
                # Skip expired codes
                if code_data.get("expired", False):
                    continue

                # Duplicate detection
                if config.data.get("duplicate_detection", True):
                    code_key = (
                        code_data["code"],
                        code_data["game"],
                        code_data["platform"],
                    )
                    if code_key in seen_codes:
                        continue
                    seen_codes.add(code_key)

                keys = [Key(**code_data)]

                # Apply existing special handlers
                keys = list(
                    flatten(
                        map(
                            lambda key: (
                                special_key_handler[key.game](key)
                                if key.game in special_key_handler
                                else [key]
                            ),
                            keys,
                        )
                    )
                )

                for key in keys:
                    key.set(game=get_short_game_key(key.game))
                    key.set(platform=get_short_platform_key(key.platform))

                all_keys.extend(keys)

    # Insert new keys
    new_keys = [db.insert(key) for key in all_keys]

    counts = Counter(key.game for key in new_keys if key)
    for game, count in sorted(counts.items()):
        _L.info(f"Got {count} new keys for {known_games[game]}")

    return all_keys
