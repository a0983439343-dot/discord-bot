import os

import discord
from discord import app_commands
from discord.ext import commands
from google import genai


class AICog(commands.Cog):
    ai = app_commands.Group(name="ai", description="Gemini AI 功能")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    async def generate(self, prompt: str) -> str:
        if not self.client:
            return "Gemini AI 尚未設定，請先在 .env 填入 GEMINI_API_KEY。"

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            result = getattr(response, "text", None)
            if not result:
                return "Gemini 沒有回傳文字。"
            return result.strip()
        except Exception as exc:
            print(f"Gemini API error: {exc}")
            return "Gemini AI 目前無法使用，請檢查 API Key、模型名稱或稍後再試。"

    async def send_result(self, interaction: discord.Interaction, result: str):
        if len(result) <= 2000:
            await interaction.followup.send(result)
            return

        chunks = [result[i:i + 1900] for i in range(0, len(result), 1900)]
        for chunk in chunks[:10]:
            await interaction.followup.send(chunk)

    @ai.command(name="ask", description="詢問 Gemini AI")
    @app_commands.describe(prompt="你想問 Gemini 的內容")
    @app_commands.checks.cooldown(1, 5.0, key=lambda interaction: interaction.user.id)
    async def ask(self, interaction: discord.Interaction, prompt: str):
        prompt = prompt.strip()
        if not prompt:
            await interaction.response.send_message("你至少要輸入一點內容。", ephemeral=True)
            return
        if len(prompt) > 4000:
            await interaction.response.send_message("問題太長了，請控制在 4000 字內。", ephemeral=True)
            return

        await interaction.response.defer()
        result = await self.generate(
            "請使用繁體中文回答。回答自然、清楚，直接處理使用者的問題，不要提及這段系統提示。\n\n"
            + prompt
        )
        await self.send_result(interaction, result)

    @ai.command(name="translate", description="使用 Gemini 翻譯文字")
    @app_commands.describe(
        text="要翻譯的文字",
        target="目標語言，例如繁體中文、英文、日文",
    )
    @app_commands.checks.cooldown(1, 5.0, key=lambda interaction: interaction.user.id)
    async def translate(
        self,
        interaction: discord.Interaction,
        text: str,
        target: str = "繁體中文",
    ):
        text = text.strip()
        target = target.strip() or "繁體中文"

        if not text:
            await interaction.response.send_message("請輸入要翻譯的文字。", ephemeral=True)
            return
        if len(text) > 4000:
            await interaction.response.send_message("文字太長了，請控制在 4000 字內。", ephemeral=True)
            return

        await interaction.response.defer()
        result = await self.generate(
            f"請把以下文字翻譯成{target}。只輸出翻譯結果，不要額外解釋。\n\n{text}"
        )
        await self.send_result(interaction, result)

    @ai.command(name="summarize", description="使用 Gemini 摘要文字")
    @app_commands.describe(text="要整理的文字")
    @app_commands.checks.cooldown(1, 5.0, key=lambda interaction: interaction.user.id)
    async def summarize(self, interaction: discord.Interaction, text: str):
        text = text.strip()

        if not text:
            await interaction.response.send_message("請輸入要整理的文字。", ephemeral=True)
            return
        if len(text) > 10000:
            await interaction.response.send_message("文字太長了，請控制在 10000 字內。", ephemeral=True)
            return

        await interaction.response.defer()
        result = await self.generate(
            "請使用繁體中文，把以下文字整理成清楚的重點摘要，保留重要資訊。\n\n"
            + text
        )
        await self.send_result(interaction, result)


async def setup(bot: commands.Bot):
    await bot.add_cog(AICog(bot))
