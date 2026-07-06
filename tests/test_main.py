from __future__ import annotations

from typing import Any

from bot.__main__ import main, parse_args
from bot.config import Config


def test_parse_spam_dry_run(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["bot", "--spam-dry-run"])

    assert parse_args().spam_dry_run is True


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
        config: Config, spam_dry_run: bool = False, spam_full_log: bool = False
    ) -> Client:
        calls["spam_dry_run"] = spam_dry_run
        calls["spam_full_log"] = spam_full_log
        return Client()

    monkeypatch.setattr("sys.argv", ["bot"])
    monkeypatch.setattr("bot.__main__.setup_logging", lambda: None)
    monkeypatch.setattr("bot.__main__.load_config", lambda: Config(token="test-token"))
    monkeypatch.setattr("bot.__main__.create_bot", create_bot)

    main()

    assert calls == {
        "spam_dry_run": False,
        "spam_full_log": False,
        "token": "test-token",
        "kwargs": {"log_handler": None},
    }


def test_main_logs_enabled_spam_args(monkeypatch, caplog) -> None:
    class Client:
        def run(self, token: str, **kwargs: Any) -> None:
            pass

    monkeypatch.setattr("sys.argv", ["bot", "--spam-dry-run", "--spam-full-log"])
    monkeypatch.setattr("bot.__main__.setup_logging", lambda: None)
    monkeypatch.setattr("bot.__main__.load_config", lambda: Config(token="test-token"))
    monkeypatch.setattr("bot.__main__.create_bot", lambda *args, **kwargs: Client())

    main()

    assert "Skipping spam punishments due to dry-run" in caplog.messages
    assert "Logging spam from 'Immune' users" in caplog.messages
