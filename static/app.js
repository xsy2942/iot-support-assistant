const sampleTelemetry = {
  sample_id: "TEL-DEMO-001",
  timestamp: "2026-04-01T10:00:00",
  device_id: "DEV-GW200-001",
  product_line: "gateway",
  device_model: "GW-200",
  firmware_version: "v2.0.1",
  online: false,
  mqtt_connected: false,
  heartbeat_age_sec: 900,
  rssi_dbm: -96,
  battery_percent: 72,
  temperature_c: 28.5,
  humidity_percent: 55.0,
  vibration_mm_s: 1.2,
  voltage_v: 229.0,
  error_code: "E104",
  last_upgrade_status: "idle",
  customer_risk_signal: null
};

const sampleTroubleshooting = {
  session_id: null,
  question: "设备连不上平台了，现场人员也说不清楚具体原因。",
  issue_type: "设备离线",
  device_model: null,
  error_code: null,
  online_status: null,
  indicator_light: null,
  network_type: null,
  heartbeat_age_sec: null,
  mqtt_connected: null,
  last_upgrade_status: null,
  tried_steps: [],
  risk_signal: null
};

const sampleAgent = {
  question: "GW-200 报 E104 且 MQTT 连接超时，平台显示心跳已经 15 分钟没有上报，应该怎么排查？",
  session_id: "demo-agent-session",
  device_model: "GW-200",
  error_code: "E104",
  online_status: "离线",
  network_type: "4G",
  mqtt_connected: false,
  heartbeat_age_sec: 900,
  top_k: 3
};

const sampleRiskAgent = {
  question: "客户要求赔偿停机损失，现场设备冒烟并且历史数据全部丢失，应该怎么处理？",
  session_id: "demo-agent-session",
  device_model: "GW-200",
  error_code: "E104",
  risk_signal: "客户投诉与安全风险",
  top_k: 3
};

const agentInput = document.querySelector("#agent-input");
const agentOutput = document.querySelector("#agent-output");
const agentRoutePill = document.querySelector("#agent-route-pill");
const telemetryInput = document.querySelector("#telemetry-input");
const diagnosisOutput = document.querySelector("#diagnosis-output");
const troubleshootingInput = document.querySelector("#troubleshooting-input");
const troubleshootingOutput = document.querySelector("#troubleshooting-output");
const troubleshootingRoutePill = document.querySelector("#troubleshooting-route-pill");
const ticketTable = document.querySelector("#ticket-table");
const ticketCount = document.querySelector("#ticket-count");
const feedbackRate = document.querySelector("#feedback-rate");
const routePill = document.querySelector("#route-pill");
const toast = document.querySelector("#toast");
const statusDot = document.querySelector(".status-dot");
const serviceStatus = document.querySelector("#service-status");

const categoryNames = {
  device_offline: "设备离线",
  mqtt_timeout: "MQTT 连接超时",
  firmware_upgrade_failed: "固件升级失败",
  sensor_sampling_abnormal: "传感器采样异常",
  power_sampling_risk: "电力采样风险",
  safety_risk: "安全风险",
  weak_signal: "信号弱",
  normal: "运行正常"
};

const severityNames = {
  critical: "严重",
  major: "较高",
  minor: "一般",
  info: "提示"
};

const routeNames = {
  direct_answer: "直接回答",
  review: "建议复核",
  handoff: "转人工",
  clarify: "先追问",
  rag_answer: "知识库回答",
  diagnostic: "规则诊断"
};

const agentStatusNames = {
  COMPLETE: "已完成",
  PARTIAL: "部分完成",
  UNKNOWN: "未知",
  INCOMPLETE: "信息不完整"
};

const statusNames = {
  open: "待处理",
  reviewing: "复核中",
  resolved: "已解决",
  closed: "已关闭"
};

const actionNames = {
  "Stop remote operations and escalate to human support with field logs.": "停止远程操作，收集现场日志并转人工处理。",
  "Check power, network, SIM balance, firewall policy, and last heartbeat.": "检查供电、网络、SIM 卡余额、防火墙策略和最近心跳时间。",
  "Verify broker host, port, TLS certificate, device credentials, and weak-network logs.": "核对 Broker 地址、端口、TLS 证书、设备凭证和弱网重连日志。",
  "Collect upgrade logs and avoid repeated upgrade attempts before human review.": "收集升级日志，人工复核前避免反复升级。",
  "Check probe wiring, calibration parameters, sampling period, and installation environment.": "检查探头接线、校准参数、采样周期和安装环境。",
  "Check phase sequence, transformer direction, ratio settings, and on-site electrical safety.": "检查相序、互感器方向、倍率设置和现场用电安全。",
  "Move antenna, check carrier signal, or switch to wired network where possible.": "调整天线位置，检查运营商信号，条件允许时切换到有线网络。",
  "Continue monitoring for two heartbeat cycles.": "继续观察两个心跳周期。"
};

const fieldLabels = {
  device_model: "设备型号",
  error_code: "错误码",
  online_status: "在线状态",
  indicator_light: "指示灯",
  network_type: "网络类型",
  heartbeat_age_sec: "心跳间隔",
  mqtt_connected: "MQTT 状态",
  last_upgrade_status: "升级状态"
};

telemetryInput.value = JSON.stringify(sampleTelemetry, null, 2);
troubleshootingInput.value = JSON.stringify(sampleTroubleshooting, null, 2);
agentInput.value = JSON.stringify(sampleAgent, null, 2);

document.querySelector("#load-sample-btn").addEventListener("click", () => {
  telemetryInput.value = JSON.stringify(sampleTelemetry, null, 2);
  troubleshootingInput.value = JSON.stringify(sampleTroubleshooting, null, 2);
  agentInput.value = JSON.stringify(sampleAgent, null, 2);
  showToast("已载入一条网关心跳超时样本");
});

document.querySelector("#refresh-btn").addEventListener("click", () => {
  refreshAll();
});

document.querySelector("#agent-run-btn").addEventListener("click", async () => {
  try {
    const payload = readJsonPayload(agentInput);
    if (!payload) return;
    const result = await postJson("/agent/respond", payload);
    renderAgent(result);
  } catch (error) {
    showToast(error.message);
  }
});

document.querySelector("#agent-stream-btn").addEventListener("click", () => {
  const payload = readJsonPayload(agentInput);
  if (!payload) return;
  runAgentStream(payload);
});

document.querySelector("#agent-risk-btn").addEventListener("click", () => {
  agentInput.value = JSON.stringify(sampleRiskAgent, null, 2);
  showToast("已载入一条高风险转人工问题");
});

document.querySelector("#analyze-btn").addEventListener("click", async () => {
  try {
    const payload = readTelemetryPayload();
    if (!payload) return;
    const result = await postJson("/diagnostics/analyze", payload);
    renderDiagnosis(result);
  } catch (error) {
    showToast(error.message);
  }
});

document.querySelector("#create-ticket-btn").addEventListener("click", async () => {
  try {
    const payload = readTelemetryPayload();
    if (!payload) return;
    const ticket = await postJson("/diagnostics/create-ticket", payload);
    showToast(`已创建工单：${ticket.ticket_id}`);
    await refreshTickets();
    await refreshReport();
  } catch (error) {
    showToast(error.message);
  }
});

document.querySelector("#troubleshooting-next-btn").addEventListener("click", async () => {
  try {
    const payload = readJsonPayload(troubleshootingInput);
    if (!payload) return;
    const result = await postJson("/troubleshooting/next", payload);
    keepTroubleshootingSession(result.session_id);
    renderTroubleshooting(result);
  } catch (error) {
    showToast(error.message);
  }
});

document.querySelector("#troubleshooting-ticket-btn").addEventListener("click", async () => {
  try {
    const payload = readJsonPayload(troubleshootingInput);
    if (!payload) return;
    const ticket = await postJson("/troubleshooting/create-ticket", payload);
    showToast(`已创建排障工单：${ticket.ticket_id}`);
    await refreshTickets();
    await refreshReport();
  } catch {
    showToast("当前排障结果暂不需要建单，或信息还不完整");
  }
});

function readTelemetryPayload() {
  return readJsonPayload(telemetryInput);
}

function readJsonPayload(input) {
  try {
    return JSON.parse(input.value);
  } catch {
    showToast("JSON 格式不正确，请检查输入");
    return null;
  }
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  return response.json();
}

async function refreshAll() {
  await Promise.all([checkHealth(), refreshTickets(), refreshReport()]);
}

async function checkHealth() {
  try {
    const response = await fetch("/health");
    const data = await response.json();
    statusDot.classList.toggle("ok", data.status === "ok");
    serviceStatus.textContent = data.status === "ok" ? "服务运行中" : "服务异常";
  } catch {
    statusDot.classList.remove("ok");
    serviceStatus.textContent = "服务不可用";
  }
}

async function refreshReport() {
  const response = await fetch("/eval/report");
  const report = await response.json();
  ticketCount.textContent = report.ticket_count;
  feedbackRate.textContent = `有用反馈率 ${(report.useful_feedback_rate * 100).toFixed(0)}%`;
}

async function refreshTickets() {
  const response = await fetch("/tickets");
  const tickets = await response.json();
  if (!tickets.length) {
    ticketTable.innerHTML = `<tr><td colspan="5" class="empty-cell">暂无工单</td></tr>`;
    return;
  }
  ticketTable.innerHTML = tickets
    .map(
      (ticket) => `
        <tr>
          <td>${escapeHtml(ticket.ticket_id)}</td>
          <td>${escapeHtml(label(categoryNames, ticket.category))}</td>
          <td>${escapeHtml(ticket.priority)}</td>
          <td>${escapeHtml(label(statusNames, ticket.status))}</td>
          <td>${escapeHtml(translateSummary(ticket.summary))}</td>
        </tr>
      `
    )
    .join("");
}

function renderDiagnosis(result) {
  routePill.textContent = `${label(routeNames, result.route)} / ${result.priority}`;
  routePill.classList.remove("muted");
  diagnosisOutput.className = "result-grid";
  diagnosisOutput.innerHTML = `
    <div class="summary-strip">
      <div class="summary-item">
        <span>故障分类</span>
        <strong>${escapeHtml(label(categoryNames, result.category))}</strong>
      </div>
      <div class="summary-item">
        <span>优先级</span>
        <strong>${escapeHtml(result.priority)}</strong>
      </div>
      <div class="summary-item">
        <span>置信度</span>
        <strong>${Math.round(result.confidence_score * 100)}%</strong>
      </div>
    </div>
    ${result.findings.map(renderFinding).join("")}
    ${renderTicketPayload(result.ticket_payload)}
  `;
}

function renderTroubleshooting(result) {
  troubleshootingRoutePill.textContent = `${label(routeNames, result.route)} / ${result.priority}`;
  troubleshootingRoutePill.classList.remove("muted");
  troubleshootingOutput.className = "result-grid";
  troubleshootingOutput.innerHTML = `
    <div class="summary-strip">
      <div class="summary-item">
        <span>识别类型</span>
        <strong>${escapeHtml(result.issue_type)}</strong>
      </div>
      <div class="summary-item">
        <span>处理路由</span>
        <strong>${escapeHtml(label(routeNames, result.route))}</strong>
      </div>
      <div class="summary-item">
        <span>置信度</span>
        <strong>${Math.round(result.confidence_score * 100)}%</strong>
      </div>
    </div>
    ${renderMissingFields(result.missing_fields)}
    ${renderFollowUpQuestions(result.follow_up_questions)}
    <div class="finding ${result.priority === "P1" ? "critical" : "major"}">
      <div class="finding-title">
        <span>建议动作</span>
        <span>${escapeHtml(result.priority)}</span>
      </div>
      <p>${escapeHtml(result.suggested_action)}</p>
    </div>
    ${renderTicketPayload(result.ticket_payload)}
  `;
}

function renderAgent(result) {
  agentRoutePill.textContent = `${label(routeNames, result.route)} / ${label(agentStatusNames, result.status)}`;
  agentRoutePill.classList.remove("muted");
  agentOutput.className = "result-grid";
  agentOutput.innerHTML = `
    <div class="summary-strip">
      <div class="summary-item">
        <span>处理路由</span>
        <strong>${escapeHtml(label(routeNames, result.route))}</strong>
      </div>
      <div class="summary-item">
        <span>执行状态</span>
        <strong>${escapeHtml(label(agentStatusNames, result.status))}</strong>
      </div>
      <div class="summary-item">
        <span>置信度</span>
        <strong>${Math.round(result.confidence_score * 100)}%</strong>
      </div>
    </div>
    <div class="finding">
      <div class="finding-title">
        <span>Agent 回答</span>
        <span>${escapeHtml(result.route)}</span>
      </div>
      <p>${escapeHtml(result.answer)}</p>
    </div>
    ${renderAgentPlan(result.plan)}
    ${renderMemoryFacts(result.memory_facts)}
    ${renderFollowUpQuestions(result.follow_up_questions)}
    ${renderAgentEvidence(result.evidence)}
    ${renderTicketPayload(result.ticket_payload)}
  `;
}

function runAgentStream(payload) {
  const params = new URLSearchParams();
  params.set("question", payload.question);
  if (payload.session_id) params.set("session_id", payload.session_id);
  if (payload.device_model) params.set("device_model", payload.device_model);
  if (payload.error_code) params.set("error_code", payload.error_code);
  if (payload.network_type) params.set("network_type", payload.network_type);
  if (payload.top_k) params.set("top_k", payload.top_k);

  agentRoutePill.textContent = "流式执行中";
  agentRoutePill.classList.remove("muted");
  agentOutput.className = "result-grid";
  agentOutput.innerHTML = `<div class="agent-stream" id="agent-stream-log"></div>`;
  const streamLog = document.querySelector("#agent-stream-log");
  const source = new EventSource(`/agent/respond/stream?${params.toString()}`);

  source.addEventListener("step", (event) => {
    const data = JSON.parse(event.data);
    streamLog.insertAdjacentHTML("beforeend", `<div class="plan-step"><b>${escapeHtml(data.name)}</b><span>${escapeHtml(data.status)}</span></div>`);
  });

  source.addEventListener("result", (event) => {
    source.close();
    renderAgent(JSON.parse(event.data));
  });

  source.onerror = () => {
    source.close();
    showToast("流式接口连接中断");
  };
}

function renderAgentPlan(plan) {
  if (!plan.length) {
    return "";
  }
  return `
    <div class="agent-plan">
      ${plan
        .map(
          (step) => `
            <div class="plan-step">
              <b>${escapeHtml(step.index)}. ${escapeHtml(step.name)}</b>
              <span>${escapeHtml(step.status)}</span>
              <p>${escapeHtml(step.reason)}</p>
            </div>
          `
        )
        .join("")}
    </div>
  `;
}

function renderAgentEvidence(evidence) {
  if (!evidence.length) {
    return `<div class="empty-state">没有可引用的知识库证据。</div>`;
  }
  return evidence
    .map(
      (item) => `
        <div class="finding">
          <div class="finding-title">
            <span>${escapeHtml(item.source_id)} · ${escapeHtml(item.title)}</span>
            <span>${Math.round(item.score * 100)}%</span>
          </div>
          <p>来源：${escapeHtml(item.source_type)} / ${escapeHtml(item.metadata.issue_type || "未分类")}</p>
          <p>${escapeHtml(item.quote)}</p>
        </div>
      `
    )
    .join("");
}

function renderMemoryFacts(facts) {
  const entries = Object.entries(facts || {});
  if (!entries.length) {
    return `<div class="empty-state">当前会话还没有沉淀上下文字段。</div>`;
  }
  return `
    <div class="field-list">
      <span>会话记忆</span>
      ${entries.map(([key, value]) => `<b>${escapeHtml(fieldLabels[key] ?? key)}：${escapeHtml(value)}</b>`).join("")}
    </div>
  `;
}

function keepTroubleshootingSession(sessionId) {
  if (!sessionId) {
    return;
  }
  const payload = readJsonPayload(troubleshootingInput);
  if (!payload) {
    return;
  }
  payload.session_id = sessionId;
  troubleshootingInput.value = JSON.stringify(payload, null, 2);
}

function renderMissingFields(fields) {
  if (!fields.length) {
    return `<div class="empty-state">关键信息已基本补齐，可以进入知识库检索、规则诊断或转人工判断。</div>`;
  }
  return `
    <div class="field-list">
      <span>缺失字段</span>
      ${fields.map((field) => `<b>${escapeHtml(fieldLabels[field] ?? field)}</b>`).join("")}
    </div>
  `;
}

function renderFollowUpQuestions(questions) {
  if (!questions.length) {
    return "";
  }
  return questions
    .map(
      (item, index) => `
        <div class="finding">
          <div class="finding-title">
            <span>追问 ${index + 1}</span>
            <span>${escapeHtml(fieldLabels[item.field] ?? item.field)}</span>
          </div>
          <p>${escapeHtml(item.question)}</p>
          <div class="option-row">
            ${item.options.map((option) => `<span>${escapeHtml(option)}</span>`).join("")}
          </div>
        </div>
      `
    )
    .join("");
}

function renderFinding(finding) {
  return `
    <div class="finding ${escapeHtml(finding.severity)}">
      <div class="finding-title">
        <span>${escapeHtml(label(categoryNames, finding.category))}</span>
        <span>${escapeHtml(label(severityNames, finding.severity))}</span>
      </div>
      <p>证据：${escapeHtml(translateEvidence(finding.evidence))}</p>
      <p>建议：${escapeHtml(label(actionNames, finding.action))}</p>
    </div>
  `;
}

function renderTicketPayload(payload) {
  if (!payload) {
    return `<div class="empty-state">当前诊断不需要创建工单。</div>`;
  }
  return `
    <div class="finding major">
      <div class="finding-title">
        <span>工单草稿</span>
        <span>${escapeHtml(payload.priority)}</span>
      </div>
      <p>${escapeHtml(translateSummary(payload.summary))}</p>
      <p>建议动作：${escapeHtml(label(actionNames, payload.suggested_action))}</p>
    </div>
  `;
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 2600);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function label(dictionary, value) {
  return dictionary[value] ?? value;
}

function translateEvidence(value) {
  return String(value ?? "")
    .replace("online=False", "在线状态=否")
    .replace("online=True", "在线状态=是")
    .replace("mqtt_connected=False", "MQTT连接=否")
    .replace("mqtt_connected=True", "MQTT连接=是")
    .replace("heartbeat_age_sec=", "心跳间隔秒数=")
    .replace("error_code=", "错误码=")
    .replace("rssi_dbm=", "信号强度=")
    .replace("temperature_c=", "温度=")
    .replace("humidity_percent=", "湿度=")
    .replace("voltage_v=", "电压=")
    .replace("last_upgrade_status=", "升级状态=")
    .replace("customer_risk_signal=", "客户风险信号=");
}

function translateSummary(value) {
  return String(value ?? "")
    .replace("triggered device_offline", "触发设备离线")
    .replace("triggered mqtt_timeout", "触发 MQTT 连接超时")
    .replace("triggered firmware_upgrade_failed", "触发固件升级失败")
    .replace("triggered sensor_sampling_abnormal", "触发传感器采样异常")
    .replace("triggered power_sampling_risk", "触发电力采样风险")
    .replace("triggered safety_risk", "触发安全风险")
    .replace("error_code=", "错误码=")
    .replace("heartbeat_age_sec=", "心跳间隔秒数=")
    .replace("mqtt_connected=False", "MQTT连接=否")
    .replace("mqtt_connected=True", "MQTT连接=是");
}

refreshAll().catch((error) => showToast(error.message));
