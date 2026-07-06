from __future__ import annotations

import asyncio
import logging

from bot.cogs.autorole import add_member_role, autorole_log_line


class Role:
    def __init__(self, name: str) -> None:
        self.name = name


class Guild:
    def __init__(self, roles: list[Role]) -> None:
        self.roles = roles


class Member:
    def __init__(self, guild: Guild) -> None:
        self.guild = guild
        self.added: list[Role] = []
        self.id = 7
        self.name = "user-7"

    async def add_roles(self, role: Role) -> None:
        self.added.append(role)


def test_user_join_gets_member_role() -> None:
    member_role = Role("Member")
    member = Member(Guild([Role("Other"), member_role]))

    assert asyncio.run(add_member_role(member))
    assert member.added == [member_role]


def test_autorole_log_line() -> None:
    member = Member(Guild([]))

    assert autorole_log_line(member, "Member") == (
        "Granted autorole Member to @user-7 (<@7>)"
    )


def test_user_join_logs_autorole(caplog) -> None:
    member_role = Role("Member")
    member = Member(Guild([member_role]))

    with caplog.at_level(logging.INFO, logger="bot.cogs.autorole"):
        assert asyncio.run(add_member_role(member))

    assert "Granted autorole Member to @user-7 (<@7>)" in caplog.messages
