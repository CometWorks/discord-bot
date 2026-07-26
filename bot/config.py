"""Config loading for the bot."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    token: str
    member_role: str = "Member"
    resistant_roles: tuple[str, ...] = ()
    immune_roles: tuple[str, ...] = ()
    log_channel_id: int | None = None
    spam_regex_patterns: tuple[str, ...] = ()
    spam_window_seconds: int = 180
    spam_channel_threshold: int = 3
    timeout_hours: int = 6


def _string_list(data: dict[str, Any], key: str) -> tuple[str, ...]:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeError(f"config.json field {key!r} must be a list of strings")
    return tuple(value)


def load_config(path: str | Path = "config.json") -> Config:
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN", "")
    config_path = Path(path)
    if not token:
        raise RuntimeError("DISCORD_TOKEN is missing")
    if not config_path.exists():
        raise RuntimeError(f"{config_path} is missing")

    with config_path.open(encoding="utf-8") as file:
        data: dict[str, Any] = json.load(file)

    required = {
        "member_role": str,
        "spam_window_seconds": int,
        "spam_channel_threshold": int,
        "timeout_hours": int,
    }
    for key, expected_type in required.items():
        if not isinstance(data.get(key), expected_type):
            raise RuntimeError(
                f"config.json field {key!r} must be {expected_type.__name__}"
            )

    log_channel_id = data.get("log_channel_id")
    if log_channel_id is not None and not isinstance(log_channel_id, int):
        raise RuntimeError("config.json field 'log_channel_id' must be integer or null")

    return Config(
        token=token,
        member_role=data["member_role"],
        resistant_roles=_string_list(data, "resistant_roles"),
        immune_roles=_string_list(data, "immune_roles"),
        log_channel_id=log_channel_id,
        spam_regex_patterns=_string_list(data, "spam_regex_patterns"),
        spam_window_seconds=data["spam_window_seconds"],
        spam_channel_threshold=data["spam_channel_threshold"],
        timeout_hours=data["timeout_hours"],
    )
