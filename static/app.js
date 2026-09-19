(function () {
  "use strict";

  var POLL_INTERVAL_MS = 1000;

  var els = {
    prepared: document.getElementById("status-prepared"),
    stage: document.getElementById("status-stage"),
    busy: document.getElementById("status-busy"),
    revision: document.getElementById("status-revision"),
    statusError: document.getElementById("status-error"),
    actionError: document.getElementById("action-error"),

    btnPrepare: document.getElementById("btn-prepare"),
    btnRun: document.getElementById("btn-run"),
    btnFix: document.getElementById("btn-fix"),
    btnReset: document.getElementById("btn-reset"),
    btnClose: document.getElementById("btn-close"),

    currentEmpty: document.getElementById("current-empty"),
    currentRun: document.getElementById("current-run"),
    currentRunId: document.getElementById("current-run-id"),
    currentRunStatus: document.getElementById("current-run-status"),
    currentRunElapsed: document.getElementById("current-run-elapsed"),
    currentRunError: document.getElementById("current-run-error"),

    currentScreen: document.getElementById("current-screen"),
    currentScreenPending: document.getElementById("current-screen-pending"),
    currentRecording: document.getElementById("current-recording"),
    currentRecordingPending: document.getElementById("current-recording-pending"),

    rulesStatus: document.getElementById("rules-status"),
    rulesError: document.getElementById("rules-error"),
    rulesFindings: document.getElementById("rules-findings"),

    audioStatus: document.getElementById("audio-status"),
    audioError: document.getElementById("audio-error"),
    audioMeta: document.getElementById("audio-meta"),
    audioTranscript: document.getElementById("audio-transcript"),
    audioVerdict: document.getElementById("audio-verdict"),
    audioSummary: document.getElementById("audio-summary"),
    audioChecks: document.getElementById("audio-checks"),

    altStatus: document.getElementById("alt-status"),
    altError: document.getElementById("alt-error"),
    altItems: document.getElementById("alt-items"),

    compareEmpty: document.getElementById("compare-empty"),
    compareBody: document.getElementById("compare-body"),
    prevRunId: document.getElementById("prev-run-id"),
    prevVerdict: document.getElementById("prev-verdict"),
    prevRecording: document.getElementById("prev-recording"),
    currRunId: document.getElementById("curr-run-id"),
    currVerdict: document.getElementById("curr-verdict"),
    currRecording: document.getElementById("curr-recording"),

    runsList: document.getElementById("runs-list"),
  };

  function text(el, value) {
    el.textContent = value === null || value === undefined || value === "" ? "" : String(value);
  }

  function detailToText(detail) {
    if (detail === null || detail === undefined) return "";
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map(function (item) {
          if (item && typeof item === "object") {
            var loc = Array.isArray(item.loc) ? item.loc.join(".") : "";
            var msg = item.msg || "";
            return (loc ? loc + ": " : "") + msg;
          }
          return String(item);
        })
        .join("; ");
    }
    return String(detail);
  }

  function showError(el, message) {
    if (!message) {
      el.hidden = true;
      text(el, "");
      return;
    }
    el.hidden = false;
    text(el, message);
  }

  async function apiRequest(method, path, body) {
    var res;
    try {
      res = await fetch(path, {
        method: method,
        headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch (networkError) {
      throw new Error("네트워크 오류로 요청을 완료하지 못했습니다.");
    }
    var payload = null;
    try {
      payload = await res.json();
    } catch (parseError) {
      payload = null;
    }
    if (!res.ok) {
      var detail = payload && Object.prototype.hasOwnProperty.call(payload, "detail") ? payload.detail : null;
      var message = detailToText(detail) || "요청이 거부되었습니다 (" + res.status + ").";
      throw new Error(message);
    }
    return payload;
  }

  function selectedChecks() {
    var boxes = document.querySelectorAll('input[name="check"]:checked');
    return Array.prototype.map.call(boxes, function (box) {
      return box.value;
    });
  }

  function findFinding(list, key) {
    return Array.isArray(list) ? list : [];
  }

  function renderFindingList(container, items, describe) {
    container.innerHTML = "";
    findFinding(items).forEach(function (item) {
      var li = document.createElement("li");
      var status = item.status || "not_run";
      li.className = "finding-status-" + status;
      li.textContent = describe(item);
      container.appendChild(li);
    });
  }

  function describeRuleFinding(finding) {
    var parts = [finding.rule_id, finding.target, finding.status, finding.summary].filter(Boolean);
    return parts.join(" · ");
  }

  function describeAudioCheck(check) {
    var parts = [check.topic, check.status, check.reason].filter(Boolean);
    return parts.join(" · ");
  }

  function describeAltItem(item) {
    var parts = [item.target, item.status, item.verdict, item.summary].filter(Boolean);
    return parts.join(" · ");
  }

  function setAudioSource(audioEl, url) {
    if (url) {
      if (audioEl.getAttribute("src") !== url) {
        audioEl.setAttribute("src", url);
      }
      audioEl.hidden = false;
    } else {
      audioEl.removeAttribute("src");
      audioEl.hidden = true;
    }
  }

  function renderRun(run) {
    if (!run) {
      els.currentEmpty.hidden = false;
      els.currentRun.hidden = true;
      return;
    }
    els.currentEmpty.hidden = true;
    els.currentRun.hidden = false;

    text(els.currentRunId, run.run_id);
    text(els.currentRunStatus, run.status);
    text(els.currentRunElapsed, run.elapsed_ms === null || run.elapsed_ms === undefined ? "측정 중" : run.elapsed_ms + "ms");
    showError(els.currentRunError, run.error);

    var artifacts = run.artifacts || {};
    if (artifacts.screen) {
      els.currentScreen.hidden = false;
      els.currentScreen.src = artifacts.screen;
      els.currentScreenPending.hidden = true;
    } else {
      els.currentScreen.hidden = true;
      els.currentScreen.removeAttribute("src");
      els.currentScreenPending.hidden = false;
    }
    if (artifacts.recording) {
      els.currentRecording.hidden = false;
      setAudioSource(els.currentRecording, artifacts.recording);
      els.currentRecordingPending.hidden = true;
    } else {
      els.currentRecording.hidden = true;
      setAudioSource(els.currentRecording, null);
      els.currentRecordingPending.hidden = false;
    }

    var rules = run.rules || { status: "not_run", error: null, findings: [] };
    text(els.rulesStatus, rules.status);
    showError(els.rulesError, rules.error);
    renderFindingList(els.rulesFindings, rules.findings, describeRuleFinding);

    var audio = run.audio || { status: "not_run", checks: [] };
    text(els.audioStatus, audio.status);
    showError(els.audioError, audio.error);
    var metaParts = [];
    if (audio.provider) metaParts.push("제공자: " + audio.provider);
    if (audio.model) metaParts.push("모델: " + audio.model);
    if (audio.elapsed_ms !== null && audio.elapsed_ms !== undefined) metaParts.push(audio.elapsed_ms + "ms");
    text(els.audioMeta, metaParts.join(" · "));
    text(els.audioTranscript, audio.transcript ? "전사: " + audio.transcript : "");
    text(els.audioVerdict, audio.verdict || "-");
    text(els.audioSummary, audio.summary);
    renderFindingList(els.audioChecks, audio.checks, describeAudioCheck);

    var altText = run.alt_text || { status: "not_run", items: [] };
    text(els.altStatus, altText.status);
    showError(els.altError, altText.error);
    renderFindingList(els.altItems, altText.items, describeAltItem);
  }

  function renderCompare(state, currentRun) {
    var runs = Array.isArray(state.runs) ? state.runs : [];
    var index = runs.findIndex(function (r) {
      return r.run_id === (currentRun && currentRun.run_id);
    });
    var previousRun = index >= 0 ? runs[index + 1] : undefined;

    if (!currentRun || !previousRun) {
      els.compareEmpty.hidden = false;
      els.compareBody.hidden = true;
      return;
    }
    els.compareEmpty.hidden = true;
    els.compareBody.hidden = false;

    text(els.prevRunId, previousRun.run_id);
    text(els.prevVerdict, previousRun.audio ? previousRun.audio.verdict : null);
    setAudioSource(els.prevRecording, previousRun.artifacts ? previousRun.artifacts.recording : null);

    text(els.currRunId, currentRun.run_id);
    text(els.currVerdict, currentRun.audio ? currentRun.audio.verdict : null);
    setAudioSource(els.currRecording, currentRun.artifacts ? currentRun.artifacts.recording : null);
  }

  function renderRunsList(state) {
    var runs = Array.isArray(state.runs) ? state.runs : [];
    els.runsList.innerHTML = "";
    runs.forEach(function (run) {
      var li = document.createElement("li");
      li.textContent = "리비전 " + run.revision + " · " + run.run_id + " · " + run.status;
      els.runsList.appendChild(li);
    });
  }

  function updateButtons(state) {
    var busy = !!state.busy;
    els.btnPrepare.disabled = busy;
    els.btnRun.disabled = busy || !state.prepared;
    els.btnFix.disabled = !state.can_fix;
    els.btnReset.disabled = busy;
    els.btnClose.disabled = busy || !state.prepared;
  }

  function renderState(state) {
    text(els.prepared, state.prepared ? "준비됨" : "준비 안 됨");
    text(els.stage, state.stage);
    text(els.busy, state.busy ? "실행 중" : "대기");
    text(els.revision, state.revision);
    showError(els.statusError, state.error);

    updateButtons(state);

    var runs = Array.isArray(state.runs) ? state.runs : [];
    var currentRun = runs.find(function (r) {
      return r.run_id === state.current_run_id;
    }) || runs[0] || null;

    renderRun(currentRun);
    renderCompare(state, currentRun);
    renderRunsList(state);
  }

  var polling = false;
  var pollTimer = null;

  async function pollState() {
    if (polling) return;
    polling = true;
    try {
      var state = await apiRequest("GET", "/api/state");
      renderState(state);
    } catch (err) {
      showError(els.statusError, err.message);
    } finally {
      polling = false;
    }
  }

  function startPolling() {
    if (pollTimer) return;
    pollState();
    pollTimer = window.setInterval(pollState, POLL_INTERVAL_MS);
  }

  function bindAction(button, handler) {
    button.addEventListener("click", async function () {
      showError(els.actionError, null);
      button.disabled = true;
      try {
        await handler();
        await pollState();
      } catch (err) {
        showError(els.actionError, err.message);
      } finally {
        button.disabled = false;
      }
    });
  }

  bindAction(els.btnPrepare, function () {
    return apiRequest("POST", "/api/prepare");
  });
  bindAction(els.btnRun, function () {
    return apiRequest("POST", "/api/run", { checks: selectedChecks() });
  });
  bindAction(els.btnFix, function () {
    return apiRequest("POST", "/api/fix");
  });
  bindAction(els.btnReset, function () {
    return apiRequest("POST", "/api/reset");
  });
  bindAction(els.btnClose, function () {
    return apiRequest("POST", "/api/close");
  });

  window.renderState = renderState;
  window.startPolling = startPolling;

  if (document.getElementById("btn-prepare")) {
    startPolling();
  }
})();
