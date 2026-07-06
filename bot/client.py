"""Bot construction and startup."""

from __future__ import annotations

import discord
from discord.ext.commands import Cog

from bot.cogs.autorole import AutoRoleCog
from bot.cogs.spam import SpamCog
from bot.config import Config

discord.VoiceClient.warn_nacl = False
discord.VoiceClient.warn_dave = False


class DiscordBot(discord.Client):
    def __init__(
        self, config: Config, spam_dry_run: bool = False, spam_full_log: bool = False
    ) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(intents=intents)
        self.config = config
        self.spam_dry_run = spam_dry_run
        self.spam_full_log = spam_full_log

    async def setup_hook(self) -> None:
        self.load_cog(AutoRoleCog(self.config))
        self.load_cog(SpamCog(self.config, self, self.spam_dry_run, self.spam_full_log))

    def load_cog(self, cog: Cog) -> None:
        for name, listener in cog.get_listeners():
            setattr(self, name, listener)


def create_bot(
    config: Config, spam_dry_run: bool = False, spam_full_log: bool = False
) -> discord.Client:
    return DiscordBot(config, spam_dry_run, spam_full_log)
