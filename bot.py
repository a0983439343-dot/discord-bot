import discord
from discord import app_commands, ui
from discord.ext import commands
import asyncio
import os

active_spam = {}

MAX_COUNT = 1000000000000
MAX_CONTENT_LEN = 2000
GUILD_ID = discord.Object(id=1509184700294627430)
ALLOWED_ROLE_ID = 1509577038443319416
OWNER_ID = 1140900506198351924

class SpamBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        self.tree.copy_global_to(guild=GUILD_ID)
        try:
            await self.tree.sync(guild=GUILD_ID)
        except Exception as e:
            print(f"Sync error: {e}")

bot = SpamBot()

@bot.event
async def on_ready():
    print(f"{bot.user} online")

async def run_spam(user_id: int, notify_channel, target_channels: list, content: str, count: int):
    sent_count = 0

    async def notify(msg: str):
        if notify_channel:
            try:
                await notify_channel.send(f"<@{user_id}> {msg}")
            except Exception:
                pass

    try:
        for _ in range(count):
            if not active_spam.get(user_id, {}).get("running", False):
                await notify(f'指令已終止，共發送 {sent_count} 則訊息。')
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
                                    await notify(f'指令已終止，共發送 {sent_count} 則訊息。')
                                    return
                                chunk = min(0.2, retry_after - elapsed)
                                await asyncio.sleep(chunk)
                                elapsed += chunk
                        else:
                            await notify(f'⚠️ {ch.name} 遭遇阻礙：{e.text}')
                            break
            await asyncio.sleep(0.01)

        await notify(f'✅ 發送完成 共 {sent_count} 則訊息')
    except Exception:
        try:
            await notify(f"❌ 發生非預期錯誤，指令已中止（已發送 {sent_count} 則）")
        except Exception:
            pass
    finally:
        active_spam.pop(user_id, None)

class ChannelSelectView(ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.selected_channels = []
        self.select_menu = ui.ChannelSelect(
            channel_types=[discord.ChannelType.text, discord.ChannelType.public_thread],
            min_values=1,
            max_values=25
        )
        self.select_menu.callback = self.select_callback
        self.add_item(self.select_menu)

    async def select_callback(self, interaction: discord.Interaction):
        self.selected_channels = self.select_menu.values
        await interaction.response.edit_message(content="⏳ 正在驗證頻道權限...", view=None)
        self.stop()

@bot.tree.command(name="spam", description="在多個頻道執行指令")
@app_commands.describe(content="請輸入想發送的訊息內容", count="發送次數")
async def spam(interaction: discord.Interaction, content: str, count: int):
    if not interaction.guild:
        await interaction.response.send_message('❌ 此指令僅能在伺服器中使用', ephemeral=True)
        return

    user_roles = [role.id for role in interaction.user.roles]
    is_admin = interaction.user.guild_permissions.administrator
    has_role = ALLOWED_ROLE_ID in user_roles

    if not is_admin and interaction.user.id != OWNER_ID and not has_role:
        await interaction.response.send_message('❌ 您沒有使用此指令的權限', ephemeral=True)
        return

    if not 1 <= count <= MAX_COUNT:
        await interaction.response.send_message(f'❌ 發送次數必須介於 1 到 {MAX_COUNT} 之間', ephemeral=True)
        return

    if not content or len(content) > MAX_CONTENT_LEN:
        await interaction.response.send_message('❌ 訊息內容長度錯誤', ephemeral=True)
        return

    user_id = interaction.user.id
    if active_spam.get(user_id, {}).get("running", False):
        await interaction.response.send_message('⚠️ 您目前已有正在執行的指令', ephemeral=True)
        return

    guild_me = interaction.guild.get_member(bot.user.id)
    if not guild_me:
        await interaction.response.send_message('❌ 無法取得機器人的伺服器成員資訊', ephemeral=True)
        return

    active_spam[user_id] = {"running": False}

    view = ChannelSelectView()
    await interaction.response.send_message("請選擇要發送的頻道：", view=view, ephemeral=True)
    await view.wait()

    if not view.selected_channels:
        active_spam.pop(user_id, None)
        await interaction.followup.send('⌛ 選擇逾時，指令已取消', ephemeral=True)
        return

    valid_channels = []
    for ch in view.selected_channels:
        resolved = ch.resolve() or interaction.guild.get_channel(ch.id)
        if resolved and isinstance(resolved, (discord.TextChannel, discord.Thread)):
            perms = resolved.permissions_for(guild_me)
            if perms.view_channel and perms.send_messages:
                valid_channels.append(resolved)

    if not valid_channels:
        active_spam.pop(user_id, None)
        await interaction.followup.send('❌ 機器人在所選頻道缺乏權限', ephemeral=True)
        return

    active_spam[user_id] = {"running": True}
    channel_mentions = ', '.join([c.mention for c in valid_channels])
    embed = discord.Embed(title="✅ Spam Success", description=f"目標頻道: {channel_mentions}\n發送次數: {count}", color=0x2ecc71)
    await interaction.followup.send(embed=embed, ephemeral=True)

    task = asyncio.create_task(run_spam(user_id, interaction.channel, valid_channels, content, count))
    active_spam[user_id]["task"] = task

@bot.tree.command(name="stopspam", description="終止進行中的指令")
@app_commands.describe(member="指定想終止指令的使用者")
async def stopspam(interaction: discord.Interaction, member: discord.Member = None):
    if not interaction.guild:
        await interaction.response.send_message('❌ 此指令僅能在伺服器中使用。', ephemeral=True)
        return

    target = member or interaction.user
    user_roles = [role.id for role in interaction.user.roles]
    is_admin = interaction.user.guild_permissions.administrator
    has_role = ALLOWED_ROLE_ID in user_roles

    if not is_admin and interaction.user.id != OWNER_ID and not has_role and interaction.user.id != target.id:
        await interaction.response.send_message("❌ 您未具備終止其他使用者指令的權限", ephemeral=True)
        return

    if active_spam.get(target.id, {}).get("running"):
        active_spam[target.id]["running"] = False
        await interaction.response.send_message(f"✅ 已終止 <@{target.id}> 的指令", ephemeral=True)
    else:
        await interaction.response.send_message("ℹ️ 目前並無執行中的指令", ephemeral=True)

@bot.tree.command(name="history", description="搜尋並刪除頻道歷史訊息")
@app_commands.describe(count="搜尋範圍", member="篩選使用者", content="篩選內容", ch1="頻道1", ch2="頻道2", ch3="頻道3")
async def history_cmd(interaction: discord.Interaction, count: int, ch1: discord.TextChannel = None, ch2: discord.TextChannel = None, ch3: discord.TextChannel = None, member: discord.Member = None, content: str = None):
    if not interaction.guild:
        await interaction.response.send_message('❌ 此指令僅能在伺服器中使用', ephemeral=True)
        return

    user_roles = [role.id for role in interaction.user.roles]
    is_admin = interaction.user.guild_permissions.administrator
    has_role = ALLOWED_ROLE_ID in user_roles

    if interaction.user.id != OWNER_ID and not is_admin and not has_role:
        await interaction.response.send_message('❌ 您沒有使用此指令的權限', ephemeral=True)
        return

    if count < 1:
        await interaction.response.send_message('❌ 搜尋範圍必須大於 0', ephemeral=True)
        return

    target_channels = [c for c in [ch1, ch2, ch3] if c is not None] or [interaction.channel]
    guild_me = interaction.guild.get_member(bot.user.id)

    if not guild_me:
        await interaction.response.send_message('❌ 無法取得機器人的伺服器成員資訊', ephemeral=True)
        return

    for ch in target_channels:
        if not isinstance(ch, (discord.TextChannel, discord.Thread)):
            await interaction.response.send_message('❌ 不支援或頻道資料未載入', ephemeral=True)
            return
        perms = ch.permissions_for(guild_me)
        if not perms.manage_messages or not perms.read_message_history:
            await interaction.response.send_message('❌ 機器人缺乏必要權限', ephemeral=True)
            return

    await interaction.response.defer(ephemeral=True)
    total_deleted = 0

    def check(msg):
        if member and msg.author.id != member.id: return False
        if content and content not in msg.content: return False
        return True

    for ch in target_channels:
        try:
            deleted = await ch.purge(limit=count, check=check)
            total_deleted += len(deleted)
        except Exception as e:
            await interaction.followup.send(f"⚠️ {ch.mention} 清理失敗: {e}", ephemeral=True)

    embed = discord.Embed(
        title="✅ History 完成", 
        description=f"共刪除 {total_deleted} 則訊息\n\n*(註：限制無法批次刪除 14 天前的訊息)*", 
        color=0x2ecc71
    )
    await interaction.followup.send(embed=embed, ephemeral=True)

bot.run(os.environ["DISCORD_TOKEN"])
