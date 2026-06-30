const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const OUT = __dirname;
const C = {
  navy: "#14233B", ink: "#1C2635", muted: "#76808D", paper: "#FBF7F0",
  white: "#FFFDF9", green: "#2F8B68", orange: "#EF6634",
  blue: "#3277C7", yellow: "#EAB83F", line: "#DED8CE", pale: "#F3EEE6",
};
const font = "'Microsoft YaHei','Noto Sans SC',Arial,sans-serif";

function esc(value) {
  return String(value).replace(/[&<>"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]));
}
function svg(body) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">
  <defs>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="10" stdDeviation="14" flood-color="#14233B" flood-opacity=".11"/></filter>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="${C.navy}"/></marker>
    <style>text{font-family:${font};letter-spacing:0}.title{font-size:42px;font-weight:800;fill:${C.navy}}.sub{font-size:18px;fill:${C.muted}}.h{font-size:24px;font-weight:800;fill:${C.ink}}.b{font-size:17px;fill:${C.ink}}.s{font-size:14px;fill:${C.muted}}.num{font-size:34px;font-weight:900}.white{fill:#fff}.bold{font-weight:800}</style>
  </defs>${body}</svg>`;
}
function title(kicker, main, sub) {
  return `<text x="70" y="72" class="s" fill="${C.orange}" font-weight="800">${esc(kicker)}</text>
  <text x="70" y="125" class="title">${esc(main)}</text>
  <text x="70" y="160" class="sub">${esc(sub)}</text>
  <path d="M70 190H1530" stroke="${C.line}" stroke-width="2"/>`;
}
function card(x,y,w,h,accent=C.green) {
  return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" fill="${C.white}" stroke="${C.line}" stroke-width="2" filter="url(#shadow)"/>
  <rect x="${x}" y="${y}" width="8" height="${h}" rx="4" fill="${accent}"/>`;
}
function pill(x,y,w,text,color=C.green) {
  return `<rect x="${x}" y="${y}" width="${w}" height="38" rx="19" fill="${color}" opacity=".13"/><text x="${x+w/2}" y="${y+25}" text-anchor="middle" class="s" fill="${color}" font-weight="800">${esc(text)}</text>`;
}
function line(x1,y1,x2,y2,color=C.navy,dash="") {
  return `<path d="M${x1} ${y1}L${x2} ${y2}" stroke="${color}" stroke-width="4" fill="none" marker-end="url(#arrow)" ${dash ? `stroke-dasharray="${dash}"` : ""}/>`;
}
function robot(x,y,scale=1,color=C.navy) {
  return `<g transform="translate(${x} ${y}) scale(${scale})"><rect x="-58" y="-43" width="116" height="86" rx="25" fill="${C.white}" stroke="${color}" stroke-width="5"/><circle cx="-23" cy="-3" r="8" fill="${C.yellow}"/><circle cx="23" cy="-3" r="8" fill="${C.yellow}"/><path d="M-24 22Q0 38 24 22" stroke="${color}" stroke-width="5" fill="none" stroke-linecap="round"/><path d="M0-43V-65" stroke="${color}" stroke-width="5"/><circle cy="-72" r="8" fill="${C.orange}"/></g>`;
}
function camera(x,y,scale=1,color=C.orange) {
  return `<g transform="translate(${x} ${y}) scale(${scale})"><rect x="-58" y="-37" width="116" height="74" rx="13" fill="${C.white}" stroke="${color}" stroke-width="5"/><circle r="25" fill="none" stroke="${color}" stroke-width="7"/><circle r="8" fill="${color}"/><rect x="-35" y="-53" width="45" height="18" rx="6" fill="${color}"/></g>`;
}
function pc(x,y,scale=1,color=C.blue) {
  return `<g transform="translate(${x} ${y}) scale(${scale})"><rect x="-65" y="-48" width="130" height="88" rx="8" fill="${C.white}" stroke="${color}" stroke-width="5"/><path d="M-25 62H25M0 40V62" stroke="${color}" stroke-width="6"/><path d="M-45-20H40M-45 0H20M-45 20H35" stroke="${color}" stroke-width="5" stroke-linecap="round"/></g>`;
}

const assets = [];

assets.push(["01_软硬件总架构", svg(`
${title("SYSTEM ARCHITECTURE", "软硬件协同的闭环架构", "从视觉感知到机器人主动播报，所有核心数据在本地局域网内完成")}
<g transform="translate(800 500)">
  <circle r="215" fill="${C.paper}" stroke="${C.line}" stroke-width="2"/>
  <circle r="150" fill="${C.navy}"/>
  ${robot(0,-12,1.15,C.white)}
  <text x="0" y="92" text-anchor="middle" class="white h">小智桌面学伴</text>
  <text x="0" y="120" text-anchor="middle" class="s" fill="#B9C4D1">主动播报 · 学段切换 · 知识问答</text>
</g>
${card(70,260,390,195,C.orange)}${camera(155,350,.62)}<text x="225" y="314" class="h">硬件感知端</text><text x="225" y="352" class="b">本地/手机摄像头</text><text x="225" y="383" class="s">人脸 · 视线 · 姿态 · 离座</text>${pill(225,405,180,"MediaPipe",C.orange)}
${card(1140,260,390,195,C.blue)}${pc(1225,350,.58)}<text x="1295" y="314" class="h">家长交互端</text><text x="1295" y="352" class="b">Web 控制与学习复盘</text><text x="1295" y="383" class="s">留言 · 阈值 · 模式 · 趋势</text>${pill(1295,405,180,"FastAPI + Web",C.blue)}
${card(70,590,390,195,C.green)}<circle cx="155" cy="682" r="48" fill="${C.green}" opacity=".12"/><path d="M130 690L150 710L184 662" stroke="${C.green}" stroke-width="10" fill="none"/><text x="225" y="644" class="h">本地智能服务</text><text x="225" y="682" class="b">策略编排与语音生成</text><text x="225" y="713" class="s">WindowsSpeech · DeepSeek · SAPI</text>${pill(225,735,210,"隐私留在局域网",C.green)}
${card(1140,590,390,195,C.yellow)}<circle cx="1225" cy="682" r="48" fill="${C.yellow}" opacity=".18"/><path d="M1200 682H1248M1224 658V706" stroke="${C.yellow}" stroke-width="10"/><text x="1295" y="644" class="h">通信下行端</text><text x="1295" y="682" class="b">MQTT 指令 + UDP 音频</text><text x="1295" y="713" class="s">无需按键，机器人立即开口</text>${pill(1295,735,190,"主动发声已打通",C.yellow)}
${line(460,360,610,430,C.orange)}${line(1140,360,990,430,C.blue)}${line(460,680,610,570,C.green)}${line(1140,680,990,570,C.yellow)}
`)]);

assets.push(["02_主动播报双通路闭环", svg(`
${title("DUAL-CHANNEL ACTIVE SPEECH", "两条提醒通路，一个主动播报闭环", "家长主动关怀与视觉自动干预共享同一可靠语音下行能力")}
<path d="M320 320C600 210 1000 210 1280 320" stroke="${C.orange}" stroke-width="14" fill="none" stroke-linecap="round"/>
<path d="M320 650C600 760 1000 760 1280 650" stroke="${C.blue}" stroke-width="14" fill="none" stroke-linecap="round"/>
${card(70,260,360,190,C.orange)}<text x="110" y="315" class="s" fill="${C.orange}" font-weight="800">通路 A · 人工关怀</text><text x="110" y="360" class="h">家长端留言</text><text x="110" y="398" class="b">点击发送后立即进入播报队列</text>${pill(110,420,160,"主动触发",C.orange)}
${card(70,550,360,190,C.blue)}<text x="110" y="605" class="s" fill="${C.blue}" font-weight="800">通路 B · 自动干预</text><text x="110" y="650" class="h">视觉检测分心</text><text x="110" y="688" class="b">连续低分达到学段阈值后触发</text>${pill(110,710,160,"策略触发",C.blue)}
<g transform="translate(800 490)"><circle r="176" fill="${C.navy}" filter="url(#shadow)"/><circle r="128" fill="none" stroke="${C.yellow}" stroke-width="3" stroke-dasharray="7 8"/>${robot(0,-25,1.05,C.white)}<text x="0" y="85" class="white h" text-anchor="middle">主动播报引擎</text><text x="0" y="115" class="s" fill="#B7C2D0" text-anchor="middle">提醒编排 · TTS · 状态回执</text></g>
${card(1170,325,360,330,C.green)}<text x="1210" y="382" class="s" fill="${C.green}" font-weight="800">ROBOT OUTPUT</text><text x="1210" y="430" class="h">小智立即开口提醒</text><path d="M1210 470H1480" stroke="${C.line}" stroke-width="2"/>
<text x="1210" y="515" class="b">① MQTT 唤醒设备下行</text><text x="1210" y="555" class="b">② UDP 推送合成音频</text><text x="1210" y="595" class="b">③ spoken 状态闭环回执</text>${pill(1210,620,235,"无需触碰机器人按键",C.green)}
${line(430,355,625,415,C.orange)}${line(430,645,625,565,C.blue)}${line(975,490,1170,490,C.green)}
`)]);

assets.push(["03_三学段语音状态机", svg(`
${title("VOICE-DRIVEN STUDY MODES", "三学段语音状态机", "开机询问、自然语音选择、切换反馈与差异化提醒策略形成完整状态闭环")}
<g transform="translate(800 510)">
  <circle r="250" fill="none" stroke="${C.line}" stroke-width="26"/>
  <path d="M-216-125A250 250 0 0 1 216-125" fill="none" stroke="${C.orange}" stroke-width="28" stroke-linecap="round"/>
  <path d="M216-125A250 250 0 0 1 0 250" fill="none" stroke="${C.green}" stroke-width="28" stroke-linecap="round"/>
  <path d="M0 250A250 250 0 0 1-216-125" fill="none" stroke="${C.blue}" stroke-width="28" stroke-linecap="round"/>
  <circle r="142" fill="${C.navy}" filter="url(#shadow)"/>
  <text y="-28" text-anchor="middle" class="s" fill="#B7C2D0">开机语音入口</text><text y="20" text-anchor="middle" class="white h">“请选择学习学段”</text><text y="62" text-anchor="middle" class="s" fill="${C.yellow}">仅在真正改变时播报反馈</text>
</g>
${card(80,250,360,205,C.orange)}<text x="120" y="305" class="s" fill="${C.orange}" font-weight="800">PRIMARY</text><text x="120" y="350" class="h">小学模式</text><text x="120" y="388" class="b">短句 · 鼓励式 · 高频正反馈</text>${pill(120,415,210,"宽容阈值 / 温和提醒",C.orange)}
${card(1160,250,360,205,C.green)}<text x="1200" y="305" class="s" fill="${C.green}" font-weight="800">MIDDLE</text><text x="1200" y="350" class="h">初中模式</text><text x="1200" y="388" class="b">目标拆解 · 节奏管理 · 复盘</text>${pill(1200,415,210,"标准阈值 / 任务导向",C.green)}
${card(80,620,360,205,C.blue)}<text x="120" y="675" class="s" fill="${C.blue}" font-weight="800">HIGH</text><text x="120" y="720" class="h">高中模式</text><text x="120" y="758" class="b">克制提醒 · 自主规划 · 效率</text>${pill(120,785,210,"严格阈值 / 尊重自主",C.blue)}
${card(1160,620,360,205,C.yellow)}<text x="1200" y="675" class="s" fill="#9A7310" font-weight="800">FEEDBACK</text><text x="1200" y="720" class="h">双向切换反馈</text><text x="1200" y="758" class="b">语音选择与家长端切换同步</text>${pill(1200,785,245,"“已进入 ×× 模式”",C.yellow)}
`)]);

assets.push(["04_USB与局域网部署拓扑", svg(`
${title("LOCAL NETWORK DEPLOYMENT", "断开 USB 后仍可运行的局域网拓扑", "USB 只负责首次烧录与调试；日常运行依靠独立供电和同一局域网")}
<g transform="translate(800 515)"><rect x="-165" y="-105" width="330" height="210" rx="80" fill="${C.navy}" filter="url(#shadow)"/><path d="M-76 5Q0-68 76 5M-46 32Q0-12 46 32" stroke="${C.yellow}" stroke-width="12" fill="none" stroke-linecap="round"/><circle cy="56" r="10" fill="${C.yellow}"/><text y="-55" text-anchor="middle" class="white h">同一局域网</text><text y="93" text-anchor="middle" class="s" fill="#C0CAD5">Wi-Fi / 手机热点 / 路由器</text></g>
${card(70,280,390,290,C.blue)}${pc(165,395,.65)}<text x="245" y="340" class="h">电脑本地服务</text><text x="245" y="382" class="b">10.143.97.5</text><text x="245" y="418" class="s">家长端 · 视觉分析 · TTS</text><text x="110" y="510" class="s">监听端口</text>${pill(200,485,220,"8000 · 1883 · 18000+",C.blue)}
${card(1140,280,390,290,C.green)}${robot(1230,395,.68,C.green)}<text x="1310" y="340" class="h">小智机器人</text><text x="1310" y="382" class="b">MAC 90:70:69:0e:a4:ac</text><text x="1310" y="418" class="s">独立供电 · Wi-Fi 在线</text><text x="1180" y="510" class="s">通信方式</text>${pill(1270,485,220,"MQTT + UDP/TTS",C.green)}
${line(460,425,625,475,C.blue)}${line(975,475,1140,425,C.green)}
<g transform="translate(800 735)"><rect x="-530" y="-72" width="1060" height="144" rx="8" fill="${C.white}" stroke="${C.line}" stroke-width="2"/><circle cx="-465" r="28" fill="${C.orange}" opacity=".14"/><path d="M-477-12L-453 12M-453-12L-477 12" stroke="${C.orange}" stroke-width="7"/><text x="-415" y="-15" class="h">运行时 USB 不需要</text><text x="-415" y="25" class="s">若电脑 DHCP 地址变化，固件仍指向旧 IP，就会出现“检查新版本失败”。</text><text x="180" y="-15" class="b bold" fill="${C.green}">稳定方案</text><text x="180" y="25" class="s">路由器 DHCP 地址保留 / 固定热点 / 后续 mDNS 自动发现</text></g>
`)]);

assets.push(["05_两日工程成果矩阵", svg(`
${title("TWO-DAY ENGINEERING SPRINT", "两日工程成果矩阵", "不是单点演示，而是从固件、服务、算法、交互到验证的完整工程闭环")}
<g transform="translate(70 235)">
  <rect width="1460" height="560" rx="8" fill="${C.white}" stroke="${C.line}" stroke-width="2" filter="url(#shadow)"/>
  <rect width="1460" height="78" rx="8" fill="${C.navy}"/>
  <text x="45" y="49" class="white h">工作层</text><text x="335" y="49" class="white h">关键突破</text><text x="960" y="49" class="white h">可验证结果</text><text x="1285" y="49" class="white h">状态</text>
  ${[
    ["固件层","ESP32 本地 OTA 地址、主动播报下行适配","开机即连本地服务，支持无按键播报","已打通",C.orange],
    ["通信层","MQTT 唤醒 + UDP/TTS 音频推送","家长留言与分心事件均可主动发声","已打通",C.green],
    ["智能层","WindowsSpeech 中文 ASR + DeepSeek 对话","“高中”“你好”“1+1”均正常识别应答","已打通",C.blue],
    ["策略层","小学 / 初中 / 高中三套差异化策略","语音选择、家长切换、仅变更时播报","已打通",C.yellow],
    ["产品层","家长端、专注分析、本地智能体运行中心","状态可视、提醒可追溯、网络可诊断","可展示",C.orange],
    ["质量层","接口、策略、语音与迁移测试覆盖","129 项自动化测试通过","通过",C.green],
  ].map((r,i)=>{
    const y=78+i*80; return `<rect x="0" y="${y}" width="1460" height="80" fill="${i%2?C.paper:C.white}"/><rect x="18" y="${y+18}" width="8" height="44" rx="4" fill="${r[4]}"/><text x="45" y="${y+49}" class="b bold">${r[0]}</text><text x="335" y="${y+49}" class="b">${r[1]}</text><text x="960" y="${y+49}" class="b">${r[2]}</text><rect x="1280" y="${y+22}" width="120" height="36" rx="18" fill="${r[4]}" opacity=".14"/><text x="1340" y="${y+47}" text-anchor="middle" class="s" fill="${r[4]}" font-weight="800">${r[3]}</text>`;
  }).join("")}
</g>
`)]);

assets.push(["06_中文识别修复前后对比", svg(`
${title("CHINESE ASR RECOVERY", "中文语音识别修复：从乱码到自然对话", "替换不稳定识别链路，统一 UTF-8 文本传递，并用真实语音完成端到端验证")}
${card(70,245,610,480,C.orange)}<text x="115" y="305" class="s" fill="${C.orange}" font-weight="800">BEFORE · 修复前</text><text x="115" y="360" class="h">识别结果不可用</text>
<rect x="115" y="405" width="520" height="92" rx="8" fill="#FFF0E8"/><text x="145" y="447" class="b" fill="#8A4228">输入：“你好 / 高中模式”</text><text x="145" y="480" class="b bold" fill="${C.orange}">输出：乱码、误识别、无法切换</text>
<path d="M115 545H635" stroke="${C.line}" stroke-width="2"/><text x="115" y="590" class="b">FunASR/SenseVoice 环境不稳定</text><text x="115" y="628" class="b">字符编码链路不一致</text><text x="115" y="666" class="b">开机选择与按键对话均受影响</text>
${card(920,245,610,480,C.green)}<text x="965" y="305" class="s" fill="${C.green}" font-weight="800">AFTER · 修复后</text><text x="965" y="360" class="h">WindowsSpeech 稳定中文识别</text>
<rect x="965" y="405" width="520" height="92" rx="8" fill="#EAF5EF"/><text x="995" y="447" class="b" fill="#245F49">输入：“高中 / 你好 / 一加一等于几”</text><text x="995" y="480" class="b bold" fill="${C.green}">输出：正确切换、正常问候、回答等于 2</text>
<path d="M965 545H1485" stroke="${C.line}" stroke-width="2"/><text x="965" y="590" class="b">Windows 原生中文语音服务</text><text x="965" y="628" class="b">UTF-8 全链路传输</text><text x="965" y="666" class="b">开机选择与按键对话双场景验证</text>
<g transform="translate(800 485)"><circle r="72" fill="${C.navy}"/><path d="M-26 0H26M8-18L26 0L8 18" stroke="${C.yellow}" stroke-width="7" fill="none" stroke-linecap="round" stroke-linejoin="round"/></g>
${pill(545,765,510,"真实设备验证：语音选择 + 中文自由对话",C.blue)}
`)]);

assets.push(["07_本地部署与官方方案对比", svg(`
${title("LOCAL VS. CLOUD CONSOLE", "本地部署与官方智能体：保留能力，补齐主动性", "官方控制台继续作为安全回退；本地服务新增视觉闭环、主动播报和工程可观测性")}
<g transform="translate(70 245)">
  <rect width="1460" height="520" rx="8" fill="${C.white}" stroke="${C.line}" stroke-width="2" filter="url(#shadow)"/>
  <rect x="0" y="0" width="310" height="520" rx="8" fill="${C.navy}"/>
  <text x="44" y="70" class="white h">能力维度</text>
  ${["对话与知识问答","家长端主动留言","摄像头分心检测","无需按键主动播报","三学段策略切换","本地运行状态可视","官方方案安全回退"].map((t,i)=>`<text x="44" y="${135+i*53}" class="white b">${t}</text>`).join("")}
  <rect x="310" width="540" height="76" fill="${C.pale}"/><text x="580" y="49" text-anchor="middle" class="h">官方控制台方案</text>
  <rect x="850" width="610" height="76" fill="#EAF5EF"/><text x="1155" y="49" text-anchor="middle" class="h" fill="${C.green}">本地增强方案</text>
  ${[
    ["●","●"],["—","●"],["—","●"],["—","●"],["△","●"],["—","●"],["●","●"]
  ].map((r,i)=>{const y=135+i*53;return `<text x="580" y="${y}" text-anchor="middle" class="h" fill="${r[0]==="●"?C.blue:C.muted}">${r[0]}</text><text x="1155" y="${y}" text-anchor="middle" class="h" fill="${r[1]==="●"?C.green:C.muted}">${r[1]}</text><path d="M310 ${y+19}H1460" stroke="${C.line}" stroke-width="1"/>`;}).join("")}
</g>
<g transform="translate(475 810)">${pill(0,0,260,"官方：稳定对话底座",C.blue)}${pill(330,0,310,"本地：主动感知与干预",C.green)}</g>
`)]);

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const edgePath = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
  const browser = await chromium.launch({
    headless: true,
    executablePath: fs.existsSync(edgePath) ? edgePath : undefined,
  });
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  for (const [name, content] of assets) {
    const svgPath = path.join(OUT, `${name}.svg`);
    const pngPath = path.join(OUT, `${name}.png`);
    fs.writeFileSync(svgPath, content, "utf8");
    await page.setContent(`<style>html,body{margin:0;background:transparent}</style>${content}`);
    await page.locator("svg").screenshot({ path: pngPath, omitBackground: true });
    console.log(path.basename(pngPath));
  }
  const previews = assets.map(([name]) => {
    const data = fs.readFileSync(path.join(OUT, `${name}.png`)).toString("base64");
    return `<figure><img src="data:image/png;base64,${data}"><figcaption>${name}</figcaption></figure>`;
  }).join("");
  await page.setViewportSize({ width: 1280, height: 1040 });
  await page.setContent(`<style>
    body{margin:0;padding:24px;background:#ece7df;font-family:"Microsoft YaHei",sans-serif}
    main{display:grid;grid-template-columns:1fr 1fr;gap:18px}
    figure{margin:0;background:white;padding:8px;border:1px solid #d9d2c8}
    img{display:block;width:100%;height:auto}figcaption{font-size:13px;font-weight:700;padding:7px 4px 2px;color:#14233b}
  </style><main>${previews}</main>`);
  await page.screenshot({ path: path.join(OUT, "_总览预览.png"), fullPage: true });
  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
