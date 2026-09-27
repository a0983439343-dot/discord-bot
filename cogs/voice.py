import asyncio
import time

import discord
from discord import app_commands
from discord.ext import commands

import storage


class VoiceCog(commands.Cog):
    voice = app_commands.Group(name="voice", description="語音頻道小工具與臨時語音")

    def __init__(self, bot):
        self.bot = bot
        self.joined_at: dict[tuple[int,int], float] = {}
        self.temp_channels: set[int] = set()

    @voice.command(name="temp", description="在你目前的語音位置建立一個臨時語音頻道")
    @app_commands.describe(name="頻道名稱")
    async def temp(self, interaction, name: str = "臨時語音"):
        if not interaction.guild or not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("你要先進語音，我才知道要在哪裡建。", ephemeral=True)
            return
        source = interaction.user.voice.channel
        category = getattr(source, "category", None)
        try:
            channel = await interaction.guild.create_voice_channel(
                name=name[:100],
                category=category,
                reason=f"臨時語音 by {interaction.user}",
            )
            self.temp_channels.add(channel.id)
            storage.add_temp_channel(interaction.guild.id, channel.id)
            await interaction.user.move_to(channel)
            await interaction.response.send_message(f"好了，幫你開了 {channel.mention}。沒人了我會幫你清掉。")
        except discord.Forbidden:
            await interaction.response.send_message("我沒有建立或移動語音頻道的權限。", ephemeral=True)

    @voice.command(name="notice", description="設定誰進出語音時要在哪個文字頻道通知")
    @app_commands.describe(channel="通知頻道")
    async def notice(self, interaction, channel: discord.TextChannel):
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("這個設定要管理伺服器權限。", ephemeral=True)
            return
        storage.set_setting(interaction.guild.id, "voice_notice_channel_id", channel.id)
        await interaction.response.send_message(f"好，以後語音進出會通知到 {channel.mention}。", ephemeral=True)

    @voice.command(name="noticeoff", description="關閉語音進出通知")
    async def noticeoff(self, interaction):
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("這個設定要管理伺服器權限。", ephemeral=True)
            return
        storage.set_setting(interaction.guild.id, "voice_notice_channel_id", 0)
        await interaction.response.send_message("語音通知關掉了。", ephemeral=True)

    @voice.command(name="stats", description="看看自己累積待在語音多久")
    async def stats(self, interaction):
        data = storage.get_profile(interaction.guild.id, interaction.user.id)
        total = int(data["voice_seconds"])
        h, rem = divmod(total, 3600)
        m = rem // 60
        await interaction.response.send_message(f"你總共待過語音 **{h} 小時 {m} 分**。")

    @commands.Cog.listener()
    async def on_ready(self):
        self.temp_channels = {
            row["channel_id"]
            for row in storage.list_temp_channels()
            if self.bot.is_allowed_guild(row["guild_id"])
        }
        now = time.time()
        for guild in self.bot.guilds:
            if not self.bot.is_allowed_guild(guild.id):
                continue
            for voice_channel in guild.voice_channels:
                for member in voice_channel.members:
                    if member.bot:
                        continue
                    self.joined_at[(guild.id, member.id)] = now
            for channel_id in list(self.temp_channels):
                channel = guild.get_channel(channel_id)
                if channel and not channel.members:
                    try:
                        await channel.delete(reason="臨時語音無人自動刪除")
                    except discord.NotFound:
                        storage.remove_temp_channel(channel.id)
                    except discord.Forbidden:
                        pass
                    else:
                        storage.remove_temp_channel(channel.id)
                        self.temp_channels.discard(channel.id)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if not self.bot.is_allowed_guild(member.guild.id):
            return
        if member.bot or not member.guild:
            return
        key = (member.guild.id, member.id)
        if before.channel is None and after.channel is not None:
            self.joined_at[key] = time.time()
            channel_id = storage.get_setting(member.guild.id, "voice_notice_channel_id")
            channel = member.guild.get_channel(int(channel_id)) if channel_id else None
            if channel:
                try:
                    await channel.send(f"🎤 {member.mention} 進了 {after.channel.mention}")
                except Exception:
                    pass
        elif before.channel is not None and after.channel is None:
            started = self.joined_at.pop(key, None)
            if started:
                storage.add_voice_seconds(member.guild.id, member.id, time.time() - started)
            channel_id = storage.get_setting(member.guild.id, "voice_notice_channel_id")
            channel = member.guild.get_channel(int(channel_id)) if channel_id else None
            if channel:
                try:
                    await channel.send(f"👋 {member.mention} 離開 {before.channel.mention}")
                except Exception:
                    pass
        elif before.channel != after.channel and after.channel is not None:
            started = self.joined_at.get(key)
            if started:
                storage.add_voice_seconds(member.guild.id, member.id, time.time() - started)
            self.joined_at[key] = time.time()

        for ch in [before.channel, after.channel]:
            if ch and ch.id in self.temp_channels and len(ch.members) == 0:
                try:
                    await ch.delete(reason="臨時語音無人自動刪除")
                except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                    pass
                storage.remove_temp_channel(ch.id)
                self.temp_channels.discard(ch.id)


async def setup(bot):
    await bot.add_cog(VoiceCog(bot))
