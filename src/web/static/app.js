// Py-IMAP Web Admin Control Panel Client Logic

document.addEventListener("DOMContentLoaded", () => {
    initThemeSwitcher();
    initTabs();
    initProviderChips();
    initSingleAccountTab();
    initDropZone();
    initSessionsTab();
    initLogDrawer();
    updateGrafanaLink();
});

// Toast notification helper
function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Adjust Grafana button URL to current host IP
function updateGrafanaLink() {
    const btn = document.getElementById("grafanaBtn");
    if (btn) {
        const host = window.location.hostname || "localhost";
        btn.href = `http://${host}:3000`;
    }
}

// Theme Switcher Logic
function initThemeSwitcher() {
    const savedTheme = localStorage.getItem("py_imap_theme") || "midnight";
    applyTheme(savedTheme);

    const themeButtons = document.querySelectorAll(".theme-btn");
    themeButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const theme = btn.dataset.theme;
            applyTheme(theme);
            localStorage.setItem("py_imap_theme", theme);
        });
    });
}

function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    document.querySelectorAll(".theme-btn").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.theme === theme);
    });
}

// Tab navigation
function initTabs() {
    const navItems = document.querySelectorAll(".nav-item");
    navItems.forEach(item => {
        item.addEventListener("click", () => {
            navItems.forEach(n => n.classList.remove("active"));
            document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));

            item.classList.add("active");
            const targetTab = document.getElementById(item.dataset.tab);
            if (targetTab) {
                targetTab.classList.add("active");
                if (item.dataset.tab === "sessionsTab") {
                    loadSessions();
                }
            }
        });
    });
}

// Provider Quick Presets Logic
function initProviderChips() {
    const chips = document.querySelectorAll(".provider-chip");
    chips.forEach(chip => {
        chip.addEventListener("click", () => {
            const target = chip.dataset.target; // 'src' or 'dst'
            const provider = chip.dataset.provider;

            // Toggle active chip in same group
            document.querySelectorAll(`.provider-chip[data-target="${target}"]`).forEach(c => c.classList.remove("active"));
            chip.classList.add("active");

            applyProviderPreset(target, provider);
        });
    });
}

function applyProviderPreset(target, provider) {
    const hostInput = document.getElementById(`${target}Host`);
    const portInput = document.getElementById(`${target}Port`);
    const sslSelect = document.getElementById(`${target}Ssl`);
    const hintText = document.getElementById(`${target}HintText`);

    if (provider === "gmail") {
        hostInput.value = "imap.gmail.com";
        portInput.value = 993;
        sslSelect.value = "true";
        if (hintText) hintText.textContent = "💡 Gmail: Cần bật 2FA và tạo 'Mật khẩu ứng dụng' (16 ký tự) trong Google Account";
    } else if (provider === "outlook") {
        hostInput.value = "outlook.office365.com";
        portInput.value = 993;
        sslSelect.value = "true";
        if (hintText) hintText.textContent = "💡 Microsoft 365: Dùng App Password hoặc kiểm tra bật IMAP trong Exchange Admin";
    } else if (provider === "yandex") {
        hostInput.value = "imap.yandex.com";
        portInput.value = 993;
        sslSelect.value = "true";
        if (hintText) hintText.textContent = "💡 Yandex: Tạo Mật khẩu ứng dụng tại Yandex ID > Security. Tên tiếng Việt tự động giải mã";
    } else if (provider === "cpanel") {
        const userInput = document.getElementById(`${target}User`).value.trim();
        let domain = "cpanel-domain.com";
        if (userInput.includes("@")) {
            domain = userInput.split("@")[1];
        }
        hostInput.value = `mail.${domain}`;
        portInput.value = 993;
        sslSelect.value = "true";
        if (hintText) hintText.textContent = `💡 cPanel: Mặc định mail.${domain} (Port 993 SSL)`;
    } else if (provider === "custom") {
        if (hintText) hintText.textContent = "";
    }
}

// Single Account Tab Logic
function initSingleAccountTab() {
    // 1. Test Source Password
    document.getElementById("btnTestSrcPass").addEventListener("click", async () => {
        const btn = document.getElementById("btnTestSrcPass");
        btn.disabled = true;
        btn.textContent = "Đang kiểm tra...";

        const payload = {
            host: document.getElementById("srcHost").value.trim(),
            port: parseInt(document.getElementById("srcPort").value) || 993,
            ssl: document.getElementById("srcSsl").value === "true",
            username: document.getElementById("srcUser").value.trim(),
            password: document.getElementById("srcPass").value.trim(),
        };

        appendTerminalLog(`[AUTH CHECK] Đang thử xác thực tài khoản nguồn: ${payload.username} @ ${payload.host}...`, "info");

        try {
            const res = await fetch("/api/check-password", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (data.is_valid) {
                showToast(`✓ Mật khẩu Nguồn hợp lệ! Độ trễ: ${data.latency_ms}ms`, "success");
                appendTerminalLog(`[AUTH SUCCESS] Nguồn ${payload.username} hợp lệ! Latency: ${data.latency_ms}ms`, "success");
            } else {
                showToast(`✗ Thất bại: ${data.provider_hint || data.error_reason}`, "error");
                appendTerminalLog(`[AUTH FAILED] Nguồn ${payload.username} thất bại: ${data.provider_hint || data.error_reason}`, "error");
            }
        } catch (e) {
            showToast(`Lỗi kết nối máy chủ: ${e.message}`, "error");
            appendTerminalLog(`[ERROR] Không thể kết nối máy chủ: ${e.message}`, "error");
        } finally {
            btn.disabled = false;
            btn.textContent = "🔑 Kiểm Tra Mật Khẩu";
        }
    });

    // 2. Test Destination Password
    document.getElementById("btnTestDstPass").addEventListener("click", async () => {
        const btn = document.getElementById("btnTestDstPass");
        btn.disabled = true;
        btn.textContent = "Đang kiểm tra...";

        const payload = {
            host: document.getElementById("dstHost").value.trim(),
            port: parseInt(document.getElementById("dstPort").value) || 993,
            ssl: document.getElementById("dstSsl").value === "true",
            username: document.getElementById("dstUser").value.trim(),
            password: document.getElementById("dstPass").value.trim(),
        };

        appendTerminalLog(`[AUTH CHECK] Đang thử xác thực tài khoản đích: ${payload.username} @ ${payload.host}...`, "info");

        try {
            const res = await fetch("/api/check-password", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (data.is_valid) {
                showToast(`✓ Mật khẩu Đích hợp lệ! Độ trễ: ${data.latency_ms}ms`, "success");
                appendTerminalLog(`[AUTH SUCCESS] Đích ${payload.username} hợp lệ! Latency: ${data.latency_ms}ms`, "success");
            } else {
                showToast(`✗ Thất bại: ${data.provider_hint || data.error_reason}`, "error");
                appendTerminalLog(`[AUTH FAILED] Đích ${payload.username} thất bại: ${data.provider_hint || data.error_reason}`, "error");
            }
        } catch (e) {
            showToast(`Lỗi kết nối máy chủ: ${e.message}`, "error");
            appendTerminalLog(`[ERROR] Không thể kết nối máy chủ: ${e.message}`, "error");
        } finally {
            btn.disabled = false;
            btn.textContent = "🔑 Kiểm Tra Đăng Nhập Đích";
        }
    });

    // 3. Inspect Source Mailbox
    document.getElementById("btnInspectSrc").addEventListener("click", async () => {
        const btn = document.getElementById("btnInspectSrc");
        btn.disabled = true;
        btn.textContent = "Đang quét...";

        const payload = {
            host: document.getElementById("srcHost").value.trim(),
            port: parseInt(document.getElementById("srcPort").value) || 993,
            ssl: document.getElementById("srcSsl").value === "true",
            username: document.getElementById("srcUser").value.trim(),
            password: document.getElementById("srcPass").value.trim(),
        };

        appendTerminalLog(`[INSPECT] Bắt đầu quét hộp thư nguồn ${payload.username}...`, "info");

        try {
            const res = await fetch("/api/inspect", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || "Không thể kết nối đến máy chủ");
            }

            renderInspectionResults(data);
            showToast(`✓ Đã quét xong hộp thư: ${data.total_size_mb} MB (${data.total_messages} thư)`, "success");
            appendTerminalLog(`[INSPECT DONE] Tổng: ${data.total_size_mb} MB (${data.total_size_gb} GB) trên ${data.folders.length} thư mục`, "success");
        } catch (e) {
            showToast(`Lỗi quét dung lượng: ${e.message}`, "error");
            appendTerminalLog(`[INSPECT ERROR] ${e.message}`, "error");
        } finally {
            btn.disabled = false;
            btn.textContent = "🔍 Quét Dung Lượng & Cây Thư Mục";
        }
    });

    // 4. Start Single Migration
    document.getElementById("btnStartSingleMigrate").addEventListener("click", async () => {
        const payload = {
            source: {
                host: document.getElementById("srcHost").value.trim(),
                port: parseInt(document.getElementById("srcPort").value) || 993,
                ssl: document.getElementById("srcSsl").value === "true",
                username: document.getElementById("srcUser").value.trim(),
                password: document.getElementById("srcPass").value.trim(),
            },
            dest: {
                host: document.getElementById("dstHost").value.trim(),
                port: parseInt(document.getElementById("dstPort").value) || 993,
                ssl: document.getElementById("dstSsl").value === "true",
                username: document.getElementById("dstUser").value.trim(),
                password: document.getElementById("dstPass").value.trim(),
            },
            sanitize_accents: document.getElementById("settingSanitizeAccents").checked,
            batch_delay_ms: parseInt(document.getElementById("settingBatchDelay").value) || 50,
        };

        if (!payload.source.username || !payload.source.password || !payload.dest.username || !payload.dest.password) {
            showToast("Vui lòng điền đầy đủ tài khoản và mật khẩu cả 2 đầu!", "error");
            return;
        }

        const btn = document.getElementById("btnStartSingleMigrate");
        btn.disabled = true;
        btn.textContent = "ĐANG DI CHUYỂN...";

        // Show progress container
        const progressCard = document.getElementById("singleProgressContainer");
        progressCard.style.display = "block";
        progressCard.scrollIntoView({ behavior: "smooth" });

        resetProgressUI();
        appendTerminalLog(`[MIGRATE START] Khởi động di chuyển: ${payload.source.username} ➔ ${payload.dest.username}`, "info");

        try {
            const res = await fetch("/api/migrate/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Khởi động di chuyển thất bại");

            showToast("Tiến trình di chuyển đã bắt đầu!", "info");
            listenToEventStream();

        } catch (e) {
            showToast(`Lỗi: ${e.message}`, "error");
            btn.disabled = false;
            btn.textContent = "🚀 BẮT ĐẦU DI CHUYỂN NGAY";
        }
    });
}

function resetProgressUI() {
    document.getElementById("progressBarFill").style.width = "0%";
    document.getElementById("progressPercentBadge").textContent = "0%";
    document.getElementById("statSuccessCount").textContent = "0";
    document.getElementById("statSkippedCount").textContent = "0";
    document.getElementById("statFailedCount").textContent = "0";
    document.getElementById("statCurrentFolder").textContent = "Đang khởi tạo...";
    document.getElementById("reportLinksContainer").style.display = "none";
}

// Render Donut Chart & Inspection Results
function renderInspectionResults(summary) {
    const container = document.getElementById("inspectionResultContainer");
    container.style.display = "block";
    container.scrollIntoView({ behavior: "smooth" });

    const badges = document.getElementById("inspectionSummaryBadges");
    badges.innerHTML = `
        <span class="badge badge-primary">Tổng Dung Lượng: ${summary.total_size_mb} MB (${summary.total_size_gb} GB)</span>
        <span class="badge badge-success">Tổng Thư: ${summary.total_messages.toLocaleString()}</span>
    `;

    // 1. Draw SVG Donut Chart
    renderStorageDonutChart(summary);

    // 2. Render Quota Progress Bar
    renderQuotaBar(summary);

    // 3. Render Folders Table
    const tbody = document.getElementById("foldersTableBody");
    tbody.innerHTML = "";

    summary.folders.forEach(f => {
        const sizeMb = (f.size_bytes / 1048576).toFixed(2);
        let statusBadge = `<span class="badge badge-success">Sẵn sàng (Ready)</span>`;
        if (f.is_excluded) statusBadge = `<span class="badge badge-danger">Loại trừ (Skip)</span>`;
        else if (!f.is_selectable) statusBadge = `<span class="badge badge-neutral">Thư mục cha</span>`;

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong>${f.name}</strong></td>
            <td><code class="code-primary">${f.role}</code></td>
            <td style="text-align: right;">${f.messages_count.toLocaleString()}</td>
            <td style="text-align: right;">${sizeMb} MB</td>
            <td style="text-align: center;">${statusBadge}</td>
        `;
        tbody.appendChild(tr);
    });
}

function renderStorageDonutChart(summary) {
    const svg = document.getElementById("storageDonutSvg");
    const legend = document.getElementById("chartLegend");
    const centerSize = document.getElementById("donutCenterSize");

    centerSize.textContent = `${summary.total_size_mb} MB`;
    svg.innerHTML = "";
    legend.innerHTML = "";

    const activeFolders = summary.folders
        .filter(f => !f.is_excluded && f.size_bytes > 0)
        .sort((a, b) => b.size_bytes - a.size_bytes);

    if (activeFolders.length === 0 || summary.total_size_bytes === 0) {
        svg.innerHTML = `<circle cx="80" cy="80" r="60" fill="none" stroke="var(--border)" stroke-width="20"/>`;
        legend.innerHTML = `<div class="legend-item"><span class="legend-color" style="background:var(--text-dim);"></span><span>Hộp thư trống</span></div>`;
        return;
    }

    const palette = ["#06b6d4", "#ec4899", "#10b981", "#f59e0b", "#8b5cf6", "#3b82f6", "#64748b"];
    const radius = 60;
    const circumference = 2 * Math.PI * radius;
    let accumulatedOffset = 0;

    activeFolders.slice(0, 5).forEach((f, idx) => {
        const color = palette[idx % palette.length];
        const fraction = f.size_bytes / summary.total_size_bytes;
        const strokeLength = fraction * circumference;
        const strokeGap = circumference - strokeLength;
        const pct = (fraction * 100).toFixed(1);

        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("cx", "80");
        circle.setAttribute("cy", "80");
        circle.setAttribute("r", radius);
        circle.setAttribute("fill", "none");
        circle.setAttribute("stroke", color);
        circle.setAttribute("stroke-width", "20");
        circle.setAttribute("stroke-dasharray", `${strokeLength} ${strokeGap}`);
        circle.setAttribute("stroke-dashoffset", -accumulatedOffset);
        circle.setAttribute("transform", "rotate(-90 80 80)");
        svg.appendChild(circle);

        accumulatedOffset += strokeLength;

        // Add to legend
        const item = document.createElement("div");
        item.className = "legend-item";
        item.innerHTML = `
            <span class="legend-color" style="background:${color};"></span>
            <span><strong>${f.name}</strong>: ${pct}% (${(f.size_bytes/1048576).toFixed(1)} MB)</span>
        `;
        legend.appendChild(item);
    });
}

function renderQuotaBar(summary) {
    const fill = document.getElementById("quotaProgressFill");
    const pctText = document.getElementById("quotaPercentText");
    const detail = document.getElementById("quotaDetailText");

    if (summary.quota_limit_bytes && summary.quota_limit_bytes > 0) {
        const usedMb = Math.round(summary.quota_used_bytes / 1048576);
        const limitMb = Math.round(summary.quota_limit_bytes / 1048576);
        const pct = Math.min(100, Math.round((summary.quota_used_bytes / summary.quota_limit_bytes) * 100));

        fill.style.width = `${pct}%`;
        pctText.textContent = `${pct}%`;
        detail.textContent = `Đã sử dụng ${usedMb} MB trong tổng hạn mức ${limitMb} MB`;

        if (pct >= 85) fill.style.background = "var(--danger)";
        else if (pct >= 70) fill.style.background = "var(--warning)";
        else fill.style.background = "var(--success)";
    } else {
        fill.style.width = "100%";
        fill.style.background = "var(--primary)";
        pctText.textContent = "Không giới hạn";
        detail.textContent = "Máy chủ không thiết lập giới hạn Quota hoặc là gói Unlimited";
    }
}

// SSE Event Stream for Live Progress
function listenToEventStream() {
    const evtSource = new EventSource("/api/migrate/stream");

    evtSource.onmessage = (event) => {
        const d = JSON.parse(event.data);

        if (d.type === "progress") {
            document.getElementById("progressBarFill").style.width = `${d.percent}%`;
            document.getElementById("progressPercentBadge").textContent = `${d.percent}%`;
            document.getElementById("statSuccessCount").textContent = d.success;
            document.getElementById("statSkippedCount").textContent = d.skipped;
            document.getElementById("statFailedCount").textContent = d.failed;
            document.getElementById("statCurrentFolder").textContent = d.folder || "-";
            appendTerminalLog(`[PROGRESS] ${d.percent}% | Folder: ${d.folder} | Success: ${d.success}`, "info");
        }

        if (d.type === "completed") {
            evtSource.close();
            const btn = document.getElementById("btnStartSingleMigrate");
            btn.disabled = false;
            btn.textContent = "🚀 BẮT ĐẦU DI CHUYỂN NGAY";

            document.getElementById("progressBarFill").style.width = "100%";
            document.getElementById("progressPercentBadge").textContent = "100%";

            showToast("✓ Hoàn tất di chuyển hộp thư!", "success");
            appendTerminalLog(`[COMPLETED] Hoàn thành: ${d.success} thư, Bỏ qua: ${d.skipped}, Lỗi: ${d.failed}`, "success");

            // Show report links
            const links = document.getElementById("reportLinksContainer");
            links.style.display = "block";
            links.innerHTML = `
                <div style="display: flex; gap: 12px; align-items: center;">
                    <a href="${d.html_report}" target="_blank" class="btn btn-primary btn-sm">📄 Xem Báo Cáo HTML Audit</a>
                    ${d.csv_report ? `<a href="${d.csv_report}" download class="btn btn-secondary btn-sm text-danger">📊 Tải CSV Danh Sách Thư Lỗi</a>` : ''}
                </div>
            `;
        }

        if (d.type === "error") {
            evtSource.close();
            const btn = document.getElementById("btnStartSingleMigrate");
            btn.disabled = false;
            btn.textContent = "🚀 BẮT ĐẦU DI CHUYỂN NGAY";
            showToast(`Lỗi tiến trình: ${d.message}`, "error");
            appendTerminalLog(`[ERROR] ${d.message}`, "error");
        }
    };
}

// Drag & Drop CSV Tab Logic
let parsedCsvData = [];

function initDropZone() {
    const dropZone = document.getElementById("dropZone");
    const fileInput = document.getElementById("csvFileInput");

    ["dragenter", "dragover"].forEach(name => {
        dropZone.addEventListener(name, (e) => {
            e.preventDefault();
            dropZone.classList.add("dragover");
        });
    });

    ["dragleave", "drop"].forEach(name => {
        dropZone.addEventListener(name, (e) => {
            e.preventDefault();
            dropZone.classList.remove("dragover");
        });
    });

    dropZone.addEventListener("drop", (e) => {
        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].name.endsWith(".csv")) {
            handleCsvFile(files[0]);
        } else {
            showToast("Vui lòng tải lên file định dạng .csv", "error");
        }
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleCsvFile(e.target.files[0]);
        }
    });

    // Check all passwords in parallel
    document.getElementById("btnCheckAllPasswords").addEventListener("click", async () => {
        const btn = document.getElementById("btnCheckAllPasswords");
        btn.disabled = true;
        btn.textContent = "Đang kiểm tra đồng thời...";
        appendTerminalLog(`[BATCH CHECK] Đang kiểm tra mật khẩu đồng thời cho ${parsedCsvData.length} tài khoản...`, "info");

        try {
            const res = await fetch("/api/check-csv", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ accounts: parsedCsvData }),
            });
            const results = await res.json();

            results.forEach((r, idx) => {
                const cell = document.getElementById(`csvAuthCell_${idx}`);
                if (cell) {
                    if (r.is_valid) {
                        cell.innerHTML = `<span class="badge badge-success">✓ HỢP LỆ (${r.latency_ms}ms)</span>`;
                    } else {
                        cell.innerHTML = `<span class="badge badge-danger" title="${r.provider_hint || r.error_reason}">✗ THẤT BẠI</span>`;
                    }
                }
            });

            showToast("✓ Hoàn tất kiểm tra mật khẩu toàn bộ danh sách CSV!", "success");
            appendTerminalLog(`[BATCH CHECK DONE] Đã kiểm tra xong toàn bộ CSV`, "success");
        } catch (e) {
            showToast(`Lỗi kiểm tra CSV: ${e.message}`, "error");
        } finally {
            btn.disabled = false;
            btn.textContent = "🔑 Kiểm Tra Toàn Bộ Mật Khẩu (Parallel)";
        }
    });
}

function handleCsvFile(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
        const text = e.target.result;
        parseCsvText(text);
    };
    reader.readAsText(file);
}

function parseCsvText(text) {
    const lines = text.split("\n").map(l => l.trim()).filter(l => l.length > 0);
    if (lines.length < 2) {
        showToast("File CSV rỗng hoặc không có dữ liệu!", "error");
        return;
    }

    const headers = lines[0].split(",").map(h => h.trim());
    parsedCsvData = [];

    for (let i = 1; i < lines.length; i++) {
        const cols = lines[i].split(",").map(c => c.trim());
        if (cols.length >= 4) {
            const rowObj = {};
            headers.forEach((h, idx) => {
                rowObj[h] = cols[idx] || "";
            });
            parsedCsvData.push(rowObj);
        }
    }

    renderCsvPreview();
    showToast(`Đã nạp ${parsedCsvData.length} tài khoản từ file CSV!`, "success");
    appendTerminalLog(`[CSV LOADED] Đã nạp thành công file CSV với ${parsedCsvData.length} dòng`, "info");
}

function renderCsvPreview() {
    const section = document.getElementById("csvPreviewSection");
    section.style.display = "block";
    document.getElementById("csvTotalCount").textContent = parsedCsvData.length;

    const tbody = document.getElementById("csvTableBody");
    tbody.innerHTML = "";

    parsedCsvData.forEach((row, idx) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${idx + 1}</td>
            <td><strong>${row.source_user || ''}</strong></td>
            <td><code class="code-source">${row.source_host || ''}</code></td>
            <td><strong>${row.dest_user || ''}</strong></td>
            <td><code class="code-dest">${row.dest_host || ''}</code></td>
            <td id="csvAuthCell_${idx}" style="text-align: center;"><span class="badge badge-neutral">Chưa test</span></td>
            <td id="csvMigrateCell_${idx}" style="text-align: center;"><span class="badge badge-neutral">Chờ</span></td>
        `;
        tbody.appendChild(tr);
    });
}

// Sessions & Archive Tab Logic
async function loadSessions() {
    const tbody = document.getElementById("sessionsTableBody");
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 20px;">Đang tải danh sách phiên...</td></tr>`;

    try {
        const res = await fetch("/api/sessions");
        const sessions = await res.json();

        if (sessions.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 20px;">Chưa có phiên di chuyển nào.</td></tr>`;
            return;
        }

        tbody.innerHTML = "";
        sessions.forEach(s => {
            const tr = document.createElement("tr");
            let badgeClass = s.status === "COMPLETED" ? "badge-success" : (s.failed_messages > 0 ? "badge-danger" : "badge-primary");

            tr.innerHTML = `
                <td><strong>#${s.id}</strong></td>
                <td>${s.source_account} ➔ ${s.dest_account}</td>
                <td style="text-align: center;"><span class="badge ${badgeClass}">${s.status}</span></td>
                <td style="text-align: right;" class="text-success">${s.migrated_messages}</td>
                <td style="text-align: right;" class="text-primary">${s.skipped_messages}</td>
                <td style="text-align: right;" class="text-danger">${s.failed_messages}</td>
                <td style="font-size: 12px; color: var(--text-muted);">${s.started_at ? s.started_at.substring(0, 19) : '-'}</td>
                <td style="text-align: center;">
                    <button class="btn btn-secondary btn-sm" onclick="openReports(${s.id})">📄 Báo cáo</button>
                    ${s.failed_messages > 0 ? `<button class="btn btn-secondary btn-sm text-warning" onclick="retrySessionPrompt(${s.id})">🔁 Thử lại</button>` : ''}
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--danger); padding: 20px;">Lỗi tải dữ liệu: ${e.message}</td></tr>`;
    }
}

document.getElementById("btnRefreshSessions").addEventListener("click", loadSessions);

function openReports(sessionId) {
    window.open(`/api/reports/view/${sessionId}`, "_blank");
}

function retrySessionPrompt(sessionId) {
    if (confirm(`Bạn có chắc muốn chạy lại (Retry) các thư bị lỗi của phiên #${sessionId}?`)) {
        showToast(`Đang kích hoạt thử lại cho phiên #${sessionId}...`, "info");
        appendTerminalLog(`[RETRY] Đang kích hoạt thử lại cho phiên ID #${sessionId}...`, "info");
        fetch(`/api/retry/${sessionId}`, { method: "POST" })
            .then(res => res.json())
            .then(d => {
                showToast(`Đã phục hồi: ${d.recovered} thư, còn lỗi: ${d.still_failed} thư`, "success");
                appendTerminalLog(`[RETRY DONE] Phục hồi: ${d.recovered} thư, Còn lỗi: ${d.still_failed} thư`, "success");
                loadSessions();
            })
            .catch(e => {
                showToast(`Lỗi retry: ${e.message}`, "error");
                appendTerminalLog(`[RETRY ERROR] ${e.message}`, "error");
            });
    }
}

// Live Terminal Log Drawer Logic
let logCounter = 0;

function initLogDrawer() {
    const drawer = document.getElementById("logDrawer");
    const toggleBtn = document.getElementById("btnToggleDrawer");
    const clearBtn = document.getElementById("btnClearLogs");
    const header = document.getElementById("drawerHeader");

    header.addEventListener("click", (e) => {
        if (e.target.tagName !== "BUTTON") {
            toggleDrawer();
        }
    });

    toggleBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        toggleDrawer();
    });

    clearBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        document.getElementById("drawerConsoleBody").innerHTML = `<div class="log-line text-muted">[Cleared] Bảng log đã được xóa.</div>`;
        logCounter = 0;
        document.getElementById("drawerLogCount").textContent = "0 logs";
    });
}

function toggleDrawer() {
    const drawer = document.getElementById("logDrawer");
    const toggleBtn = document.getElementById("btnToggleDrawer");
    if (drawer.classList.contains("collapsed")) {
        drawer.classList.remove("collapsed");
        drawer.classList.add("expanded");
        toggleBtn.textContent = "▼ Thu nhỏ Console";
    } else {
        drawer.classList.remove("expanded");
        drawer.classList.add("collapsed");
        toggleBtn.textContent = "▲ Mở rộng Console";
    }
}

function appendTerminalLog(message, type = "info") {
    const body = document.getElementById("drawerConsoleBody");
    const countBadge = document.getElementById("drawerLogCount");
    logCounter++;
    countBadge.textContent = `${logCounter} logs`;

    const now = new Date().toTimeString().split(" ")[0];
    let typeClass = "log-msg";
    if (type === "success") typeClass = "log-success";
    else if (type === "error") typeClass = "log-error";
    else if (type === "warning") typeClass = "log-warning";
    else if (type === "info") typeClass = "log-info";

    const line = document.createElement("div");
    line.className = "log-line";
    line.innerHTML = `<span class="log-time">[${now}]</span> <span class="${typeClass}">${message}</span>`;
    body.appendChild(line);

    // Auto-scroll to bottom
    body.scrollTop = body.scrollHeight;
}
