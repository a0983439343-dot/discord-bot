import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

active_spam = {}

MAX_COUNT = 1000000000000
MAX_CONTENT_LEN = 2000
GUILD_ID = discord.Object(id=1509184700294627430)
ALLOWED_ROLE_ID = 1509577038443319416

@bot.event
async def on_ready():
    print(f'{bot.user} 系統已成功連線並啟動')
    try:
        bot.tree.copy_global_to(guild=GUILD_ID)
        synced = await bot.tree.sync(guild=GUILD_ID)
        print(f"已成功同步 {len(synced)} 項伺服器指令")
    except Exception as e:
        print(f"同步指令時發生錯誤: {e}")

async def run_spam(user_id: int, notify_channel, target_channels: list, content: str, count: int):
    sent_count = 0

    async def notify(msg: str):
        if notify_channel is None:
            print(f"[notify] user={user_id} | {msg}")
            return
        try:
            await notify_channel.send(f"<@{user_id}> {msg}")
        except Exception as e:
            print(f"[notify 失敗] {e}")

    try:
        for _ in range(count):
            if not active_spam.get(user_id, {}).get("running", False):
                await notify(f'指令已終止，共發送 {sent_count} 則訊息')
                return

            for ch in target_channels:
                while True:
                    try:
                        await ch.send(content)
                        sent_count += 1
                        break
                    except discord.HTTPException as e:
                        if e.status == 429:
                            retry_after = getattr(e, 'retry_after', 2.0)
                            elapsed = 0.0
                            while elapsed < retry_after:
                                if not active_spam.get(user_id, {}).get("running", False):
                                    await notify(f'指令已終止，共發送 {sent_count} 則訊息')
                                    return
                                chunk = min(0.2, retry_after - elapsed)
                                await asyncio.sleep(chunk)
                                elapsed += chunk
                        else:
                            await notify(f'⚠️ {ch.name} 遭遇阻礙：{e.text}')
                            break

            await asyncio.sleep(0.01)

        await notify(f'✅ 發送完成，共發送 {sent_count} 則訊息')
    except Exception as e:
        print(f"執行指令時發生系統例外: {e}")
        try:
            await notify(f"❌ 發生非預期錯誤，指令已中止（已發送 {sent_count} 則）")
        except Exception:
            pass
    finally:
        active_spam.pop(user_id, None)

class ChannelSelectView(discord.ui.View):
    def __init__(self, user_id: int, content: str, count: int, notify_channel):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.content = content
        self.count = count
        self.notify_channel = notify_channel
        self.done = False
        self.message: discord.Message | None = None

    @discord.ui.channel_select(
        placeholder="選擇目標頻道（最多3個）",
        min_values=1,
        max_values=3,
        channel_types=[discord.ChannelType.text]
    )
    async def select_channels(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ 這不是你的指令", ephemeral=True)
            return

        self.done = True
        self.stop()

        guild_me = interaction.guild.me
        if guild_me is None:
            await interaction.response.edit_message(content="❌ 無法取得機器人的伺服器成員資訊", embed=None, view=None)
            active_spam.pop(self.user_id, None)
            return

        target_channels = []
        for raw_ch in select.values:
            ch = interaction.guild.get_channel(raw_ch.id)
            if ch is None:
                try:
                    ch = await interaction.guild.fetch_channel(raw_ch.id)
                except Exception:
                    pass

            if not isinstance(ch, discord.TextChannel):
                await interaction.response.edit_message(content=f"❌ 頻道資料載入失敗或不支援非文字頻道", embed=None, view=None)
                active_spam.pop(self.user_id, None)
                return

            perms = ch.permissions_for(guild_me)
            if not perms.view_channel or not perms.send_messages:
                await interaction.response.edit_message(content=f"❌ 機器人在 {ch.mention} 缺乏必要權限", embed=None, view=None)
                active_spam.pop(self.user_id, None)
                return

            target_channels.append(ch)

        total = self.count * len(target_channels)
        channel_mentions = ', '.join([c.mention for c in target_channels])
        embed = discord.Embed(
            title="✅ Spam 已啟動",
            description=f"目標頻道: {channel_mentions}\n每頻道次數: {self.count}（合計 {total} 則）",
            color=0x2ecc71
        )
        await interaction.response.edit_message(content="", embed=embed, view=None)

        asyncio.create_task(run_spam(self.user_id, self.notify_channel, target_channels, self.content, self.count))

    async def on_timeout(self):
        if not self.done:
            active_spam.pop(self.user_id, None)
            if self.message:
                try:
                    await self.message.edit(content="⏰ 已逾時，指令取消", view=None)
                except Exception:
                    pass

@bot.tree.command(name="spam", description="在指定頻道執行指令")
@app_commands.describe(
    content="請輸入想發送的訊息內容",
    count=f"請輸入發送次數（1～{MAX_COUNT}）"
)
async def spam(interaction: discord.Interaction, content: str, count: int):
    if not interaction.guild:
        await interaction.response.send_message('❌ 此指令僅能在伺服器中使用', ephemeral=True)
        return

    if count < 1 or count > MAX_COUNT:
        await interaction.response.send_message(f'❌ 發送次數必須介於 1 到 {MAX_COUNT} 之間', ephemeral=True)
        return

    if not content:
        await interaction.response.send_message('❌ 訊息內容不可為空', ephemeral=True)
        return

    if len(content) > MAX_CONTENT_LEN:
        await interaction.response.send_message(f'❌ 訊息內容不可超過 {MAX_CONTENT_LEN} 字元', ephemeral=True)
        return

    user_id = interaction.user.id
    if user_id in active_spam and active_spam[user_id].get("running"):
        await interaction.response.send_message('⚠️ 您目前已有正在執行的指令，請等待當前指令結束', ephemeral=True)
        return

    if interaction.guild.me is None:
        await interaction.response.send_message('❌ 無法取得機器人的伺服器成員資訊', ephemeral=True)
        return

    active_spam[user_id] = {"running": True}

    view = ChannelSelectView(user_id, content, count, interaction.channel)
    await interaction.response.send_message("📌 請選擇目標頻道（30 秒內選擇）", view=view)
    view.message = await interaction.original_response()

@bot.tree.command(name="stopspam", description="終止進行中的指令")
@app_commands.describe(member="指定想終止指令的使用者 (未填寫則預設為操作者本人)")
async def stopspam(interaction: discord.Interaction, member: discord.Member = None):
    if not interaction.guild:
        await interaction.response.send_message('❌ 此指令僅能在伺服器中使用。', ephemeral=True)
        return

    target = member if member else interaction.user

    user_roles = [role.id for role in interaction.user.roles]
    is_admin = interaction.user.guild_permissions.administrator

    if (interaction.user.id != 1140900506198351924 and
            not is_admin and
            ALLOWED_ROLE_ID not in user_roles and
            interaction.user.id != target.id):
        await interaction.response.send_message("❌ 您未具備終止其他使用者指令的權限", ephemeral=True)
        return

    if target.id in active_spam and active_spam[target.id].get("running"):
        active_spam[target.id]["running"] = False
        await interaction.response.send_message(f"✅ 已終止 {target.mention} 的指令")
    else:
        await interaction.response.send_message(f"ℹ️ 狀態查詢：{target.mention} 目前並無執行中的指令", ephemeral=True)

bot.run(os.environ.get("DISCORD_TOKEN"))

