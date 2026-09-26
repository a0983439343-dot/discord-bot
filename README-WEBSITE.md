# Official Bot Website

純靜態、無網站帳號登入的官方產品網站。

## 已完成
- Premium dark/light responsive UI
- Home / Features / Commands / Docs / Permissions / Status / Statistics / Updates / FAQ / Support / About
- Command search、分類、範例複製
- Choose / Confess / LFG 互動 Demo
- Status API adapter
- Mobile navigation、theme switcher、404、favicon、robots、sitemap

## 設定
編輯 site-config.js：
brandName、creator、inviteUrl、supportUrl、githubUrl、statusEndpoint、version。

Status API 回傳 JSON：
{"status":"online","message":"Live heartbeat connected.","updatedAt":"2026-09-26T12:00:00.000Z","latency":42,"servers":128,"commands":2104823,"uptime":"99.98%","version":"v2.5.0","api":true,"database":true}

未設定 statusEndpoint 時，網站會明確顯示尚未連線，不會把假資料標成 Online。

GitHub Pages：Settings → Pages → Deploy from a branch → main / root。