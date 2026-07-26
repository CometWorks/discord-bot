from __future__ import annotations

import discord
from discord.ext import commands

from bot.client import create_bot
from bot.cogs.spam import SpamProtection
from bot.config import Config


def test_bot_uses_client_not_command_bot() -> None:
    client = create_bot(Config(token="test"))

    assert isinstance(client, discord.Client)
    assert not isinstance(client, commands.Bot)


def test_bot_accepts_spam_protection() -> None:
    client = create_bot(Config(token="test"), SpamProtection.PARTIAL)

    assert getattr(client, "spam_protection") == SpamProtection.PARTIAL


def test_bot_accepts_spam_full_log() -> None:
    client = create_bot(Config(token="test"), spam_full_log=True)

    assert getattr(client, "spam_full_log") is True
