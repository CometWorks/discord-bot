from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from bot.cogs import spam
from bot.cogs.spam import (
    SpamCog,
    SpamTracker,
    archive_spam,
    discord_log_message,
    message_signature,
    punish_spammer,
    punishment_log_line,
    send_discord_log,
    should_log_punishment,
    unique_attachment_names,
    user_log_name,
)
from bot.config import Config


class Permissions:
    def __init__(self, administrator: bool = False) -> None:
        self.administrator = administrator


class Role:
    def __init__(self, name: str, administrator: bool = False) -> None:
        self.name = name
        self.permissions = Permissions(administrator)


class Attachment:
    def __init__(self, url: str, data: bytes = b"image") -> None:
        self.url = url
        self.data = data

    async def read(self) -> bytes:
        return self.data


class Channel:
    def __init__(self, channel_id: int) -> None:
        self.id = channel_id


class Author:
    bot = False

    def __init__(
        self, user_id: int, roles: list[str], admin_roles: set[str] | None = None
    ) -> None:
        self.id = user_id
        self.name = f"user-{user_id}"
        admin_roles = admin_roles or set()
        self.roles = [Role(role, role in admin_roles) for role in roles]
        self.kicked = False
        self.timed_out = False

    def __str__(self) -> str:
        return self.name

    async def kick(self, reason: str) -> None:
        self.kicked = reason == "Repeated cross-channel spam"

    async def timeout(self, until: datetime, reason: str) -> None:
        self.timed_out = (
            until > datetime.now(UTC) and reason == "Repeated cross-channel spam"
        )


class Message:
    def __init__(
        self,
        author: Author,
        content: str,
        channel_id: int,
        attachments: list[str | tuple[str, bytes]] | None = None,
    ) -> None:
        self.author = author
        self.content = content
        self.channel = Channel(channel_id)
        self.attachments = [
            (
                Attachment(*attachment)
                if isinstance(attachment, tuple)
                else Attachment(attachment)
            )
            for attachment in attachments or []
        ]
        self.deleted = False

    async def delete(self) -> None:
        self.deleted = True


class LogChannel:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send(self, message: str) -> None:
        self.messages.append(message)


class Client:
    def __init__(self, channel: LogChannel | None = None) -> None:
        self.channel = channel

    def get_channel(self, channel_id: int) -> LogChannel | None:
        return self.channel


CONFIG = Config(
    token="test",
    resistant_roles=("Resistant",),
    immune_roles=("Immune",),
)


def test_same_image_counts_as_same_message() -> None:
    author = Author(1, ["Member"])
    first = Message(author, "look", 1, ["https://example/image.png"])
    second = Message(author, "look", 2, ["https://example/image.png"])

    assert asyncio.run(message_signature(first)) == asyncio.run(
        message_signature(second)
    )


def test_same_image_with_different_cdn_links_counts_as_same_message() -> None:
    author = Author(1, ["Member"])
    first = Message(
        author, "look", 1, [("https://cdn.discordapp.com/a/image.png", b"same")]
    )
    second = Message(
        author, "look", 2, [("https://cdn.discordapp.com/b/image.png", b"same")]
    )

    assert asyncio.run(message_signature(first)) == asyncio.run(
        message_signature(second)
    )


def test_member_spam_across_channels_is_kicked_and_deleted() -> None:
    author = Author(1, ["Member"])
    tracker = SpamTracker(timedelta(minutes=3))
    now = datetime(2026, 1, 1, tzinfo=UTC)
    messages = [Message(author, "spam", channel) for channel in [1, 2, 3]]

    matches: list[Message] = []
    for message in messages:
        matches = asyncio.run(tracker.add(message, now))

    assert asyncio.run(punish_spammer(author, matches, CONFIG)) == "kick"
    assert author.kicked
    assert all(message.deleted for message in messages)


def test_resistant_spam_across_channels_is_timed_out_and_deleted() -> None:
    author = Author(1, ["Member", "Resistant"])
    tracker = SpamTracker(timedelta(minutes=3))
    now = datetime(2026, 1, 1, tzinfo=UTC)
    messages = [Message(author, "spam", channel) for channel in [1, 2, 3]]

    matches: list[Message] = []
    for message in messages:
        matches = asyncio.run(tracker.add(message, now))

    assert asyncio.run(punish_spammer(author, matches, CONFIG)) == "mute"
    assert author.timed_out
    assert all(message.deleted for message in messages)


def test_dry_run_kick_is_logged_but_not_applied() -> None:
    author = Author(1, ["Member"])
    messages = [Message(author, "spam", channel) for channel in [1, 2, 3]]

    assert asyncio.run(punish_spammer(author, messages, CONFIG, dry_run=True)) == "kick"
    assert not author.kicked
    assert not any(message.deleted for message in messages)


def test_dry_run_mute_is_logged_but_not_applied() -> None:
    author = Author(1, ["Member", "Resistant"])
    messages = [Message(author, "spam", channel) for channel in [1, 2, 3]]

    assert asyncio.run(punish_spammer(author, messages, CONFIG, dry_run=True)) == "mute"
    assert not author.timed_out
    assert not any(message.deleted for message in messages)


def test_immune_spam_has_no_effect() -> None:
    author = Author(1, ["Member", "Immune"])
    messages = [Message(author, "spam", channel) for channel in [1, 2, 3]]

    assert asyncio.run(punish_spammer(author, messages, CONFIG)) == "ignored"
    assert not author.kicked
    assert not author.timed_out
    assert not any(message.deleted for message in messages)


def test_admin_role_is_immune() -> None:
    author = Author(1, ["Member", "Admin"], admin_roles={"Admin"})
    messages = [Message(author, "spam", channel) for channel in [1, 2, 3]]

    assert asyncio.run(punish_spammer(author, messages, CONFIG)) == "ignored"
    assert not author.kicked
    assert not author.timed_out
    assert not any(message.deleted for message in messages)


def test_immune_spam_logging_is_opt_in() -> None:
    assert not should_log_punishment("ignored", full_log=False)
    assert should_log_punishment("ignored", full_log=True)
    assert should_log_punishment("kick", full_log=False)


def test_repeated_message_in_one_channel_is_not_spam() -> None:
    author = Author(1, ["Member"])
    tracker = SpamTracker(timedelta(minutes=3))
    now = datetime(2026, 1, 1, tzinfo=UTC)

    matches = [
        asyncio.run(tracker.add(Message(author, "same", 1), now)) for _ in range(5)
    ]

    assert matches == [[], [], [], [], []]


def test_different_messages_in_different_channels_are_not_spam() -> None:
    author = Author(1, ["Member"])
    tracker = SpamTracker(timedelta(minutes=3))
    now = datetime(2026, 1, 1, tzinfo=UTC)

    messages = [
        Message(author, content, channel)
        for channel, content in enumerate(["a", "b", "c"], 1)
    ]

    assert [asyncio.run(tracker.add(message, now)) for message in messages] == [
        [],
        [],
        [],
    ]


def test_spam_cog_uses_configured_channel_threshold() -> None:
    cog = SpamCog(Config(token="test", spam_channel_threshold=2), cast(Any, Client()))

    assert cog.tracker.threshold == 2


def test_overlapping_spam_detection_only_punishes_once(monkeypatch) -> None:
    author = Author(1, ["Member"])
    cog = SpamCog(CONFIG, cast(Any, Client()))
    release = asyncio.Event()
    calls = 0

    async def fake_punish(member, messages, config, dry_run=False):
        nonlocal calls
        calls += 1
        await release.wait()
        return "kick"

    async def fake_archive(member, messages, punishment):
        return type("Archive", (), {"name": "abcd1234"})()

    async def run() -> None:
        await cog.on_message(cast(Any, Message(author, "spam", 1)))
        await cog.on_message(cast(Any, Message(author, "spam", 2)))
        pending = asyncio.create_task(
            cog.on_message(cast(Any, Message(author, "spam", 3)))
        )
        await asyncio.sleep(0)

        fourth = Message(author, "spam", 4)
        await cog.on_message(cast(Any, fourth))
        assert fourth.deleted

        release.set()
        await pending

    monkeypatch.setattr(spam, "punish_spammer", fake_punish)
    monkeypatch.setattr(spam, "archive_spam", fake_archive)

    asyncio.run(run())

    assert calls == 1


def test_edge_overlapping_tracker_add_only_punishes_once(monkeypatch) -> None:
    author = Author(1, ["Member"])
    cog = SpamCog(CONFIG, cast(Any, Client()))
    release_add = asyncio.Event()
    release_punish = asyncio.Event()
    calls = 0

    class EdgeTracker:
        async def add(self, message):
            await release_add.wait()
            return [message]

        def clear(self, user_id):
            pass

    async def fake_punish(member, messages, config, dry_run=False):
        nonlocal calls
        calls += 1
        await release_punish.wait()
        return "kick"

    async def fake_archive(member, messages, punishment):
        return type("Archive", (), {"name": "abcd1234"})()

    async def run() -> tuple[Message, Message]:
        first = Message(author, "spam", 1)
        second = Message(author, "spam", 2)
        tasks = [
            asyncio.create_task(cog.on_message(cast(Any, first))),
            asyncio.create_task(cog.on_message(cast(Any, second))),
        ]
        await asyncio.sleep(0)

        release_add.set()
        await asyncio.sleep(0)
        release_punish.set()
        await asyncio.gather(*tasks)
        return first, second

    cog.tracker = cast(Any, EdgeTracker())
    monkeypatch.setattr(spam, "punish_spammer", fake_punish)
    monkeypatch.setattr(spam, "archive_spam", fake_archive)

    first, second = asyncio.run(run())

    assert calls == 1
    assert [first.deleted, second.deleted].count(True) == 1


def test_archive_spam_writes_flagged_messages(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(spam, "SPAM_DIR", tmp_path)
    author = Author(7, ["Member"])
    messages = [Message(author, "spam", 1, ["https://example/image.png"])]

    path = asyncio.run(archive_spam(author, messages, "kick"))

    assert path.parent == tmp_path
    assert len(path.name) == 8
    assert (path / "message.txt").read_text(encoding="utf-8") == "spam"
    assert (path / "image.png").read_bytes() == b"image"


def test_unique_attachment_names_adds_suffixes() -> None:
    assert unique_attachment_names(["image.png", "image.png", "image.png"]) == [
        "image.png",
        "image-1.png",
        "image-2.png",
    ]


def test_archive_spam_saves_images_with_same_filename(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(spam, "SPAM_DIR", tmp_path)
    author = Author(7, ["Member"])
    messages = [
        Message(
            author,
            "spam",
            1,
            [
                ("https://cdn.discordapp.com/a/image.png", b"first"),
                ("https://cdn.discordapp.com/b/image.png", b"second"),
            ],
        )
    ]

    path = asyncio.run(archive_spam(author, messages, "kick"))

    assert (path / "image.png").read_bytes() == b"first"
    assert (path / "image-1.png").read_bytes() == b"second"


def test_archive_spam_deduplicates_identical_logs(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(spam, "SPAM_DIR", tmp_path)
    author = Author(7, ["Member"])
    messages = [Message(author, "spam", 1, ["https://example/image.png"])]

    first = asyncio.run(archive_spam(author, messages, "kick"))
    second = asyncio.run(archive_spam(author, messages, "kick"))

    assert first == second
    assert list(tmp_path.iterdir()) == [first]


def test_archive_spam_saves_one_attachment_set(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(spam, "SPAM_DIR", tmp_path)
    author = Author(7, ["Member"])
    messages = [
        Message(
            author, "spam", 1, [("https://cdn.discordapp.com/a/image.png", b"same")]
        ),
        Message(
            author, "spam", 2, [("https://cdn.discordapp.com/b/image.png", b"same")]
        ),
        Message(
            author, "spam", 3, [("https://cdn.discordapp.com/c/image.png", b"same")]
        ),
    ]

    path = asyncio.run(archive_spam(author, messages, "kick"))

    assert sorted(item.name for item in path.iterdir()) == ["image.png", "message.txt"]


def test_archive_spam_does_not_rewrite_existing_folder(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(spam, "SPAM_DIR", tmp_path)
    author = Author(7, ["Member"])
    messages = [Message(author, "spam", 1, ["https://example/image.png"])]

    path = asyncio.run(archive_spam(author, messages, "kick"))
    (path / "marker.txt").write_text("keep", encoding="utf-8")

    assert asyncio.run(archive_spam(author, messages, "kick")) == path
    assert (path / "marker.txt").read_text(encoding="utf-8") == "keep"


def test_archive_spam_hashes_attachment_bytes_not_cdn_urls(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(spam, "SPAM_DIR", tmp_path)
    author = Author(7, ["Member"])
    first = [
        Message(
            author, "spam", 1, [("https://cdn.discordapp.com/a/image.png", b"same")]
        )
    ]
    second = [
        Message(
            author, "spam", 1, [("https://cdn.discordapp.com/b/image.png", b"same")]
        )
    ]

    first_path = asyncio.run(archive_spam(author, first, "kick"))
    second_path = asyncio.run(archive_spam(author, second, "kick"))

    assert first_path == second_path
    assert (first_path / "image.png").read_bytes() == b"same"


def test_text_log_line_references_spam_folder() -> None:
    author = Author(7, ["Member"])

    assert punishment_log_line(author, "kick", "abcd1234") == (
        "Kick @user-7 (<@7>) for spam abcd1234"
    )


def test_user_log_name_uses_name_and_mention() -> None:
    assert user_log_name(Author(7, ["Member"])) == "@user-7 (<@7>)"


def test_discord_log_message_uses_required_format() -> None:
    author = Author(7, ["Member"])
    messages = [Message(author, "spam text", 1, ["https://example/image.png"])]

    assert discord_log_message(author, messages, "mute") == (
        "# Muted <@7> for Spam\n"
        "Content:\n```\nspam text\n```\n"
        "Attachments:\n```\nhttps://example/image.png\n```"
    )


def test_discord_log_message_uses_one_attachment_set() -> None:
    author = Author(7, ["Member"])
    messages = [
        Message(author, "spam text", 1, ["https://example/first.png"]),
        Message(author, "spam text", 2, ["https://example/second.png"]),
        Message(author, "spam text", 3, ["https://example/third.png"]),
    ]

    assert discord_log_message(author, messages, "kick") == (
        "# Kicked <@7> for Spam\n"
        "Content:\n```\nspam text\n```\n"
        "Attachments:\n```\nhttps://example/first.png\n```"
    )


def test_discord_log_message_omits_empty_content_section() -> None:
    author = Author(7, ["Member"])
    messages = [Message(author, "", 1, ["https://example/image.png"])]

    assert discord_log_message(author, messages, "kick") == (
        "# Kicked <@7> for Spam\n" "Attachments:\n```\nhttps://example/image.png\n```"
    )


def test_discord_log_message_omits_empty_attachments_section() -> None:
    author = Author(7, ["Member"])
    messages = [Message(author, "spam text", 1)]

    assert discord_log_message(author, messages, "kick") == (
        "# Kicked <@7> for Spam\nContent:\n```\nspam text\n```"
    )


def test_discord_log_is_optional() -> None:
    channel = LogChannel()
    author = Author(7, ["Member"])
    messages = [Message(author, "spam text", 1)]

    asyncio.run(send_discord_log(Client(channel), author, messages, "kick", CONFIG))

    assert channel.messages == []


def test_discord_log_sends_when_channel_configured() -> None:
    channel = LogChannel()
    author = Author(7, ["Member"])
    messages = [Message(author, "spam text", 1)]
    config = Config(token="test", log_channel_id=123)

    asyncio.run(send_discord_log(Client(channel), author, messages, "kick", config))

    assert channel.messages == ["# Kicked <@7> for Spam\nContent:\n```\nspam text\n```"]


def test_discord_log_ignores_immune_by_default() -> None:
    channel = LogChannel()
    author = Author(7, ["Member"])
    messages = [Message(author, "spam text", 1)]
    config = Config(token="test", log_channel_id=123)

    asyncio.run(send_discord_log(Client(channel), author, messages, "ignored", config))

    assert channel.messages == []


def test_discord_log_sends_immune_when_full_log_enabled() -> None:
    channel = LogChannel()
    author = Author(7, ["Member"])
    messages = [Message(author, "spam text", 1)]
    config = Config(token="test", log_channel_id=123)

    asyncio.run(
        send_discord_log(
            Client(channel), author, messages, "ignored", config, full_log=True
        )
    )

    assert channel.messages == [
        "# Ignored <@7> for Spam\nContent:\n```\nspam text\n```"
    ]
