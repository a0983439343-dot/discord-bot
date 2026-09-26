window.BOT_COMMANDS=[
{name:"/mimic",category:"Entertainment",title:"模仿成員",desc:"以指定成員目前的暱稱與頭像建立模仿訊息。",params:"member",example:"/mimic @User"},
{name:"/roulette",category:"Entertainment",title:"Roulette",desc:"六格遊戲回合，每次射擊減少剩餘機會，命中時套用 60 秒 Timeout。",params:"無",example:"/roulette"},
{name:"/choose",category:"Entertainment",title:"隨機選擇",desc:"從多個選項中隨機選出一個，並附加趣味回應。",params:"options",example:"/choose Pizza | Burger | Ramen"},
{name:"/confess",category:"Social",title:"匿名告解",desc:"透過 Modal 提交內容，Bot 以深色 Embed 匿名發布。",params:"Modal",example:"/confess"},
{name:"/play",category:"Social",title:"揪團",desc:"建立揪團卡片，成員可以回覆參加、可能晚點或下次一定。",params:"活動內容",example:"/play"},
{name:"/suggest",category:"Social",title:"功能建議",desc:"提交功能想法或創意，安靜送入回饋中心。",params:"Modal",example:"/suggest"},
{name:"/report",category:"Social",title:"錯誤回報",desc:"提交 Bug 與問題資訊，送入回饋中心供後續處理。",params:"Modal",example:"/report"},
{name:"/owe",category:"Utilities",title:"記帳",desc:"建立一筆欠款，紀錄金額與原因。",params:"amount, reason",example:"/owe 150 Dinner"},
{name:"/pay",category:"Utilities",title:"償還",desc:"更新指定欠款為已結清或紀錄還款。",params:"debt",example:"/pay"},
{name:"/debt_list",category:"Utilities",title:"欠款列表",desc:"查看目前尚未結清的欠款。",params:"無",example:"/debt_list"},
{name:"/remind",category:"Utilities",title:"提醒",desc:"使用 30m、2h 等格式建立提醒，到期後標記目標。",params:"time, message",example:"/remind 30m 開會"},
{name:"Temporary Voice",category:"Utilities",title:"臨時語音",desc:"建立個人語音包廂，無人時自動清理。",params:"按鈕互動",example:"➕ 建立語音包廂"}
];