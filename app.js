(()=>{
"use strict";

const C=Object.assign({
  brandName:"Discord Bot",
  shortName:"B",
  creator:"Your Name",
  version:"v1.0.0",
  inviteUrl:"",
  supportUrl:"",
  statusEndpoint:""
},window.BOT_SITE_CONFIG||{});

const fallbackCommands=[
  {name:"/spam",category:"Core",title:"多頻道訊息發送",desc:"選擇多個文字頻道並發送指定內容與次數。",params:"content / count",example:"/spam content:你好 count:10"},
  {name:"/stopspam",category:"Control",title:"停止進行中的發送",desc:"停止自己目前的工作；具備相應權限者可協助停止其他工作。",params:"target?",example:"/stopspam"},
  {name:"/history",category:"History & Cleanup",title:"歷史訊息清理",desc:"搜尋指定頻道範圍的歷史訊息，並依成員或內容篩選。",params:"channels / member / content",example:"/history"}
];

const commands=Array.isArray(window.BOT_COMMANDS)&&window.BOT_COMMANDS.length?window.BOT_COMMANDS:fallbackCommands;
const $=(s,r=document)=>r.querySelector(s);
const $$=(s,r=document)=>Array.from(r.querySelectorAll(s));

function safeText(value){return String(value??"");}
function toast(message,warning=false){
  const item=document.createElement("div");
  item.className="toast"+(warning?" warn":"");
  item.textContent=message;
  document.body.appendChild(item);
  requestAnimationFrame(()=>item.classList.add("show"));
  setTimeout(()=>{
    item.classList.remove("show");
    setTimeout(()=>item.remove(),220);
  },2600);
}

function setupConfig(){
  $$("[data-brand-name]").forEach(el=>el.textContent=C.brandName);
  const title=document.querySelector("title");
  if(title)title.textContent=C.brandName+" — Official";
  const version=$("#versionText");
  if(version)version.textContent=C.version;
  const year=$("#year");
  if(year)year.textContent=new Date().getFullYear();

  $$(".invite-link").forEach(link=>{
    if(C.inviteUrl){
      link.href=C.inviteUrl;
      link.target="_blank";
      link.rel="noopener noreferrer";
    }else{
      link.href="#";
      link.addEventListener("click",event=>{
        event.preventDefault();
        toast("目前尚未設定 Bot 邀請連結。",true);
      });
    }
  });

  $$(".support-link").forEach(link=>{
    if(C.supportUrl){
      link.href=C.supportUrl;
      link.target="_blank";
      link.rel="noopener noreferrer";
    }else{
      link.href="#";
      link.addEventListener("click",event=>{
        event.preventDefault();
        toast("目前尚未設定支援連結。",true);
      });
    }
  });
}

function setupTheme(){
  const button=$("#themeBtn");
  if(!button)return;
  let theme=localStorage.getItem("bot-site-theme");
  if(theme!=="light"&&theme!=="dark"){
    theme=matchMedia("(prefers-color-scheme:light)").matches?"light":"dark";
  }
  const apply=()=>{
    document.documentElement.dataset.theme=theme;
    button.textContent=theme==="light"?"☼":"◐";
    button.setAttribute("aria-label",theme==="light"?"切換深色模式":"切換淺色模式");
    localStorage.setItem("bot-site-theme",theme);
  };
  apply();
  button.addEventListener("click",()=>{
    theme=theme==="light"?"dark":"light";
    apply();
  });
}

function setupMenu(){
  const button=$("#menuBtn");
  const nav=$("#navLinks");
  if(!button||!nav)return;
  button.addEventListener("click",()=>{
    const open=nav.classList.toggle("mobile-open");
    button.setAttribute("aria-expanded",String(open));
  });
  $$("a",nav).forEach(link=>link.addEventListener("click",()=>{
    nav.classList.remove("mobile-open");
    button.setAttribute("aria-expanded","false");
  }));
}

function commandData(filter="all",query=""){
  const q=query.trim().toLowerCase();
  return commands.filter(command=>{
    const matchesFilter=filter==="all"||command.category===filter;
    const hay=[command.name,command.category,command.title,command.desc,command.params].map(safeText).join(" ").toLowerCase();
    return matchesFilter&&(!q||hay.includes(q));
  });
}

function renderCommands(filter="all",query=""){
  const root=$("#commandList");
  if(!root)return;
  const data=commandData(filter,query);
  if(!data.length){
    root.innerHTML='<div class="surface">找不到符合條件的指令。</div>';
    return;
  }
  root.innerHTML=data.map(command=>
    '<article class="surface interactive command-card reveal">'+
      '<div>'+
        '<div class="command-name">'+
          '<code>'+safeText(command.name)+'</code>'+
          '<span class="pill">'+safeText(command.category)+'</span>'+
          '<span class="pill">'+safeText(command.params)+'</span>'+
        '</div>'+
        '<h3>'+safeText(command.title)+'</h3>'+
        '<p>'+safeText(command.desc)+'</p>'+
      '</div>'+
      '<div class="command-side">'+
        '<span class="example" title="'+safeText(command.example)+'">'+safeText(command.example)+'</span>'+
        '<button class="copy-btn" type="button" data-copy="'+encodeURIComponent(command.example||"")+'">複製</button>'+
      '</div>'+
    '</article>'
  ).join("");
  activateInteractive(root);
  $$(".copy-btn",root).forEach(button=>{
    button.addEventListener("click",async()=>{
      const value=decodeURIComponent(button.dataset.copy||"");
      try{
        await navigator.clipboard.writeText(value);
        button.textContent="已複製";
        toast("指令已複製。");
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
      $$(".filter").forEach(item=>item.classList.remove("active"));
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

function setupButtonGlow(){
  $$(".btn,.icon-btn,.copy-btn,.filter").forEach(button=>{
    button.addEventListener("pointermove",event=>{
      const rect=button.getBoundingClientRect();
      button.style.setProperty("--btn-x",((event.clientX-rect.left)/rect.width*100)+"%");
      button.style.setProperty("--btn-y",((event.clientY-rect.top)/rect.height*100)+"%");
    });
  });
}

function activateInteractive(root=document){
  if(!matchMedia("(pointer:fine)").matches)return;
  $$(".interactive",root).forEach(card=>{
    if(card.dataset.interactiveBound==="1")return;
    card.dataset.interactiveBound="1";
    card.addEventListener("pointermove",event=>{
      const rect=card.getBoundingClientRect();
      const x=(event.clientX-rect.left)/rect.width;
      const y=(event.clientY-rect.top)/rect.height;
      const rx=(0.5-y)*7;
      const ry=(x-0.5)*8;
      card.style.setProperty("--glow-x",(x*100)+"%");
      card.style.setProperty("--glow-y",(y*100)+"%");
      card.style.setProperty("--rx",rx.toFixed(2)+"deg");
      card.style.setProperty("--ry",ry.toFixed(2)+"deg");
      card.style.transform="perspective(900px) translateY(-7px) scale(1.022) rotateX("+rx.toFixed(2)+"deg) rotateY("+ry.toFixed(2)+"deg)";
    });
    card.addEventListener("pointerleave",()=>{
      card.style.transform="";
      card.style.removeProperty("--glow-x");
      card.style.removeProperty("--glow-y");
      card.style.removeProperty("--rx");
      card.style.removeProperty("--ry");
    });
  });
}

function setupVisualGrid(){
  const grid=$("#visualGrid");
  if(!grid)return;
  grid.innerHTML=Array.from({length:36},(_,index)=>"<i data-cell='"+index+"'></i>").join("");
  const cells=$$("i",grid);
  let previous=-1;
  cells.forEach((cell,index)=>{
    cell.addEventListener("pointerenter",()=>{
      if(previous>=0)cells[previous].classList.remove("hot");
      cell.classList.add("hot");
      previous=index;
    });
  });
  grid.addEventListener("pointerleave",()=>{
    cells.forEach(cell=>cell.classList.remove("hot"));
    previous=-1;
  });
}

function setupReveal(){
  const targets=$$(".reveal");
  if(!("IntersectionObserver" in window)){
    targets.forEach(el=>el.classList.add("in"));
    return;
  }
  const observer=new IntersectionObserver(entries=>{
    entries.forEach(entry=>{
      if(entry.isIntersecting){
        entry.target.classList.add("in");
        observer.unobserve(entry.target);
      }
    });
  },{threshold:.12});
  targets.forEach(el=>observer.observe(el));
}

function setupMouse(){
  if(!matchMedia("(pointer:fine)").matches)return;
  let raf=0;
  document.addEventListener("pointermove",event=>{
    if(raf)return;
    raf=requestAnimationFrame(()=>{
      document.documentElement.style.setProperty("--mouse-x",event.clientX+"px");
      document.documentElement.style.setProperty("--mouse-y",event.clientY+"px");
      raf=0;
    });
  },{passive:true});
}

function setupScrollSpy(){
  const sections=$$("main section[id]");
  const links=$$("#navLinks a");
  if(!("IntersectionObserver" in window)||!sections.length)return;
  const map=new Map(links.map(link=>[link.getAttribute("href")?.slice(1),link]));
  const observer=new IntersectionObserver(entries=>{
    entries.forEach(entry=>{
      if(entry.isIntersecting){
        links.forEach(link=>link.classList.remove("active"));
        map.get(entry.target.id)?.classList.add("active");
      }
    });
  },{rootMargin:"-35% 0px -55% 0px",threshold:0});
  sections.forEach(section=>observer.observe(section));
}

function setupParallax(){
  if(!matchMedia("(pointer:fine)").matches)return;
  const visual=$(".hero-visual");
  if(!visual)return;
  visual.addEventListener("pointermove",event=>{
    const rect=visual.getBoundingClientRect();
    const x=(event.clientX-rect.left)/rect.width-.5;
    const y=(event.clientY-rect.top)/rect.height-.5;
    const consoleEl=$(".console",visual);
    const floatA=$(".float-a",visual);
    const floatB=$(".float-b",visual);
    if(consoleEl)consoleEl.style.transform="translate3d("+(x*8).toFixed(1)+"px,"+(y*8).toFixed(1)+"px,0)";
    if(floatA)floatA.style.transform="translate3d("+(x*-12).toFixed(1)+"px,"+(y*-8).toFixed(1)+"px,0)";
    if(floatB)floatB.style.transform="translate3d("+(x*10).toFixed(1)+"px,"+(y*7).toFixed(1)+"px,0)";
  });
  visual.addEventListener("pointerleave",()=>{
    [$(".console",visual),$(".float-a",visual),$(".float-b",visual)].forEach(el=>{if(el)el.style.transform=""});
  });
}

async function loadStatus(){
  if(!C.statusEndpoint)return;
  try{
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),6500);
    const response=await fetch(C.statusEndpoint,{cache:"no-store",signal:controller.signal,headers:{Accept:"application/json"}});
    clearTimeout(timer);
    if(!response.ok)throw new Error();
    const data=await response.json();
    const state=data.status==="online"||data.status==="operational"?"operational":data.status==="degraded"?"degraded":data.status==="offline"?"offline":"unknown";
    const labels={operational:"服務正常運作",degraded:"部分功能異常",offline:"服務暫時離線",unknown:"狀態資料無法確認"};
    $("#statusTitle").textContent=labels[state];
    $("#statusDetail").textContent=data.message||"服務狀態已更新。";
    $("#lastUpdate").textContent=data.updatedAt?new Date(data.updatedAt).toLocaleString("zh-TW"):"剛剛更新";
    $("#heroStatus").textContent=state==="operational"?"正常":state==="degraded"?"部分異常":state==="offline"?"離線":"未知";
    $("#heroState").textContent=state==="operational"?"SERVICE ONLINE":"SERVICE CHECK";
    $("#statusDot").className="status-dot-large "+state;
  }catch{
    $("#statusTitle").textContent="目前無法確認";
    $("#statusDetail").textContent="暫時取得不到即時狀態資料。";
    $("#lastUpdate").textContent="—";
    $("#heroStatus").textContent="未知";
    $("#heroState").textContent="SERVICE CHECK";
    $("#statusDot").className="status-dot-large";
  }
}

function init(){
  setupConfig();
  setupTheme();
  setupMenu();
  setupCommands();
  setupVisualGrid();
  setupButtonGlow();
  activateInteractive(document);
  setupReveal();
  setupMouse();
  setupScrollSpy();
  setupParallax();
  loadStatus();
  if(C.statusEndpoint)setInterval(loadStatus,30000);
}

document.addEventListener("DOMContentLoaded",init);
})();