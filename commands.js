window.BOT_COMMANDS=[
{name:"/spam",category:"Core",title:"多頻道訊息發送",desc:"由授權使用者選擇多個文字頻道後執行訊息發送，會檢查機器人是否具備發送權限。",params:"content, count",example:"/spam Hello 10"},
{name:"/stopspam",category:"Control",title:"停止進行中的發送",desc:"停止自己或在具備權限時停止指定使用者目前執行中的發送工作。",params:"member?",example:"/stopspam"},
{name:"/history",category:"History & Cleanup",title:"歷史訊息清理",desc:"搜尋指定範圍的歷史訊息，可依成員或內容篩選，並在機器人具有必要權限時刪除符合條件的訊息。",params:"count, channels?, member?, content?",example:"/history 100"}];