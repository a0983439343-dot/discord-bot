import io
import os
import urllib.parse
import time

import aiohttp
import discord
import yt_dlp
from PIL import Image, ImageStat
from discord import app_commands
from discord.ext import commands


class SearchCog(commands.Cog):
    search = app_commands.Group(name="search", description="在 YouTube、Wikipedia、GitHub 找東西")
    image = app_commands.Group(name="image", description="簡單的圖片處理工具")
    ai = app_commands.Group(name="ai", description="可選的 AI 工具")

    def __init__(self, bot):
        self.bot = bot
        self.ai_cooldowns = {}
        self.ai_cooldown_seconds = 8

    async def _check_ai_limit(self, interaction):
        key = (interaction.guild.id if interaction.guild else 0, interaction.user.id)
        now = time.monotonic()
        last = self.ai_cooldowns.get(key, 0)
        remaining = self.ai_cooldown_seconds - (now - last)
        if remaining > 0:
            await interaction.response.send_message(
                f"先等等 {remaining:.1f} 秒，再問我下一題。",
                ephemeral=True,
            )
            return False
        self.ai_cooldowns[key] = now
        return True

    async def _send_ai_output(self, interaction, answer: str, filename: str, empty_message: str):
        answer = (answer or "").strip()
        if not answer:
            await interaction.followup.send(empty_message)
            return
        if len(answer) <= 1900:
            await interaction.followup.send(answer)
            return
        data = io.BytesIO(answer.encode("utf-8"))
        await interaction.followup.send(
            "這次內容有點長，我改成文字檔給你，直接打開就能看。",
            file=discord.File(data, filename=filename),
        )

    @search.command(name="youtube", description="搜尋 YouTube 並列出幾個結果")
    @app_commands.describe(query="關鍵字")
    async def youtube(self, interaction, query: str):
        await interaction.response.defer()
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "extract_flat": True, "default_search": "ytsearch5"}) as ydl:
                data = await self.bot.loop.run_in_executor(None, lambda: ydl.extract_info(f"ytsearch5:{query}", download=False))
            entries = (data or {}).get("entries", [])[:5]
            if not entries:
                await interaction.followup.send("沒找到東西。")
                return
            lines = []
            for i, e in enumerate(entries, 1):
                url = e.get("webpage_url") or f"https://www.youtube.com/watch?v={e.get('id')}"
                lines.append(f"{i}. **{e.get('title','未知')}**\n{url}")
            await interaction.followup.send("🔎 YouTube 搜尋結果：\n" + "\n".join(lines))
        except Exception:
            await interaction.followup.send("YouTube 搜尋這次沒回來。")

    @search.command(name="wikipedia", description="搜尋 Wikipedia")
    @app_commands.describe(query="想查的東西")
    async def wikipedia(self, interaction, query: str):
        await interaction.response.defer()
        url = "https://zh.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
            "action":"query","format":"json","list":"search","srsearch":query,"srlimit":5
        })
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=8) as resp:
                    data = await resp.json()
            items = data["query"]["search"]
            if not items:
                await interaction.followup.send("Wikipedia 沒找到。")
                return
            lines = [f"{i+1}. **{x['title']}**\nhttps://zh.wikipedia.org/wiki/{urllib.parse.quote(x['title'])}" for i,x in enumerate(items)]
            await interaction.followup.send("📖 找到這些：\n" + "\n".join(lines))
        except Exception:
            await interaction.followup.send("Wikipedia 現在沒回應。")

    @search.command(name="github", description="搜尋 GitHub 公開專案")
    @app_commands.describe(query="關鍵字")
    async def github(self, interaction, query: str):
        await interaction.response.defer()
        url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode({"q":query,"per_page":5})
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"Accept":"application/vnd.github+json","User-Agent":"discord-bot"}, timeout=8) as resp:
                    data = await resp.json()
            items = data.get("items", [])
            if not items:
                await interaction.followup.send("GitHub 沒找到。")
                return
            lines = [f"{i+1}. **{x['full_name']}** ⭐ {x.get('stargazers_count',0)}\n{x['html_url']}" for i,x in enumerate(items)]
            await interaction.followup.send("💻 GitHub 搜尋結果：\n" + "\n".join(lines))
        except Exception:
            await interaction.followup.send("GitHub 搜尋這次失敗了。")

    @image.command(name="resize", description="把圖片縮到指定寬度")
    @app_commands.describe(image="要處理的圖片", width="寬度 64 到 2048")
    async def resize(self, interaction, image: discord.Attachment, width: app_commands.Range[int,64,2048]):
        if not image.content_type or not image.content_type.startswith("image/"):
            await interaction.response.send_message("請丟圖片給我。", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            data = await image.read()
            pic = Image.open(io.BytesIO(data)).convert("RGBA")
            ratio = width / pic.width
            height = max(1, int(pic.height * ratio))
            pic = pic.resize((width, height), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            pic.save(out, format="PNG")
            out.seek(0)
            await interaction.followup.send(f"好了，縮成 {width} × {height}。", file=discord.File(out, "resized.png"))
        except Exception:
            await interaction.followup.send("這張圖處理失敗了。")

    @image.command(name="color", description="抓一張圖片的平均顏色")
    @app_commands.describe(image="要分析的圖片")
    async def color(self, interaction, image: discord.Attachment):
        if not image.content_type or not image.content_type.startswith("image/"):
            await interaction.response.send_message("請丟圖片給我。", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            data = await image.read()
            pic = Image.open(io.BytesIO(data)).convert("RGB").resize((1,1))
            r,g,b = ImageStat.Stat(pic).mean
            hex_color = f"#{int(r):02X}{int(g):02X}{int(b):02X}"
            await interaction.followup.send(f"這張圖抓到的平均色大概是 **{hex_color}**。")
        except Exception:
            await interaction.followup.send("這張圖分析失敗了。")

    @image.command(name="ocr", description="從圖片抓文字，需要設定 OCR_SPACE_API_KEY")
    @app_commands.describe(image="有文字的圖片")
    async def ocr(self, interaction, image: discord.Attachment):
        key = os.getenv("OCR_SPACE_API_KEY")
        if not key:
            await interaction.response.send_message("OCR 功能還沒設定 API Key，其他圖片工具可以直接用。", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            data = await image.read()
            form = aiohttp.FormData()
            form.add_field("file", data, filename="image.png", content_type=image.content_type or "image/png")
            form.add_field("language", "cht")
            form.add_field("isOverlayRequired", "false")
            form.add_field("OCREngine", "2")
            headers = {"apikey": key}
            async with aiohttp.ClientSession() as session:
                async with session.post("https://api.ocr.space/parse/image", data=form, headers=headers, timeout=20) as resp:
                    result = await resp.json(content_type=None)
            texts = [x.get("ParsedText","") for x in result.get("ParsedResults", [])]
            text = "\n".join(t.strip() for t in texts if t.strip())[:1800]
            await interaction.followup.send(("抓到的文字：\n" + text) if text else "這張圖沒抓到文字。")
        except Exception:
            await interaction.followup.send("OCR 這次失敗了，再試一次。")

    @ai.command(name="ask", description="問 AI 一件事，需要設定 OPENAI_API_KEY")
    @app_commands.describe(prompt="想問的內容")
    async def ask(self, interaction, prompt: str):
        if not await self._check_ai_limit(interaction):
            return
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            await interaction.response.send_message("AI 還沒設定 API Key，所以先沒開。", ephemeral=True)
            return
        await interaction.response.defer()
        model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
        payload = {
            "model": model,
            "input": [
                {
                    "role":"system",
                    "content":[{"type":"input_text","text":"你是在朋友群裡幫忙的 Discord Bot。講話自然、簡短、像真人聊天，不要自稱 AI，不要用很官腔的條列，除非使用者真的需要整理。使用繁體中文。"}],
                },
                {"role":"user","content":[{"type":"input_text","text":prompt[:6000]}]},
            ],
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/responses",
                    headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
                    json=payload,
                    timeout=45,
                ) as resp:
                    data = await resp.json(content_type=None)
            output = []
            for item in data.get("output", []):
                for part in item.get("content", []):
                    if isinstance(part, dict) and part.get("type") in {"output_text","text"}:
                        output.append(part.get("text",""))
            answer = "\n".join(output).strip()
            await self._send_ai_output(interaction, answer, "ai-answer.txt", "我剛剛沒拿到答案，再問一次。")
        except Exception:
            await interaction.followup.send("AI 這次沒回來，再試一次。")

    @ai.command(name="translate", description="讓 AI 幫你翻譯並順一下語氣")
    @app_commands.describe(text="原文", target="目標語言")
    async def ai_translate(self, interaction, text: str, target: str = "繁體中文"):
        if not await self._check_ai_limit(interaction):
            return
        await interaction.response.defer()
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            await interaction.followup.send("AI 翻譯還沒設定 API Key。")
            return
        model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
        payload = {
            "model":model,
            "input":[
                {"role":"system","content":[{"type":"input_text","text":"你是翻譯助手。只回翻譯結果，語氣自然。"}]},
                {"role":"user","content":[{"type":"input_text","text":f"翻成{target}：{text[:5000]}"}]},
            ],
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post("https://api.openai.com/v1/responses", headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"}, json=payload, timeout=45) as resp:
                    data = await resp.json(content_type=None)
            answer = "\n".join(part.get("text","") for item in data.get("output",[]) for part in item.get("content",[]) if isinstance(part,dict) and part.get("text"))
            await self._send_ai_output(interaction, answer, "ai-translate.txt", "沒翻出結果。")
        except Exception:
            await interaction.followup.send("AI 翻譯這次沒回來。")

    @ai.command(name="summarize", description="幫你把一段長文字濃縮一下")
    @app_commands.describe(text="要整理的內容")
    async def summarize(self, interaction, text: str):
        if not await self._check_ai_limit(interaction):
            return
        await interaction.response.defer()
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            await interaction.followup.send("AI 還沒設定 API Key。")
            return
        model = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
        payload = {"model":model,"input":[
            {"role":"system","content":[{"type":"input_text","text":"把內容濃縮成自然的繁體中文。抓重點，不要一直重複。"}]},
            {"role":"user","content":[{"type":"input_text","text":text[:12000]}]},
        ]}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post("https://api.openai.com/v1/responses", headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"}, json=payload, timeout=45) as resp:
                    data = await resp.json(content_type=None)
            answer = "\n".join(part.get("text","") for item in data.get("output",[]) for part in item.get("content",[]) if isinstance(part,dict) and part.get("text"))
            await self._send_ai_output(interaction, answer, "ai-summary.txt", "這次沒整理出結果。")
        except Exception:
            await interaction.followup.send("AI 整理這次沒回來。")


async def setup(bot):
    await bot.add_cog(SearchCog(bot))
