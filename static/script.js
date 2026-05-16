const positions = {
  P1: {x: 170, y: 140, type:"process"},
  P2: {x: 170, y: 360, type:"process"},
  R1: {x: 720, y: 140, type:"resource"},
  R2: {x: 720, y: 360, type:"resource"}
};
let logs=[], timerOn=false, startTime=0, elapsed=0, timerInt=null;
let lastData=null, selected=null, customEdges=[];

function startApp(){document.getElementById("welcome").classList.add("hidden");document.getElementById("app").classList.remove("hidden"); startTimer(false)}
function startTimer(run=true){clearInterval(timerInt); if(run){timerOn=true;startTime=Date.now()-elapsed} timerInt=setInterval(()=>{if(timerOn){elapsed=Date.now()-startTime;updateTimer()}},100)}
function stopTimer(){timerOn=false}
function resetTimer(){elapsed=0;updateTimer();timerOn=false}
function updateTimer(){let s=elapsed/1000,m=Math.floor(s/60),sec=Math.floor(s%60),d=Math.floor((s%1)*10);document.getElementById("timer").textContent=`${String(m).padStart(2,"0")}:${String(sec).padStart(2,"0")}.${d}`}

function addLog(text){logs.push(text);if(logs.length>13)logs.shift();document.getElementById("logs").innerHTML=logs.map(x=>`<div class="log">${x}</div>`).join("")}
function edgeKey(e){return `${e[0]}-${e[1]}`}

function render(data){
  lastData=data;
  document.getElementById("status").textContent=data.ai;
  document.getElementById("status").style.background=data.deadlock?"linear-gradient(135deg,#ff3366,#ff9f1c)":"linear-gradient(135deg,#16c784,#00d4ff)";
  document.getElementById("aiTitle").textContent=data.ai;
  document.getElementById("aiDetails").textContent=data.details;
  document.getElementById("prediction").textContent=data.prediction;
  document.getElementById("prediction").style.color=data.predictionWarning?"#ff668a":"#85ffc5";
  document.getElementById("r1").textContent=data.resources.R1.instances;
  document.getElementById("r2").textContent=data.resources.R2.instances;
  document.getElementById("deadCount").textContent=data.deadlockCount;
  document.getElementById("progressText").textContent=`Steps: ${data.step}/${data.total}`;
  document.getElementById("progressBar").style.width=data.total?`${(data.step/data.total)*100}%`:"0%";

  if(data.deadlock) stopTimer();

  const svg=document.getElementById("graph");
  svg.innerHTML=`
    <defs>
      <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#dce7ff"/></marker>
      <marker id="arrowDead" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#ff3366"/></marker>
    </defs>`;
  const deadEdgeSet=new Set(data.deadEdges.map(edgeKey));
  const deadNodeSet=new Set(data.deadNodes);

  for(const e of data.edges){
    const a=positions[e[0]],b=positions[e[1]],dx=b.x-a.x,dy=b.y-a.y,len=Math.sqrt(dx*dx+dy*dy),ux=dx/len,uy=dy/len;
    const x1=a.x+ux*62,y1=a.y+uy*62,x2=b.x-ux*62,y2=b.y-uy*62,dead=deadEdgeSet.has(edgeKey(e));
    svg.innerHTML+=`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${dead?'#ff3366':'#dce7ff'}" stroke-width="4" marker-end="url(#${dead?'arrowDead':'arrow'})" class="${dead?'dead':''}"/>
    <text x="${(x1+x2)/2}" y="${(y1+y2)/2-10}" fill="#eef5ff" font-size="15" text-anchor="middle">${e[0]} → ${e[1]}</text>`;
  }

  for(const [name,p] of Object.entries(positions)){
    const dead=deadNodeSet.has(name);
    if(p.type==="process"){
      svg.innerHTML+=`<circle cx="${p.x}" cy="${p.y}" r="55" fill="${dead?'#ff3366':'#367cff'}" class="${dead?'dead':''}"/><text x="${p.x}" y="${p.y+8}" fill="white" font-size="25" font-weight="900" text-anchor="middle">${name}</text>`;
    }else{
      svg.innerHTML+=`<rect x="${p.x-55}" y="${p.y-55}" width="110" height="110" rx="22" fill="${dead?'#ff3366':'#14b889'}" class="${dead?'dead':''}"/>
      <text x="${p.x}" y="${p.y+8}" fill="white" font-size="25" font-weight="900" text-anchor="middle">${name}</text>
      <text x="${p.x}" y="${p.y+40}" fill="#ffea7a" font-size="16" font-weight="900" text-anchor="middle">x${data.resources[name].instances}</text>`;
    }
  }

  addLog(data.message);
  if(data.deadlock){document.getElementById("siren").play().catch(()=>{})}
  else if(data.message.startsWith("Step")){document.getElementById("beep").play().catch(()=>{})}
}

async function post(url,body={}){const r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});render(await r.json())}
function nextStep(){if(!timerOn && (!lastData || lastData.step===0)){elapsed=0;startTimer(true)} post("/api/next")}
function reset(){resetTimer();post("/api/reset")}
function setMode(mode){resetTimer();post("/api/mode",{mode})}
function banker(){post("/api/banker")}
function resource(name,delta){post("/api/resource",{name,delta})}
function predict(){if(lastData){addLog(lastData.prediction)}}

function openCustom(){document.getElementById("customModal").classList.remove("hidden")}
function closeCustom(){document.getElementById("customModal").classList.add("hidden")}
function pickNode(n){
  if(!selected){selected=n;document.getElementById("selectedNode").textContent=`Selected: ${n}`;return}
  if(selected!==n){customEdges.push([selected,n]);renderCustomEdges()}
  selected=null;document.getElementById("selectedNode").textContent="Selected: none"
}
function renderCustomEdges(){document.getElementById("customEdges").innerHTML=customEdges.map(e=>`<div>${e[0]} → ${e[1]}</div>`).join("")||"No edges yet."}
function clearCustom(){customEdges=[];selected=null;renderCustomEdges();document.getElementById("selectedNode").textContent="Selected: none"}
async function confirmCustom(){closeCustom();resetTimer();await post("/api/custom",{edges:customEdges})}

function toggleChat(){document.getElementById("chatPanel").classList.toggle("hidden")}
async function askAI(){
  const input=document.getElementById("question"),q=input.value.trim(); if(!q)return;
  const chat=document.getElementById("chatBody");
  chat.innerHTML+=`<div class="user">${q}</div>`; input.value="";
  chat.innerHTML+=`<div class="bot" id="typing">Thinking...</div>`; chat.scrollTop=chat.scrollHeight;
  const res=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({question:q})});
  const data=await res.json(); document.getElementById("typing").remove();
  chat.innerHTML+=`<div class="bot">${data.answer}</div>`; chat.scrollTop=chat.scrollHeight;
}

fetch("/api/state").then(r=>r.json()).then(render);
