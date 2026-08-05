/* ============================================================
   SecScan — Frontend Application Logic
   Handles file upload, paste-to-scan, results rendering,
   chart visualization, and JSON export.
   ============================================================ */

(function () {
  "use strict";

  // ---- DOM references ----
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const dropZone = $("#drop-zone");
  const fileInput = $("#file-input");
  const pasteFilename = $("#paste-filename");
  const pasteTextarea = $("#paste-textarea");
  const scanBtn = $("#scan-btn");
  const errorMsg = $("#error-msg");
  const tabBtns = $$(".tab-btn");
  const tabPanels = $$(".tab-panel");

  const uploadSection = $("#upload-section");
  const loadingSection = $("#loading-section");
  const resultsSection = $("#results-section");
  const rescanBtn = $("#rescan-btn");
  const exportBtn = $("#export-btn");

  // ---- State ----
  let selectedFile = null;       // File object from file input
  let currentResult = null;      // Latest ScanResult from API
  let severityChart = null;      // Chart.js instance
  let activeTab = "file";        // "file" | "paste"

  // ---- Severity config ----
  const SEVERITY_CONFIG = {
    Critical: { color: "#ff3b3b", label: "严重", zh: "严重" },
    High:     { color: "#ff8c00", label: "高危", zh: "高危" },
    Medium:   { color: "#ffd700", label: "中危", zh: "中危" },
    Low:      { color: "#3b82f6", label: "低危", zh: "低危" },
    Info:     { color: "#6e7681", label: "信息", zh: "信息" },
  };

  // ============================================================
  //  Tab switching
  // ============================================================
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      activeTab = tab;
      tabBtns.forEach((b) => b.classList.toggle("active", b === btn));
      tabPanels.forEach((p) => {
        p.classList.toggle("active", p.id === `tab-${tab}`);
      });
      updateScanButton();
    });
  });

  // ============================================================
  //  File upload — drag & drop + click to browse
  // ============================================================
  dropZone.addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  });

  // Drag events
  ["dragenter", "dragover"].forEach((evt) => {
    dropZone.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach((evt) => {
    dropZone.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove("dragover");
    });
  });

  dropZone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelected(files[0]);
    }
  });

  function handleFileSelected(file) {
    // Validate file extension
    const ext = file.name.split(".").pop().toLowerCase();
    if (!["py", "js", "mjs"].includes(ext)) {
      showError("不支持的文件类型，请上传 .py、.js 或 .mjs 文件");
      return;
    }
    // Validate file size (5 MB max)
    if (file.size > 5 * 1024 * 1024) {
      showError("文件大小超过 5 MB 限制");
      return;
    }
    clearError();
    selectedFile = file;
    dropZone.classList.add("file-selected");
    dropZone.querySelector(".drop-icon").textContent = "✅";
    dropZone.querySelector(".drop-text").innerHTML =
      `已选择: <strong>${escapeHtml(file.name)}</strong> (${formatSize(file.size)})`;
    dropZone.querySelector(".drop-hint").textContent = "点击重新选择文件";
    updateScanButton();
  }

  // ============================================================
  //  Paste tab — track content changes
  // ============================================================
  pasteTextarea.addEventListener("input", updateScanButton);
  pasteFilename.addEventListener("input", updateScanButton);

  // ============================================================
  //  Scan button state
  // ============================================================
  function updateScanButton() {
    let enabled = false;
    if (activeTab === "file") {
      enabled = !!selectedFile;
    } else {
      enabled = pasteTextarea.value.trim().length > 0 && pasteFilename.value.trim().length > 0;
    }
    scanBtn.disabled = !enabled;
  }

  // ============================================================
  //  Scan action
  // ============================================================
  scanBtn.addEventListener("click", async () => {
    clearError();
    let formData;

    if (activeTab === "file" && selectedFile) {
      formData = new FormData();
      formData.append("file", selectedFile);
    } else if (activeTab === "paste") {
      const code = pasteTextarea.value;
      let filename = pasteFilename.value.trim();
      // Ensure filename has a valid extension
      if (!filename.match(/\.(py|js|mjs)$/i)) {
        filename += ".py";
      }
      const blob = new Blob([code], { type: "text/plain" });
      const file = new File([blob], filename, { type: "text/plain" });
      formData = new FormData();
      formData.append("file", file);
    } else {
      return;
    }

    // Show loading
    uploadSection.classList.add("hidden");
    loadingSection.classList.remove("hidden");
    setButtonLoading(true);

    try {
      const resp = await fetch("/api/scan", { method: "POST", body: formData });
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || `扫描失败 (HTTP ${resp.status})`);
      }
      const result = await resp.json();
      currentResult = result;
      renderResults(result);
    } catch (err) {
      showError(err.message || "扫描请求失败，请检查网络连接");
      uploadSection.classList.remove("hidden");
    } finally {
      loadingSection.classList.add("hidden");
      setButtonLoading(false);
    }
  });

  // ============================================================
  //  Render results
  // ============================================================
  function renderResults(result) {
    // Update summary cards
    $("#summary-total").textContent = result.summary.total;
    $("#summary-critical").textContent = result.summary.critical;
    $("#summary-high").textContent = result.summary.high;
    $("#summary-medium").textContent = result.summary.medium;
    $("#summary-low").textContent = result.summary.low;
    $("#summary-info").textContent = result.summary.info;

    // Update meta card
    $("#meta-filename").textContent = result.filename;
    $("#meta-language").textContent = result.language;
    $("#meta-scan-time").textContent = formatTime(result.scan_time);
    $("#meta-scan-id").textContent = result.scan_id;

    // Render chart
    renderChart(result.summary);

    // Render vulnerability list
    renderVulnList(result.vulnerabilities);

    // Show results section
    resultsSection.classList.remove("hidden");
    // Smooth scroll to results
    resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ============================================================
  //  Chart — severity distribution pie chart
  // ============================================================
  function renderChart(summary) {
    const ctx = $("#severity-chart").getContext("2d");

    // Destroy previous chart if exists
    if (severityChart) {
      severityChart.destroy();
    }

    const labels = [];
    const data = [];
    const colors = [];

    const entries = [
      ["Critical", summary.critical],
      ["High", summary.high],
      ["Medium", summary.medium],
      ["Low", summary.low],
      ["Info", summary.info],
    ];

    entries.forEach(([sev, count]) => {
      if (count > 0) {
        labels.push(SEVERITY_CONFIG[sev].zh);
        data.push(count);
        colors.push(SEVERITY_CONFIG[sev].color);
      }
    });

    if (data.length === 0) {
      // No vulnerabilities — show a green "安全" placeholder
      labels.push("无漏洞");
      data.push(1);
      colors.push("#22c55e");
    }

    severityChart = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [{
          data: data,
          backgroundColor: colors,
          borderColor: "#0d1117",
          borderWidth: 2,
          hoverOffset: 8,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              color: "#e6edf3",
              font: { size: 13 },
              padding: 16,
              usePointStyle: true,
              pointStyle: "circle",
            },
          },
          tooltip: {
            backgroundColor: "#1a2236",
            titleColor: "#e6edf3",
            bodyColor: "#e6edf3",
            borderColor: "#2a3447",
            borderWidth: 1,
            padding: 12,
          },
        },
        cutout: "55%",
      },
    });
  }

  // ============================================================
  //  Vulnerability list rendering
  // ============================================================
  function renderVulnList(vulns) {
    const container = $("#vuln-list");
    container.innerHTML = "";

    if (!vulns || vulns.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">✅</div>
          <p>未检测到安全漏洞，代码很安全！</p>
        </div>`;
      return;
    }

    vulns.forEach((vuln, idx) => {
      const item = document.createElement("div");
      item.className = "vuln-item";
      item.dataset.idx = idx;

      const sevClass = `sev-${vuln.severity}`;
      const sevLabel = SEVERITY_CONFIG[vuln.severity]
        ? SEVERITY_CONFIG[vuln.severity].zh
        : vuln.severity;

      item.innerHTML = `
        <div class="vuln-header">
          <span class="vuln-toggle">▶</span>
          <span class="vuln-badge ${sevClass}">${sevLabel}</span>
          <span class="vuln-type">${escapeHtml(vuln.vuln_type)}</span>
          <span class="vuln-line">第 ${vuln.line} 行</span>
          <span class="vuln-rule">${escapeHtml(vuln.rule_id)} · ${escapeHtml(vuln.cwe_id)}</span>
        </div>
        <div class="vuln-body">
          <div class="vuln-desc">
            <strong>漏洞描述：</strong>${escapeHtml(vuln.description)}
          </div>
          <div class="vuln-section-label">📝 漏洞代码</div>
          <div class="code-block" id="code-${idx}"></div>
          <div class="vuln-section-label">🛡️ CWE 参考</div>
          <div class="vuln-desc" style="padding-top:4px">
            <a class="cwe-link" href="https://cwe.mitre.org/data/definitions/${vuln.cwe_id.replace('CWE-', '')}.html" target="_blank" rel="noopener">
              ${escapeHtml(vuln.cwe_id)} — 查看详情 ↗
            </a>
          </div>
          <div class="fix-box">
            <div class="vuln-section-label">💡 修复建议</div>
            <div class="fix-content">${escapeHtml(vuln.fix_suggestion)}</div>
          </div>
        </div>
      `;

      // Render code snippet with line numbers
      const codeContainer = item.querySelector(`#code-${idx}`);
      renderCodeSnippet(codeContainer, vuln.code_snippet, vuln.line);

      // Toggle expand/collapse
      const header = item.querySelector(".vuln-header");
      header.addEventListener("click", () => {
        item.classList.toggle("expanded");
      });

      container.appendChild(item);
    });
  }

  // ============================================================
  //  Code snippet with line numbers + highlight
  // ============================================================
  function renderCodeSnippet(container, snippet, highlightLine) {
    container.innerHTML = "";
    const lines = snippet.split("\n");

    // Determine starting line number: if snippet has multiple lines and
    // the highlight line is within range, start from (highlightLine - offset).
    // For single-line snippets, just show line number = highlightLine.
    let startLine;
    if (lines.length === 1) {
      startLine = highlightLine;
    } else {
      // Multi-line snippet: assume it starts a few lines before the highlight
      startLine = Math.max(1, highlightLine - Math.floor(lines.length / 2));
    }

    lines.forEach((lineText, i) => {
      const lineNum = startLine + i;
      const lineEl = document.createElement("div");
      lineEl.className = "code-line";
      if (lineNum === highlightLine) {
        lineEl.classList.add("highlight");
      }
      lineEl.innerHTML = `
        <span class="line-num">${lineNum}</span>
        <span class="line-code">${escapeHtml(lineText) || " "}</span>
      `;
      container.appendChild(lineEl);
    });
  }

  // ============================================================
  //  Export report as JSON
  // ============================================================
  exportBtn.addEventListener("click", () => {
    if (!currentResult) return;
    const json = JSON.stringify(currentResult, null, 2);
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `secscan_report_${currentResult.scan_id.substring(0, 8)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  });

  // ============================================================
  //  Rescan button — reset to upload screen
  // ============================================================
  rescanBtn.addEventListener("click", () => {
    resultsSection.classList.add("hidden");
    uploadSection.classList.remove("hidden");
    // Reset file selection
    selectedFile = null;
    fileInput.value = "";
    dropZone.classList.remove("file-selected");
    dropZone.querySelector(".drop-icon").textContent = "📂";
    dropZone.querySelector(".drop-text").innerHTML =
      '拖拽文件到此处，或<span class="browse-link">点击选择文件</span>';
    dropZone.querySelector(".drop-hint").textContent = "支持 .py / .js / .mjs 文件，最大 5 MB";
    // Clear paste area
    pasteTextarea.value = "";
    updateScanButton();
    // Scroll to top
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  // ============================================================
  //  Helper functions
  // ============================================================
  function setButtonLoading(loading) {
    scanBtn.querySelector(".btn-text").classList.toggle("hidden", loading);
    scanBtn.querySelector(".btn-loading").classList.toggle("hidden", !loading);
    scanBtn.disabled = loading;
  }

  function showError(msg) {
    errorMsg.textContent = msg;
    errorMsg.classList.remove("hidden");
  }

  function clearError() {
    errorMsg.textContent = "";
    errorMsg.classList.add("hidden");
  }

  function escapeHtml(str) {
    if (str == null) return "";
    const div = document.createElement("div");
    div.textContent = String(str);
    return div.innerHTML;
  }

  function formatSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  function formatTime(isoStr) {
    try {
      const d = new Date(isoStr);
      return d.toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return isoStr;
    }
  }

  // Init
  updateScanButton();
})();
