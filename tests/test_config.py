from __future__ import annotations

import json

from bot.config import Config, load_config


def test_load_config_reads_config_values(tmp_path, monkeypatch) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "member_role": "Member",
                "resistant_roles": ["Resistant"],
                "immune_roles": ["Immune"],
                "log_channel_id": 123,
                "spam_regex_patterns": [r"free\s+nitro"],
                "spam_window_seconds": 180,
                "spam_channel_threshold": 4,
                "timeout_hours": 6,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")

    config = load_config(path)

    assert config == Config(
        token="test-token",
        member_role="Member",
        resistant_roles=("Resistant",),
        immune_roles=("Immune",),
        log_channel_id=123,
        spam_regex_patterns=(r"free\s+nitro",),
        spam_window_seconds=180,
        spam_channel_threshold=4,
        timeout_hours=6,
    )
