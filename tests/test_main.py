from __future__ import annotations

from typing import Any

import pytest

from bot.__main__ import main, parse_args
from bot.cogs.spam import SpamProtection
from bot.config import Config


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ([], SpamProtection.FULL),
        (["--spam-punish=None"], SpamProtection.NONE),
        (["--spam-punish=Partial"], SpamProtection.PARTIAL),
        (["--spam-punish=Full"], SpamProtection.FULL),
    ],
)
def test_parse_spam_protection(monkeypatch, arguments, expected) -> None:
    monkeypatch.setattr("sys.argv", ["bot", *arguments])

    assert parse_args().spam_protection == expected


def test_parse_spam_full_log(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["bot", "--spam-full-log"])

    assert parse_args().spam_full_log is True


def test_main_disables_discord_logging_setup(monkeypatch) -> None:
    calls: dict[str, Any] = {}

    class Client:
        def run(self, token: str, **kwargs: Any) -> None:
            calls["token"] = token
            calls["kwargs"] = kwargs

    def create_bot(
        config: Config,
        spam_protection: SpamProtection = SpamProtection.FULL,
        spam_full_log: bool = False,
    ) -> Client:
        calls["spam_protection"] = spam_protection
        calls["spam_full_log"] = spam_full_log
        return Client()

    monkeypatch.setattr("sys.argv", ["bot"])
    monkeypatch.setattr("bot.__main__.setup_logging", lambda: None)
    monkeypatch.setattr("bot.__main__.load_config", lambda: Config(token="test-token"))
    monkeypatch.setattr("bot.__main__.create_bot", create_bot)

    main()

    assert calls == {
        "spam_protection": SpamProtection.FULL,
        "spam_full_log": False,
        "token": "test-token",
        "kwargs": {"log_handler": None},
    }


def test_main_logs_enabled_spam_args(monkeypatch, caplog) -> None:
    class Client:
        def run(self, token: str, **kwargs: Any) -> None:
            pass

    monkeypatch.setattr("sys.argv", ["bot", "--spam-punish=None", "--spam-full-log"])
    monkeypatch.setattr("bot.__main__.setup_logging", lambda: None)
    monkeypatch.setattr("bot.__main__.load_config", lambda: Config(token="test-token"))
    monkeypatch.setattr("bot.__main__.create_bot", lambda *args, **kwargs: Client())

    main()

    assert "Skipping spam punishments due to dry-run" in caplog.messages
    assert "Logging spam from 'Immune' users" in caplog.messages


def test_main_logs_partial_spam_protection(monkeypatch, caplog) -> None:
    class Client:
        def run(self, token: str, **kwargs: Any) -> None:
            pass

    monkeypatch.setattr("sys.argv", ["bot", "--spam-punish=Partial"])
    monkeypatch.setattr("bot.__main__.setup_logging", lambda: None)
    monkeypatch.setattr("bot.__main__.load_config", lambda: Config(token="test-token"))
    monkeypatch.setattr("bot.__main__.create_bot", lambda *args, **kwargs: Client())

    main()

    assert "Treating all punishable users as spam resistant" in caplog.messages
