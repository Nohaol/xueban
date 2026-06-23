const STATUS_META = {
  flow: {
    label: "心流专注",
    decisionTitle: "当前无需打扰",
    decisionSummary: "孩子处在连续专注区间，建议保持陪伴感，不主动打断。",
    primaryAction: "继续观察",
    advisorTitle: "保持陪伴感，不要打断心流",
    advisorSummary: "孩子已经进入连续专注区间，外部干预越少，学习效率通常越高。",
    bullets: ["此时不建议主动语音打断。", "如果需要提醒休息，尽量等这一段专注自然结束。"],
  },
  normal: {
    label: "稳定学习",
    decisionTitle: "当前无需打扰",
    decisionSummary: "整体状态平稳，继续观察比频繁提醒更合适。",
    primaryAction: "继续观察",
    advisorTitle: "保持节奏，减少无效干预",
    advisorSummary: "整体状态平稳，建议以陪伴式观察为主。",
    bullets: ["继续观察后续趋势。", "如果视线偏移连续出现，再考虑温和提醒。"],
  },
  distracted: {
    label: "轻度分心",
    decisionTitle: "适合轻提醒一次",
    decisionSummary: "当前更像阶段性的注意力波动，短句提醒通常比追问更有效。",
    primaryAction: "发送轻提醒",
    advisorTitle: "轻提醒通常比追问更有效",
    advisorSummary: "当前更像阶段性的注意力波动，短句提醒或调整坐姿往往更有效。",
    bullets: ["优先使用单步提醒。", "不要把一次分心直接解释为态度问题。"],
  },
  away: {
    label: "短暂离座",
    decisionTitle: "先观察，不急着提醒",
    decisionSummary: "当前仍在短暂离座容忍时间内，可以等待孩子自然回到座位。",
    primaryAction: "稍后提醒",
    advisorTitle: "属于正常放松区间",
    advisorSummary: "当前仍在短暂离座容忍时间内，不建议立刻频繁提醒。",
    bullets: ["先保持观察，等待孩子自然回到座位。", "临近学习节点时，可准备温和提醒。"],
  },
  timeout_away: {
    label: "超时离座",
    decisionTitle: "确认休息状态",
    decisionSummary: "离座已经超过阈值，建议先温和确认孩子是否在合理休息。",
    primaryAction: "发送回座提醒",
    advisorTitle: "先确认休息，再决定是否介入",
    advisorSummary: "超时离座不一定代表逃避学习，优先确认是否处于用餐、如厕或短暂走动场景。",
    bullets: ["建议先通过小智温和确认情况。", "如果连续多次超时离座，再考虑调整学习与休息节奏。"],
  },
};

const METRIC_META = [
  ["presence", "在座覆盖", "#3f7460"],
  ["posture", "位姿匹配", "#d7904b"],
  ["gaze", "面向一致", "#557fa3"],
  ["stability", "动作稳定", "#c55d5d"],
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
  socketConnected: false,
  socketReconnectTimer: null,
  aiAdvice: null,
  sessionStartedAt: Date.now(),
  videoSnapshotPaused: false,
  videoSnapshotToken: 0,
  videoSnapshotTimer: null,
  videoSnapshotInFlight: false,
  videoStableFrames: 0,
  videoSnapshotDelay: 900,
  calibrationTimer: null,
  calibrationEndsAt: 0,
  calibrationSourceId: "",
  calibrationStartedAt: 0,
  calibrationPhase: "",
};

const VIDEO_REFRESH_SLOW_MS = 900;
const VIDEO_REFRESH_WARM_MS = 360;
const VIDEO_REFRESH_FAST_MS = 140;
const VIDEO_STABLE_FRAME_COUNT = 3;

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

function dateTime(timestamp) {
  if (!timestamp) return "";
  const date = new Date(timestamp);
  return `${pad(date.getMonth() + 1)}/${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function compactDuration(totalSeconds) {
  const safe = Math.max(Math.floor(Number(totalSeconds) || 0), 0);
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${pad(minutes)}:${pad(seconds)}`;
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

function isCalibrating() {
  return state.calibrationPhase === "collecting" || state.calibrationPhase === "writing";
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
      sourceId: "",
      engineMode: "boot",
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
  element.className = "status-pill";
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
  if (isCalibrating() && (!state.calibrationSourceId || safe.sourceId === state.calibrationSourceId)) {
    renderCalibrationState(safe);
    return;
  }
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

  $("studentLabel").textContent = safe.studentLabel;
  $("focusScore").textContent = safe.focusScore;
  $("frameScore").textContent = `专注度 ${safe.focusScore}`;
  $("frameStatus").textContent = meta.label;
  setStatusClass($("frameStatus"), safe.status);
  $("decisionTitle").textContent = meta.decisionTitle;
  $("decisionSummary").textContent = meta.decisionSummary;
  $("primaryDecisionButton").textContent = meta.primaryAction;
  $("sourceLabel").textContent = safe.sourceLabel || safe.sourceId || "等待视频源";
  $("lastUpdateSummary").textContent = clock(safe.timestamp);
  $("engineMode").textContent = engineModeLabel(safe.engineMode);
  $("connectionLabel").textContent = state.socketConnected ? "本地视觉节点已接入" : "本地画面稳定，状态通道重连中";
  $("timeoutMask").classList.toggle("show", safe.status === "timeout_away");
  $("awayCountdown").textContent = duration(safe.awaySeconds);
  if (safe.awaySeconds > 0) {
    $("awayDuration").textContent = duration(safe.awaySeconds);
    $("awayStatus").textContent = safe.status === "timeout_away" ? "已超时离座" : "正在离座";
  } else {
    $("awayDuration").textContent = "当前在座";
    $("awayStatus").textContent = "在座状态";
  }

  renderMetrics(safe.metrics);
  renderCompactEvents();
  renderTimeline();
  renderTimelineStats(safe);
  renderHeatmap();
  renderAdvisor(meta);
  renderAnalytics();
  updateSessionTimer();
}

function renderCalibrationState(safe) {
  state.payload = safe;
  const remainingSeconds = Math.max(Math.ceil((state.calibrationEndsAt - Date.now()) / 1000), 0);
  const isWriting = state.calibrationPhase === "writing";
  $("studentLabel").textContent = safe.studentLabel;
  $("focusScore").textContent = "--";
  $("frameScore").textContent = isWriting ? "写入校准" : "姿态校准中";
  $("frameStatus").textContent = isWriting ? "写入校准" : "姿态校准中";
  setStatusClass($("frameStatus"), "normal");
  $("decisionTitle").textContent = isWriting ? "正在确认校准结果" : "正在校准姿态基准";
  $("decisionSummary").textContent = isWriting
    ? "正在等待本机节点写入当前设备的姿态基准。"
    : "请保持当前正确学习姿态，校准期间暂不更新专注判断。";
  $("primaryDecisionButton").textContent = isWriting ? "写入中" : "校准中";
  $("sourceLabel").textContent = safe.sourceLabel || safe.sourceId || "当前视频源";
  $("lastUpdateSummary").textContent = isWriting ? "确认中" : `剩余 ${remainingSeconds}s`;
  $("engineMode").textContent = isWriting ? "写入校准" : "校准中";
  $("connectionLabel").textContent = "正在记录当前设备的姿态基准";
  $("timeoutMask").classList.remove("show");
  $("awayCountdown").textContent = duration(0);
  $("awayDuration").textContent = "校准中";
  $("awayStatus").textContent = "暂停判断";
  renderMetrics({ presence: 0, posture: 0, gaze: 0, stability: 0 });
  updateSessionTimer();
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

function renderCompactEvents() {
  const events = state.events.slice(0, 3);
  if (!events.length) {
    $("compactEvents").innerHTML = '<div class="compact-event"><time>--:--</time><span>等待视觉节点事件。</span></div>';
    return;
  }
  $("compactEvents").innerHTML = events
    .map((item) => `<div class="compact-event"><time>${item.time}</time><span>${item.text}</span></div>`)
    .join("");
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
    ["当前状态持续", `${currentRun} 帧`, (STATUS_META[latestStatus] || STATUS_META.normal).label],
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
    { key: "score", label: "专注分", color: "#285242", getter: (item) => item.score },
    { key: "gaze", label: "视线", color: "#64ad85", getter: (item) => item.metrics?.gaze },
    { key: "posture", label: "坐姿", color: "#d7904b", getter: (item) => item.metrics?.posture },
    { key: "stability", label: "稳定", color: "#557fa3", getter: (item) => item.metrics?.stability },
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

function updateSessionTimer() {
  const elapsed = Math.floor((Date.now() - state.sessionStartedAt) / 1000);
  $("sessionTimer").textContent = `学习中 ${compactDuration(elapsed)}`;
}

function setVideoState(mode, message = "") {
  const shell = $("videoFrame").closest(".video-frame");
  const frame = $("videoFrame");
  const label = $("videoState");
  shell.classList.remove("is-loading", "is-error");
  if (mode === "loading") {
    state.videoSnapshotPaused = true;
    state.videoStableFrames = 0;
    state.videoSnapshotDelay = VIDEO_REFRESH_SLOW_MS;
    shell.classList.add("is-loading");
    frame.removeAttribute("src");
    label.textContent = message || "正在检测视频源";
    return;
  }
  if (mode === "error") {
    state.videoSnapshotPaused = false;
    state.videoStableFrames = 0;
    state.videoSnapshotDelay = VIDEO_REFRESH_SLOW_MS;
    shell.classList.add("is-error");
    frame.removeAttribute("src");
    label.textContent = message || "无画面";
    return;
  }
  state.videoSnapshotPaused = false;
  label.textContent = "";
}

function scheduleVideoSnapshot(delay = state.videoSnapshotDelay) {
  window.clearTimeout(state.videoSnapshotTimer);
  state.videoSnapshotTimer = window.setTimeout(refreshVideoSnapshot, delay);
}

function noteVideoSnapshotSuccess() {
  state.videoSnapshotInFlight = false;
  state.videoStableFrames += 1;
  state.videoSnapshotDelay =
    state.videoStableFrames >= VIDEO_STABLE_FRAME_COUNT
      ? VIDEO_REFRESH_FAST_MS
      : VIDEO_REFRESH_WARM_MS;
  setVideoState("live");
  scheduleVideoSnapshot();
}

function noteVideoSnapshotError() {
  state.videoSnapshotInFlight = false;
  state.videoStableFrames = 0;
  state.videoSnapshotDelay = VIDEO_REFRESH_SLOW_MS;
  setVideoState("error", "等待新画面");
  scheduleVideoSnapshot(VIDEO_REFRESH_SLOW_MS);
}

function refreshVideoSnapshot(options = {}) {
  if (!options.force && (state.videoSnapshotPaused || state.videoSnapshotInFlight)) return;
  const frame = $("videoFrame");
  const token = Date.now();
  state.videoSnapshotToken = token;
  state.videoSnapshotInFlight = true;
  frame.onload = () => {
    if (state.videoSnapshotToken === token) {
      noteVideoSnapshotSuccess();
    }
  };
  frame.onerror = () => {
    if (state.videoSnapshotToken === token) {
      noteVideoSnapshotError();
    }
  };
  frame.src = `/snapshot.jpg?t=${token}`;
}

function resetClientSession() {
  window.clearTimeout(state.videoSnapshotTimer);
  window.clearTimeout(state.socketReconnectTimer);
  state.events = [];
  state.heatmap = new Array(24).fill("normal");
  state.samples = [];
  state.aiAdvice = null;
  state.socketConnected = false;
  state.socketReconnectTimer = null;
  state.sessionStartedAt = Date.now();
  state.videoSnapshotPaused = false;
  state.videoSnapshotToken = 0;
  state.videoSnapshotTimer = null;
  state.videoSnapshotInFlight = false;
  state.videoStableFrames = 0;
  state.videoSnapshotDelay = VIDEO_REFRESH_SLOW_MS;
  setVideoState("loading", "正在重置到本机摄像头");
  render({});
}

async function resetToDefaultCamera() {
  resetClientSession();
  try {
    await sendControl("reset_session", "", { silent: true });
    await refreshSources().catch(() => {});
    connectSocket();
    setVideoState("live");
    refreshVideoSnapshot({ force: true });
    $("controlResult").textContent = "已重置为本机摄像头。";
  } catch (error) {
    setVideoState("error", "重置失败，正在重试");
    scheduleVideoSnapshot(VIDEO_REFRESH_SLOW_MS);
    $("controlResult").textContent = "重置失败，请稍后再试。";
  }
}

function switchView(viewName) {
  document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((button) => button.classList.remove("active"));
  $(`view-${viewName}`).classList.add("active");
  document.querySelector(`[data-view="${viewName}"]`).classList.add("active");
  const titles = {
    watch: "看护",
    advice: "建议",
    review: "复盘",
    device: "设备",
  };
  $("pageTitle").textContent = titles[viewName] || "看护";
}

async function sendAiScript() {
  const advice = state.aiAdvice || {};
  const script = (advice.xiaozhiScript || advice.message || $("aiScriptText").textContent || "").trim();
  if (!script || script === "本次不建议让小智主动打断。" || script.startsWith("暂无")) {
    $("controlResult").textContent = "当前没有可发送的小智话术，请先点击智能分析。";
    switchView("advice");
    return;
  }
  $("parentMessage").value = script;
  await sendControl("ai_script_message", script);
  $("aiScriptHint").textContent = "已作为小智提醒发送。";
}

function connectSocket() {
  if (state.socket) {
    state.socket.onclose = null;
    state.socket.onerror = null;
    state.socket.onmessage = null;
    state.socket.close();
  }
  window.clearTimeout(state.socketReconnectTimer);
  state.socket = new WebSocket(wsUrl());
  $("connectionLabel").textContent = "正在连接本地节点";

  state.socket.onopen = () => {
    state.socketConnected = true;
    $("connectionLabel").textContent = "本地视觉节点已接入";
  };

  state.socket.onmessage = (event) => {
    try {
      render(JSON.parse(event.data));
    } catch (error) {
      $("connectionLabel").textContent = "状态数据解析失败";
    }
  };

  state.socket.onclose = () => {
    state.socketConnected = false;
    if (state.payload) {
      $("connectionLabel").textContent = "本地画面稳定，状态通道重连中";
    } else {
      $("connectionLabel").textContent = "本地连接已断开";
    }
    state.socketReconnectTimer = window.setTimeout(connectSocket, 1500);
  };

  state.socket.onerror = () => {
    state.socketConnected = false;
    if (state.payload) {
      $("connectionLabel").textContent = "本地画面稳定，状态通道重连中";
    } else {
      $("connectionLabel").textContent = "等待本地服务启动";
    }
  };
}

async function fetchJson(path, options) {
  const response = await fetch(api(path), options);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    const error = new Error((data && data.error) || `HTTP ${response.status}`);
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

function renderSourceList(items = []) {
  const builtinSlots = [
    {
      source_id: "local-default",
      source_type: "local_camera",
      label: "本机摄像头",
      location: "0",
      transport: "stream",
      is_builtin: true,
      status: "idle",
      note: "固定本机摄像头槽位",
    },
    {
      source_id: "local-1",
      source_type: "local_camera",
      label: "本机摄像头 1",
      location: "1",
      transport: "stream",
      is_builtin: true,
      status: "idle",
      note: "固定本机摄像头槽位",
    },
  ];
  const byId = new Map(items.map((source) => [source.source_id, source]));
  const fixedSources = builtinSlots.map((fallback) => Object.assign({}, fallback, byId.get(fallback.source_id) || {}));
  const extensionSources = items
    .filter((source) => !["local-default", "local-1"].includes(source.source_id))
    .slice(0, 3);
  const spacers = Array.from({ length: Math.max(3 - extensionSources.length, 0) }, () => ({ spacer: true }));
  const slots = [...fixedSources, ...extensionSources, ...spacers].slice(0, 5);

  $("sourceList").innerHTML = slots
    .map((source) => {
      if (source.spacer) {
        return '<div class="source-spacer"></div>';
      }
      const selected = source.is_selected ? " selected" : "";
      const status = STATUS_LABELS[source.status] || source.status || "待命";
      const transport = TRANSPORT_LABELS[source.transport] || source.transport;
      const calibration = source.calibration || {};
      const calibrationText = calibration.calibrated
        ? `已校准 · ${dateTime(calibration.calibratedAt)}`
        : "未校准";
      const calibrationClass = calibration.calibrated ? "is-calibrated" : "is-uncalibrated";
      const deleteButton = source.is_builtin
        ? ""
        : `<button class="danger-button" type="button" data-delete-source-id="${source.source_id}">删除</button>`;
      return `
        <div class="source-item${selected}">
          <div>
            <strong>${source.label}</strong>
            <span>${status} · ${transport} · ${source.location}</span>
            <small class="source-calibration ${calibrationClass}">${calibrationText}</small>
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
  return data;
}

function findSource(items, sourceId) {
  return (items || []).find((source) => source.source_id === sourceId);
}

function hasFreshCalibration(source, startedAt) {
  const calibration = source?.calibration || {};
  return Boolean(calibration.calibrated && Number(calibration.calibratedAt || 0) >= startedAt - 1000);
}

async function waitForCalibrationSource(sourceId, startedAt) {
  for (let attempt = 0; attempt < 12; attempt += 1) {
    const data = await refreshSources();
    const source = findSource(data.items || [], sourceId);
    if (hasFreshCalibration(source, startedAt)) {
      return source;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 700));
  }
  return null;
}

async function refreshAiAdvice() {
  try {
    $("manualAiButton").disabled = true;
    $("manualAiButton").textContent = "分析中";
    const data = await fetchJson("/ai/advice?force=true");
    state.aiAdvice = data.advice;
    const seconds = Number(data.nextRefreshSeconds || data.minIntervalSeconds || 120);
    $("aiCostLabel").textContent = data.cached ? `缓存 ${seconds}s` : "已更新";
    if (state.payload) {
      render(state.payload);
    }
    switchView("advice");
  } catch (error) {
    state.aiAdvice = {
      title: "AI 建议暂不可用",
      summary: "DeepSeek 接口暂时没有返回，页面继续使用本地规则建议。",
      bullets: ["不会影响视频分析。", "后端会继续按两分钟节流。"],
    };
    if (state.payload) {
      render(state.payload);
    }
    switchView("advice");
  } finally {
    $("manualAiButton").disabled = false;
    $("manualAiButton").textContent = "智能分析";
  }
}

async function selectSource(sourceId) {
  window.clearTimeout(state.videoSnapshotTimer);
  state.videoSnapshotInFlight = false;
  $("sourceLabel").textContent = "正在切换视频源";
  $("engineMode").textContent = "重连中";
  setVideoState("loading", "正在检测视频源");
  try {
    await fetchJson("/sources/select", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sourceId }),
    });
    await sendControl("refresh_stream", "", { silent: true });
    await refreshSources();
    setTimeout(() => {
      setVideoState("live");
      refreshVideoSnapshot();
    }, 520);
  } catch (error) {
    const note = error.data?.note || error.data?.source?.note || "该视频源没有检测到可用画面。";
    $("sourceLabel").textContent = error.data?.current?.label || state.payload?.sourceLabel || "当前视频源";
    $("engineMode").textContent = "无画面";
    $("controlResult").textContent = `视频源不可用：${note}`;
    setVideoState("error", "无画面");
    await refreshSources().catch(() => {});
  }
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
    switchView("advice");
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

async function sendControl(command, text = "", options = {}) {
  const payload = { command, issuedAt: Date.now() };
  if (text) payload.text = text;
  const data = await fetchJson("/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!options.silent) {
    if (data.message) {
      $("controlResult").textContent = data.message;
      return data;
    }
    $("controlResult").textContent = text
      ? `家长留言已发送：${data.text}`
      : `指令已发送：${data.command}`;
  }
  return data;
}

function setCalibrationButton(progress, label, mode = "") {
  const button = $("calibrationButton");
  const row = $("calibrationRow");
  if (!button) return;
  if (row) row.style.setProperty("--calibration-progress", `${Math.max(0, Math.min(progress, 100))}%`);
  button.classList.toggle("is-running", mode === "running");
  button.classList.toggle("is-pending", mode === "pending");
  button.classList.toggle("is-complete", mode === "complete");
  button.disabled = mode === "running" || mode === "pending";
  button.textContent = label;
}

async function startPostureCalibration() {
  if (state.calibrationPhase) return;
  if (state.calibrationTimer) {
    clearInterval(state.calibrationTimer);
    state.calibrationTimer = null;
  }
  setCalibrationButton(0, "准备校准", "running");
  try {
    const data = await sendControl("calibrate_posture", "", { silent: true });
    const durationMs = Math.max(Number(data.duration || 12) * 1000, 3000);
    const startedAt = Date.now();
    state.calibrationStartedAt = startedAt;
    state.calibrationEndsAt = startedAt + durationMs;
    state.calibrationSourceId = data.sourceId || state.payload?.sourceId || "";
    state.calibrationPhase = "collecting";
    $("controlResult").textContent = "正在校准：请保持当前正确学习姿态。";
    state.calibrationTimer = setInterval(() => {
      const progress = Math.min(((Date.now() - startedAt) / durationMs) * 100, 100);
      setCalibrationButton(progress, `校准中 ${Math.round(progress)}%`, "running");
      if (progress >= 100) {
        clearInterval(state.calibrationTimer);
        state.calibrationTimer = null;
        state.calibrationPhase = "writing";
        state.calibrationEndsAt = Date.now() + 9000;
        setCalibrationButton(100, "写入校准", "pending");
        $("controlResult").textContent = "正在确认校准结果，请稍等。";
        waitForCalibrationSource(state.calibrationSourceId, state.calibrationStartedAt)
          .then((source) => {
            if (source) {
              state.calibrationPhase = "";
              state.calibrationEndsAt = 0;
              setCalibrationButton(100, "校准完成", "complete");
              $("controlResult").textContent = `姿态校准完成：${dateTime(source.calibration.calibratedAt)}。`;
              return;
            }
            state.calibrationPhase = "";
            state.calibrationEndsAt = 0;
            setCalibrationButton(0, "姿态校准", "");
            $("controlResult").textContent = "校准失败：没有检测到完整、稳定的人脸。请把眼睛和脸部移到画面中间后再试。";
          })
          .catch(() => {
            state.calibrationPhase = "";
            state.calibrationEndsAt = 0;
            setCalibrationButton(0, "姿态校准", "");
            $("controlResult").textContent = "校准结果刷新失败，请手动刷新设备列表确认。";
          })
          .finally(() => {
            state.calibrationSourceId = "";
            window.setTimeout(() => setCalibrationButton(0, "姿态校准", ""), 2600);
          });
      }
    }, 120);
  } catch (error) {
    if (state.calibrationTimer) {
      clearInterval(state.calibrationTimer);
      state.calibrationTimer = null;
    }
    state.calibrationEndsAt = 0;
    state.calibrationSourceId = "";
    state.calibrationPhase = "";
    setCalibrationButton(0, "姿态校准", "");
    $("controlResult").textContent = "姿态校准启动失败，请确认视频源正常。";
  }
}

function bindEvents() {
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.view));
  });
  document.querySelectorAll("[data-command]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.command === "refresh_stream") {
        resetToDefaultCamera();
        return;
      }
      sendControl(button.dataset.command);
    });
  });
  document.querySelectorAll("[data-template]").forEach((button) => {
    button.addEventListener("click", () => {
      $("parentMessage").value = button.dataset.template;
      switchView("advice");
    });
  });

  $("sourceForm").addEventListener("submit", addNetworkSource);
  $("refreshSourcesButton").addEventListener("click", refreshSources);
  $("sendMessageButton").addEventListener("click", () => {
    const text = $("parentMessage").value.trim();
    sendControl(text ? "parent_message" : "voice_talk", text);
  });
  $("manualAiButton").addEventListener("click", refreshAiAdvice);
  $("calibrationButton").addEventListener("click", startPostureCalibration);
  $("sendAiScriptButton").addEventListener("click", sendAiScript);
  $("primaryDecisionButton").addEventListener("click", () => {
    const status = state.payload?.status || "normal";
    if (status === "distracted") {
      $("parentMessage").value = "小智提醒你：把注意力放回书本上，我们再坚持十分钟。";
      switchView("advice");
      return;
    }
    if (status === "timeout_away") {
      $("parentMessage").value = "小智提醒你：休息好了就回到座位，我们继续完成这一小段。";
      switchView("advice");
      return;
    }
    $("controlResult").textContent = "当前建议继续观察，暂不主动打断。";
  });
}

function init() {
  setVideoState("loading", "正在连接视频源");
  $("sourceName").value = "IP Webcam 手机摄像头";
  $("sourceUrl").value = "http://192.168.137.71:8080/video";
  bindEvents();
  render({});
  refreshSources().catch(() => {
    $("controlResult").textContent = "视频源列表暂时不可用，请确认后端服务已启动。";
  });
  connectSocket();
  setInterval(updateSessionTimer, 1000);
  setTimeout(() => {
    setVideoState("live");
    refreshVideoSnapshot();
  }, 600);
}

init();
