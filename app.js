(()=>{
"use strict";
const C=Object.assign({
  brandName:"Discord Bot",
  creator:"Your Name",
  version:"v1.0.0",
  inviteUrl:"",
  supportUrl:"",
  statusEndpoint:""
},window.BOT_SITE_CONFIG||{});

const COMMANDS=[
  {name:"/spam",category:"Core",title:"多頻道訊息發送",desc:"選擇多個文字頻道並發送指定內容與次數。",params:"content / count",example:"/spam content:你好 count:10"},
  {name:"/stopspam",category:"Control",title:"停止進行中的發送",desc:"停止自己目前的工作；具備權限者可停止指定使用者。",params:"target?",example:"/stopspam"},
  {name:"/history",category:"History & Cleanup",title:"歷史訊息清理",desc:"搜尋指定頻道範圍的歷史訊息，並依成員或內容篩選。",params:"channels / member / content",example:"/history"}
];

const $=(selector,root=document)=>root.querySelector(selector);
const $$=(selector,root=document)=>Array.from(root.querySelectorAll(selector));

function toast(message,warning=false){
  const el=document.createElement("div");
  el.className="toast"+(warning?" warn":"");
  el.textContent=message;
  document.body.appendChild(el);
  requestAnimationFrame(()=>el.classList.add("show"));
  setTimeout(()=>{
    el.classList.remove("show");
    setTimeout(()=>el.remove(),220);
  },2600);
}

function setupLinks(){
  $$(".invite-link").forEach(a=>{
    if(C.inviteUrl){
      a.href=C.inviteUrl;
      a.target="_blank";
      a.rel="noreferrer";
    }else{
      a.href="#";
      a.addEventListener("click",e=>{
        e.preventDefault();
        toast("尚未設定 inviteUrl，請在 site-config.js 填入 Discord 邀請連結。",true);
      });
    }
  });
  $$(".support-link").forEach(a=>{
    if(C.supportUrl){
      a.href=C.supportUrl;
      a.target="_blank";
      a.rel="noreferrer";
    }else{
      a.href="#";
      a.addEventListener("click",e=>{
        e.preventDefault();
        toast("尚未設定 supportUrl，請在 site-config.js 填入支援社群連結。",true);
      });
    }
  });
}

function renderCommands(filter="all",query=""){
  const root=$("#commands");
  if(!root)return;
  const q=query.trim().toLowerCase();
  const data=COMMANDS.filter(c=>
    (filter==="all"||c.category===filter)&&
    (!q||[c.name,c.category,c.title,c.desc,c.params].join(" ").toLowerCase().includes(q))
  );

  if(!data.length){
    root.innerHTML='<div class="demo-result">找不到符合條件的指令。</div>';
    return;
  }

  root.innerHTML=data.map(c=>(
    '<article class="command">'+
      '<div>'+
        '<div class="command-name"><code>'+c.name+'</code><span class="tag">'+c.category+'</span><span class="tag">'+c.params+'</span></div>'+
        '<h3>'+c.title+'</h3>'+
        '<p>'+c.desc+'</p>'+
      '</div>'+
      '<div class="command-side"><span class="example">'+c.example+'</span><button class="copy" type="button" data-copy="'+encodeURIComponent(c.example)+'">複製</button></div>'+
    '</article>'
  )).join("");

  $$(".copy",root).forEach(button=>{
    button.addEventListener("click",async()=>{
      const value=decodeURIComponent(button.dataset.copy||"");
      try{
        await navigator.clipboard.writeText(value);
        button.textContent="已複製";
        toast("已複製指令範例。");
        setTimeout(()=>button.textContent="複製",1200);
      }catch{
        toast(value);
      }
    });
  });
}

function setupCommands(){
  renderCommands();
  $$(".filter").forEach(button=>{
    button.addEventListener("click",()=>{
      $$(".filter").forEach(x=>x.classList.remove("active"));
      button.classList.add("active");
      renderCommands(button.dataset.filter||"all",$("#commandSearch")?.value||"");
    });
  });
  const search=$("#commandSearch");
  if(search)search.addEventListener("input",()=>renderCommands($(".filter.active")?.dataset.filter||"all",search.value));
  const clear=$("#clearSearch");
  if(clear)clear.addEventListener("click",()=>{
    if(search)search.value="";
    renderCommands($(".filter.active")?.dataset.filter||"all","");
  });
}

function setupTheme(){
  const button=$("#themeBtn");
  if(!button)return;
  let theme=localStorage.getItem("bot-site-theme")||(matchMedia("(prefers-color-scheme:light)").matches?"light":"dark");
  const apply=()=>{
    document.documentElement.dataset.theme=theme;
    button.textContent=theme==="light"?"☼":"◐";
    localStorage.setItem("bot-site-theme",theme);
  };
  apply();
  button.addEventListener("click",()=>{
    theme=theme==="light"?"dark":"light";
    apply();
  });
}

function setupMobileMenu(){
  const button=$("#menuBtn");
  const nav=$(".nav-links");
  if(!button||!nav)return;
  button.addEventListener("click",()=>nav.classList.toggle("mobile-open"));
  nav.querySelectorAll("a").forEach(a=>a.addEventListener("click",()=>nav.classList.remove("mobile-open")));
}

function setupDemos(){
  const choose=$("#chooseBtn");
  if(choose)choose.addEventListener("click",()=>{
    const values=$$(".choice").slice(0,3).map(x=>x.value.trim()).filter(Boolean);
    if(!values.length){toast("至少輸入一個選項。",true);return;}
    $("#chooseResult").textContent="結果： "+values[Math.floor(Math.random()*values.length)];
  });

  const anonButton=$("#anonBtn");
  if(anonButton)anonButton.addEventListener("click",()=>{
    const value=$("#anonInput")?.value.trim();
    if(!value){toast("先輸入一段留言。",true);return;}
    $("#anonResult").textContent="匿名玩家： "+value;
  });
}

function updateService(serviceId,dotId,label,good=true){
  const textEl=$(serviceId);
  const dotEl=$(dotId);
  if(textEl)textEl.textContent=label;
  if(dotEl)dotEl.className="service-dot"+(good?" good":" bad");
}

async function loadStatus(){
  const endpoint=C.statusEndpoint;
  if(!endpoint){
    $("#statusTitle").textContent="Status data unavailable";
    $("#statusDetail").textContent="尚未設定公開心跳端點。";
    $("#lastUpdate").textContent="Not connected";
    $("#heroStatus").textContent="Unknown";
    $("#heroState").textContent="PLATFORM READY";
    return;
  }

  try{
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),6500);
    const response=await fetch(endpoint,{
      cache:"no-store",
      signal:controller.signal,
      headers:{Accept:"application/json"}
    });
    clearTimeout(timer);
    if(!response.ok)throw new Error("status "+response.status);

    const data=await response.json();
    const status=data.status==="online"||data.status==="operational"
      ?"operational"
      :data.status==="degraded"
      ?"degraded"
      :data.status==="offline"
      ?"offline"
      :"unknown";

    const labels={
      operational:"All Systems Operational",
      degraded:"Partial Degradation",
      offline:"Bot Offline",
      unknown:"Status data unavailable"
    };

    $("#statusTitle").textContent=labels[status];
    $("#statusDetail").textContent=data.message||"Live heartbeat connected.";
    $("#lastUpdate").textContent=data.updatedAt?new Date(data.updatedAt).toLocaleString("zh-TW"):"Just now";
    $("#heroStatus").textContent=status==="operational"?"Operational":status;
    $("#heroState").textContent=status==="operational"?"LIVE PLATFORM":"PLATFORM CHECK";
    $("#statusDot").className="status-big-dot "+status;
    $("#statLatency").textContent=Number.isFinite(Number(data.latency))?Math.round(Number(data.latency))+" ms":"—";
    $("#statServers").textContent=data.servers!=null?Number(data.servers).toLocaleString():"—";
    $("#statUptime").textContent=data.uptime||"—";

    updateService("#botService","#botDot",status==="operational"?"Operational":status==="offline"?"Offline":"Unavailable",status==="operational");
    updateService("#apiService","#apiDot",data.api===false?"Unavailable":"Operational",data.api!==false);
    updateService("#dbService","#dbDot",data.database===false?"Unavailable":"Operational",data.database!==false);
  }catch{
    $("#statusTitle").textContent="Status data unavailable";
    $("#statusDetail").textContent="無法取得即時心跳資料。";
    $("#lastUpdate").textContent="Fetch failed";
    $("#heroStatus").textContent="Unavailable";
    $("#heroState").textContent="STATUS UNAVAILABLE";
    $("#statusDot").className="status-big-dot offline";
    updateService("#botService","#botDot","Unavailable",false);
    updateService("#apiService","#apiDot","Unavailable",false);
    updateService("#dbService","#dbDot","Unknown",false);
  }
}

function setup(){
  document.title=C.brandName+" — Official";
  const version=$("#versionText");
  const year=$("#year");
  if(version)version.textContent=C.version;
  if(year)year.textContent=new Date().getFullYear();
  setupLinks();
  setupCommands();
  setupTheme();
  setupMobileMenu();
  setupDemos();
  loadStatus();
  if(C.statusEndpoint)setInterval(loadStatus,30000);
}

document.addEventListener("DOMContentLoaded",setup);
})();