import asyncio
import functools
import re
from dataclasses import dataclass, field

import discord
import yt_dlp
from discord import app_commands, ui
from discord.ext import commands


YTDL_SEARCH = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "extract_flat": True,
    "noplaylist": True,
    "default_search": "ytsearch5",
}
YTDL_STREAM = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "noplaylist": True,
    "format": "bestaudio/best",
}


@dataclass
class Song:
    title: str
    url: str
    webpage_url: str
    duration: int | None = None
    requester_id: int | None = None


@dataclass
class Player:
    queue: list[Song] = field(default_factory=list)
    current: Song | None = None
    voice: discord.VoiceClient | None = None
    volume: float = 0.8
    loop_mode: str = "off"


class MusicSearchView(ui.View):
    def __init__(self, cog, interaction, results, timeout=45):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.owner_id = interaction.user.id
        for index, song in enumerate(results[:5]):
            button = ui.Button(
                label=f"{index + 1}. {song.title[:70]}",
                style=discord.ButtonStyle.secondary,
                row=index // 2,
            )
            async def callback(i: discord.Interaction, selected=song):
                if i.user.id != self.owner_id:
                    await i.response.send_message("不是你在選啦 😂", ephemeral=True)
                    return
                self.stop()
                await i.response.defer()
                ok, msg = await self.cog.enqueue_song(i, selected)
                await i.followup.send(msg, ephemeral=False if ok else True)
            button.callback = callback
            self.add_item(button)


class MusicControlView(ui.View):
    def __init__(self, cog, guild_id, timeout=None):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.guild_id = guild_id

    @ui.button(label="⏯️ 播放/繼續", style=discord.ButtonStyle.primary)
    async def play_pause(self, interaction: discord.Interaction, button: ui.Button):
        player = self.cog.players.get(self.guild_id)
        if not player or not player.voice:
            await interaction.response.send_message("目前沒有正在播的東西。", ephemeral=True)
            return
        if player.voice.is_playing():
            player.voice.pause()
            await interaction.response.send_message("先暫停一下。", ephemeral=True)
        elif player.voice.is_paused():
            player.voice.resume()
            await interaction.response.send_message("繼續播。", ephemeral=True)
        else:
            await interaction.response.send_message("目前沒有正在播的東西。", ephemeral=True)

    @ui.button(label="⏭️ 下一首", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: ui.Button):
        player = self.cog.players.get(self.guild_id)
        if player and player.voice and player.voice.is_playing():
            player.voice.stop()
            await interaction.response.send_message("跳下一首。", ephemeral=True)
        else:
            await interaction.response.send_message("現在沒在播歌。", ephemeral=True)

    @ui.button(label="🔀 隨機", style=discord.ButtonStyle.secondary)
    async def shuffle(self, interaction: discord.Interaction, button: ui.Button):
        player = self.cog.players.get(self.guild_id)
        if player and len(player.queue) > 1:
            import random
            random.shuffle(player.queue)
            await interaction.response.send_message("佇列打亂了。", ephemeral=True)
        else:
            await interaction.response.send_message("佇列裡沒幾首歌可以打亂。", ephemeral=True)

    @ui.button(label="🔁 循環", style=discord.ButtonStyle.secondary)
    async def loop(self, interaction: discord.Interaction, button: ui.Button):
        player = self.cog.players.get(self.guild_id)
        if not player:
            await interaction.response.send_message("現在沒有音樂工作階段。", ephemeral=True)
            return
        player.loop_mode = {"off":"one", "one":"all", "all":"off"}[player.loop_mode]
        labels = {"off":"關閉", "one":"單曲", "all":"整個佇列"}
        await interaction.response.send_message(f"循環：**{labels[player.loop_mode]}**。", ephemeral=True)

    @ui.button(label="⏹️ 停止", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: ui.Button):
        await self.cog.stop_player(self.guild_id)
        await interaction.response.send_message("音樂停了，Bot 也離開語音。", ephemeral=True)


class MusicCog(commands.Cog):
    music = app_commands.Group(name="music", description="在語音頻道搜尋並播放音樂")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players: dict[int, Player] = {}

    def player(self, guild_id: int) -> Player:
        return self.players.setdefault(guild_id, Player())

    async def ytdlp_search(self, query: str):
        loop = asyncio.get_running_loop()
        def task():
            with yt_dlp.YoutubeDL(YTDL_SEARCH) as ydl:
                return ydl.extract_info(query, download=False)
        data = await loop.run_in_executor(None, task)
        if not data:
            return []
        entries = data.get("entries") if isinstance(data, dict) else None
        if entries is None:
            entries = [data]
        results = []
        for entry in entries:
            if not entry:
                continue
            webpage = entry.get("webpage_url") or entry.get("original_url")
            if not webpage and entry.get("id"):
                webpage = f"https://www.youtube.com/watch?v={entry['id']}"
            if webpage:
                results.append(
                    Song(
                        title=entry.get("title") or "不知道這首叫什麼",
                        url=entry.get("url") or webpage,
                        webpage_url=webpage,
                        duration=entry.get("duration"),
                    )
                )
        return results

    async def make_stream(self, song: Song):
        loop = asyncio.get_running_loop()
        def task():
            with yt_dlp.YoutubeDL(YTDL_STREAM) as ydl:
                data = ydl.extract_info(song.webpage_url, download=False)
                stream_url = data.get("url")
                return stream_url, data.get("title") or song.title, data.get("duration")
        stream_url, title, duration = await loop.run_in_executor(None, task)
        if not stream_url:
            raise RuntimeError("no stream")
        return stream_url, title, duration

    async def enqueue_song(self, interaction: discord.Interaction, song: Song):
        if not interaction.guild:
            return False, "這個要在伺服器裡用。"
        if not interaction.user.voice or not interaction.user.voice.channel:
            return False, "你先進一個語音頻道，我才知道歌要播哪裡。"
        voice_channel = interaction.user.voice.channel
        player = self.player(interaction.guild.id)
        try:
            if not player.voice or not player.voice.is_connected():
                player.voice = await voice_channel.connect()
            elif player.voice.channel != voice_channel:
                await player.voice.move_to(voice_channel)
        except Exception:
            return False, "我進不去那個語音頻道，看看 Bot 有沒有連線權限。"
        song.requester_id = interaction.user.id
        player.queue.append(song)
        if not player.voice.is_playing() and not player.voice.is_paused() and not player.current:
            await self.play_next(interaction.guild.id)
            return True, f"好，正在播 **{song.title}** 🎵"
        return True, f"加進去了：**{song.title}**。現在排在第 {len(player.queue)} 首。"

    async def play_next(self, guild_id: int):
        player = self.players.get(guild_id)
        if not player or not player.voice or not player.voice.is_connected():
            return
        if player.loop_mode == "one" and player.current:
            song = player.current
        else:
            if not player.queue:
                player.current = None
                await asyncio.sleep(20)
                if player.queue == [] and player.voice and player.voice.is_connected() and not player.voice.is_playing():
                    await player.voice.disconnect()
                return
            song = player.queue.pop(0)
            player.current = song
        try:
            stream_url, title, duration = await self.make_stream(song)
            song.title = title
            song.duration = duration
            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(
                    stream_url,
                    before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                    options="-vn",
                ),
                volume=player.volume,
            )
        except Exception as exc:
            print("Music stream error:", repr(exc))
            channel = player.voice.channel
            if channel:
                try:
                    await channel.send(f"這首我播不起來，先跳過：{song.title}")
                except Exception:
                    pass
            player.current = None
            await self.play_next(guild_id)
            return

        loop = self.bot.loop
        def after(error):
            if error:
                print("Music player error:", repr(error))
            asyncio.run_coroutine_threadsafe(self.after_track(guild_id), loop)
        player.voice.play(source, after=after)
        try:
            await player.voice.channel.send(f"🎵 現在播：**{song.title}**")
        except Exception:
            pass

    async def after_track(self, guild_id: int):
        player = self.players.get(guild_id)
        if not player:
            return
        if player.loop_mode == "one":
            await self.play_next(guild_id)
            return
        if player.loop_mode == "all" and player.current:
            player.queue.append(player.current)
        player.current = None
        await self.play_next(guild_id)

    async def stop_player(self, guild_id: int):
        player = self.players.pop(guild_id, None)
        if not player:
            return
        if player.voice:
            try:
                player.voice.stop()
                await player.voice.disconnect(force=True)
            except Exception:
                pass

    @music.command(name="search", description="直接搜尋 YouTube 歌曲並選一首")
    @app_commands.describe(query="歌名、歌手或關鍵字")
    async def search(self, interaction: discord.Interaction, query: str):
        if not interaction.guild:
            await interaction.response.send_message("這個要在伺服器裡用。", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            results = await self.ytdlp_search(query)
        except Exception:
            await interaction.followup.send("YouTube 搜尋這次沒回來，過一下再試。")
            return
        if not results:
            await interaction.followup.send("找不到這首，換個關鍵字看看。")
            return
        lines = [f"{i+1}. **{s.title}**" for i, s in enumerate(results[:5])]
        view = MusicSearchView(self, interaction, results)
        await interaction.followup.send("🎵 找到這些：\n" + "\n".join(lines) + "\n點下面選你要的。", view=view)

    @music.command(name="play", description="搜尋歌曲，選一首後直接播放")
    @app_commands.describe(query="歌名、歌手或關鍵字")
    async def play(self, interaction: discord.Interaction, query: str):
        if not interaction.guild:
            await interaction.response.send_message("這個要在伺服器裡用。", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            results = await self.ytdlp_search(query if re.match(r"^https?://", query) else f"ytsearch5:{query}")
        except Exception:
            await interaction.followup.send("YouTube 這次搜尋失敗了，再試一次。")
            return

        if not results:
            await interaction.followup.send("找不到這首，換個關鍵字看看。")
            return

        if len(results) == 1:
            ok, msg = await self.enqueue_song(interaction, results[0])
            await interaction.followup.send(msg, ephemeral=not ok)
            return

        lines = [f"{i+1}. **{song.title}**" for i, song in enumerate(results[:5])]
        view = MusicSearchView(self, interaction, results[:5])
        await interaction.followup.send(
            "🎵 找到這些，點你要的：\n" + "\n".join(lines),
            view=view,
        )

    @music.command(name="queue", description="看看現在音樂佇列")
    async def queue(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("這個要在伺服器裡用。", ephemeral=True)
            return
        player = self.players.get(interaction.guild.id)
        if not player or (not player.current and not player.queue):
            await interaction.response.send_message("現在沒排歌。")
            return
        lines = [f"🎶 正在播：**{player.current.title}**" if player.current else "目前沒在播"]
        if player.queue:
            lines.append("接下來：")
            lines.extend(f"{i+1}. {song.title}" for i, song in enumerate(player.queue[:20]))
        await interaction.response.send_message("\n".join(lines))

    @music.command(name="nowplaying", description="看看現在正在播什麼")
    async def nowplaying(self, interaction: discord.Interaction):
        player = self.players.get(interaction.guild.id) if interaction.guild else None
        if not player or not player.current:
            await interaction.response.send_message("現在沒在播歌。", ephemeral=True)
            return
        await interaction.response.send_message(f"🎵 現在是 **{player.current.title}**\n🔁 循環：{player.loop_mode}")

    @music.command(name="pause", description="暫停目前歌曲")
    async def pause(self, interaction: discord.Interaction):
        player = self.players.get(interaction.guild.id) if interaction.guild else None
        if player and player.voice and player.voice.is_playing():
            player.voice.pause()
            await interaction.response.send_message("先停一下。")
        else:
            await interaction.response.send_message("現在沒有正在播放的歌。", ephemeral=True)

    @music.command(name="resume", description="繼續播放")
    async def resume(self, interaction: discord.Interaction):
        player = self.players.get(interaction.guild.id) if interaction.guild else None
        if player and player.voice and player.voice.is_paused():
            player.voice.resume()
            await interaction.response.send_message("繼續播。")
        else:
            await interaction.response.send_message("現在沒有暫停中的歌。", ephemeral=True)

    @music.command(name="skip", description="跳到下一首")
    async def skip(self, interaction: discord.Interaction):
        player = self.players.get(interaction.guild.id) if interaction.guild else None
        if player and player.voice and (player.voice.is_playing() or player.voice.is_paused()):
            player.voice.stop()
            await interaction.response.send_message("好，下一首。")
        else:
            await interaction.response.send_message("現在沒東西可以跳。", ephemeral=True)

    @music.command(name="volume", description="調整音量 0 到 100")
    @app_commands.describe(value="音量百分比")
    async def volume(self, interaction: discord.Interaction, value: app_commands.Range[int, 0, 100]):
        player = self.players.get(interaction.guild.id) if interaction.guild else None
        if not player:
            await interaction.response.send_message("現在還沒開始播。", ephemeral=True)
            return
        player.volume = value / 100
        if player.voice and isinstance(player.voice.source, discord.PCMVolumeTransformer):
            player.voice.source.volume = player.volume
        await interaction.response.send_message(f"音量調成 **{value}%**。")

    @music.command(name="shuffle", description="把目前佇列打亂")
    async def shuffle(self, interaction: discord.Interaction):
        import random
        player = self.players.get(interaction.guild.id) if interaction.guild else None
        if not player or len(player.queue) < 2:
            await interaction.response.send_message("佇列裡至少要有兩首才值得打亂。", ephemeral=True)
            return
        random.shuffle(player.queue)
        await interaction.response.send_message("好了，順序打亂。")

    @music.command(name="loop", description="切換單曲、全部或關閉循環")
    async def loop(self, interaction: discord.Interaction):
        player = self.players.get(interaction.guild.id) if interaction.guild else None
        if not player:
            await interaction.response.send_message("現在沒音樂工作階段。", ephemeral=True)
            return
        player.loop_mode = {"off":"one", "one":"all", "all":"off"}[player.loop_mode]
        await interaction.response.send_message(f"現在是 **{player.loop_mode}** 循環。")

    @music.command(name="remove", description="移除佇列裡指定編號的歌曲")
    @app_commands.describe(index="歌曲編號")
    async def remove(self, interaction: discord.Interaction, index: app_commands.Range[int, 1, 50]):
        player = self.players.get(interaction.guild.id) if interaction.guild else None
        if not player or index > len(player.queue):
            await interaction.response.send_message("沒有這個編號。", ephemeral=True)
            return
        removed = player.queue.pop(index - 1)
        await interaction.response.send_message(f"拿掉了：**{removed.title}**")

    @music.command(name="clear", description="清空等待中的歌曲")
    async def clear(self, interaction: discord.Interaction):
        player = self.players.get(interaction.guild.id) if interaction.guild else None
        if not player:
            await interaction.response.send_message("佇列本來就是空的。", ephemeral=True)
            return
        count = len(player.queue)
        player.queue.clear()
        await interaction.response.send_message(f"清掉 {count} 首等待中的歌。")

    @music.command(name="leave", description="讓 Bot 離開語音")
    async def leave(self, interaction: discord.Interaction):
        await self.stop_player(interaction.guild.id)
        await interaction.response.send_message("好，我先離開語音。")


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))
