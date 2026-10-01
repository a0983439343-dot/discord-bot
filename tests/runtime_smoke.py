import asyncio
import os
import tempfile
from types import SimpleNamespace

import discord
from discord import app_commands

import bot as bot_module
import storage
from cogs.games import GamesCog
from cogs.giveaway import text as giveaway_text
from cogs.media import MediaCog
from cogs.moderation import ModerationCog
from cogs.music import MusicCog
from cogs.profile import fmt_seconds
from cogs.settings import SettingsCog
from cogs.social import parse_role_ids
from cogs.utility import UtilityCog
from cogs.voice import VoiceCog


class FakeResponse:
    def __init__(self):
        self.messages = []
        self.deferred = False

    async def send_message(self, content=None, **kwargs):
        self.messages.append((content, kwargs))

    async def defer(self, **kwargs):
        self.deferred = True


class FakeFollowup:
    def __init__(self):
        self.messages = []

    async def send(self, content=None, **kwargs):
        self.messages.append((content, kwargs))


class FakeInteraction:
    def __init__(self, guild=True, *, user_id=456, channel_id=789, permissions=None):
        self.guild = SimpleNamespace(id=123) if guild else None
        self.user = SimpleNamespace(id=user_id)
        self.channel = SimpleNamespace(id=channel_id)
        self.response = FakeResponse()
        self.followup = FakeFollowup()
        self.permissions = permissions


def callback(cog_cls, method_name):
    return getattr(cog_cls, method_name).callback


async def main():
    original_db = storage.DB_PATH
    with tempfile.TemporaryDirectory() as tmp:
        storage.DB_PATH = os.path.join(tmp, "bot.sqlite3")
        storage.init_db()

        for module in [
            bot_module.utility,
            bot_module.social,
            bot_module.games,
            bot_module.music,
            bot_module.moderation,
            bot_module.profile,
            bot_module.voice,
            bot_module.giveaway,
            bot_module.media,
            bot_module.settings,
            bot_module.help_cog,
        ]:
            await module.setup(bot_module.bot)

        commands = list(bot_module.bot.tree.walk_commands())
        assert len(commands) >= 120, len(commands)
        qualified = {c.qualified_name for c in commands}
        assert "calc" in qualified
        assert "music.play" in qualified
        assert "game.rps" in qualified
        assert "giveaway.create" in qualified
        assert "ai.ask" in qualified
        assert "security.antispam" in qualified
        assert "note.list" in qualified
        assert "voice.temp" in qualified

        utility = bot_module.bot.get_cog("UtilityCog")
        games = bot_module.bot.get_cog("GamesCog")
        media = bot_module.bot.get_cog("MediaCog")
        moderation = bot_module.bot.get_cog("ModerationCog")
        music = bot_module.bot.get_cog("MusicCog")
        settings = bot_module.bot.get_cog("SettingsCog")
        voice = bot_module.bot.get_cog("VoiceCog")
        assert all((utility, games, media, moderation, music, settings, voice))

        i = FakeInteraction()
        await callback(UtilityCog, "calc")(utility, i, "2+3*4")
        assert i.response.messages[-1][0] == "2+3*4 = **14**"

        i = FakeInteraction()
        await callback(UtilityCog, "calc")(utility, i, "2**9")
        assert i.response.messages[-1][1].get("ephemeral") is True

        i = FakeInteraction()
        await callback(UtilityCog, "convert")(utility, i, 2.0, "km", "m")
        assert "2000" in i.response.messages[-1][0]

        i = FakeInteraction()
        await callback(UtilityCog, "roll")(utility, i, "2d6+3")
        assert "總和" in i.response.messages[-1][0]

        i = FakeInteraction()
        await callback(UtilityCog, "choose")(utility, i, "A,B,C")
        assert "我幫你選" in i.response.messages[-1][0]

        i = FakeInteraction()
        await callback(UtilityCog, "password")(utility, i, 16)
        assert len(i.response.messages[-1][0].split("\n")[0].replace("這組給你：", "")) == 16

        i = FakeInteraction()
        await callback(UtilityCog, "days")(utility, i, "2026-01-01", "2026-01-10")
        assert "9 天" in i.response.messages[-1][0]

        i = FakeInteraction(guild=False)
        await callback(UtilityCog, "countdown")(utility, i, 5)
        assert i.response.messages[-1][1].get("ephemeral") is True

        reminder_id = storage.add_reminder(123, 456, 789, "test", 9999999999)
        i = FakeInteraction()
        await callback(UtilityCog, "remind_list")(utility, i)
        assert str(reminder_id) in i.response.messages[-1][0]

        i = FakeInteraction(guild=False)
        assert games.allowed(i) is False
        i = FakeInteraction(guild=True)
        assert games.allowed(i) is True
        assert games.session_key(i) == (123, 456)

        assert parse_role_ids("1, 2 3\n4") == [1, 2, 3, 4]
        assert fmt_seconds(3661) == "1 小時 1 分 1 秒"
        assert giveaway_text({"prize": "test", "ends_at": 9999999999}, 3)

        i = FakeInteraction(guild=False)
        await callback(MusicCog, "leave")(music, i)
        assert i.response.messages[-1][1].get("ephemeral") is True

        i = FakeInteraction(guild=False)
        await callback(SettingsCog, "note_list")(settings, i)
        assert i.response.messages[-1][1].get("ephemeral") is True

        i = FakeInteraction(guild=False)
        await callback(VoiceCog, "notice")(voice, i, None)
        assert i.response.messages[-1][1].get("ephemeral") is True

        i = FakeInteraction(guild=False)
        await callback(MediaCog, "ask")(media, i, "hello")
        assert i.response.messages[-1][1].get("ephemeral") is True

        assert moderation.can_manage(FakeInteraction(guild=False)) is False
        assert moderation.can_mod(FakeInteraction(guild=False)) is False
        assert moderation.can_kick(FakeInteraction(guild=False)) is False
        assert moderation.can_ban(FakeInteraction(guild=False)) is False

        print(f"Runtime offline smoke OK: {len(commands)} registered commands")


if __name__ == "__main__":
    asyncio.run(main())
