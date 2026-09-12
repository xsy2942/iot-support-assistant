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

const sampleFields = {
  question: {
    deviceModel: "GW-200",
    errorCode: "E104",
    issueType: "MQTT 连接超时",
    onlineStatus: "离线",
    networkType: "4G",
    mqttConnected: "false"
  },
  tickets: {
    deviceModel: "",
    errorCode: "",
    issueType: "",
    onlineStatus: "",
    networkType: "",
    mqttConnected: ""
  }
};

const modeConfig = {
  question: {
    label: "新问题",
    inputLabel: "客户原话或现场描述",
    placeholder: "粘贴客户原话，例如：设备连不上平台了，截图里像是报 E104，现场是 GW-200。",
    note: "最常用：客户怎么说就怎么粘贴，知道设备型号或错误码时顺手填下面字段。"
  },
  tickets: {
    label: "继续工单",
    inputLabel: "客户新的补充",
    placeholder: "选择一个待处理工单后，输入客户今天/明天补充的新情况，例如：客户说重启后还是离线，现场又看到 E104。",
    note: "用于继续处理未解决问题：选择历史工单后，系统会带着原问题、工单号和已知字段继续生成回复。"
  }
};

const categoryNames = {
  high_risk_or_low_confidence: "风险问题",
  agent_handoff: "需要人工跟进",
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
  direct_answer: "可直接回复",
  review: "需要复核",
  handoff: "需要跟进",
  clarify: "需要补充信息",
  rag_answer: "可直接回复",
  diagnostic: "设备状态建议"
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
let currentTicket = null;
let cachedTickets = [];

const input = document.querySelector("#agent-input");
const inputLabel = document.querySelector("#agent-input-label");
const inputModeNote = document.querySelector("#input-mode-note");
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
const ticketReopenPanel = document.querySelector("#ticket-reopen-panel");
const openTicketSelect = document.querySelector("#open-ticket-select");
const ticketPreview = document.querySelector("#ticket-preview");
const telemetryInput = document.querySelector("#telemetry-input");
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
telemetryInput.value = JSON.stringify(sampleTelemetry, null, 2);

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

document.querySelector("#refresh-open-tickets-btn").addEventListener("click", async () => {
  await refreshTickets();
  showToast("已刷新待处理工单");
});

document.querySelector("#load-ticket-btn").addEventListener("click", () => {
  loadSelectedTicket(openTicketSelect.value);
});

openTicketSelect.addEventListener("change", () => {
  const ticket = cachedTickets.find((item) => item.ticket_id === openTicketSelect.value);
  renderTicketPreview(ticket);
});

document.querySelector("#telemetry-run-btn").addEventListener("click", async () => {
  try {
    resetTicketAction();
    renderDiagnosis(await postJson("/diagnostics/analyze", readTelemetryPayload()));
  } catch (error) {
    showToast(error.message);
  }
});

attachmentInput.addEventListener("change", () => {
  const incoming = Array.from(attachmentInput.files || []).map((file) => ({
    id: `${file.name}-${file.size}-${file.lastModified}`,
    filename: file.name,
    content_type: file.type || "image/*",
    size_bytes: file.size,
    note: "客户上传的设备现场图片或错误截图",
    previewUrl: URL.createObjectURL(file)
  }));
  const existingIds = new Set(attachments.map((item) => item.id));
  attachments = [...attachments, ...incoming.filter((item) => !existingIds.has(item.id))];
  attachmentInput.value = "";
  renderAttachmentList();
});

attachmentList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-remove-attachment]");
  if (!button) {
    return;
  }
  removeAttachment(button.dataset.removeAttachment);
});

ticketTable.addEventListener("click", (event) => {
  const button = event.target.closest("[data-continue-ticket]");
  if (!button) {
    return;
  }
  setInputMode("tickets");
  loadSelectedTicket(button.dataset.continueTicket);
  document.querySelector("#intake").scrollIntoView({ behavior: "smooth", block: "start" });
});

ticketTable.addEventListener("change", async (event) => {
  const select = event.target.closest("[data-ticket-status]");
  if (!select) {
    return;
  }
  try {
    await postJson(`/tickets/${encodeURIComponent(select.dataset.ticketStatus)}/status`, { status: select.value });
    showToast(`工单状态已更新为：${label(statusNames, select.value)}`);
    await refreshAll();
  } catch (error) {
    showToast(error.message);
  }
});

document.querySelector("#agent-run-btn").addEventListener("click", async () => {
  try {
    resetTicketAction();
    if (currentMode === "tickets") {
      renderAgent(await postJson("/agent/respond", readTicketContinuationPayload()));
    } else {
      renderAgent(await postJson("/agent/respond", readQuestionPayload()));
    }
  } catch (error) {
    showToast(error.message);
  }
});

document.querySelector("#agent-stream-btn").addEventListener("click", () => {
  try {
    runAgentStream(currentMode === "tickets" ? readTicketContinuationPayload() : readQuestionPayload());
  } catch (error) {
    showToast(error.message);
  }
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
  inputModeNote.textContent = modeConfig[mode].note;
  inputLabel.textContent = modeConfig[mode].inputLabel;
  input.placeholder = modeConfig[mode].placeholder;
  supportFields.classList.remove("hidden");
  ticketReopenPanel.classList.toggle("hidden", mode !== "tickets");
  document.querySelector("#agent-stream-btn").disabled = !["question", "tickets"].includes(mode);
  fillSample(mode);
  resetResult();
}

function fillSample(mode) {
  clearAttachments();
  if (mode === "question") {
    input.value = sampleQuestion;
    setFieldValues(sampleFields.question);
  } else {
    input.value = "客户补充：";
    setFieldValues(sampleFields.tickets);
    refreshOpenTicketSelect(cachedTickets);
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

function readTicketContinuationPayload() {
  if (!currentTicket) {
    throw new Error("请先选择并载入一个待处理工单");
  }
  const raw = input.value.trim();
  if (!raw || raw === "客户补充：") {
    throw new Error("请填写客户本次补充内容");
  }
  const question = [
    `继续处理工单 ${currentTicket.ticket_id}`,
    `原问题：${currentTicket.question}`,
    `当前摘要：${currentTicket.summary}`,
    `客户补充：${raw}`
  ].join("\n");
  return {
    question,
    session_id: currentTicket.ticket_id,
    top_k: 3,
    device_model: fieldInputs.deviceModel.value.trim() || currentTicket.device_model || undefined,
    firmware_version: currentTicket.firmware_version || undefined,
    error_code: fieldInputs.errorCode.value.trim() || currentTicket.error_code || undefined,
    issue_type: fieldInputs.issueType.value || currentTicket.category || undefined,
    online_status: fieldInputs.onlineStatus.value || undefined,
    network_type: fieldInputs.networkType.value || undefined,
    mqtt_connected: fieldInputs.mqttConnected.value === "" ? undefined : fieldInputs.mqttConnected.value === "true",
    attachments: [...(currentTicket.attachments || []), ...toApiAttachments()]
  };
}

function readTelemetryPayload() {
  return readJsonPayload(telemetryInput);
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
  cachedTickets = tickets;
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
  refreshOpenTicketSelect(tickets);

  if (!tickets.length) {
    ticketTable.innerHTML = `<tr><td colspan="6" class="empty-cell">暂无工单</td></tr>`;
    return;
  }
  ticketTable.innerHTML = tickets
    .map(
      (ticket) => `
        <tr>
          <td>
            <strong class="ticket-id">${escapeHtml(ticket.ticket_id)}</strong>
            <span class="ticket-meta-line">${escapeHtml(ticket.priority)} · ${escapeHtml(label(categoryNames, ticket.category))}</span>
          </td>
          <td>${escapeHtml(ticketQuestion(ticket))}${renderTicketAttachmentBadge(ticket)}</td>
          <td>${escapeHtml(ticketSuggestion(ticket))}</td>
          <td>${escapeHtml(label(statusNames, ticket.status))}</td>
          <td>${escapeHtml(formatDateTime(ticket.updated_at))}</td>
          <td>${renderTicketAction(ticket)}</td>
        </tr>
      `
    )
    .join("");
}

function refreshOpenTicketSelect(tickets) {
  const openTickets = (tickets || []).filter((ticket) => ["open", "reviewing"].includes(ticket.status));
  if (!openTickets.length) {
    currentTicket = null;
    openTicketSelect.innerHTML = `<option value="">暂无待处理工单</option>`;
    ticketPreview.textContent = "暂无待处理工单。";
    return;
  }
  if (currentTicket && !openTickets.some((ticket) => ticket.ticket_id === currentTicket.ticket_id)) {
    currentTicket = null;
  }
  const selectedValue = currentTicket ? currentTicket.ticket_id : openTicketSelect.value;
  openTicketSelect.innerHTML = openTickets
    .map(
      (ticket) =>
        `<option value="${escapeHtml(ticket.ticket_id)}">${escapeHtml(ticket.ticket_id)} · ${escapeHtml(ticket.device_model || "型号未知")} · ${escapeHtml(label(categoryNames, ticket.category))}</option>`
    )
    .join("");
  if (selectedValue && openTickets.some((ticket) => ticket.ticket_id === selectedValue)) {
    openTicketSelect.value = selectedValue;
  }
  if (!currentTicket) {
    renderTicketPreview(openTickets.find((ticket) => ticket.ticket_id === openTicketSelect.value) || openTickets[0]);
  }
}

function loadSelectedTicket(ticketId) {
  const ticket = cachedTickets.find((item) => item.ticket_id === ticketId);
  if (!ticket) {
    showToast("没有找到这个待处理工单，请先刷新");
    return;
  }
  currentTicket = ticket;
  openTicketSelect.value = ticket.ticket_id;
  renderTicketPreview(ticket);
  input.value = "客户补充：";
  setFieldValues({
    deviceModel: ticket.device_model || "",
    errorCode: ticket.error_code || "",
    issueType: reverseCategoryName(ticket.category),
    onlineStatus: "",
    networkType: "",
    mqttConnected: ""
  });
  showToast(`已载入工单：${ticket.ticket_id}`);
}

function renderTicketPreview(ticket) {
  if (!ticket) {
    ticketPreview.textContent = "请选择一个待处理工单。";
    return;
  }
  ticketPreview.innerHTML = `
    <div class="ticket-preview-heading">
      <strong>${escapeHtml(ticket.ticket_id)}</strong>
      <span>${escapeHtml(ticket.priority)} · ${escapeHtml(label(statusNames, ticket.status))}</span>
    </div>
    <div class="ticket-preview-tags">
      <span>${escapeHtml(ticket.device_model || "型号未知")}</span>
      <span>${escapeHtml(ticket.error_code || "无错误码")}</span>
      <span>${escapeHtml(label(categoryNames, ticket.category))}</span>
    </div>
    <div class="ticket-preview-section">
      <b>上次报错信息</b>
      <p>${escapeHtml(ticketQuestion(ticket))}</p>
    </div>
    <div class="ticket-preview-section">
      <b>上次处理建议</b>
      <p>${escapeHtml(ticketSuggestion(ticket))}</p>
    </div>
    <div class="ticket-preview-footer">
      <span>最近更新：${escapeHtml(formatDateTime(ticket.updated_at))}</span>
      ${ticket.attachments && ticket.attachments.length ? `<span>附件 ${ticket.attachments.length} 张</span>` : ""}
    </div>
  `;
}

function renderTicketAction(ticket) {
  const canContinue = ["open", "reviewing"].includes(ticket.status);
  return `
    <div class="ticket-actions">
      ${canContinue ? `<button class="small-button" type="button" data-continue-ticket="${escapeHtml(ticket.ticket_id)}">继续处理</button>` : ""}
      <select class="status-select" data-ticket-status="${escapeHtml(ticket.ticket_id)}" aria-label="更新工单状态">
        ${Object.entries(statusNames)
          .map(([value, text]) => `<option value="${value}" ${ticket.status === value ? "selected" : ""}>${text}</option>`)
          .join("")}
      </select>
    </div>
  `;
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
    ${renderSourceSummary(result.route, result.status, result.confidence_score)}
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
    ${renderSourceSummary(result.route, result.priority, result.confidence_score)}
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
    ${renderSourceSummary(result.route, result.category, result.confidence_score)}
  `;
}

function diagnosisAdvice(result) {
  if (!result.findings.length) {
    return "设备状态数据未触发明显故障规则，建议继续观察两个心跳周期。";
  }
  const first = result.findings[0];
  const action = label(actionNames, first.action);
  if (result.ticket_payload) {
    return `设备状态数据触发「${label(categoryNames, first.category)}」规则，优先级为 ${result.priority}。建议：${action}`;
  }
  return `设备状态数据未达到转人工阈值。建议：${action}`;
}

function renderSourceSummary(route, status, confidenceScore) {
  return `
    <div class="summary-strip">
      <div class="summary-item">
        <span>答案来源</span>
        <strong>${escapeHtml(answerSourceLabel(route))}</strong>
      </div>
      <div class="summary-item">
        <span>处理方式</span>
        <strong>${escapeHtml(label(routeNames, route))}</strong>
      </div>
      <div class="summary-item">
        <span>可信度</span>
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
    attachmentList.textContent = "未上传图片；当前版本会把图片作为工单附件留存。";
    return;
  }
  attachmentList.innerHTML = attachments
    .map(
      (item) => `
        <div class="attachment-chip">
          <img src="${escapeHtml(item.previewUrl)}" alt="" />
          <span>${escapeHtml(item.filename)}</span>
          <b>${formatBytes(item.size_bytes)}</b>
          <button class="remove-attachment" type="button" data-remove-attachment="${escapeHtml(item.id)}">删除</button>
        </div>
      `
    )
    .join("");
}

function removeAttachment(id) {
  const removed = attachments.find((item) => item.id === id);
  if (removed && removed.previewUrl) {
    URL.revokeObjectURL(removed.previewUrl);
  }
  attachments = attachments.filter((item) => item.id !== id);
  renderAttachmentList();
}

function renderTicketAttachmentBadge(ticket) {
  const count = ticket.attachments ? ticket.attachments.length : 0;
  if (!count) {
    return "";
  }
  return `<span class="ticket-badge">含 ${count} 张图片</span>`;
}

function ticketSuggestion(ticket) {
  const suggestion = label(actionNames, ticket.suggested_action || "");
  if (/高风险或证据不足/.test(suggestion)) {
    return "请先补充现场故障描述、设备状态和操作日志；如确认存在安全风险，立即升级给二线工程师。";
  }
  if (/建议人工复核/.test(suggestion)) {
    return suggestion.replace("建议人工复核：", "请继续核对：");
  }
  return suggestion || "暂无处理建议，请继续确认现场情况。";
}

function ticketQuestion(ticket) {
  const question = String(ticket.question || "");
  const telemetryMatch = question.match(/^Telemetry diagnosis for (\S+) (\S+)$/i);
  if (telemetryMatch) {
    return `${telemetryMatch[1]} 设备 ${telemetryMatch[2]} 状态异常，需要根据上报数据继续排查。`;
  }
  return question || "暂无客户问题描述。";
}

function formatDateTime(value) {
  if (!value) {
    return "时间未知";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(date);
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

function answerSourceLabel(route) {
  const sourceNames = {
    rag_answer: "知识库检索",
    clarify: "信息补全判断",
    handoff: "转人工规则",
    diagnostic: "设备状态规则",
    direct_answer: "规则判断",
    review: "人工复核规则"
  };
  return sourceNames[route] ?? "系统判断";
}

function reverseCategoryName(value) {
  const normalized = categoryNames[value] ?? value;
  const allowed = ["设备离线", "MQTT 连接超时", "固件升级失败", "传感器采样异常"];
  return allowed.includes(normalized) ? normalized : "";
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
