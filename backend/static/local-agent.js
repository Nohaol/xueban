const $ = (id) => document.getElementById(id);

function setText(id, value) {
  $(id).textContent = value ?? "--";
}

function stageSourceLabel(source) {
  return { voice: "语音选择", parent: "家长端切换", system: "系统设置", default: "默认模式" }[source] || source;
}

function commandLabel(command) {
  return {
    parent_message: "家长留言",
    stage_change: "学段切换",
    focus_reminder: "专注提醒",
    managed_ai_reminder: "智能提醒",
  }[command] || "系统提醒";
}

function renderStatus(data) {
  const online = Boolean(data.device.online);
  $("device-dot").style.background = online ? "#2f8b68" : "#ef6634";
  setText("device-status", online ? "机器人局域网链路在线" : "机器人链路待连接");
  setText("device-name", data.device.name);
  setText("device-id", `${data.device.id} · ${data.device.transport}`);
  setText("stage-label", data.stage.label);
  setText("stage-source", stageSourceLabel(data.stage.source));

  setText("current-ip", data.network.currentIp || "未检测");
  setText("target-ip", data.network.firmwareTargetIp || "未配置");
  const networkTag = $("network-tag");
  const networkTip = $("network-tip");
  if (data.network.targetMatchesCurrent) {
    networkTag.textContent = "地址一致";
    networkTag.className = "tag success";
    networkTip.textContent = "可以断开 USB。电脑与机器人接入当前局域网后，主动播报链路可继续工作。";
    networkTip.className = "notice";
  } else {
    networkTag.textContent = "需要更新";
    networkTag.className = "tag warning";
    networkTip.textContent = "电脑 IP 已变化，固件仍指向旧地址。请固定 DHCP 地址或重新写入当前 OTA 地址。";
    networkTip.className = "notice warning";
  }

  $("service-list").innerHTML = data.services.map((service) => `
    <div class="service ${service.online ? "online" : ""}">
      <i></i><b>${service.name}</b><span>:${service.port}</span>
    </div>`).join("");

  $("capability-list").innerHTML = data.capabilities.map((item) => `
    <div class="capability"><i style="background:${item.online ? "#2f8b68" : "#ef6634"}"></i>
      <strong>${item.name}</strong><span>${item.value}</span>
    </div>`).join("");

  setText("reminder-count", `${data.reminders.completed} 条完成`);
  $("reminder-list").innerHTML = data.reminders.recent.length
    ? data.reminders.recent.map((item) => `
      <div class="reminder">
        <strong>${item.text || commandLabel(item.command)}</strong>
        <span>${commandLabel(item.command)} · ${item.status} · ${item.delivery || "队列"}</span>
      </div>`).join("")
    : '<p class="empty">暂无提醒记录</p>';

  setText("updated-at", new Date(data.generatedAt).toLocaleTimeString("zh-CN"));
}

async function refresh() {
  $("refresh").disabled = true;
  try {
    const response = await fetch("/local-agent/status", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderStatus(await response.json());
  } catch (error) {
    setText("device-status", `状态读取失败：${error.message}`);
  } finally {
    $("refresh").disabled = false;
  }
}

$("refresh").addEventListener("click", refresh);
refresh();
setInterval(refresh, 5000);
