"""Detect repeated cross-channel spam."""

from __future__ import annotations

import hashlib
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import discord
from discord.ext import commands

from bot.config import Config
from bot.logs import SPAM_DIR

_LOGGER = logging.getLogger(__name__)


class SpamProtection(StrEnum):
    NONE = "None"
    PARTIAL = "Partial"
    FULL = "Full"


@dataclass(frozen=True)
class SeenMessage:
    when: datetime
    user_id: int
    channel_id: int
    signature: str
    message: Any


def message_hash(content: str, attachments: list[bytes]) -> str:
    text = content.strip().encode("utf-8")
    hasher = hashlib.sha256()
    hasher.update(len(text).to_bytes(8, "big"))
    hasher.update(text)
    for digest in sorted(hashlib.sha256(data).digest() for data in attachments):
        hasher.update(digest)
    return hasher.hexdigest()[:16]


async def message_signature(message: Any) -> str:
    attachments = [await attachment.read() for attachment in message.attachments]
    return message_hash(message.content, attachments)


def role_names(member: Any) -> set[str]:
    return {role.name for role in getattr(member, "roles", [])}


def has_admin_role(member: Any) -> bool:
    return any(
        getattr(getattr(role, "permissions", None), "administrator", False)
        for role in getattr(member, "roles", [])
    )


def compile_spam_patterns(patterns: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    compiled = []
    for pattern in patterns:
        try:
            compiled.append(re.compile(pattern, re.IGNORECASE))
        except re.error as error:
            raise RuntimeError(f"Invalid spam regex {pattern!r}: {error}") from error
    return tuple(compiled)


def matches_spam_pattern(content: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(content) for pattern in patterns)


class SpamTracker:
    def __init__(self, window: timedelta, threshold: int = 3) -> None:
        self.window = window
        self.threshold = threshold
        self._messages: defaultdict[int, list[SeenMessage]] = defaultdict(list)

    async def add(self, message: Any, now: datetime | None = None) -> list[Any]:
        now = now or datetime.now(UTC)
        signature = await message_signature(message)
        cutoff = now - self.window
        user_messages = [
            item
            for item in self._messages[message.author.id]
            if item.when >= cutoff and item.message.id != message.id
        ]
        self._messages[message.author.id] = user_messages
        user_messages.append(
            SeenMessage(now, message.author.id, message.channel.id, signature, message)
        )

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
    images.sort()
    images = list(
        zip(
            unique_attachment_names([name for name, _ in images]),
            [data for _, data in images],
        )
    )
    path = SPAM_DIR / message_hash(text, [data for _, data in images])
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
    member: Any,
    messages: list[Any],
    config: Config,
    protection: SpamProtection = SpamProtection.FULL,
) -> str:
    names = role_names(member)
    if has_admin_role(member) or names & set(config.immune_roles):
        return "ignored"

    punishment = "mute" if names & set(config.resistant_roles) else "kick"
    if protection == SpamProtection.NONE:
        return punishment

    spam_id = await message_signature(messages[0])
    for message in messages:
        await message.delete()

    if protection == SpamProtection.PARTIAL or punishment == "mute":
        until = datetime.now(UTC) + timedelta(hours=config.timeout_hours)
        await member.timeout(until, reason=f"Spam detected: {spam_id}")
        return punishment

    await member.kick(reason=f"Spam detected: {spam_id}")
    return punishment


class SpamCog(commands.Cog):
    def __init__(
        self,
        config: Config,
        client: discord.Client,
        protection: SpamProtection = SpamProtection.FULL,
        full_log: bool = False,
    ) -> None:
        self.config = config
        self.client = client
        self.protection = protection
        self.full_log = full_log
        self.tracker = SpamTracker(
            timedelta(seconds=config.spam_window_seconds), config.spam_channel_threshold
        )
        self.patterns = compile_spam_patterns(config.spam_regex_patterns)
        self._punishing: set[int] = set()

    async def _delete_if_punishing(self, message: discord.Message) -> bool:
        if message.author.id not in self._punishing:
            return False
        if self.protection != SpamProtection.NONE:
            await message.delete()
        return True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        user_id = message.author.id
        if await self._delete_if_punishing(message):
            return

        matches = (
            [message]
            if matches_spam_pattern(message.content, self.patterns)
            else await self.tracker.add(message)
        )
        if not matches:
            return

        if await self._delete_if_punishing(message):
            return

        self._punishing.add(user_id)
        try:
            punishment = await punish_spammer(
                message.author, matches, self.config, self.protection
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

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent) -> None:
        if "content" in payload.data or "attachments" in payload.data:
            await self.on_message(payload.message)
