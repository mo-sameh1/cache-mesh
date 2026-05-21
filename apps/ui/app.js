const STORAGE_KEY = "cachemesh.demo.console.settings";

const defaults = {
  deploymentMode: "local",
  endpoints: {
    gateway: "http://localhost:8000",
    nameService: "http://localhost:8100",
    inference: "http://localhost:8050",
    replicas: {
      "replica-a": "http://localhost:8201",
      "replica-b": "http://localhost:8202",
      "replica-c": "http://localhost:8203",
    },
  },
};

const state = {
  settings: loadSettings(),
  services: {},
  members: [],
  coordination: {},
  lastQuery: null,
  lastPromptBody: null,
  snapshots: {},
  polling: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function loadSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    return mergeSettings(defaults, saved || {});
  } catch {
    return structuredClone(defaults);
  }
}

function mergeSettings(base, value) {
  return {
    ...base,
    ...value,
    endpoints: {
      ...base.endpoints,
      ...(value.endpoints || {}),
      replicas: {
        ...base.endpoints.replicas,
        ...((value.endpoints || {}).replicas || {}),
      },
    },
  };
}

function saveSettings() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.settings));
}

function endpoint(path, base) {
  return `${base.replace(/\/$/, "")}${path}`;
}

async function fetchJson(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeoutMs || 5000);
  try {
    const response = await fetch(url, {
      method: options.method || "GET",
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
    });
    const text = await response.text();
    const json = text ? JSON.parse(text) : {};
    if (!response.ok) {
      const message = json.detail || `${response.status} ${response.statusText}`;
      throw new Error(Array.isArray(message) ? JSON.stringify(message) : message);
    }
    return json;
  } finally {
    clearTimeout(timer);
  }
}

async function probe(name, url) {
  try {
    const data = await fetchJson(endpoint("/health", url), { timeoutMs: 3000 });
    return { name, url, ok: data.status === "ok", status: data.status, detail: data.detail, data };
  } catch (error) {
    return { name, url, ok: false, status: "unreachable", detail: error.message };
  }
}

function replicaEntries() {
  return Object.entries(state.settings.endpoints.replicas);
}

async function refreshAll() {
  $("#poll-status").textContent = "Polling";
  $("#poll-status").className = "status-pill ok";

  const serviceChecks = [
    ["Gateway", state.settings.endpoints.gateway],
    ["Name Service", state.settings.endpoints.nameService],
    ["Inference", state.settings.endpoints.inference],
    ...replicaEntries().map(([id, url]) => [id, url]),
  ];

  const results = await Promise.all(serviceChecks.map(([name, url]) => probe(name, url)));
  state.services = Object.fromEntries(results.map((result) => [result.name, result]));
  await refreshMembers();
  await refreshCoordination();
  renderAll();
}

async function refreshMembers() {
  try {
    const data = await fetchJson(endpoint("/members", state.settings.endpoints.nameService), { timeoutMs: 3500 });
    state.members = data.members || [];
  } catch {
    state.members = [];
  }
}

async function refreshCoordination() {
  const statuses = await Promise.all(
    replicaEntries().map(async ([id, url]) => {
      try {
        return [id, await fetchJson(endpoint("/coordination", url), { timeoutMs: 3500 })];
      } catch (error) {
        return [id, { replica_id: id, status: "unreachable", detail: error.message }];
      }
    })
  );
  state.coordination = Object.fromEntries(statuses);
}

function renderAll() {
  renderServiceGrid();
  renderMembers();
  renderToken();
  renderReplicas();
  renderDirectReadPlaceholders();
  renderFaults();
  renderSettings();
  renderSyncReplicaOptions();
  $("#last-updated").textContent = new Date().toLocaleTimeString();
}

function renderServiceGrid() {
  const container = $("#service-grid");
  const template = $("#service-card-template");
  container.innerHTML = "";
  Object.values(state.services).forEach((service) => {
    const node = template.content.cloneNode(true);
    node.querySelector("h3").textContent = service.name;
    node.querySelector(".card-detail").textContent = service.detail || service.status;
    node.querySelector(".card-url").textContent = service.url;
    const dot = node.querySelector(".status-dot");
    dot.classList.add(service.ok ? "ok" : "bad");
    container.appendChild(node);
  });
}

function renderMembers() {
  const container = $("#members-list");
  if (!state.members.length) {
    container.innerHTML = `<div class="result-box empty">No members reported.</div>`;
    return;
  }
  container.innerHTML = state.members
    .map((member) => {
      const statusClass = member.status === "healthy" ? "ok" : member.status === "suspect" ? "warn" : "bad";
      return `
        <article class="status-card">
          <div class="card-title-row">
            <h3>${escapeHtml(member.replica_id)}</h3>
            <span class="status-pill ${statusClass}">${escapeHtml(member.status)}</span>
          </div>
          <p class="card-detail">${escapeHtml(member.host)}:${member.port}</p>
          <code class="card-url">${escapeHtml(`http://${member.host}:${member.port}`)}</code>
        </article>
      `;
    })
    .join("");
}

function renderToken() {
  const statuses = Object.values(state.coordination);
  const holder = statuses.find((item) => item.has_token);
  const active = statuses.find((item) => item.has_token && item.local_write_active);
  const pending = statuses.find((item) => item.pending_token_transfer_to);
  $("#token-panel").innerHTML = `
    <p class="muted">Current holder</p>
    <div class="token-holder">${escapeHtml(holder?.replica_id || "Unknown")}</div>
    <div class="metric-row"><strong>Active writer</strong><span>${escapeHtml(active?.replica_id || "None")}</span></div>
    <div class="metric-row"><strong>Pending transfer</strong><span>${escapeHtml(pending?.pending_token_transfer_to || "None")}</span></div>
    <div class="metric-row"><strong>Token version</strong><span>${escapeHtml(String(holder?.token_version ?? "n/a"))}</span></div>
  `;
}

function renderReplicas() {
  const container = $("#replica-grid");
  container.innerHTML = replicaEntries()
    .map(([id, url]) => {
      const health = state.services[id];
      const coord = state.coordination[id] || {};
      const member = state.members.find((item) => item.replica_id === id);
      const status = health?.ok && coord.status !== "unreachable" ? "ok" : "bad";
      const statusText = member?.status || coord.status || health?.status || "unknown";
      return `
        <article class="replica-card">
          <div class="card-title-row">
            <h3>${escapeHtml(id)}</h3>
            <span class="status-pill ${status === "ok" ? "ok" : "bad"}">${escapeHtml(statusText)}</span>
          </div>
          <div class="metric-row"><strong>URL</strong><span>${escapeHtml(url)}</span></div>
          <div class="metric-row"><strong>Has token</strong><span>${yesNo(coord.has_token)}</span></div>
          <div class="metric-row"><strong>Writing</strong><span>${yesNo(coord.local_write_active)}</span></div>
          <div class="metric-row"><strong>Remote writers</strong><span>${escapeHtml((coord.remote_writers || []).join(", ") || "None")}</span></div>
          <div class="metric-row"><strong>Queue</strong><span>${escapeHtml((coord.token_queue || []).join(", ") || "Empty")}</span></div>
        </article>
      `;
    })
    .join("");
}

function renderDirectReadPlaceholders() {
  const container = $("#direct-read-grid");
  if (container.dataset.hasResults === "true") {
    return;
  }
  container.innerHTML = replicaEntries()
    .map(([id]) => `
      <article class="replica-card">
        <h3>${escapeHtml(id)}</h3>
        <p class="card-detail">No direct read yet.</p>
      </article>
    `)
    .join("");
}

function renderFaults() {
  $("#fault-grid").innerHTML = replicaEntries()
    .map(([id]) => `
      <article class="replica-card">
        <div class="card-title-row">
          <h3>${escapeHtml(id)}</h3>
          <span class="status-pill neutral">Fault API</span>
        </div>
        <div class="button-row">
          <button class="secondary-button" type="button" data-fault="${id}:slow_response:3:true">Slow Next</button>
          <button class="secondary-button" type="button" data-fault="${id}:pause_node:5:true">Pause Next</button>
          <button class="secondary-button" type="button" data-fault="${id}:error_response:30:false">Reject 30s</button>
          <button class="secondary-button" type="button" data-fault="${id}:disabled:1:true">Clear</button>
        </div>
      </article>
    `)
    .join("");
}

function renderSettings() {
  $("#mode-local").classList.toggle("active", state.settings.deploymentMode === "local");
  $("#mode-three").classList.toggle("active", state.settings.deploymentMode === "three");
  $("#gateway-url").value = state.settings.endpoints.gateway;
  $("#name-service-url").value = state.settings.endpoints.nameService;
  $("#inference-url").value = state.settings.endpoints.inference;
  $("#replica-a-url").value = state.settings.endpoints.replicas["replica-a"];
  $("#replica-b-url").value = state.settings.endpoints.replicas["replica-b"];
  $("#replica-c-url").value = state.settings.endpoints.replicas["replica-c"];
  $("#env-output").textContent = buildEnvOutput();
}

function renderSyncReplicaOptions() {
  const options = replicaEntries().map(([id]) => `<option value="${id}">${id}</option>`).join("");
  $("#snapshot-replica").innerHTML = options;
  $("#replay-replica").innerHTML = options;
}

function buildEnvOutput() {
  const replicas = state.settings.endpoints.replicas;
  const nameUrl = state.settings.endpoints.nameService;
  const gatewayTargets = Object.entries(replicas).map(([id, url]) => `${id}=${url}`).join(",");
  const gatewayUrls = Object.values(replicas).join(",");
  return [
    `NAME_SERVICE_URL=${nameUrl}`,
    `INFERENCE_ADAPTER_URL=${state.settings.endpoints.inference}`,
    `GATEWAY_REPLICA_TARGETS=${gatewayTargets}`,
    `GATEWAY_REPLICA_URLS=${gatewayUrls}`,
    `REPLICA_PEER_TARGETS=${gatewayTargets}`,
    "",
    `replica-a advertised host: ${hostFromUrl(replicas["replica-a"])}`,
    `replica-b advertised host: ${hostFromUrl(replicas["replica-b"])}`,
    `replica-c advertised host: ${hostFromUrl(replicas["replica-c"])}`,
    `gateway host: ${hostFromUrl(state.settings.endpoints.gateway)}`,
  ].join("\n");
}

function hostFromUrl(url) {
  try {
    return new URL(url).hostname;
  } catch {
    return "invalid-url";
  }
}

async function sendQuery() {
  const body = currentQueryBody();
  state.lastPromptBody = body;
  $("#query-badge").textContent = "Sending";
  $("#query-badge").className = "status-pill neutral";
  try {
    const data = await fetchJson(endpoint("/cache/query", state.settings.endpoints.gateway), {
      method: "POST",
      body,
      timeoutMs: 30000,
    });
    state.lastQuery = data;
    $("#query-badge").textContent = data.hit ? "Cache hit" : "Cache miss";
    $("#query-badge").className = `status-pill ${data.hit ? "ok" : "warn"}`;
    renderQueryResult(data);
    renderFlowTrace(data);
    $("#raw-response").textContent = JSON.stringify(data, null, 2);
    addEvent("Gateway query", data);
    await readAllReplicas();
    await refreshAll();
  } catch (error) {
    $("#query-badge").textContent = "Failed";
    $("#query-badge").className = "status-pill bad";
    addEvent("Gateway query failed", { error: error.message });
  }
}

function currentQueryBody() {
  return {
    prompt: $("#prompt-input").value.trim(),
    model_id: $("#model-id-input").value.trim() || "demo-model",
    semantic_enabled: $("#semantic-enabled").checked,
  };
}

function renderQueryResult(data) {
  $("#gateway-result").classList.remove("empty");
  $("#gateway-result").innerHTML = `
    <div class="metric-row"><strong>Status</strong><span>${escapeHtml(data.status)}</span></div>
    <div class="metric-row"><strong>Cache</strong><span>${data.hit ? "Hit" : "Miss"}</span></div>
    <div class="metric-row"><strong>Selected replica</strong><span>${escapeHtml(data.selected_replica_id || "None")}</span></div>
    <div class="metric-row"><strong>Cache status</strong><span>${escapeHtml(data.cache_status)}</span></div>
    <div class="metric-row"><strong>Score</strong><span>${escapeHtml(String(data.score ?? "n/a"))}</span></div>
    <p class="card-detail">${escapeHtml(data.detail || "")}</p>
    <p>${escapeHtml(data.response_text || "")}</p>
  `;
}

function renderFlowTrace(data) {
  const steps = ["Gateway received prompt", "Gateway asked name-service for members"];
  if (data.selected_replica_id) {
    steps.push(`Gateway read ${data.selected_replica_id}`);
  }
  if (data.hit) {
    steps.push("Replica returned cache hit");
  } else {
    steps.push("Replica missed cache");
    steps.push("Gateway called inference-adapter");
    if (data.selected_replica_id) {
      steps.push(`${data.selected_replica_id} stored the response`);
      steps.push(`${data.selected_replica_id} attempted peer replication`);
    }
  }
  $("#flow-trace").innerHTML = steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("");
}

async function readAllReplicas() {
  if (!state.lastPromptBody) {
    state.lastPromptBody = currentQueryBody();
  }
  const body = state.lastPromptBody;
  const results = await Promise.all(
    replicaEntries().map(async ([id, url]) => {
      try {
        const data = await fetchJson(endpoint("/cache/read", url), { method: "POST", body, timeoutMs: 8000 });
        return { id, url, ok: true, data };
      } catch (error) {
        return { id, url, ok: false, data: { detail: error.message, hit: false } };
      }
    })
  );
  const container = $("#direct-read-grid");
  container.dataset.hasResults = "true";
  container.innerHTML = results
    .map(({ id, url, ok, data }) => `
      <article class="replica-card">
        <div class="card-title-row">
          <h3>${escapeHtml(id)}</h3>
          <span class="status-pill ${ok && data.hit ? "ok" : ok ? "warn" : "bad"}">${ok && data.hit ? "hit" : ok ? "miss" : "failed"}</span>
        </div>
        <div class="metric-row"><strong>URL</strong><span>${escapeHtml(url)}</span></div>
        <div class="metric-row"><strong>Score</strong><span>${escapeHtml(String(data.score ?? "n/a"))}</span></div>
        <p class="card-detail">${escapeHtml(data.detail || "")}</p>
      </article>
    `)
    .join("");
  addEvent("Direct replica reads", Object.fromEntries(results.map((item) => [item.id, item.data])));
}

async function armFault(replicaId, mode, durationSec, once) {
  const payload = { mode, duration_sec: Number(durationSec), once: once === "true" };
  try {
    const data = await fetchJson(endpoint(`/admin/faults/${replicaId}`, state.settings.endpoints.gateway), {
      method: "POST",
      body: payload,
      timeoutMs: 8000,
    });
    addEvent(`Fault ${replicaId} ${mode}`, data);
    await refreshAll();
  } catch (error) {
    addEvent(`Fault ${replicaId} failed`, { error: error.message, payload });
  }
}

async function createSnapshot() {
  const id = $("#snapshot-replica").value;
  const sinceRaw = $("#snapshot-since").value;
  const payload = { replica_id: id };
  if (sinceRaw !== "") {
    payload.since_lamport_ts = Number(sinceRaw);
  }
  try {
    const data = await fetchJson(endpoint("/sync/snapshot", state.settings.endpoints.replicas[id]), {
      method: "POST",
      body: payload,
      timeoutMs: 8000,
    });
    state.snapshots[id] = data.snapshot_id;
    $("#replay-replica").value = id;
    $("#replay-snapshot-id").value = data.snapshot_id || "";
    $("#sync-response").textContent = JSON.stringify(data, null, 2);
    addEvent("Snapshot created", data);
  } catch (error) {
    addEvent("Snapshot failed", { error: error.message, payload });
  }
}

async function replaySnapshot() {
  const id = $("#replay-replica").value;
  const payload = {
    replica_id: id,
    snapshot_id: $("#replay-snapshot-id").value.trim() || null,
    operation_count: Number($("#replay-count").value || 0),
  };
  try {
    const data = await fetchJson(endpoint("/sync/replay", state.settings.endpoints.replicas[id]), {
      method: "POST",
      body: payload,
      timeoutMs: 8000,
    });
    $("#sync-response").textContent = JSON.stringify(data, null, 2);
    addEvent("Replay requested", data);
  } catch (error) {
    addEvent("Replay failed", { error: error.message, payload });
  }
}

function applyMode(mode) {
  state.settings.deploymentMode = mode;
  saveSettings();
  renderAll();
  refreshAll();
}

function collectSettingsFromForm() {
  state.settings.endpoints.gateway = $("#gateway-url").value.trim();
  state.settings.endpoints.nameService = $("#name-service-url").value.trim();
  state.settings.endpoints.inference = $("#inference-url").value.trim();
  state.settings.endpoints.replicas["replica-a"] = $("#replica-a-url").value.trim();
  state.settings.endpoints.replicas["replica-b"] = $("#replica-b-url").value.trim();
  state.settings.endpoints.replicas["replica-c"] = $("#replica-c-url").value.trim();
  saveSettings();
  addEvent("Settings saved", state.settings);
}

function addEvent(title, data) {
  const container = $("#event-log");
  const item = document.createElement("article");
  item.className = "event-item";
  item.innerHTML = `
    <strong>${escapeHtml(title)}</strong>
    <time>${new Date().toLocaleTimeString()}</time>
    <pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>
  `;
  container.prepend(item);
  while (container.children.length > 30) {
    container.lastElementChild.remove();
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function yesNo(value) {
  if (value === undefined || value === null) {
    return "n/a";
  }
  return value ? "Yes" : "No";
}

function wireEvents() {
  $$(".tab-button").forEach((button) => {
    button.addEventListener("click", () => {
      $$(".tab-button").forEach((item) => item.classList.remove("active"));
      $$(".tab-panel").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      $(`#${button.dataset.tab}`).classList.add("active");
    });
  });

  $("#refresh-now").addEventListener("click", refreshAll);
  $("#query-form").addEventListener("submit", (event) => {
    event.preventDefault();
    sendQuery();
  });
  $("#send-twice").addEventListener("click", async () => {
    await sendQuery();
    await sendQuery();
  });
  $("#read-all-replicas").addEventListener("click", readAllReplicas);
  $("#clear-events").addEventListener("click", () => {
    $("#event-log").innerHTML = "";
  });
  $("#mode-local").addEventListener("click", () => applyMode("local"));
  $("#mode-three").addEventListener("click", () => {
    state.settings.deploymentMode = "three";
    saveSettings();
    renderAll();
    refreshAll();
  });
  $("#save-settings").addEventListener("click", () => {
    collectSettingsFromForm();
    refreshAll();
  });
  $("#create-snapshot").addEventListener("click", createSnapshot);
  $("#replay-snapshot").addEventListener("click", replaySnapshot);

  document.addEventListener("click", (event) => {
    const faultButton = event.target.closest("[data-fault]");
    if (faultButton) {
      const [replicaId, mode, duration, once] = faultButton.dataset.fault.split(":");
      armFault(replicaId, mode, duration, once);
    }

    const copyButton = event.target.closest("[data-copy-target]");
    if (copyButton) {
      const target = $(`#${copyButton.dataset.copyTarget}`);
      navigator.clipboard?.writeText(target.textContent || "");
      copyButton.textContent = "Copied";
      setTimeout(() => {
        copyButton.textContent = "Copy";
      }, 1000);
    }
  });
}

function startPolling() {
  if (state.polling) {
    clearInterval(state.polling);
  }
  refreshAll();
  state.polling = setInterval(refreshAll, 3000);
}

wireEvents();
renderAll();
startPolling();
