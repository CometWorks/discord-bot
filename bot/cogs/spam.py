"""Detect repeated cross-channel spam."""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, DefaultDict, Deque
from urllib.parse import unquote, urlparse

import discord
from discord.ext import commands

from bot.config import Config
from bot.logs import SPAM_DIR

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeenMessage:
    when: datetime
    user_id: int
    channel_id: int
    signature: tuple[str, tuple[str, ...]]
    message: Any


async def message_signature(message: Any) -> tuple[str, tuple[str, ...]]:
    attachments = []
    for attachment in message.attachments:
        data = await attachment.read()
        attachments.append(hashlib.blake2s(data, digest_size=16).hexdigest())
    return (message.content.strip(), tuple(sorted(attachments)))


def role_names(member: Any) -> set[str]:
    return {role.name for role in getattr(member, "roles", [])}


def has_admin_role(member: Any) -> bool:
    return any(
        getattr(getattr(role, "permissions", None), "administrator", False)
        for role in getattr(member, "roles", [])
    )


class SpamTracker:
    def __init__(self, window: timedelta, threshold: int = 3) -> None:
        self.window = window
        self.threshold = threshold
        self._messages: DefaultDict[int, Deque[SeenMessage]] = defaultdict(deque)

    async def add(self, message: Any, now: datetime | None = None) -> list[Any]:
        now = now or datetime.now(UTC)
        user_messages = self._messages[message.author.id]
        signature = await message_signature(message)
        user_messages.append(
            SeenMessage(now, message.author.id, message.channel.id, signature, message)
        )

        cutoff = now - self.window
        while user_messages and user_messages[0].when < cutoff:
            user_messages.popleft()

        matches = [item for item in user_messages if item.signature == signature]
        if len({item.channel_id for item in matches}) >= self.threshold:
            return [item.message for item in matches]
        return []

    def clear(self, user_id: int) -> None:
        self._messages.pop(user_id, None)


def user_log_name(member: Any) -> str:
    return f"@{getattr(member, 'name', str(member))} (<@{member.id}>)"


def punishment_log_line(member: Any, punishment: str, spam_id: str) -> str:
    return f"{punishment.capitalize()} {user_log_name(member)} for spam {spam_id}"


def should_log_punishment(punishment: str, full_log: bool) -> bool:
    return punishment != "ignored" or full_log


def attachment_name(attachment: Any) -> str:
    name = Path(unquote(urlparse(getattr(attachment, "url", "")).path)).name
    return name or "attachment"


def unique_attachment_names(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    unique = []
    for name in names:
        count = seen.get(name, 0)
        seen[name] = count + 1
        if count == 0:
            unique.append(name)
            continue

        path = Path(name)
        unique.append(f"{path.stem}-{count}{path.suffix}")
    return unique


async def archive_spam(member: Any, messages: list[Any], punishment: str) -> Path:
    SPAM_DIR.mkdir(parents=True, exist_ok=True)
    text = messages[0].content
    images: list[tuple[str, bytes]] = []
    for attachment in messages[0].attachments:
        name = attachment_name(attachment)
        data = await attachment.read()
        images.append((name, data))
    images = list(
        zip(
            unique_attachment_names([name for name, _ in images]),
            [data for _, data in images],
        )
    )
    hasher = hashlib.blake2s(digest_size=4)
    hasher.update(text.encode("utf-8"))
    for name, data in images:
        hasher.update(name.encode("utf-8"))
        hasher.update(data)
    path = SPAM_DIR / hasher.hexdigest()
    if path.exists():
        return path

    path.mkdir(exist_ok=True)
    (path / "message.txt").write_text(text, encoding="utf-8")
    for name, data in images:
        (path / name).write_bytes(data)
    return path


def discord_log_message(member: Any, messages: list[Any], punishment: str) -> str:
    title = {"ignored": "Ignored", "kick": "Kicked", "mute": "Muted"}[punishment]
    content = messages[0].content
    attachments = "\n".join(
        url
        for attachment in messages[0].attachments
        if (url := getattr(attachment, "url", ""))
    )
    sections = [f"# {title} <@{member.id}> for Spam"]
    if content:
        sections.append(f"Content:\n```\n{content}\n```")
    if attachments:
        sections.append(f"Attachments:\n```\n{attachments}\n```")
    return "\n".join(sections)


async def send_discord_log(
    client: Any,
    member: Any,
    messages: list[Any],
    punishment: str,
    config: Config,
    full_log: bool = False,
) -> None:
    if config.log_channel_id is None or not should_log_punishment(punishment, full_log):
        return

    channel = client.get_channel(config.log_channel_id)
    if channel is None or not hasattr(channel, "send"):
        _LOGGER.warning("Could not find spam log channel %s", config.log_channel_id)
        return

    await channel.send(discord_log_message(member, messages, punishment))


async def punish_spammer(
    member: Any, messages: list[Any], config: Config, dry_run: bool = False
) -> str:
    names = role_names(member)
    if has_admin_role(member) or names & set(config.immune_roles):
        return "ignored"

    punishment = "mute" if names & set(config.resistant_roles) else "kick"
    if dry_run:
        return punishment

    for message in messages:
        await message.delete()

    if punishment == "mute":
        until = datetime.now(UTC) + timedelta(hours=config.timeout_hours)
        await member.timeout(until, reason="Repeated cross-channel spam")
        return punishment

    await member.kick(reason="Repeated cross-channel spam")
    return punishment


class SpamCog(commands.Cog):
    def __init__(
        self,
        config: Config,
        client: discord.Client,
        dry_run: bool = False,
        full_log: bool = False,
    ) -> None:
        self.config = config
        self.client = client
        self.dry_run = dry_run
        self.full_log = full_log
        self.tracker = SpamTracker(
            timedelta(seconds=config.spam_window_seconds), config.spam_channel_threshold
        )
        self._punishing: set[int] = set()

    async def _delete_if_punishing(self, message: discord.Message) -> bool:
        if message.author.id not in self._punishing:
            return False
        if not self.dry_run:
            await message.delete()
        return True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        user_id = message.author.id
        if await self._delete_if_punishing(message):
            return

        matches = await self.tracker.add(message)
        if not matches:
            return

        if await self._delete_if_punishing(message):
            return

        self._punishing.add(user_id)
        try:
            punishment = await punish_spammer(
                message.author, matches, self.config, self.dry_run
            )
            if not should_log_punishment(punishment, self.full_log):
                return

            archive = await archive_spam(message.author, matches, punishment)
            _LOGGER.info(punishment_log_line(message.author, punishment, archive.name))
            await send_discord_log(
                self.client,
                message.author,
                matches,
                punishment,
                self.config,
                self.full_log,
            )
        finally:
            self.tracker.clear(user_id)
            self._punishing.discard(user_id)
