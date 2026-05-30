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

@bot.event
async def on_ready():
    print(f'{bot.user} 系統已成功連線並啟動')
    try:
        bot.tree.copy_global_to(guild=GUILD_ID)
        synced = await bot.tree.sync(guild=GUILD_ID)
        print(f"已成功同步 {len(synced)} 項伺服器指令")
    except Exception as e:
        print(f"同步指令時發生錯誤: {e}")

@bot.tree.command(name="spam", description="在指定頻道執行指令 (不選則預設當前頻道)")
@app_commands.describe(
    content="請輸入想發送的訊息內容",
    count=f"請輸入發送次數（1～{MAX_COUNT}）",
    ch1="頻道1 (選填)",
    ch2="頻道2 (選填)",
    ch3="頻道3 (選填)"
)
async def spam(
    interaction: discord.Interaction, 
    content: str, 
    count: int, 
    ch1: discord.TextChannel = None, 
    ch2: discord.TextChannel = None, 
    ch3: discord.TextChannel = None
):
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

    target_channels = [c for c in [ch1, ch2, ch3] if c is not None]
    if not target_channels:
        target_channels = [interaction.channel]

    guild_me = interaction.guild.me
    if guild_me is None:
        await interaction.response.send_message('❌ 無法取得機器人的伺服器成員資訊。', ephemeral=True)
        return

    for ch in target_channels:
        if not isinstance(ch, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
            await interaction.response.send_message(f'❌ {ch.name} 不支援或頻道資料未載入。', ephemeral=True)
            return
        
        perms = ch.permissions_for(guild_me)
        if not perms.view_channel or not perms.send_messages:
            await interaction.response.send_message(f'❌ 機器人在 {ch.mention} 缺乏必要權限。', ephemeral=True)
            return

    active_spam[user_id] = {"running": True}
    sent_count = 0

    async def notify(msg: str):
        try:
            await interaction.followup.send(f"<@{user_id}> {msg}")
        except Exception:
            try:
                await interaction.channel.send(f"<@{user_id}> {msg}")
            except Exception:
                pass

    try:
        channel_mentions = ', '.join([c.mention for c in target_channels])
        embed = discord.Embed(title="✅ Spam Success", description=f"目標頻道: {channel_mentions}\n發送次數: {count}", color=0x2ecc71)
        await interaction.response.send_message(embed=embed)

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

            await asyncio.sleep(0)

        await notify(f'✅ 發送完成，共發送 {sent_count} 則訊息。')
    except Exception as e:
        print(f"執行指令時發生系統例外: {e}")
        try:
            await notify(f"❌ 發生非預期錯誤，指令已中止（已發送 {sent_count} 則）。")
        except Exception:
            pass
    finally:
        active_spam.pop(user_id, None)

@bot.tree.command(name="stopspam", description="終止進行中的指令")
@app_commands.describe(member="指定想終止指令的使用者 (未填寫則預設為操作者本人)")
async def stopspam(interaction: discord.Interaction, member: discord.Member = None):
    if not interaction.guild:
        await interaction.response.send_message('❌ 此指令僅能在伺服器中使用。', ephemeral=True)
        return

    target = member if member else interaction.user
    ALLOWED_ROLE_ID = 1509577038443319416

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
