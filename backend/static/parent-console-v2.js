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
  ["presence", "在座覆盖", "#365E4C"],
  ["posture", "位姿匹配", "#D48357"],
  ["gaze", "面向一致", "#5B849F"],
  ["stability", "动作稳定", "#C76963"],
];

const UI_COLORS = {
  primaryGreen: "#365E4C",
  accentAmber: "#D48357",
  neutralBlue: "#5B849F",
  alertCoral: "#C76963",
  darkGreen: "#4E876E",
  darkMuted: "#4B514D",
};

const HEATMAP_STATUS_LABELS = {
  empty: "\u672a\u68c0\u6d4b",
  normal: "\u5e73\u7a33",
  flow: "\u5e73\u7a33",
  distracted: "\u6ce2\u52a8",
  away: "\u79bb\u5ea7",
  timeout_away: "\u79bb\u5ea7",
};

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
  reviewSamples: [],
  reviewRange: "45m",
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
  displayStatus: "normal",
  displayStatusSince: Date.now(),
  pendingDisplayStatus: "",
  pendingDisplayStartedAt: 0,
  lastEventAtByStatus: {},
  lastReviewSampleAt: 0,
  lastReviewSampleStatus: "",
  lastReviewSampleScore: null,
  lastTrendRenderKey: "",
  stageInitialized: false,
  lastStageNoticeKey: "",
  stageSyncInFlight: false,
  settings: {
    xiaozhiMcpUrl: "",
    xiaozhiMcpTokenConfigured: false,
    tokenPreservationValue: "",
    tokenDirty: false,
    aiAnalysisMode: "manual",
    awayThresholdMinutes: 15,
    handlingMode: "parent",
    studyStage: "middle",
    stageLabel: "初中",
    stageSource: "default",
    stageUpdatedAt: 0,
    policy: {
      score_threshold: 65,
      persist_seconds: 15,
      cooldown_seconds: 120,
      max_per_10_minutes: 3,
    },
  },
  aiAutoTimer: null,
  lastManagedReminderAt: 0,
};

const STAGE_LABELS = {
  primary: "小学",
  middle: "初中",
  high: "高中",
};

const STAGE_SOURCE_LABELS = {
  parent: "家长设置",
  voice: "小智语音",
  system: "系统同步",
  default: "默认",
};

const VIDEO_REFRESH_SLOW_MS = 900;
const VIDEO_REFRESH_WARM_MS = 360;
const VIDEO_REFRESH_FAST_MS = 140;
const VIDEO_STABLE_FRAME_COUNT = 3;
const STATUS_DISPLAY_DELAY_MS = {
  flow: 5000,
  normal: 3000,
  distracted: 15000,
  away: 8000,
  timeout_away: 0,
};
const STATUS_EVENT_COOLDOWN_MS = {
  flow: 60000,
  normal: 60000,
  distracted: 90000,
  away: 45000,
  timeout_away: 30000,
};
const REVIEW_RANGES = {
  "5m": { label: "近 5 分钟", ms: 5 * 60 * 1000 },
  "15m": { label: "近 15 分钟", ms: 15 * 60 * 1000 },
  "30m": { label: "近 30 分钟", ms: 30 * 60 * 1000 },
  session: { label: "本次学习", ms: Infinity },
};
const REVIEW_RANGE_CONFIG = {
  "45m": { label: "45min", ms: 45 * 60 * 1000, bucketMs: 3 * 60 * 1000 },
  "90m": { label: "90min", ms: 90 * 60 * 1000, bucketMs: 5 * 60 * 1000 },
  "120m": { label: "120min", ms: 120 * 60 * 1000, bucketMs: 6 * 60 * 1000 },
};
const REVIEW_HISTORY_LIMIT_MS = 4 * 60 * 60 * 1000;
const REVIEW_SAMPLE_INTERVAL_MS = 30 * 1000;
const SETTINGS_STORAGE_KEY = "parentConsoleV2Settings";

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

function timeRangeLabel(start, end) {
  const startDate = new Date(start);
  const endDate = new Date(end);
  const sameDay = startDate.toDateString() === endDate.toDateString();
  const startTime = `${pad(startDate.getHours())}:${pad(startDate.getMinutes())}`;
  const endTime = `${pad(endDate.getHours())}:${pad(endDate.getMinutes())}`;
  if (sameDay) return `${startTime}-${endTime}`;
  return `${pad(startDate.getMonth() + 1)}/${pad(startDate.getDate())} ${startTime}-${pad(endDate.getMonth() + 1)}/${pad(endDate.getDate())} ${endTime}`;
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
      studyStage: state.settings.studyStage,
      stageLabel: state.settings.stageLabel,
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

function displayDelay(status) {
  return STATUS_DISPLAY_DELAY_MS[status] ?? 5000;
}

function resolveDisplayStatus(rawStatus) {
  const now = Date.now();
  const nextStatus = rawStatus || "normal";
  if (nextStatus === state.displayStatus) {
    state.pendingDisplayStatus = "";
    state.pendingDisplayStartedAt = 0;
    return state.displayStatus;
  }

  const delay = displayDelay(nextStatus);
  if (delay <= 0) {
    state.displayStatus = nextStatus;
    state.displayStatusSince = now;
    state.pendingDisplayStatus = "";
    state.pendingDisplayStartedAt = 0;
    return state.displayStatus;
  }

  if (state.pendingDisplayStatus !== nextStatus) {
    state.pendingDisplayStatus = nextStatus;
    state.pendingDisplayStartedAt = now;
    return state.displayStatus;
  }

  if (now - state.pendingDisplayStartedAt >= delay) {
    state.displayStatus = nextStatus;
    state.displayStatusSince = now;
    state.pendingDisplayStatus = "";
    state.pendingDisplayStartedAt = 0;
  }

  return state.displayStatus;
}

function displayEventText(displayStatus, rawPayload) {
  if (displayStatus !== rawPayload.status && rawPayload.status === "distracted") {
    return "检测到短暂状态波动，继续观察。";
  }
  return rawPayload.eventText || "视觉状态已更新。";
}

function pushEvent(payload) {
  const latest = state.events[0];
  const text = payload.eventText || "视觉状态已更新。";
  const now = Date.now();
  const cooldown = STATUS_EVENT_COOLDOWN_MS[payload.status] ?? 60000;
  const lastAt = state.lastEventAtByStatus[payload.status] || 0;
  if (latest && latest.text === text && latest.status === payload.status) return;
  if (now - lastAt < cooldown) return;
  state.lastEventAtByStatus[payload.status] = now;
  state.events.unshift({
    time: clock(payload.timestamp),
    text,
    status: payload.status,
  });
  state.events = state.events.slice(0, 10);
}

function normalizeStudyStage(stage) {
  return Object.prototype.hasOwnProperty.call(STAGE_LABELS, stage) ? stage : "middle";
}

function policyNumber(policy, key, fallback) {
  const value = Number(policy?.[key]);
  return Number.isFinite(value) && value >= 0 ? value : fallback;
}

function stageNotice(stage, source) {
  const label = STAGE_LABELS[stage] || "当前";
  if (source === "voice") return `已由小智语音切换为${label}模式`;
  if (source === "parent") return `已由家长切换为${label}模式`;
  if (source === "system") return `已由系统切换为${label}模式`;
  return `已同步为${label}模式`;
}

function renderStudyStage() {
  const stage = normalizeStudyStage(state.settings.studyStage);
  const label = state.settings.stageLabel || STAGE_LABELS[stage];
  document.querySelectorAll("[data-stage-label]").forEach((element) => {
    element.textContent = `${label}模式`;
  });
  document.querySelectorAll('input[name="studyStage"]').forEach((input) => {
    input.checked = input.value === stage;
  });

  $("stageLabel").textContent = label;
  $("stageSource").textContent =
    STAGE_SOURCE_LABELS[state.settings.stageSource] || STAGE_SOURCE_LABELS.system;
  $("policyScoreThreshold").textContent = policyNumber(
    state.settings.policy,
    "score_threshold",
    65
  );
  $("policyPersistSeconds").textContent = policyNumber(
    state.settings.policy,
    "persist_seconds",
    15
  );
  $("policyCooldownSeconds").textContent = policyNumber(
    state.settings.policy,
    "cooldown_seconds",
    120
  );
  $("policyMaxPer10Minutes").textContent = policyNumber(
    state.settings.policy,
    "max_per_10_minutes",
    3
  );
}

function applyStudyStage(data, options = {}) {
  const stage = normalizeStudyStage(data.studyStage || data.ageMode);
  const source = data.stageSource || state.settings.stageSource || "system";
  state.settings.studyStage = stage;
  state.settings.stageLabel = data.stageLabel || STAGE_LABELS[stage];
  state.settings.stageSource = source;
  state.settings.stageUpdatedAt = data.stageUpdatedAt || state.settings.stageUpdatedAt || 0;
  if (data.policy) {
    state.settings.policy = Object.assign({}, state.settings.policy, data.policy);
  }
  state.stageInitialized = true;
  renderStudyStage();

  if (options.announce) {
    const noticeKey = `${stage}:${source}:${state.settings.stageUpdatedAt || "current"}`;
    if (noticeKey !== state.lastStageNoticeKey) {
      state.lastStageNoticeKey = noticeKey;
      $("stageSyncStatus").textContent = stageNotice(stage, source);
    }
  } else if (options.statusText) {
    $("stageSyncStatus").textContent = options.statusText;
  }
}

async function syncStudyStageDetails(expectedStage, options = {}) {
  if (state.stageSyncInFlight) return;
  state.stageSyncInFlight = true;
  try {
    const current = await fetchJson("/study-stage");
    if (expectedStage && current.studyStage !== expectedStage) return;
    applyStudyStage(current, options);
  } catch (error) {
    $("stageSyncStatus").textContent = "阶段详情同步失败，将自动重试";
  } finally {
    state.stageSyncInFlight = false;
  }
}

function handlePayloadStudyStage(payload) {
  if (!payload.studyStage) return;
  const stage = normalizeStudyStage(payload.studyStage);
  if (!state.stageInitialized) {
    applyStudyStage(
      {
        studyStage: stage,
        stageLabel: payload.stageLabel,
      },
      { statusText: "已与本地节点同步" }
    );
    syncStudyStageDetails(stage).catch(() => {});
    return;
  }
  if (stage === state.settings.studyStage) return;

  applyStudyStage(
    {
      studyStage: stage,
      stageLabel: payload.stageLabel,
      stageSource: "system",
    },
    { statusText: "检测到阶段变化，正在同步来源" }
  );
  syncStudyStageDetails(stage, { announce: true }).catch(() => {});
}

function render(payload) {
  const safe = normalizePayload(payload || {});
  handlePayloadStudyStage(safe);
  if (isCalibrating() && (!state.calibrationSourceId || safe.sourceId === state.calibrationSourceId)) {
    renderCalibrationState(safe);
    return;
  }
  const displayStatus = resolveDisplayStatus(safe.status);
  const displayPayload = Object.assign({}, safe, {
    status: displayStatus,
    eventText: displayEventText(displayStatus, safe),
  });
  const meta = STATUS_META[displayStatus] || STATUS_META.normal;
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
  const now = Date.now();
  const statusChanged = state.lastReviewSampleStatus && state.lastReviewSampleStatus !== safe.status;
  const scoreChanged = state.lastReviewSampleScore !== null && Math.abs(state.lastReviewSampleScore - safe.focusScore) >= 12;
  const intervalElapsed = now - state.lastReviewSampleAt >= REVIEW_SAMPLE_INTERVAL_MS;
  if (!state.lastReviewSampleAt || intervalElapsed || statusChanged || scoreChanged) {
    state.reviewSamples.push({
      status: safe.status,
      score: safe.focusScore,
      metrics: Object.assign({}, safe.metrics),
      timestamp: now,
    });
    state.lastReviewSampleAt = now;
    state.lastReviewSampleStatus = safe.status;
    state.lastReviewSampleScore = safe.focusScore;
  }
  state.reviewSamples = state.reviewSamples.filter((item) => now - item.timestamp <= REVIEW_HISTORY_LIMIT_MS);
  pushEvent(displayPayload);

  setStudentLabel(safe.studentLabel);
  $("focusScore").textContent = safe.focusScore;
  $("frameScore").textContent = `专注度 ${safe.focusScore}`;
  $("frameStatus").textContent = meta.label;
  setStatusClass($("frameStatus"), displayStatus);
  $("decisionTitle").textContent = meta.decisionTitle;
  $("decisionSummary").textContent = meta.decisionSummary;
  $("primaryDecisionButton").textContent = meta.primaryAction;
  $("sourceLabel").textContent = safe.sourceLabel || safe.sourceId || "等待视频源";
  $("lastUpdateSummary").textContent = clock(safe.timestamp);
  $("engineMode").textContent = engineModeLabel(safe.engineMode);
  setConnectionLabel(state.socketConnected ? "本地视觉节点已接入" : "本地画面稳定，状态通道重连中");
  $("timeoutMask").classList.toggle("show", displayStatus === "timeout_away");
  $("awayCountdown").textContent = duration(safe.awaySeconds);
  if (safe.awaySeconds > 0) {
    $("awayDuration").textContent = duration(safe.awaySeconds);
    $("awayStatus").textContent = displayStatus === "timeout_away" ? "已超时离座" : "正在观察";
  } else {
    $("awayDuration").textContent = "当前在座";
    $("awayStatus").textContent = "在座状态";
  }

  renderMetrics(safe.metrics);
  renderCompactEvents();
  renderTimelineStats();
  renderHeatmap();
  renderAdvisor(meta);
  renderAnalytics();
  updateSessionTimer();
  maybeRunManagedReminder(safe).catch(() => {
    $("controlResult").textContent = "托管提醒发送失败，请检查小智 MCP 或本地服务状态。";
  });
}

function renderCalibrationState(safe) {
  state.payload = safe;
  const remainingSeconds = Math.max(Math.ceil((state.calibrationEndsAt - Date.now()) / 1000), 0);
  const isWriting = state.calibrationPhase === "writing";
  setStudentLabel(safe.studentLabel);
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
  setConnectionLabel("正在记录当前设备的姿态基准");
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

function reviewRangeMeta() {
  return REVIEW_RANGE_CONFIG[state.reviewRange] || REVIEW_RANGE_CONFIG["45m"];
}

function fixedReviewWindow(meta, now = Date.now()) {
  if (!Number.isFinite(meta.ms)) {
    return { start: state.sessionStartedAt, end: now };
  }
  const bucketMs = meta.bucketMs || Math.max(meta.ms / Math.max(trendBucketCount(meta), 1), 60 * 1000);
  const end = Math.ceil(now / bucketMs) * bucketMs;
  return { start: end - meta.ms, end };
}

function reviewSamplesForRange() {
  const meta = reviewRangeMeta();
  if (!Number.isFinite(meta.ms)) return state.reviewSamples.slice();
  const window = fixedReviewWindow(meta);
  return state.reviewSamples.filter((item) => item.timestamp >= window.start && item.timestamp <= window.end);
}

function sampleEvery(items, maxCount = 80) {
  if (items.length <= maxCount) return items;
  const step = Math.ceil(items.length / maxCount);
  return items.filter((_, index) => index % step === 0 || index === items.length - 1);
}

function minutesAgoLabel(timestamp, now = Date.now()) {
  const deltaMinutes = Math.max(0, Math.round((now - timestamp) / 60000));
  if (deltaMinutes < 1) return "现在";
  if (deltaMinutes < 60) return `${deltaMinutes}分钟前`;
  const hours = Math.floor(deltaMinutes / 60);
  const minutes = deltaMinutes % 60;
  return minutes ? `${hours}h${minutes}m前` : `${hours}h前`;
}

function average(items, getter) {
  if (!items.length) return 0;
  return Math.round(items.reduce((sum, item) => sum + clamp(getter(item)), 0) / items.length);
}

function reviewStats(samples) {
  const focusedCount = samples.filter((item) => statusGroup(item.status) === "focused").length;
  const distractedSamples = samples.filter((item) => statusGroup(item.status) === "distracted").length;
  const awaySamples = samples.filter((item) => statusGroup(item.status) === "away").length;
  const total = Math.max(samples.length, 1);
  const focusRatio = Math.round((focusedCount / total) * 100);
  const distractedRatio = Math.round((distractedSamples / total) * 100);
  const awayRatio = Math.round((awaySamples / total) * 100);
  const distractedCount = countTransitions(samples, (status) => statusGroup(status) === "distracted");
  const awayCount = countTransitions(samples, (status) => statusGroup(status) === "away");
  const avgScore = average(samples, (item) => item.score);
  const avgPosture = average(samples, (item) => item.metrics?.posture);
  return { focusRatio, distractedRatio, awayRatio, distractedCount, awayCount, avgScore, avgPosture };
}

function buildReviewAiContext() {
  const samples = reviewSamplesForRange();
  const stats = reviewStats(samples);
  const meta = reviewRangeMeta();
  const trendBuckets = buildTrendBuckets(samples, meta).map((bucket) => ({
    start: bucket.start,
    end: bucket.end,
    count: bucket.count,
    score: bucket.score,
    metrics: bucket.metrics,
  }));
  const heatmapHighlights = heatmapBuckets(samples)
    .filter((bucket) => bucket.count && bucket.status !== "normal")
    .slice(-16)
    .map((bucket) => ({
      timeLabel: bucket.timeLabel,
      status: bucket.status,
      count: bucket.count,
      avgScore: bucket.avgScore,
    }));
  return {
    range: { key: state.reviewRange, label: meta.label, ms: meta.ms },
    sampleCount: samples.length,
    stats,
    trendBuckets,
    heatmapHighlights,
    recentEvents: state.events.slice(0, 8),
    current: state.payload,
    settings: {
      handlingMode: state.settings.handlingMode,
      studyStage: state.settings.studyStage,
      stageLabel: state.settings.stageLabel,
      policy: Object.assign({}, state.settings.policy),
    },
  };
}

function renderTimelineStats() {
  const samples = reviewSamplesForRange();
  const stats = reviewStats(samples);
  const meta = reviewRangeMeta();
  const statusHint = stats.focusRatio >= 75 ? "整体节奏稳定" : stats.focusRatio >= 55 ? "存在一些波动" : "需要重点关注";

  const attentionCount = stats.distractedCount + stats.awayCount;
  const attentionHint = stats.awayCount
    ? `含 ${stats.awayCount} 次离座`
    : "连续波动只记一次";
  const cards = [
    ["专注占比", `${stats.focusRatio}%`, statusHint, ""],
    ["平均专注分", `${stats.avgScore || "--"}`, meta.label, ""],
    ["需要关注", `${attentionCount} 次`, attentionHint, stats.awayCount ? "is-danger" : stats.distractedCount ? "is-warning" : ""],
  ];

  $("timelineStats").innerHTML = cards
    .map(
      ([label, value, hint, tone]) => `
        <div class="review-summary-card ${tone}">
          <span>${label}</span>
          <strong>${value}</strong>
          <small>${hint}</small>
        </div>
      `
    )
    .join("");
}

function renderHeatmap() {
  const samples = reviewSamplesForRange();
  const buckets = heatmapBuckets(samples);
  $("heatmap").innerHTML = buckets
    .map((bucket, index) => {
      const status = bucket.count ? bucket.status || "normal" : "empty";
      const alpha = bucket.count ? Math.max(0.24, Math.min(0.86, bucket.intensity)) : 0.08;
      const label = HEATMAP_STATUS_LABELS[status] || HEATMAP_STATUS_LABELS.normal;
      const timeLabel = bucket.timeLabel || (bucket.count ? bucket.title : "\u6682\u65e0\u91c7\u6837");
      const score = bucket.count ? `\u5747\u5206 ${bucket.avgScore}` : "\u6682\u65e0\u5747\u5206";
      const detail = `${timeLabel}\n\u72b6\u6001\uff1a${label}\n\u91c7\u6837\uff1a${bucket.count} \u4e2a\uff5c${score}`;
      const column = Math.floor(index / 7);
      const edgeClass = column >= 12 ? " tooltip-left" : column <= 2 ? " tooltip-right" : "";
      return `<span class="heatmap-cell tone-${status}${edgeClass}" tabindex="0" style="--heat-alpha:${alpha.toFixed(2)}" data-tooltip="${escapeAttr(detail)}" aria-label="${escapeAttr(detail)}"></span>`;
    })
    .join("");
}

function escapeAttr(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function heatmapBuckets(samples) {
  const meta = reviewRangeMeta();
  return bucketSamples(samples, 112, meta.ms, fixedReviewWindow(meta));
}

function bucketSamples(samples, count, windowMs, fixedWindow = null) {
  if (false && !samples.length) {
    return Array.from({ length: count }, () => ({ status: "normal", count: 0, intensity: 0.12, title: "暂无采样" }));
  }
  const last = fixedWindow?.end ?? Date.now();
  const first = fixedWindow?.start ?? (last - windowMs);
  const span = windowMs;
  return Array.from({ length: count }, (_, bucketIndex) => {
    const start = first + (span / count) * bucketIndex;
    const end = first + (span / count) * (bucketIndex + 1);
    const bucketItems = samples.filter((item) => item.timestamp >= start && (bucketIndex === count - 1 ? item.timestamp <= end : item.timestamp < end));
    const groups = { focused: 0, distracted: 0, away: 0 };
    let scoreSum = 0;
    bucketItems.forEach((item) => {
      groups[statusGroup(item.status)] += 1;
      scoreSum += clamp(item.score);
    });
    const status = groups.away ? "away" : groups.distracted > groups.focused ? "distracted" : "normal";
    const avgScore = bucketItems.length ? scoreSum / bucketItems.length : 0;
    const instability = bucketItems.length ? 1 - avgScore / 100 : 0;
    const density = Math.min(1, bucketItems.length / Math.max(samples.length / count, 1));
    const intensity = Math.max(density * 0.62, instability * 0.84);
    const startDate = new Date(start);
    const endDate = new Date(end);
    return {
      status,
      count: bucketItems.length,
      avgScore: Math.round(avgScore),
      intensity,
      timeLabel: `${pad(startDate.getHours())}:${pad(startDate.getMinutes())}-${pad(endDate.getHours())}:${pad(endDate.getMinutes())}`,
      title: `${pad(startDate.getHours())}:${pad(startDate.getMinutes())}-${pad(endDate.getHours())}:${pad(endDate.getMinutes())} · ${bucketItems.length} 个采样`,
    };
  });
}

function trendWindowForRange(samples, meta) {
  const now = Date.now();
  if (Number.isFinite(meta.ms)) {
    const bucketMs = meta.bucketMs || Math.max(meta.ms / Math.max(trendBucketCount(meta), 1), 60 * 1000);
    const end = Math.ceil(now / bucketMs) * bucketMs;
    return { start: end - meta.ms, end };
  }
  if (!samples.length) {
    return { start: state.sessionStartedAt, end: now };
  }
  const firstSampleAt = samples.reduce((min, item) => Math.min(min, item.timestamp), samples[0].timestamp);
  const start = Math.min(state.sessionStartedAt, firstSampleAt);
  return { start, end: Math.max(now, start + 60 * 1000) };
}

function trendBucketCount(meta) {
  if (!Number.isFinite(meta.ms)) return 18;
  if (meta.bucketMs) return Math.max(1, Math.round(meta.ms / meta.bucketMs));
  return 18;
}

function buildTrendBuckets(samples, meta) {
  const window = trendWindowForRange(samples, meta);
  const count = trendBucketCount(meta);
  const span = Math.max(window.end - window.start, 1000);
  return Array.from({ length: count }, (_, index) => {
    const start = window.start + (span / count) * index;
    const end = window.start + (span / count) * (index + 1);
    const bucketItems = samples.filter((item) => item.timestamp >= start && (index === count - 1 ? item.timestamp <= end : item.timestamp < end));
    const score = bucketItems.length
      ? Math.round(bucketItems.reduce((sum, item) => sum + clamp(item.score), 0) / bucketItems.length)
      : null;
    const metrics = bucketItems.length
      ? {
          gaze: Math.round(bucketItems.reduce((sum, item) => sum + clamp(item.metrics?.gaze), 0) / bucketItems.length),
          posture: Math.round(bucketItems.reduce((sum, item) => sum + clamp(item.metrics?.posture), 0) / bucketItems.length),
          stability: Math.round(bucketItems.reduce((sum, item) => sum + clamp(item.metrics?.stability), 0) / bucketItems.length),
          presence: Math.round(bucketItems.reduce((sum, item) => sum + clamp(item.metrics?.presence), 0) / bucketItems.length),
        }
      : null;
    return { start, end, count: bucketItems.length, score, metrics };
  });
}

function smoothTrendValues(buckets, getter = (bucket) => bucket.score) {
  const values = buckets.map((bucket) => {
    const value = getter(bucket);
    return value === null || value === undefined ? null : clamp(value);
  });
  return values.map((value, index) => {
    if (value === null || value === undefined) return null;
    let weightedSum = 0;
    let weightTotal = 0;
    [-2, -1, 0, 1, 2].forEach((offset) => {
      const nearby = values[index + offset];
      if (nearby === null || nearby === undefined) return;
      const weight = offset === 0 ? 4 : Math.abs(offset) === 1 ? 2 : 1;
      weightedSum += nearby * weight;
      weightTotal += weight;
    });
    return Math.round(weightedSum / Math.max(weightTotal, 1));
  });
}

function trendPathForBuckets(buckets, chart, getter = (bucket) => bucket.score) {
  const span = Math.max(chart.end - chart.start, 1000);
  const smoothed = smoothTrendValues(buckets, getter);
  let hasOpenSegment = false;
  return buckets
    .map((bucket, index) => {
      const value = smoothed[index];
      if (!bucket.count || value === null || value === undefined) {
        hasOpenSegment = false;
        return "";
      }
      const center = (bucket.start + bucket.end) / 2;
      const x = chart.left + ((center - chart.start) / span) * chart.width;
      const y = chart.top + (1 - clamp(value) / 100) * chart.height;
      const command = hasOpenSegment ? "L" : "M";
      hasOpenSegment = true;
      return `${command}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .filter(Boolean)
    .join(" ");
}

function renderTrendTooltipContent(data) {
  const rows = [
    ["专注分", data.score],
    ["面向一致", data.gaze],
    ["位姿匹配", data.posture],
    ["动作稳定", data.stability],
    ["在座状态", data.presence],
  ];
  return `
    <strong>${data.time || "当前采样段"}</strong>
    <div>
      ${rows
        .map(([label, value]) => `<span>${label}</span><b>${value === "--" ? "--" : `${value}`}</b>`)
        .join("")}
    </div>
  `;
}

function bindTrendTooltips() {
  const chart = $("trendChart");
  const tooltip = $("trendTooltip");
  if (!chart || !tooltip) return;

  const show = (target, event) => {
    if (!target?.dataset?.tooltip) return;
    let data = null;
    try {
      data = JSON.parse(target.dataset.tooltip);
    } catch {
      return;
    }
    tooltip.innerHTML = renderTrendTooltipContent(data);
    tooltip.classList.add("show");
    const targetRect = target.getBoundingClientRect();
    const pointer = typeof event?.clientX === "number"
      ? event
      : { clientX: targetRect.left + targetRect.width / 2, clientY: targetRect.top + targetRect.height / 2 };
    move(pointer);
  };
  const move = (event) => {
    const rect = chart.getBoundingClientRect();
    const x = Math.max(12, Math.min(event.clientX - rect.left + 14, rect.width - 176));
    const y = Math.max(12, Math.min(event.clientY - rect.top - 26, rect.height - 132));
    tooltip.style.transform = `translate(${x}px, ${y}px)`;
  };
  const hide = () => {
    tooltip.classList.remove("show");
  };

  chart.querySelectorAll(".chart-score-bar").forEach((bar) => {
    bar.addEventListener("mouseenter", (event) => show(bar, event));
    bar.addEventListener("mousemove", move);
    bar.addEventListener("mouseleave", hide);
    bar.addEventListener("focus", (event) => show(bar, event));
    bar.addEventListener("blur", hide);
  });
}

function renderReviewDistribution(samples) {
  const stats = reviewStats(samples);
  if (!samples.length) {
    $("reviewDonut").style.background = "linear-gradient(90deg, rgba(78, 135, 110, 0.28) 0% 100%)";
    $("reviewBalanceLabel").textContent = "等待采样";
    $("reviewBreakdown").innerHTML = ["专注", "波动", "离座"].map((label) => `
      <div class="review-breakdown-row">
        <span>${label}</span>
        <div class="review-breakdown-track"><i class="review-breakdown-fill" style="width:0%;background:${UI_COLORS.darkMuted}"></i></div>
        <strong>--</strong>
      </div>
    `).join("");
    return;
  }
  const focusedStop = stats.focusRatio;
  const distractedStop = focusedStop + stats.distractedRatio;
  $("reviewDonut").style.background = `linear-gradient(90deg, ${UI_COLORS.darkGreen} 0% ${focusedStop}%, ${UI_COLORS.accentAmber} ${focusedStop}% ${distractedStop}%, ${UI_COLORS.alertCoral} ${distractedStop}% 100%)`;
  $("reviewBalanceLabel").textContent = samples.length ? `${samples.length} 个采样点` : "等待采样";
  const rows = [
    ["专注", stats.focusRatio, UI_COLORS.darkGreen],
    ["波动", stats.distractedRatio, UI_COLORS.accentAmber],
    ["离座", stats.awayRatio, UI_COLORS.alertCoral],
  ];
  $("reviewBreakdown").innerHTML = rows.map(([label, value, color]) => `
    <div class="review-breakdown-row">
      <span>${label}</span>
      <div class="review-breakdown-track">
        <i class="review-breakdown-fill" style="width:${value}%;background:${color}"></i>
      </div>
      <strong>${value}%</strong>
    </div>
  `).join("");
}

function renderReviewInsight(samples) {
  const stats = reviewStats(samples);
  let tone = "观察";
  let title = "保持当前节奏";
  let copy = "整体比较平稳，少打断，关注任务是否按计划推进。";
  if (!samples.length) {
    title = "等待学习数据";
    copy = "开始学习后，这里会沉淀更长时间的状态趋势。";
  } else if (stats.awayCount > 0) {
    tone = "关注离座";
    title = "留意离座发生的时段";
    copy = "如果离座集中出现在同一类任务后，考虑调整休息节奏或任务切分。";
  } else if (stats.distractedCount >= 2 || stats.focusRatio < 60) {
    tone = "轻度关注";
    title = "波动比平时更明显";
    copy = "建议先看任务难度和疲劳程度，再决定是否用一句短提醒介入。";
  } else if (stats.avgPosture && stats.avgPosture < 65) {
    tone = "坐姿观察";
    title = "坐姿匹配度偏低";
    copy = "可以在下一段学习前做一次姿态校准，避免摄像头角度造成误判。";
  }
  $("reviewInsightTone").textContent = tone;
  $("reviewHeadline").textContent = title;
  $("reviewSummary").textContent = copy;
  $("reviewInsight").innerHTML = `
    <div class="review-insight-card">
      <strong>${title}</strong>
      <p>${copy}</p>
      <small>${reviewRangeMeta().label} · ${samples.length} 个采样点</small>
    </div>
  `;
}

function renderAnalytics() {
  const rangeSamples = reviewSamplesForRange();
  const rangeMeta = reviewRangeMeta();
  const trendItems = [
    { key: "bar", label: "分数柱", color: "rgba(237, 244, 239, 0.18)" },
    { key: "line", label: "稳定趋势", color: UI_COLORS.darkGreen },
  ];

  $("trendLegend").innerHTML = trendItems
    .map((item) => `<span><i style="background:${item.color}"></i>${item.label}</span>`)
    .join("");
  $("trendRangeLabel").textContent = `${rangeMeta.label}趋势`;
  $("heatmapRangeLabel").textContent = rangeMeta.label;
  $("reviewSampleLabel").textContent = rangeSamples.length ? `${rangeSamples.length} 个采样点` : "等待数据";

  const latestSample = rangeSamples[rangeSamples.length - 1];
  const trendRenderKey = [
    state.reviewRange,
    rangeSamples.length,
    latestSample?.timestamp || 0,
    latestSample?.score || 0,
    latestSample?.metrics?.stability || 0,
    Math.floor(Date.now() / 60000),
  ].join(":");
  if (state.lastTrendRenderKey === trendRenderKey && $("trendChart").querySelector("svg")) {
    renderReviewDistribution(rangeSamples);
    renderReviewInsight(rangeSamples);
    return;
  }
  state.lastTrendRenderKey = trendRenderKey;

  const chart = { left: 26, top: 14, width: 486, height: 358 };
  const buckets = buildTrendBuckets(rangeSamples, rangeMeta);
  chart.start = buckets[0]?.start || Date.now();
  chart.end = buckets[buckets.length - 1]?.end || Date.now();
  const span = Math.max(chart.end - chart.start, 1000);
  const now = Date.now();
  const gridLines = [0, 25, 50, 75, 100]
    .map((value) => {
      const y = chart.top + (1 - value / 100) * chart.height;
      return `
        <line class="chart-grid-line" x1="${chart.left}" y1="${y.toFixed(1)}" x2="${chart.left + chart.width}" y2="${y.toFixed(1)}" />
        <text class="chart-y-label" x="${chart.left - 7}" y="${(y + 4).toFixed(1)}">${value}</text>
      `;
    })
    .join("");
  const tickFractions = [0, 0.25, 0.5, 0.75, 1];
  const tickLabels = tickFractions
    .map((fraction) => {
      const x = chart.left + chart.width * fraction;
      const tickAt = chart.start + span * fraction;
      return `
        <line class="chart-tick" x1="${x.toFixed(1)}" y1="${chart.top + chart.height}" x2="${x.toFixed(1)}" y2="${chart.top + chart.height + 4}" />
        <text class="chart-x-label" x="${x.toFixed(1)}" y="${chart.top + chart.height + 28}">${minutesAgoLabel(tickAt, now)}</text>
      `;
    })
    .join("");
  const maxBarWidth = 18;
  const barWidth = Math.min(maxBarWidth, Math.max(9, (chart.width / buckets.length) * 0.42));
  const scoreBars = buckets
    .map((bucket) => {
      if (!bucket.count || bucket.score === null || bucket.score === undefined) return "";
      const center = (bucket.start + bucket.end) / 2;
      const x = chart.left + ((center - chart.start) / span) * chart.width;
      const score = clamp(bucket.score);
      const y = chart.top + (1 - score / 100) * chart.height;
      const height = chart.top + chart.height - y;
      const isRecent = bucket.end >= now - Math.max(rangeMeta.ms / buckets.length, 60 * 1000);
      const detail = {
        time: `${timeRangeLabel(bucket.start, bucket.end)} · ${bucket.count} 个采样`,
        score,
        gaze: bucket.metrics?.gaze ?? "--",
        posture: bucket.metrics?.posture ?? "--",
        stability: bucket.metrics?.stability ?? "--",
        presence: bucket.metrics?.presence ?? "--",
      };
      return `
        <rect
          class="chart-score-bar${isRecent ? " is-recent" : ""}"
          x="${(x - barWidth / 2).toFixed(1)}"
          y="${y.toFixed(1)}"
          width="${barWidth.toFixed(1)}"
          height="${Math.max(height, 2).toFixed(1)}"
          rx="${(barWidth / 2).toFixed(1)}"
          tabindex="0"
          data-tooltip="${escapeAttr(JSON.stringify(detail))}"
        ></rect>
      `;
    })
    .join("");
  const stabilityGetter = (bucket) => bucket.metrics?.stability;
  const smoothed = smoothTrendValues(buckets, stabilityGetter);
  const trendPath = trendPathForBuckets(buckets, chart, stabilityGetter);
  const trendArea = trendPath
    ? `${trendPath} L ${chart.left + chart.width} ${chart.top + chart.height} L ${chart.left} ${chart.top + chart.height} Z`
    : "";
  const dots = buckets
    .map((bucket, index) => {
      const value = smoothed[index];
      if (!bucket.count || value === null || value === undefined) return "";
      const x = chart.left + ((((bucket.start + bucket.end) / 2) - chart.start) / span) * chart.width;
      const y = chart.top + (1 - clamp(value) / 100) * chart.height;
      return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="4.2" />`;
    })
    .join("");
  const emptyState = rangeSamples.length
    ? ""
    : `<g class="chart-empty">
        <text x="241" y="144">等待该时间窗内的采样</text>
        <text x="241" y="164">曲线会按真实时间落点生成</text>
      </g>`;
  $("trendChart").innerHTML = `
    <svg viewBox="0 0 528 430" preserveAspectRatio="none" aria-label="指标趋势图">
      <defs>
        <clipPath id="trendPlotClip"><rect x="${chart.left}" y="${chart.top}" width="${chart.width}" height="${chart.height}" rx="6" /></clipPath>
      </defs>
      <rect class="chart-plot-bg" x="${chart.left}" y="${chart.top}" width="${chart.width}" height="${chart.height}" rx="6" />
      <g class="chart-grid">${gridLines}</g>
      <g class="chart-axis">${tickLabels}</g>
      <g class="chart-bars" clip-path="url(#trendPlotClip)">${scoreBars}</g>
      <g class="chart-lines" clip-path="url(#trendPlotClip)">
        ${trendArea ? `<path class="chart-trend-area" d="${trendArea}" />` : ""}
        <path class="chart-trend-line" d="${trendPath}" />
        <g class="chart-dots">${dots}</g>
      </g>
      ${emptyState}
    </svg>
    <div class="trend-tooltip" id="trendTooltip" role="status"></div>
  `;
  bindTrendTooltips();
  renderReviewDistribution(rangeSamples);
  renderReviewInsight(rangeSamples);
}

function renderAdvisor(meta) {
  const advice = state.aiAdvice;
  const sendButton = $("sendAiScriptButton");
  const scriptHint = $("aiScriptHint");
  if (!advice) {
    $("advisorTitle").textContent = meta.advisorTitle;
    $("advisorSummary").textContent = meta.advisorSummary;
    $("advisorBullets").innerHTML = meta.bullets.map((item) => `<li>${item}</li>`).join("");
    $("aiScriptText").textContent = "暂无，需要时点击生成复盘建议。";
    $("aiDetailGrid").innerHTML = "";
    sendButton.disabled = true;
    scriptHint.textContent = "AI 复盘后可一键转为小智提醒。";
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
    ["复盘依据", advice.reason || "基于近期状态占比、趋势桶、热力墙和事件记录生成。"],
    ["是否提醒", advice.shouldRemind ? "建议提醒" : "暂不提醒"],
    ["提醒等级", advice.reminderLevel || "observe"],
  ];
  if (Array.isArray(advice.observations) && advice.observations.length) {
    details.push(["时域观察", advice.observations.join("；")]);
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
  const label = `学习中 ${compactDuration(elapsed)}`;
  $("sessionTimer").textContent = label;
  document.querySelectorAll("[data-session-timer]").forEach((element) => {
    element.textContent = label;
  });
}

function setStudentLabel(label) {
  $("studentLabel").textContent = label;
  document.querySelectorAll("[data-student-label]").forEach((element) => {
    element.textContent = label;
  });
}

function setConnectionLabel(label) {
  $("connectionLabel").textContent = label;
  document.querySelectorAll("[data-connection-label]").forEach((element) => {
    element.textContent = label;
  });
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
  document.querySelector(".workspace").classList.toggle("is-review-mode", viewName === "review");
  const titles = {
    watch: "看护",
    advice: "建议",
    review: "Study Review",
    device: "设备",
  };
  $("pageTitle").textContent = titles[viewName] || "看护";
}

async function sendAiScript() {
  const advice = state.aiAdvice || {};
  const script = (advice.xiaozhiScript || advice.message || $("aiScriptText").textContent || "").trim();
  if (!script || script === "本次不建议让小智主动打断。" || script.startsWith("暂无")) {
    $("controlResult").textContent = "当前没有可发送的小智话术，请先生成复盘建议。";
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
  setConnectionLabel("正在连接本地节点");

  state.socket.onopen = () => {
    state.socketConnected = true;
    setConnectionLabel("本地视觉节点已接入");
  };

  state.socket.onmessage = (event) => {
    try {
      render(JSON.parse(event.data));
    } catch (error) {
      setConnectionLabel("状态数据解析失败");
    }
  };

  state.socket.onclose = () => {
    state.socketConnected = false;
    if (state.payload) {
      setConnectionLabel("本地画面稳定，状态通道重连中");
    } else {
      setConnectionLabel("本地连接已断开");
    }
    state.socketReconnectTimer = window.setTimeout(connectSocket, 1500);
  };

  state.socket.onerror = () => {
    state.socketConnected = false;
    if (state.payload) {
      setConnectionLabel("本地画面稳定，状态通道重连中");
    } else {
      setConnectionLabel("等待本地服务启动");
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

function effectiveManagedScoreThreshold() {
  return policyNumber(state.settings.policy, "score_threshold", 65);
}

function effectiveManagedCooldownMs() {
  return policyNumber(state.settings.policy, "cooldown_seconds", 120) * 1000;
}

function isMaskedToken(value) {
  return /\*{3,}/.test(String(value || "").trim());
}

function readSettingsForm() {
  return {
    xiaozhiMcpUrl: $("xiaozhiMcpUrl").value.trim(),
    aiAnalysisMode: $("aiAnalysisMode").value,
    awayThresholdMinutes: Math.max(1, Math.min(120, Number($("awayThresholdMinutes").value || 15))),
    handlingMode: $("handlingMode").value,
  };
}

function writeSettingsForm() {
  $("xiaozhiMcpUrl").value = state.settings.xiaozhiMcpUrl || "";
  if (!state.settings.tokenDirty) {
    $("xiaozhiMcpToken").value = "";
  }
  $("xiaozhiMcpToken").placeholder = state.settings.xiaozhiMcpTokenConfigured
    ? "已配置，留空则保持不变"
    : "可选";
  $("aiAnalysisMode").value = state.settings.aiAnalysisMode || "manual";
  $("awayThresholdMinutes").value = state.settings.awayThresholdMinutes || 15;
  $("handlingMode").value = state.settings.handlingMode || "parent";
  renderStudyStage();
}

function saveLocalSettings() {
  try {
    window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify({
      aiAnalysisMode: state.settings.aiAnalysisMode,
      handlingMode: state.settings.handlingMode,
    }));
  } catch (error) {
    // Local persistence is best effort only.
  }
}

function loadLocalSettings() {
  try {
    const raw = window.localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (!raw) return;
    const local = JSON.parse(raw);
    if (local.aiAnalysisMode) state.settings.aiAnalysisMode = local.aiAnalysisMode;
    if (local.handlingMode) state.settings.handlingMode = local.handlingMode;
  } catch (error) {
    // Ignore malformed local settings.
  }
}

function applyAiAnalysisSchedule() {
  window.clearInterval(state.aiAutoTimer);
  state.aiAutoTimer = null;
  const mode = state.settings.aiAnalysisMode;
  if (mode === "manual") {
    $("aiCostLabel").textContent = "手动生成";
    return;
  }
  const minutes = Math.max(1, Number(mode || 5));
  $("aiCostLabel").textContent = `每 ${minutes} 分钟复盘`;
  state.aiAutoTimer = window.setInterval(() => {
    refreshAiAdvice({ force: false, switchToAdvice: false, silent: true });
  }, minutes * 60 * 1000);
}

async function loadSettings() {
  try {
    const remote = await fetchJson("/settings");
    state.settings = Object.assign({}, state.settings, {
      xiaozhiMcpUrl: remote.xiaozhiMcpUrl || "",
      xiaozhiMcpTokenConfigured:
        Boolean(remote.xiaozhiMcpTokenConfigured) || isMaskedToken(remote.xiaozhiMcpToken),
      tokenPreservationValue: isMaskedToken(remote.xiaozhiMcpToken)
        ? remote.xiaozhiMcpToken
        : "",
      tokenDirty: false,
      awayThresholdMinutes: Number(remote.awayTimeoutMinutes || state.settings.awayThresholdMinutes),
    });
    applyStudyStage(remote, { statusText: "已与后端设置同步" });
  } catch (error) {
    $("stageSyncStatus").textContent = "设置读取失败，等待本地节点";
  }
  writeSettingsForm();
  applyAiAnalysisSchedule();
}

async function saveSettings(event) {
  event.preventDefault();
  state.settings = Object.assign({}, state.settings, readSettingsForm());
  saveLocalSettings();
  applyAiAnalysisSchedule();
  const payload = {
    awayTimeoutMinutes: state.settings.awayThresholdMinutes,
    xiaozhiMcpUrl: state.settings.xiaozhiMcpUrl,
    ageMode: state.settings.studyStage,
    stageSource: ["parent", "voice", "system"].includes(state.settings.stageSource)
      ? state.settings.stageSource
      : "system",
  };
  if (state.settings.tokenDirty) {
    payload.xiaozhiMcpToken = $("xiaozhiMcpToken").value.trim();
  } else if (state.settings.tokenPreservationValue) {
    payload.xiaozhiMcpToken = state.settings.tokenPreservationValue;
  }
  const saved = await fetchJson("/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  state.settings.awayThresholdMinutes = Number(saved.awayTimeoutMinutes || state.settings.awayThresholdMinutes);
  state.settings.xiaozhiMcpTokenConfigured =
    Boolean(saved.xiaozhiMcpTokenConfigured) || isMaskedToken(saved.xiaozhiMcpToken);
  state.settings.tokenPreservationValue = isMaskedToken(saved.xiaozhiMcpToken)
    ? saved.xiaozhiMcpToken
    : "";
  state.settings.tokenDirty = false;
  applyStudyStage(saved, { statusText: "设置已保存并同步" });
  writeSettingsForm();
  $("controlResult").textContent =
    `设置已保存：${state.settings.stageLabel}模式，提醒阈值 ${effectiveManagedScoreThreshold()} 分，冷却 ${policyNumber(state.settings.policy, "cooldown_seconds", 120)} 秒。`;
}

async function setStudyStage(stage) {
  const previousStage = state.settings.studyStage;
  const inputs = document.querySelectorAll('input[name="studyStage"]');
  inputs.forEach((input) => {
    input.disabled = true;
  });
  $("stageSyncStatus").textContent = "正在同步阶段设置";
  try {
    const saved = await fetchJson("/study-stage", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage, source: "parent" }),
    });
    applyStudyStage(saved, { announce: true });
  } catch (error) {
    state.settings.studyStage = previousStage;
    renderStudyStage();
    $("stageSyncStatus").textContent = "阶段切换失败，请稍后重试";
  } finally {
    inputs.forEach((input) => {
      input.disabled = false;
    });
  }
}

function shouldManagedReminder(payload) {
  if (state.settings.handlingMode !== "managed") return false;
  if (!payload) return false;
  const now = Date.now();
  const cooldownMs = effectiveManagedCooldownMs();
  if (now - state.lastManagedReminderAt < cooldownMs) return false;
  if (payload.status === "timeout_away") return true;
  return payload.focusScore < effectiveManagedScoreThreshold();
}

function fallbackManagedScript(payload) {
  if (payload.status === "timeout_away") {
    return "小智提醒你：休息好了就回到座位上，我们继续完成这一小段哦！";
  }
  if (payload.metrics?.posture < 55) {
    return "小智提醒你：坐直一点，眼睛和书本保持舒服的距离。";
  }
  return "小智提醒你：把注意力放回当前任务上，我们再坚持一小段。";
}

async function maybeRunManagedReminder(payload) {
  if (!shouldManagedReminder(payload)) return;
  state.lastManagedReminderAt = Date.now();
  const advice = state.aiAdvice || await refreshAiAdvice({ force: false, switchToAdvice: false, silent: true });
  const script = (advice?.xiaozhiScript || advice?.message || fallbackManagedScript(payload)).trim();
  if (!script) return;
  const result = await sendControl("managed_ai_reminder", script, { silent: true });
  $("controlResult").textContent = `托管${reminderQueueMessage(result)}`;
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

async function refreshAiAdvice(options = {}) {
  const force = options.force !== false;
  const switchToAdviceView = options.switchToAdvice !== false;
  const silent = Boolean(options.silent);
  try {
    if (!silent) {
      $("manualAiButton").disabled = true;
      $("manualAiButton").textContent = "复盘中";
    }
    const data = await fetchJson(`/ai/review?force=${force ? "true" : "false"}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ context: buildReviewAiContext() }),
    });
    state.aiAdvice = data.advice;
    const seconds = Number(data.nextRefreshSeconds || data.minIntervalSeconds || 120);
    if (state.settings.aiAnalysisMode === "manual") {
      $("aiCostLabel").textContent = data.cached ? `缓存 ${seconds}s` : "已更新";
    }
    if (state.payload) {
      render(state.payload);
    }
    if (switchToAdviceView) switchView("advice");
    return state.aiAdvice;
  } catch (error) {
    state.aiAdvice = {
      title: "AI 复盘建议暂不可用",
      summary: "DeepSeek 接口暂时没有返回，页面继续使用本地复盘规则建议。",
      bullets: ["不会影响视频分析。", "后端会继续按两分钟节流。"],
    };
    if (state.payload) {
      render(state.payload);
    }
    if (switchToAdviceView) switchView("advice");
    return state.aiAdvice;
  } finally {
    if (!silent) {
      $("manualAiButton").disabled = false;
      $("manualAiButton").textContent = "生成复盘建议";
    }
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

function reminderQueueMessage(data) {
  if (!data?.reminder) return "指令已由本地节点接收。";
  if (data.mcpStatus?.running) {
    return "提醒已入队；MCP 正在运行，等待设备领取。";
  }
  if (data.mcpStatus) {
    return "提醒已入队；MCP 未运行，暂不会播报。";
  }
  return "提醒已入队；MCP 状态暂不可用，尚不能确认播报。";
}

async function sendControl(command, text = "", options = {}) {
  const payload = { command, issuedAt: Date.now() };
  if (text) payload.text = text;
  const data = await fetchJson("/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (data.reminder) {
    data.mcpStatus = await fetchJson("/mcp/status").catch(() => null);
  }
  if (!options.silent) {
    if (data.reminder) {
      $("controlResult").textContent = reminderQueueMessage(data);
    } else if (data.message) {
      $("controlResult").textContent = data.message;
    } else {
      $("controlResult").textContent = `指令已接收：${data.command}`;
    }
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
      document.querySelectorAll("[data-template]").forEach((item) => {
        item.classList.toggle("is-active", item === button);
      });
      $("parentMessage").value = button.dataset.template;
      switchView("advice");
    });
  });
  document.querySelectorAll("[data-range]").forEach((button) => {
    button.addEventListener("click", () => {
      state.reviewRange = button.dataset.range || "45m";
      document.querySelectorAll("[data-range]").forEach((item) => {
        item.classList.toggle("active", item === button);
      });
      renderTimelineStats();
      renderHeatmap();
      renderAnalytics();
    });
  });

  $("sourceForm").addEventListener("submit", addNetworkSource);
  $("settingsForm").addEventListener("submit", saveSettings);
  $("xiaozhiMcpToken").addEventListener("input", () => {
    state.settings.tokenDirty = true;
    $("xiaozhiMcpToken").placeholder = "保存后更新 Token";
  });
  document.querySelectorAll('input[name="studyStage"]').forEach((input) => {
    input.addEventListener("change", () => {
      if (input.checked) setStudyStage(input.value);
    });
  });
  $("refreshSourcesButton").addEventListener("click", refreshSources);
  $("sendMessageButton").addEventListener("click", () => {
    const text = $("parentMessage").value.trim();
    if (!text) {
      $("controlResult").textContent = "请先填写要发送给小智的提醒话术，或点击生成复盘建议。";
      return;
    }
    sendControl("parent_message", text);
  });
  $("manualAiButton").addEventListener("click", () => refreshAiAdvice({ force: true, switchToAdvice: true }));
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
  loadLocalSettings();
  writeSettingsForm();
  bindEvents();
  render({});
  loadSettings().catch(() => {
    $("controlResult").textContent = "设置读取失败，已使用本地默认值。";
  });
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
