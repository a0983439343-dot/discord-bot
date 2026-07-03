import discord
from discord import app_commands, ui
from discord.ext import commands
import asyncio
import os

active_spam = {}
MAX_COUNT = 1000000000000
MAX_CONTENT_LEN = 2000
OWNER_ID = 1140900506198351924
GUILD_ID = discord.Object(id=1509184700294627430)
ALLOWED_ROLE_ID = 1509577038443319416

class SpamBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.guilds = True
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        self.tree.copy_global_to(guild=GUILD_ID)
        try:
            await self.tree.sync(guild=GUILD_ID)
        except Exception as e:
            print(f"Sync error: {e}")

bot = SpamBot()

@bot.tree.error
async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    msg = f"❌ 指令執行發生錯誤: {error}"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass

async def run_spam(user_id: int, notify_channel, target_channels: list, content: str, count: int):
    sent_count = 0
    failed_channels = set()

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
                if ch.id in failed_channels:
                    continue
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
                            failed_channels.add(ch.id)
                            await notify(f'⚠️ {ch.name} 遭遇阻礙，已停止該頻道發送: {e.text}')
                            break
            await asyncio.sleep(0.01)

        await notify(f'✅ 發送完成 共 {sent_count} 則訊息')
    except asyncio.CancelledError:
        await notify(f'指令已終止，共發送 {sent_count} 則訊息。')
        raise
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
        self.stop()
        try:
            await interaction.response.edit_message(content="⏳ 正在驗證頻道權限...", view=None)
        except Exception:
            pass

@bot.tree.command(name="spam", description="在多個頻道執行指令")
@app_commands.describe(content="內容", count="次數")
async def spam(interaction: discord.Interaction, content: str, count: int):
    if not interaction.guild:
        await interaction.response.send_message('❌ 此指令僅能在伺服器中使用', ephemeral=True)
        return

    if interaction.user.id in active_spam:
        await interaction.response.send_message('⚠️ 您目前已有正在執行的指令', ephemeral=True)
        return

    member = interaction.guild.get_member(interaction.user.id)
    if not member:
        await interaction.response.send_message('❌ 無法取得使用者資訊', ephemeral=True)
        return

    user_roles = [role.id for role in member.roles]
    is_admin = member.guild_permissions.administrator
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

    active_spam[interaction.user.id] = {"running": False, "task": None}
    view = ChannelSelectView()
    await interaction.response.send_message("請選擇要發送的頻道：", view=view, ephemeral=True)
    await view.wait()

    if not view.selected_channels:
        active_spam.pop(interaction.user.id, None)
        await interaction.followup.send('⌛ 選擇逾時或已取消', ephemeral=True)
        return

    guild_me = interaction.guild.get_member(bot.user.id)
    if not guild_me:
        active_spam.pop(interaction.user.id, None)
        await interaction.followup.send('❌ 無法取得機器人權限資訊', ephemeral=True)
        return

    valid_channels = []
    skipped_channels = []
    
    for ch in view.selected_channels:
        resolved = ch.resolve() or interaction.guild.get_channel(ch.id)
        if resolved and isinstance(resolved, (discord.TextChannel, discord.Thread)):
            perms = resolved.permissions_for(guild_me)
            send_allowed = perms.send_messages or getattr(perms, 'send_messages_in_threads', False)
            if perms.view_channel and send_allowed:
                valid_channels.append(resolved)
            else:
                skipped_channels.append(resolved.name)
        else:
            skipped_channels.append(str(ch.id))

    if not valid_channels:
        active_spam.pop(interaction.user.id, None)
        await interaction.followup.send(f'❌ 無法在所選頻道發送訊息 (缺少權限: {", ".join(skipped_channels)})', ephemeral=True)
        return

    active_spam[interaction.user.id] = {"running": True}
    embed = discord.Embed(title="✅ Spam Success", description=f"發送次數: {count}\n目標: {', '.join([c.mention for c in valid_channels])}", color=0x2ecc71)
    if skipped_channels:
        embed.add_field(name="⚠️ 跳過的頻道", value=", ".join(skipped_channels))
    
    await interaction.followup.send(embed=embed, ephemeral=True)
    task = asyncio.create_task(run_spam(interaction.user.id, interaction.channel, valid_channels, content, count))
    active_spam[interaction.user.id]["task"] = task

@bot.tree.command(name="stopspam", description="終止進行中的指令")
@app_commands.describe(member="指定想終止指令的使用者")
async def stopspam(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user

    invoker = interaction.guild.get_member(interaction.user.id)
    if not invoker:
        await interaction.response.send_message("❌ 無法取得使用者資訊", ephemeral=True)
        return

    user_roles = [role.id for role in invoker.roles]
    is_admin = invoker.guild_permissions.administrator
    
    if not is_admin and interaction.user.id != OWNER_ID and ALLOWED_ROLE_ID not in user_roles and interaction.user.id != target.id:
        await interaction.response.send_message("❌ 無權限", ephemeral=True)
        return

    if target.id in active_spam:
        active_spam[target.id]["running"] = False
        task = active_spam[target.id].get("task")
        if task and not task.done():
            task.cancel()
        await interaction.response.send_message(f"✅ 已終止 <@{target.id}> 的指令", ephemeral=True)
    else:
        await interaction.response.send_message("ℹ️ 目前並無執行中的指令", ephemeral=True)

@bot.tree.command(name="history", description="搜尋並刪除頻道歷史訊息")
@app_commands.describe(count="搜尋範圍 (1-1000)", member="篩選使用者", content="篩選內容", ch1="頻道1", ch2="頻道2", ch3="頻道3")
async def history_cmd(interaction: discord.Interaction, count: app_commands.Range[int, 1, 1000], ch1: discord.TextChannel = None, ch2: discord.TextChannel = None, ch3: discord.TextChannel = None, member: discord.Member = None, content: str = None):
    invoker = interaction.guild.get_member(interaction.user.id)
    if not invoker:
        await interaction.response.send_message('❌ 無法取得使用者資訊', ephemeral=True)
        return

    user_roles = [role.id for role in invoker.roles]
    is_admin = invoker.guild_permissions.administrator
    
    if interaction.user.id != OWNER_ID and not is_admin and ALLOWED_ROLE_ID not in user_roles:
        await interaction.response.send_message('❌ 無權限', ephemeral=True)
        return

    target_channels = [c for c in [ch1, ch2, ch3] if c is not None] or [interaction.channel]
    guild_me = interaction.guild.get_member(bot.user.id)
    
    if not guild_me:
        await interaction.response.send_message('❌ 無法取得機器人資訊', ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    total_deleted = 0

    def check(msg):
        if member and msg.author.id != member.id: return False
        if content and content not in msg.content: return False
        return True

    for ch in target_channels:
        perms = ch.permissions_for(guild_me)
        if not perms.manage_messages or not perms.read_message_history:
            await interaction.followup.send(f'❌ 機器人在 {ch.mention} 缺乏必要權限', ephemeral=True)
            continue
            
        try:
            deleted = await ch.purge(limit=count, check=check)
            total_deleted += len(deleted)
            await asyncio.sleep(1)
        except discord.HTTPException as e:
            await interaction.followup.send(f"⚠️ {ch.mention} 清理失敗: HTTP {e.status}", ephemeral=True)

    await interaction.followup.send(f"✅ 完成，共刪除 {total_deleted} 則訊息", ephemeral=True)

bot.run(os.environ["DISCORD_TOKEN"])
