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

const sampleQuestion = "客户说设备连不上平台，截图里像是报 E104，现场是 GW-200，应该怎么处理？";
const sampleTroubleshooting = "设备连不上平台了，现场人员只说指示灯不是常亮，客户也不清楚具体错误码。";

const sampleFields = {
  question: {
    deviceModel: "GW-200",
    errorCode: "E104",
    issueType: "MQTT 连接超时",
    onlineStatus: "离线",
    networkType: "4G",
    mqttConnected: "false"
  },
  troubleshooting: {
    deviceModel: "",
    errorCode: "",
    issueType: "设备离线",
    onlineStatus: "",
    networkType: "",
    mqttConnected: ""
  }
};

const modeConfig = {
  question: {
    label: "客户原话",
    inputLabel: "客户原话或现场描述",
    placeholder: "粘贴客户原话，例如：设备连不上平台了，截图里像是报 E104，现场是 GW-200。"
  },
  troubleshooting: {
    label: "排障补充",
    inputLabel: "已知现象",
    placeholder: "用于客户说不清楚时先补信息，例如：设备离线、指示灯闪烁、现场暂时不知道错误码。"
  },
  telemetry: {
    label: "设备遥测",
    inputLabel: "平台遥测 JSON",
    placeholder: "粘贴设备平台上报的遥测 JSON，例如心跳、MQTT 状态、信号强度、电压、温度。"
  }
};

const categoryNames = {
  high_risk_or_low_confidence: "高风险或低置信度",
  agent_handoff: "Agent 转人工",
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
  "memory.read": "读取会话记忆",
  "troubleshooting.guide": "检查缺失信息",
  "knowledge.search": "检索知识库",
  "ticket.draft": "生成工单草稿",
  "final.clarify": "返回追问",
  "final.answer": "生成答复",
  "final.handoff": "转人工复核",
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

let currentMode = "question";
let lastTicketPayload = null;
let attachments = [];

const input = document.querySelector("#agent-input");
const inputLabel = document.querySelector("#agent-input-label");
const output = document.querySelector("#agent-output");
const routePill = document.querySelector("#agent-route-pill");
const inputModePill = document.querySelector("#input-mode-pill");
const createTicketButton = document.querySelector("#agent-create-ticket-btn");
const ticketTable = document.querySelector("#ticket-table");
const todayTicketCount = document.querySelector("#today-ticket-count");
const openTicketCount = document.querySelector("#open-ticket-count");
const p1TicketCount = document.querySelector("#p1-ticket-count");
const handoffTicketCount = document.querySelector("#handoff-ticket-count");
const feedbackRateValue = document.querySelector("#feedback-rate-value");
const feedbackRate = document.querySelector("#feedback-rate");
const todayStatTotal = document.querySelector("#today-stat-total");
const todayStatOpen = document.querySelector("#today-stat-open");
const todayStatReviewing = document.querySelector("#today-stat-reviewing");
const todayStatResolved = document.querySelector("#today-stat-resolved");
const todayStatP1 = document.querySelector("#today-stat-p1");
const supportFields = document.querySelector("#text-support-fields");
const attachmentInput = document.querySelector("#attachment-input");
const attachmentList = document.querySelector("#attachment-list");
const toast = document.querySelector("#toast");
const statusDot = document.querySelector(".status-dot");
const serviceStatus = document.querySelector("#service-status");

const fieldInputs = {
  deviceModel: document.querySelector("#device-model-field"),
  errorCode: document.querySelector("#error-code-field"),
  issueType: document.querySelector("#issue-type-field"),
  onlineStatus: document.querySelector("#online-status-field"),
  networkType: document.querySelector("#network-type-field"),
  mqttConnected: document.querySelector("#mqtt-connected-field")
};

setInputMode("question");

document.querySelectorAll("[data-input-mode]").forEach((button) => {
  button.addEventListener("click", () => setInputMode(button.dataset.inputMode));
});

document.querySelector("#load-sample-btn").addEventListener("click", () => {
  fillSample(currentMode);
  showToast(`已填入${modeConfig[currentMode].label}示例`);
});

document.querySelector("#refresh-btn").addEventListener("click", () => {
  refreshAll();
});

attachmentInput.addEventListener("change", () => {
  attachments.forEach((item) => {
    if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
  });
  attachments = Array.from(attachmentInput.files || []).map((file) => ({
    filename: file.name,
    content_type: file.type || "image/*",
    size_bytes: file.size,
    note: "客户上传的设备现场图片或错误截图",
    previewUrl: URL.createObjectURL(file)
  }));
  renderAttachmentList();
});

document.querySelector("#agent-run-btn").addEventListener("click", async () => {
  try {
    resetTicketAction();
    if (currentMode === "telemetry") {
      renderDiagnosis(await postJson("/diagnostics/analyze", readTelemetryPayload()));
    } else if (currentMode === "troubleshooting") {
      renderTroubleshooting(await postJson("/troubleshooting/next", readTroubleshootingPayload()));
    } else {
      renderAgent(await postJson("/agent/respond", readQuestionPayload()));
    }
  } catch (error) {
    showToast(error.message);
  }
});

document.querySelector("#agent-stream-btn").addEventListener("click", () => {
  if (currentMode !== "question") {
    showToast("流式查看当前只用于客户原话 Agent 问答");
    return;
  }
  runAgentStream(readQuestionPayload());
});

createTicketButton.addEventListener("click", async () => {
  if (!lastTicketPayload) {
    showToast("当前结论没有可创建的工单草稿");
    return;
  }
  try {
    const ticket = await postJson("/tickets/create", lastTicketPayload);
    showToast(`已创建工单：${ticket.ticket_id}`);
    resetTicketAction();
    await refreshAll();
  } catch (error) {
    showToast(error.message);
  }
});

function setInputMode(mode) {
  currentMode = mode;
  document.querySelectorAll("[data-input-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.inputMode === mode);
  });
  inputModePill.textContent = modeConfig[mode].label;
  inputLabel.textContent = modeConfig[mode].inputLabel;
  input.placeholder = modeConfig[mode].placeholder;
  supportFields.classList.toggle("hidden", mode === "telemetry");
  document.querySelector("#agent-stream-btn").disabled = mode !== "question";
  fillSample(mode);
  resetResult();
}

function fillSample(mode) {
  clearAttachments();
  if (mode === "question") {
    input.value = sampleQuestion;
    setFieldValues(sampleFields.question);
  } else if (mode === "troubleshooting") {
    input.value = sampleTroubleshooting;
    setFieldValues(sampleFields.troubleshooting);
  } else {
    input.value = JSON.stringify(sampleTelemetry, null, 2);
    setFieldValues({});
  }
}

function setFieldValues(values) {
  fieldInputs.deviceModel.value = values.deviceModel || "";
  fieldInputs.errorCode.value = values.errorCode || "";
  fieldInputs.issueType.value = values.issueType || "";
  fieldInputs.onlineStatus.value = values.onlineStatus || "";
  fieldInputs.networkType.value = values.networkType || "";
  fieldInputs.mqttConnected.value = values.mqttConnected || "";
}

function clearAttachments() {
  attachments.forEach((item) => {
    if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
  });
  attachments = [];
  attachmentInput.value = "";
  renderAttachmentList();
}

function readQuestionPayload() {
  const raw = input.value.trim();
  if (!raw && !attachments.length) {
    throw new Error("请先输入客户问题，或上传一张现场图片");
  }
  return {
    question: raw || "客户上传了设备现场图片，但没有补充文字描述。请先判断需要追问哪些关键信息。",
    session_id: "demo-agent-session",
    top_k: 3,
    attachments: toApiAttachments(),
    ...collectStructuredFields()
  };
}

function readTroubleshootingPayload() {
  const raw = input.value.trim();
  if (!raw) {
    throw new Error("请先输入已知故障现象");
  }
  return {
    session_id: "demo-troubleshooting-session",
    question: raw,
    ...collectStructuredFields()
  };
}

function readTelemetryPayload() {
  return readJsonPayload(input);
}

function collectStructuredFields() {
  const fields = {};
  if (fieldInputs.deviceModel.value.trim()) fields.device_model = fieldInputs.deviceModel.value.trim();
  if (fieldInputs.errorCode.value.trim()) fields.error_code = fieldInputs.errorCode.value.trim();
  if (fieldInputs.issueType.value) fields.issue_type = fieldInputs.issueType.value;
  if (fieldInputs.onlineStatus.value) fields.online_status = fieldInputs.onlineStatus.value;
  if (fieldInputs.networkType.value) fields.network_type = fieldInputs.networkType.value;
  if (fieldInputs.mqttConnected.value !== "") fields.mqtt_connected = fieldInputs.mqttConnected.value === "true";
  return fields;
}

function toApiAttachments() {
  return attachments.map(({ filename, content_type, size_bytes, note }) => ({
    filename,
    content_type,
    size_bytes,
    note
  }));
}

function readJsonPayload(target) {
  try {
    return JSON.parse(target.value);
  } catch {
    throw new Error("JSON 格式不正确，请检查输入");
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
  feedbackRateValue.textContent = `${(report.useful_feedback_rate * 100).toFixed(0)}%`;
  feedbackRate.textContent = `${report.feedback_count} 条反馈记录`;
}

async function refreshTickets() {
  const response = await fetch("/tickets");
  const tickets = await response.json();
  const todayTickets = tickets.filter((ticket) => isToday(ticket.created_at));
  const allOpen = tickets.filter((ticket) => ticket.status === "open");
  const allP1 = tickets.filter((ticket) => ticket.priority === "P1");
  const allHandoff = tickets.filter(isHandoffTicket);
  const todayOpen = todayTickets.filter((ticket) => ticket.status === "open");
  const todayReviewing = todayTickets.filter((ticket) => ticket.status === "reviewing");
  const todayResolved = todayTickets.filter((ticket) => ["resolved", "closed"].includes(ticket.status));
  const todayP1 = todayTickets.filter((ticket) => ticket.priority === "P1");

  todayTicketCount.textContent = todayTickets.length;
  openTicketCount.textContent = allOpen.length;
  p1TicketCount.textContent = allP1.length;
  handoffTicketCount.textContent = allHandoff.length;
  todayStatTotal.textContent = todayTickets.length;
  todayStatOpen.textContent = todayOpen.length;
  todayStatReviewing.textContent = todayReviewing.length;
  todayStatResolved.textContent = todayResolved.length;
  todayStatP1.textContent = todayP1.length;

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
          <td>${escapeHtml(translateSummary(ticket.summary))}${renderTicketAttachmentBadge(ticket)}</td>
        </tr>
      `
    )
    .join("");
}

function renderAgent(result) {
  routePill.textContent = `${label(routeNames, result.route)} / ${label(agentStatusNames, result.status)}`;
  routePill.classList.remove("muted");
  setTicketAction(result.ticket_payload);
  output.className = "result-grid";
  output.innerHTML = `
    ${renderAnswer(result.answer, result.route)}
    ${renderFollowUpQuestions(result.follow_up_questions)}
    ${renderTicketPayload(result.ticket_payload)}
    ${renderAgentEvidence(result.evidence)}
    ${renderDecisionSummary(result.route, result.status, result.confidence_score)}
    ${renderMemoryFacts(result.memory_facts)}
    ${renderTraceDetails(result.react_trace)}
  `;
}

function renderTroubleshooting(result) {
  routePill.textContent = `${label(routeNames, result.route)} / ${result.priority}`;
  routePill.classList.remove("muted");
  setTicketAction(result.ticket_payload);
  const advice = result.follow_up_questions.length
    ? `当前信息不足，建议先向客户确认 ${result.follow_up_questions.length} 个关键信息，再继续判断。`
    : result.suggested_action;
  output.className = "result-grid";
  output.innerHTML = `
    ${renderAnswer(advice, result.route)}
    ${renderFollowUpQuestions(result.follow_up_questions)}
    ${renderMissingFields(result.missing_fields)}
    ${renderTicketPayload(result.ticket_payload)}
    ${renderDecisionSummary(result.route, result.priority, result.confidence_score)}
  `;
}

function renderDiagnosis(result) {
  routePill.textContent = `${label(routeNames, result.route)} / ${result.priority}`;
  routePill.classList.remove("muted");
  setTicketAction(result.ticket_payload);
  output.className = "result-grid";
  output.innerHTML = `
    ${renderAnswer(diagnosisAdvice(result), result.route)}
    ${result.findings.map(renderFinding).join("")}
    ${renderTicketPayload(result.ticket_payload)}
    ${renderDecisionSummary(result.route, result.category, result.confidence_score)}
  `;
}

function diagnosisAdvice(result) {
  if (!result.findings.length) {
    return "设备遥测未触发明显故障规则，建议继续观察两个心跳周期。";
  }
  const first = result.findings[0];
  const action = label(actionNames, first.action);
  if (result.ticket_payload) {
    return `遥测数据触发「${label(categoryNames, first.category)}」规则，优先级为 ${result.priority}。建议：${action}`;
  }
  return `遥测数据未达到转人工阈值。建议：${action}`;
}

function renderDecisionSummary(route, status, confidenceScore) {
  return `
    <div class="summary-strip">
      <div class="summary-item">
        <span>处理路由</span>
        <strong>${escapeHtml(label(routeNames, route))}</strong>
      </div>
      <div class="summary-item">
        <span>当前状态</span>
        <strong>${escapeHtml(statusLabel(status))}</strong>
      </div>
      <div class="summary-item">
        <span>置信度</span>
        <strong>${Math.round(confidenceScore * 100)}%</strong>
      </div>
    </div>
  `;
}

function renderAnswer(answer, route) {
  return `
    <div class="answer-card ${route === "handoff" ? "major" : ""}">
      <div class="finding-title">
        <span>建议回复</span>
        <span>${escapeHtml(label(routeNames, route))}</span>
      </div>
      <p>${escapeHtml(answer)}</p>
    </div>
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

  routePill.textContent = "流式执行中";
  routePill.classList.remove("muted");
  output.className = "result-grid";
  output.innerHTML = `<div class="agent-stream" id="agent-stream-log"></div>`;
  const streamLog = document.querySelector("#agent-stream-log");
  const source = new EventSource(`/agent/respond/stream?${params.toString()}`);

  source.addEventListener("step", (event) => {
    const data = JSON.parse(event.data);
    streamLog.insertAdjacentHTML(
      "beforeend",
      `<div class="plan-step"><b>${escapeHtml(data.index)}. ${escapeHtml(label(actionNames, data.action))}</b><span>${escapeHtml(data.next_decision)}</span></div>`
    );
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

function renderTraceDetails(trace) {
  if (!trace || !trace.length) {
    return "";
  }
  return `
    <details class="trace-details">
      <summary>查看 Agent 执行过程</summary>
      <div class="react-trace">
        ${trace
          .map(
            (step) => `
              <div class="react-step">
                <div class="finding-title">
                  <span>${escapeHtml(step.index)}. ${escapeHtml(label(actionNames, step.action))}</span>
                  <span>${escapeHtml(step.action)}</span>
                </div>
                <p>${escapeHtml(step.reasoning_summary)}</p>
                <p>${escapeHtml(step.next_decision)}</p>
              </div>
            `
          )
          .join("")}
      </div>
    </details>
  `;
}

function renderAgentEvidence(evidence) {
  if (!evidence || !evidence.length) {
    return "";
  }
  return `
    <div class="evidence-list">
      <div class="section-label">参考依据</div>
      ${evidence
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
        .join("")}
    </div>
  `;
}

function renderMemoryFacts(facts) {
  const entries = Object.entries(facts || {});
  if (!entries.length) {
    return "";
  }
  return `
    <div class="field-list">
      <span>会话记忆</span>
      ${entries.map(([key, value]) => `<b>${escapeHtml(fieldLabels[key] ?? key)}：${escapeHtml(value)}</b>`).join("")}
    </div>
  `;
}

function renderMissingFields(fields) {
  if (!fields.length) {
    return `<div class="empty-state">关键信息已基本补齐，可以进入知识库检索、规则诊断或转人工判断。</div>`;
  }
  return `
    <div class="field-list">
      <span>仍缺少</span>
      ${fields.map((field) => `<b>${escapeHtml(fieldLabels[field] ?? field)}</b>`).join("")}
    </div>
  `;
}

function renderFollowUpQuestions(questions) {
  if (!questions.length) {
    return "";
  }
  return `
    <div class="evidence-list">
      <div class="section-label">需要继续追问客户</div>
      ${questions
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
        .join("")}
    </div>
  `;
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
    return "";
  }
  const attachmentText = payload.attachments && payload.attachments.length ? `附件：${payload.attachments.length} 张图片。` : "";
  return `
    <div class="finding major">
      <div class="finding-title">
        <span>工单草稿</span>
        <span>${escapeHtml(payload.priority)}</span>
      </div>
      <p>${escapeHtml(translateSummary(payload.summary))}</p>
      <p>${escapeHtml(attachmentText)}建议动作：${escapeHtml(label(actionNames, payload.suggested_action))}</p>
    </div>
  `;
}

function setTicketAction(payload) {
  if (payload) {
    lastTicketPayload = {
      ...payload,
      attachments: payload.attachments && payload.attachments.length ? payload.attachments : toApiAttachments()
    };
  } else {
    lastTicketPayload = null;
  }
  createTicketButton.disabled = !lastTicketPayload;
}

function resetTicketAction() {
  setTicketAction(null);
}

function resetResult() {
  routePill.textContent = "未运行";
  routePill.classList.add("muted");
  output.className = "empty-state";
  output.textContent = "生成后这里先显示可发给客户的建议回复；如果信息不足，会先列出需要追问的问题。";
  resetTicketAction();
}

function renderAttachmentList() {
  if (!attachments.length) {
    attachmentList.textContent = "未上传图片";
    return;
  }
  attachmentList.innerHTML = attachments
    .map(
      (item) => `
        <div class="attachment-chip">
          <img src="${escapeHtml(item.previewUrl)}" alt="" />
          <span>${escapeHtml(item.filename)}</span>
          <b>${formatBytes(item.size_bytes)}</b>
        </div>
      `
    )
    .join("");
}

function renderTicketAttachmentBadge(ticket) {
  const count = ticket.attachments ? ticket.attachments.length : 0;
  if (!count) {
    return "";
  }
  return `<span class="ticket-badge">含 ${count} 张图片</span>`;
}

function isToday(value) {
  if (!value) {
    return false;
  }
  return new Date(value).toDateString() === new Date().toDateString();
}

function isHandoffTicket(ticket) {
  const text = `${ticket.category} ${ticket.summary} ${ticket.suggested_action}`;
  return /人工|复核|风险|投诉|赔偿|安全|低置信度/.test(text);
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

function statusLabel(value) {
  return agentStatusNames[value] ?? categoryNames[value] ?? value;
}

function formatBytes(value) {
  if (!Number.isFinite(value)) {
    return "";
  }
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
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
