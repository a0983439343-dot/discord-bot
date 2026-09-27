# 部署注意事項

## 必填環境變數
- DISCORD_TOKEN：Discord Bot Token。
- GUILD_IDS：允許使用 Bot 的伺服器 ID，逗號分隔。
- OWNER_ID、ALLOWED_ROLE_ID：/spam 等受限功能使用的管理識別。

## 音樂
音樂功能除了 Python 套件外，還需要系統層級的 FFmpeg。
可以直接把 ffmpeg 放進系統 PATH，或設定 FFMPEG_PATH 指向 executable。

## 資料庫
Bot 的 SQLite 會固定放在專案目錄的 `data/bot.sqlite3`。
部署平台必須提供持久化磁碟，否則重新部署／重建環境時，XP、提醒、設定、投票、抽獎、身分組面板與筆記都可能遺失。

## 白名單
GUILD_IDS 會同時控制：
1. Slash Command 同步的伺服器。
2. 事件型功能（XP、自動回覆、防刷、歡迎／離開、語音）。
3. Bot 被加入不在白名單的伺服器時，會主動離開。

## AI
AI 回覆短內容會直接顯示；超過 Discord 訊息長度限制時會自動改成可直接開啟的 .txt 附件。
AI 指令有基本使用冷卻，避免短時間大量消耗 API。

## 匿名投票
匿名投票不再直接把 Discord 使用者 ID 存進投票紀錄；會使用 HMAC 產生只供同一場投票辨識用的匿名鍵。
