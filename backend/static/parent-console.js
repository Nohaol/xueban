const STATUS_META = {
  flow: {
    label: "心流专注",
    advisorTitle: "保持陪伴感，不要打断心流",
    advisorSummary: "孩子已经进入连续专注区间，外部干预越少，学习效率通常越高。",
    bullets: ["此时不建议主动语音打断。", "如果需要提醒休息，尽量等这一段专注自然结束。"],
  },
  normal: {
    label: "稳定学习",
    advisorTitle: "保持节奏，减少无效干预",
    advisorSummary: "整体状态平稳，建议以陪伴式观察为主，而不是高频打断式管理。",
    bullets: ["继续观察后续趋势。", "如果视线偏移连续出现，再考虑温和提醒。"],
  },
  distracted: {
    label: "轻度分心",
    advisorTitle: "轻提醒通常比追问更有效",
    advisorSummary: "当前更像阶段性的注意力波动，短句提醒或调整坐姿往往更有效。",
    bullets: ["优先使用“把注意力放回书本”这类单步提醒。", "不要把一次分心直接解释为态度问题。"],
  },
  away: {
    label: "短暂离座",
    advisorTitle: "属于正常放松区间",
    advisorSummary: "当前仍在短暂离座容忍时间内，不建议立刻频繁提醒。",
    bullets: ["先保持观察，等待孩子自然回到座位。", "临近学习节点时，可准备温和提醒。"],
  },
  timeout_away: {
    label: "超时离座",
    advisorTitle: "先确认休息，再决定是否介入",
    advisorSummary: "超时离座不一定代表逃避学习，优先确认是否处于用餐、如厕或短暂走动场景。",
    bullets: ["建议先通过小智温和确认情况。", "如果连续多次超时离座，再考虑调整学习与休息节奏。"],
  },
};

const METRIC_META = [
  ["gaze", "视线聚焦", "#6fc59f"],
  ["posture", "坐姿健康", "#e8b36f"],
  ["stability", "身体稳定", "#8eb6d7"],
  ["presence", "在座覆盖", "#d98989"],
];

const STATUS_LABELS = {
  idle: "待命",
  connecting: "连接中",
  live: "实时视频正常",
  offline: "离线",
  mock: "演示回退",
};

const TRANSPORT_LABELS = {
  stream: "连续视频流",
  snapshot: "截图地址",
};

const EVENT_TRANSLATIONS = {
  "Face detected and tracked in the current study zone.": "已在当前学习区域内检测并跟踪到人脸。",
  "No face detected. Treating the seat as unattended.": "没有检测到人脸，当前座位视为无人。",
  "Face position suggests a slouched or off-axis posture.": "人脸位置显示坐姿可能前倾或偏离。",
  "Face is drifting away from the center of the study area.": "人脸明显偏离学习区域中心，可能出现分心。",
  "Large movement detected around the head and upper body.": "头部和上半身附近检测到较大幅度动作。",
  "Student appears far from the camera. Presence is still valid.": "孩子距离摄像头较远，但仍能确认在座。",
  "Engine booting. Waiting for the first frame.": "视觉节点正在启动，等待第一帧画面。",
  "Strong sustained attention detected.": "检测到持续稳定的专注状态。",
  "Study rhythm is steady.": "学习节奏平稳。",
  "Attention drift is rising. A light reminder may help.": "注意力有轻微漂移，稍后可以温和提醒。",
  "Temporary away-from-seat state detected.": "检测到短暂离座。",
  "Away-from-seat timeout exceeded.": "离座时间超过阈值。",
};

const state = {
  payload: null,
  events: [],
  heatmap: new Array(24).fill("normal"),
  samples: [],
  socket: null,
  aiAdvice: null,
};

const $ = (id) => document.getElementById(id);

function api(path) {
  return `${window.location.origin}${path}`;
}

function wsUrl() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}/ws`;
}

function pad(value) {
  return String(value).padStart(2, "0");
}

function clock(timestamp) {
  const date = new Date(timestamp || Date.now());
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function duration(totalSeconds) {
  const safe = Math.max(Math.floor(Number(totalSeconds) || 0), 0);
  return `${pad(Math.floor(safe / 60))}分${pad(safe % 60)}秒`;
}

function clamp(value) {
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return 0;
  return Math.max(0, Math.min(100, Math.round(numeric)));
}

function translateEvent(text) {
  return EVENT_TRANSLATIONS[text] || text || "视觉状态已更新。";
}

function statusGroup(status) {
  if (status === "flow" || status === "normal") return "focused";
  if (status === "away" || status === "timeout_away") return "away";
  return "distracted";
}

function statusToneLabel(status) {
  const meta = STATUS_META[status] || STATUS_META.normal;
  return meta.label;
}

function normalizePayload(payload) {
  const metrics = Object.assign(
    { gaze: 0, posture: 0, stability: 0, presence: 0 },
    payload.metrics || {}
  );
  Object.keys(metrics).forEach((key) => {
    metrics[key] = clamp(metrics[key]);
  });

  return Object.assign(
    {
      timestamp: Date.now(),
      studentLabel: "学生 A",
      status: "normal",
      focusScore: 82,
      awaySeconds: 0,
      eventText: "视觉节点待命。",
      sourceLabel: "等待视频源",
      engineMode: "启动中",
    },
    payload,
    {
      metrics,
      focusScore: clamp(payload.focusScore),
      awaySeconds: Math.max(Number(payload.awaySeconds || 0), 0),
      eventText: translateEvent(payload.eventText),
    }
  );
}

function setStatusClass(element, status) {
  const compact = element.id === "frameStatus";
  element.className = compact ? "status-pill compact" : "status-pill";
  if (status !== "flow" && status !== "normal") {
    element.classList.add(`status-${status}`);
  }
}

function pushEvent(payload) {
  const latest = state.events[0];
  const text = payload.eventText || "视觉状态已更新。";
  if (latest && latest.text === text && latest.status === payload.status) return;
  state.events.unshift({
    time: clock(payload.timestamp),
    text,
    status: payload.status,
  });
  state.events = state.events.slice(0, 10);
}

function render(payload) {
  const safe = normalizePayload(payload || {});
  const meta = STATUS_META[safe.status] || STATUS_META.normal;
  state.payload = safe;
  state.heatmap.shift();
  state.heatmap.push(safe.status);
  state.samples.push({
    status: safe.status,
    score: safe.focusScore,
    metrics: Object.assign({}, safe.metrics),
    timestamp: safe.timestamp,
  });
  state.samples = state.samples.slice(-72);
  pushEvent(safe);

  $("focusScore").textContent = safe.focusScore;
  $("frameScore").textContent = `专注度 ${safe.focusScore}`;
  $("statusPill").textContent = meta.label;
  $("frameStatus").textContent = meta.label;
  setStatusClass($("statusPill"), safe.status);
  setStatusClass($("frameStatus"), safe.status);
  $("sourceLabel").textContent = safe.sourceLabel || safe.sourceId || "等待视频源";
  $("microHint").textContent = safe.eventText;
  $("lastUpdateText").textContent = `最近刷新：${clock(safe.timestamp)}`;
  $("lastUpdateSummary").textContent = clock(safe.timestamp);
  $("engineMode").textContent = engineModeLabel(safe.engineMode);
  $("connectionLabel").textContent = "本地视觉节点已接入";
  $("timeoutMask").classList.toggle("show", safe.status === "timeout_away");
  $("awayCountdown").textContent = duration(safe.awaySeconds);
  $("awayDuration").textContent = duration(safe.awaySeconds);
  $("awayStatus").textContent =
    safe.awaySeconds > 0
      ? safe.status === "timeout_away"
        ? "已超时离座"
        : "正在离座"
      : "当前在座";

  renderMetrics(safe.metrics);
  renderTimeline();
  renderTimelineStats(safe);
  renderHeatmap();
  renderAdvisor(meta);
  renderAnalytics();
}

function engineModeLabel(mode) {
  if (mode === "camera") return "真实分析";
  if (mode === "mock") return "回退预览";
  if (mode === "boot") return "启动中";
  return mode || "运行中";
}

function renderMetrics(metrics) {
  $("metricList").innerHTML = METRIC_META.map(([key, label, color]) => {
    const score = clamp(metrics[key]);
    return `
      <div class="metric-row">
        <span>${label}</span>
        <div class="metric-track">
          <div class="metric-fill" style="width:${score}%;background:${color}"></div>
        </div>
        <strong>${score}</strong>
      </div>
    `;
  }).join("");
}

function renderTimeline() {
  if (!state.events.length) {
    $("timeline").innerHTML = '<div class="timeline-item"><span class="timeline-time">--:--</span><span>等待视觉节点事件。</span></div>';
    return;
  }
  $("timeline").innerHTML = state.events
    .map(
      (item) => `
        <div class="timeline-item">
          <span class="timeline-time">${item.time}</span>
          <span>${item.text}</span>
        </div>
      `
    )
    .join("");
}

function countTransitions(items, matcher) {
  let count = 0;
  let previousMatched = false;
  items.forEach((item) => {
    const matched = matcher(item.status);
    if (matched && !previousMatched) count += 1;
    previousMatched = matched;
  });
  return count;
}

function renderTimelineStats(payload) {
  const samples = state.samples.length ? state.samples : state.heatmap.map((status) => ({ status }));
  const focusedCount = samples.filter((item) => statusGroup(item.status) === "focused").length;
  const focusRatio = Math.round((focusedCount / Math.max(samples.length, 1)) * 100);
  const distractedCount = countTransitions(samples, (status) => statusGroup(status) === "distracted");
  const awayCount = countTransitions(samples, (status) => statusGroup(status) === "away");
  const latestStatus = payload.status;
  let currentRun = 0;
  for (let index = samples.length - 1; index >= 0; index -= 1) {
    if (samples[index].status !== latestStatus) break;
    currentRun += 1;
  }

  const cards = [
    ["近段专注占比", `${focusRatio}%`, "根据最近状态采样"],
    ["分心波动", `${distractedCount} 次`, "连续波动只记一次"],
    ["离座记录", `${awayCount} 次`, "含短暂离座和超时"],
    ["当前状态持续", `${currentRun} 帧`, statusToneLabel(latestStatus)],
  ];

  $("timelineStats").innerHTML = cards
    .map(
      ([label, value, hint]) => `
        <div class="timeline-stat">
          <span>${label}</span>
          <strong>${value}</strong>
          <small>${hint}</small>
        </div>
      `
    )
    .join("");
}

function renderHeatmap() {
  $("heatmap").innerHTML = state.heatmap
    .map((status) => `<span class="heatmap-cell tone-${status}"></span>`)
    .join("");
}

function pointsFor(items, getter, width = 300, height = 82) {
  const count = Math.max(items.length - 1, 1);
  return items
    .map((item, index) => {
      const x = (index / count) * width;
      const y = height - (clamp(getter(item)) / 100) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function renderAnalytics() {
  const samples = state.samples.length ? state.samples : [{ score: 82, status: "normal", metrics: {} }];
  const recent = samples.slice(-36);
  const trendItems = [
    { key: "score", label: "专注分", color: "#315c49", getter: (item) => item.score },
    { key: "gaze", label: "视线", color: "#6fc59f", getter: (item) => item.metrics?.gaze },
    { key: "posture", label: "坐姿", color: "#e8b36f", getter: (item) => item.metrics?.posture },
    { key: "stability", label: "稳定", color: "#8eb6d7", getter: (item) => item.metrics?.stability },
  ];

  $("trendLegend").innerHTML = trendItems
    .map((item) => `<span><i style="background:${item.color}"></i>${item.label}</span>`)
    .join("");

  const gridLines = [0, 25, 50, 75, 100]
    .map((value) => `<line x1="0" y1="${82 - value * 0.82}" x2="300" y2="${82 - value * 0.82}" />`)
    .join("");
  const lines = trendItems
    .map(
      (item) => `
        <polyline
          points="${pointsFor(recent, item.getter)}"
          fill="none"
          stroke="${item.color}"
          stroke-width="${item.key === "score" ? 3 : 2}"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      `
    )
    .join("");
  $("trendChart").innerHTML = `
    <svg viewBox="0 0 300 96" preserveAspectRatio="none" aria-label="指标趋势图">
      <g class="chart-grid">${gridLines}</g>
      <g transform="translate(0 7)">${lines}</g>
    </svg>
  `;

  const focused = samples.filter((item) => statusGroup(item.status) === "focused").length;
  const distracted = samples.filter((item) => statusGroup(item.status) === "distracted").length;
  const away = samples.length - focused - distracted;
  const total = Math.max(samples.length, 1);
  const focusedDeg = (focused / total) * 360;
  const distractedDeg = ((focused + distracted) / total) * 360;
  $("statusDonut").style.background = `conic-gradient(#6fc59f 0deg ${focusedDeg}deg, #e8b36f ${focusedDeg}deg ${distractedDeg}deg, #d98989 ${distractedDeg}deg 360deg)`;
  $("donutCopy").innerHTML = `
    <strong>${Math.round((focused / total) * 100)}%</strong>
    <span>最近专注占比</span>
    <small><i class="dot focus"></i>专注 ${focused} 帧</small>
    <small><i class="dot drift"></i>分心 ${distracted} 帧</small>
    <small><i class="dot away"></i>离座 ${away} 帧</small>
  `;

  $("metricSparkGrid").innerHTML = METRIC_META.map(([key, label, color]) => {
    const latest = clamp(recent[recent.length - 1]?.metrics?.[key]);
    const first = clamp(recent[0]?.metrics?.[key]);
    const delta = latest - first;
    const deltaLabel = delta > 0 ? `+${delta}` : `${delta}`;
    return `
      <div class="spark-card">
        <div class="spark-copy">
          <span>${label}</span>
          <strong>${latest}</strong>
          <small class="${delta >= 0 ? "rise" : "fall"}">${deltaLabel}</small>
        </div>
        <svg viewBox="0 0 120 42" preserveAspectRatio="none">
          <polyline
            points="${pointsFor(recent, (item) => item.metrics?.[key], 120, 42)}"
            fill="none"
            stroke="${color}"
            stroke-width="3"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </div>
    `;
  }).join("");
}

function renderAdvisor(meta) {
  const advice = state.aiAdvice;
  const sendButton = $("sendAiScriptButton");
  const scriptHint = $("aiScriptHint");
  if (!advice) {
    $("advisorTitle").textContent = meta.advisorTitle;
    $("advisorSummary").textContent = meta.advisorSummary;
    $("advisorBullets").innerHTML = meta.bullets.map((item) => `<li>${item}</li>`).join("");
    $("aiScriptText").textContent = "暂无，需要时点击智能分析。";
    $("aiDetailGrid").innerHTML = "";
    sendButton.disabled = true;
    scriptHint.textContent = "智能分析后可一键转为小智提醒。";
    return;
  }

  $("advisorTitle").textContent = advice.title || meta.advisorTitle;
  $("advisorSummary").textContent = advice.summary || meta.advisorSummary;
  const bullets = Array.isArray(advice.bullets) && advice.bullets.length ? advice.bullets : meta.bullets;
  $("advisorBullets").innerHTML = bullets.map((item) => `<li>${item}</li>`).join("");
  const script = advice.xiaozhiScript || advice.message || "";
  $("aiScriptText").textContent = script || "本次不建议让小智主动打断。";
  sendButton.disabled = !script.trim();
  scriptHint.textContent = script.trim() ? "确认后可发送给小智朗读。" : "本次建议观察，不主动提醒。";

  const details = [
    ["判断依据", advice.reason || "根据当前专注度、视线、坐姿和在座状态综合判断。"],
    ["是否提醒", advice.shouldRemind ? "建议提醒" : "暂不提醒"],
    ["提醒等级", advice.reminderLevel || "observe"],
  ];
  if (Array.isArray(advice.observations) && advice.observations.length) {
    details.push(["指标观察", advice.observations.join("；")]);
  }
  if (Array.isArray(advice.actionPlan) && advice.actionPlan.length) {
    details.push(["行动建议", advice.actionPlan.join("；")]);
  }
  $("aiDetailGrid").innerHTML = details
    .map(([label, text]) => `<div class="ai-detail-item"><span>${label}</span><p>${text}</p></div>`)
    .join("");
}

async function sendAiScript() {
  const advice = state.aiAdvice || {};
  const script = (advice.xiaozhiScript || advice.message || $("aiScriptText").textContent || "").trim();
  if (!script || script === "本次不建议让小智主动打断。" || script.startsWith("暂无")) {
    $("controlResult").textContent = "当前没有可发送的小智话术，请先点击智能分析。";
    return;
  }
  $("parentMessage").value = script;
  await sendControl("ai_script_message", script);
  $("aiScriptHint").textContent = "已作为小智提醒发送。";
}

function connectSocket() {
  if (state.socket) state.socket.close();
  state.socket = new WebSocket(wsUrl());
  $("connectionLabel").textContent = "正在连接本地节点";

  state.socket.onmessage = (event) => {
    try {
      render(JSON.parse(event.data));
    } catch (error) {
      $("connectionLabel").textContent = "状态数据解析失败";
    }
  };

  state.socket.onclose = () => {
    $("connectionLabel").textContent = "本地连接已断开";
    setTimeout(connectSocket, 1500);
  };

  state.socket.onerror = () => {
    $("connectionLabel").textContent = "等待本地服务启动";
  };
}

async function fetchJson(path, options) {
  const response = await fetch(api(path), options);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

function renderSourceList(items = []) {
  $("sourceList").innerHTML = items
    .map((source) => {
      const selected = source.is_selected ? " selected" : "";
      const status = STATUS_LABELS[source.status] || source.status || "待命";
      const transport = TRANSPORT_LABELS[source.transport] || source.transport;
      const deleteButton = source.is_builtin
        ? ""
        : `<button class="danger-button" type="button" data-delete-source-id="${source.source_id}">删除</button>`;
      return `
        <div class="source-item${selected}">
          <div>
            <strong>${source.label}</strong>
            <span>${status} · ${transport} · ${source.location}</span>
          </div>
          <div class="source-actions">
            <button type="button" data-source-id="${source.source_id}">
              ${source.is_selected ? "已选中" : "切换"}
            </button>
            ${deleteButton}
          </div>
        </div>
      `;
    })
    .join("");

  document.querySelectorAll("[data-source-id]").forEach((button) => {
    button.addEventListener("click", () => selectSource(button.dataset.sourceId));
  });
  document.querySelectorAll("[data-delete-source-id]").forEach((button) => {
    button.addEventListener("click", () => deleteSource(button.dataset.deleteSourceId));
  });
}

async function refreshSources() {
  const data = await fetchJson("/sources");
  renderSourceList(data.items || []);
}

async function refreshAiAdvice() {
  try {
    $("manualAiButton").disabled = true;
    $("manualAiButton").textContent = "分析中";
    const data = await fetchJson("/ai/advice?force=true");
    state.aiAdvice = data.advice;
    const seconds = Number(data.nextRefreshSeconds || data.minIntervalSeconds || 120);
    const suffix = data.cached ? `缓存建议，${seconds} 秒后可重新调用` : `DeepSeek ${data.model} 已更新`;
    $("advisorSummary").textContent = `${state.aiAdvice.summary || ""}（${suffix}）`;
    if (state.payload) {
      render(state.payload);
    }
  } catch (error) {
    state.aiAdvice = {
      title: "AI 建议暂不可用",
      summary: "DeepSeek 接口暂时没有返回，页面继续使用本地规则建议。",
      bullets: ["不会影响视频分析。", "后端会继续按两分钟节流。"],
    };
    if (state.payload) {
      render(state.payload);
    }
  } finally {
    $("manualAiButton").disabled = false;
    $("manualAiButton").textContent = "智能分析";
  }
}

async function selectSource(sourceId) {
  await fetchJson("/sources/select", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sourceId }),
  });
  await refreshSources();
  sendControl("refresh_stream");
}

async function deleteSource(sourceId) {
  if (!window.confirm("确定删除这个视频源吗？")) return;
  await fetchJson(`/sources/${encodeURIComponent(sourceId)}`, { method: "DELETE" });
  await refreshSources();
  $("controlResult").textContent = "视频源已删除。";
}

async function addNetworkSource(event) {
  event.preventDefault();
  const label = $("sourceName").value.trim() || "IP Webcam 手机摄像头";
  const url = $("sourceUrl").value.trim();
  const transport = $("sourceTransport").value;
  if (!url) {
    $("controlResult").textContent = "请先填写手机摄像头地址。";
    return;
  }

  const data = await fetchJson("/sources/network", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label, url, transport }),
  });
  if (Array.isArray(data.items)) {
    renderSourceList(data.items);
  }
  await selectSource(data.source.source_id);
  $("controlResult").textContent = "视频源已添加并切换。";
}

async function sendControl(command, text = "") {
  const payload = { command, issuedAt: Date.now() };
  if (text) payload.text = text;
  const data = await fetchJson("/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  $("controlResult").textContent = text
    ? `家长留言已发送：${data.text}`
    : `指令已发送：${data.command}`;
}

function bindEvents() {
  $("sourceForm").addEventListener("submit", addNetworkSource);
  $("refreshSourcesButton").addEventListener("click", refreshSources);
  $("sendMessageButton").addEventListener("click", () => {
    const text = $("parentMessage").value.trim();
    sendControl(text ? "parent_message" : "voice_talk", text);
  });
  $("manualAiButton").addEventListener("click", refreshAiAdvice);
  $("sendAiScriptButton").addEventListener("click", sendAiScript);
  document.querySelectorAll("[data-command]").forEach((button) => {
    button.addEventListener("click", () => sendControl(button.dataset.command));
  });
}

function init() {
  $("videoFrame").src = `/video_feed?t=${Date.now()}`;
  $("sourceName").value = "IP Webcam 手机摄像头";
  $("sourceUrl").value = "http://192.168.137.71:8080/video";
  bindEvents();
  render({});
  refreshSources().catch(() => {
    $("controlResult").textContent = "视频源列表暂时不可用，请确认后端服务已启动。";
  });
  connectSocket();
}

init();
