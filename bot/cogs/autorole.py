"""Assign the default member role when users join."""

from __future__ import annotations

import logging
from typing import Any

import discord
from discord.ext import commands

from bot.config import Config

_LOGGER = logging.getLogger(__name__)


def autorole_log_line(member: Any, role_name: str) -> str:
    return f"Granted autorole {role_name} to @{member.name} (<@{member.id}>)"


async def add_member_role(member: Any, role_name: str = "Member") -> bool:
    role = discord.utils.get(member.guild.roles, name=role_name)
    if role is None:
        return False

    await member.add_roles(role)
    _LOGGER.info(autorole_log_line(member, role_name))
    return True


class AutoRoleCog(commands.Cog):
    def __init__(self, config: Config) -> None:
        self.config = config

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        await add_member_role(member, self.config.member_role)
