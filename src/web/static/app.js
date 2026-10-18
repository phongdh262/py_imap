// Py-IMAP Web Admin Control Panel Client Logic (Minimalist Monochrome Edition)

document.addEventListener("DOMContentLoaded", () => {
    initThemeSwitcher();
    initTabs();
    initProviderChips();
    initSingleAccountTab();
    initDropZone();
    initActiveTasksTab();
    initSessionsTab();
    initLogDrawer();
    updateGrafanaLink();
    loadActiveTasks();
    setInterval(loadActiveTasks, 3000);
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
        setTimeout(() => toast.remove(), 250);
    }, 3500);
}

// Adjust Grafana button URL to current host IP
function updateGrafanaLink() {
    const btn = document.getElementById("grafanaBtn");
    if (btn) {
        const host = window.location.hostname || "localhost";
        btn.href = `http://${host}:3000`;
    }
}

// Minimalist Theme Switcher Logic (Dark / Light)
function initThemeSwitcher() {
    let savedTheme = localStorage.getItem("py_imap_theme") || "dark";
    if (savedTheme === "midnight" || savedTheme === "obsidian") {
        savedTheme = "dark";
    }
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
            switchToTab(item.dataset.tab);
        });
    });
}

function switchToTab(tabId) {
    document.querySelectorAll(".nav-item").forEach(n => {
        n.classList.toggle("active", n.dataset.tab === tabId);
    });
    document.querySelectorAll(".tab-pane").forEach(p => {
        p.classList.toggle("active", p.id === tabId);
    });
    if (tabId === "sessionsTab") {
        loadSessions();
    } else if (tabId === "activeTasksTab") {
        loadActiveTasks();
    }
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
        if (hintText) hintText.textContent = "Lưu ý Gmail: Bật 2FA và tạo Mật khẩu ứng dụng (16 ký tự)";
    } else if (provider === "outlook") {
        hostInput.value = "outlook.office365.com";
        portInput.value = 993;
        sslSelect.value = "true";
        if (hintText) hintText.textContent = "Lưu ý Microsoft 365: Dùng App Password hoặc bật IMAP trong Exchange";
    } else if (provider === "yandex") {
        hostInput.value = "imap.yandex.com";
        portInput.value = 993;
        sslSelect.value = "true";
        if (hintText) hintText.textContent = "Lưu ý Yandex: Tạo Mật khẩu ứng dụng tại Yandex ID > Security";
    } else if (provider === "cpanel") {
        const userInput = document.getElementById(`${target}User`).value.trim();
        let domain = "cpanel-domain.com";
        if (userInput.includes("@")) {
            domain = userInput.split("@")[1];
        }
        hostInput.value = `mail.${domain}`;
        portInput.value = 993;
        sslSelect.value = "true";
        if (hintText) hintText.textContent = `cPanel: Mặc định mail.${domain} (Port 993 SSL)`;
    } else if (provider === "custom") {
        if (hintText) hintText.textContent = "";
    }
}

// Single Account Tab Logic
function initSingleAccountTab() {
    // 1. Test Source Password
    document.getElementById("btnTestSrcPass").addEventListener("click", async () => {
        const btn = document.getElementById("btnTestSrcPass");
        const hint = document.getElementById("srcHintText");

        const payload = {
            host: document.getElementById("srcHost").value.trim(),
            port: parseInt(document.getElementById("srcPort").value) || 993,
            ssl: document.getElementById("srcSsl").value === "true",
            username: document.getElementById("srcUser").value.trim(),
            password: document.getElementById("srcPass").value.trim(),
        };

        if (!payload.username || !payload.password) {
            if (hint) {
                hint.innerHTML = `<span style="color:var(--danger-text); font-weight:600;">Vui lòng nhập Email và Mật khẩu nguồn!</span>`;
            }
            showToast("Vui lòng nhập Email và Mật khẩu nguồn!", "error");
            return;
        }

        btn.disabled = true;
        btn.textContent = "Đang kiểm tra kết nối...";
        if (hint) {
            hint.innerHTML = `<span style="color:var(--text-muted);">Đang kết nối IMAP SSL và thử đăng nhập...</span>`;
        }

        appendTerminalLog(`[AUTH CHECK] Kiểm tra xác thực nguồn: ${payload.username} @ ${payload.host}...`, "info");

        try {
            const res = await fetch("/api/check-password", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (data.is_valid) {
                btn.textContent = `✓ Hợp Lệ (${data.latency_ms}ms)`;
                if (hint) {
                    hint.innerHTML = `<span style="color:#16a34a; font-weight:600;">✓ Mật khẩu chính xác! Độ trễ IMAP: ${data.latency_ms}ms</span>`;
                }
                showToast(`Mật khẩu Nguồn hợp lệ (${data.latency_ms}ms)`, "success");
                appendTerminalLog(`[AUTH OK] Nguồn ${payload.username} hợp lệ, Latency: ${data.latency_ms}ms`, "success");
            } else {
                const reason = data.provider_hint || data.error_reason || (data.detail || "Sai mật khẩu hoặc chưa bật IMAP");
                btn.textContent = "✗ Không Hợp Lệ";
                if (hint) {
                    hint.innerHTML = `<span style="color:var(--danger-text); font-weight:600;">✗ Thất bại: ${reason}</span>`;
                }
                showToast(`Thất bại: ${reason}`, "error");
                appendTerminalLog(`[AUTH FAILED] Nguồn ${payload.username} thất bại: ${reason}`, "error");
            }
        } catch (e) {
            btn.textContent = "✗ Lỗi Kết Nối";
            if (hint) {
                hint.innerHTML = `<span style="color:var(--danger-text); font-weight:600;">✗ Lỗi: ${e.message}</span>`;
            }
            showToast(`Lỗi kết nối máy chủ: ${e.message}`, "error");
            appendTerminalLog(`[ERROR] Không thể kết nối máy chủ: ${e.message}`, "error");
        } finally {
            btn.disabled = false;
            setTimeout(() => {
                btn.textContent = "Kiểm Tra Mật Khẩu";
            }, 4000);
        }
    });

    // 2. Test Destination Password
    document.getElementById("btnTestDstPass").addEventListener("click", async () => {
        const btn = document.getElementById("btnTestDstPass");
        const hint = document.getElementById("dstHintText");

        const payload = {
            host: document.getElementById("dstHost").value.trim(),
            port: parseInt(document.getElementById("dstPort").value) || 993,
            ssl: document.getElementById("dstSsl").value === "true",
            username: document.getElementById("dstUser").value.trim(),
            password: document.getElementById("dstPass").value.trim(),
        };

        if (!payload.username || !payload.password) {
            if (hint) {
                hint.innerHTML = `<span style="color:var(--danger-text); font-weight:600;">Vui lòng nhập Email và Mật khẩu đích!</span>`;
            }
            showToast("Vui lòng nhập Email và Mật khẩu đích!", "error");
            return;
        }

        btn.disabled = true;
        btn.textContent = "Đang kiểm tra kết nối...";
        if (hint) {
            hint.innerHTML = `<span style="color:var(--text-muted);">Đang kết nối IMAP SSL và thử đăng nhập...</span>`;
        }

        appendTerminalLog(`[AUTH CHECK] Kiểm tra xác thực đích: ${payload.username} @ ${payload.host}...`, "info");

        try {
            const res = await fetch("/api/check-password", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (data.is_valid) {
                btn.textContent = `✓ Hợp Lệ (${data.latency_ms}ms)`;
                if (hint) {
                    hint.innerHTML = `<span style="color:#16a34a; font-weight:600;">✓ Mật khẩu chính xác! Độ trễ IMAP: ${data.latency_ms}ms</span>`;
                }
                showToast(`Mật khẩu Đích hợp lệ (${data.latency_ms}ms)`, "success");
                appendTerminalLog(`[AUTH OK] Đích ${payload.username} hợp lệ, Latency: ${data.latency_ms}ms`, "success");
            } else {
                const reason = data.provider_hint || data.error_reason || (data.detail || "Sai mật khẩu hoặc chưa bật IMAP");
                btn.textContent = "✗ Không Hợp Lệ";
                if (hint) {
                    hint.innerHTML = `<span style="color:var(--danger-text); font-weight:600;">✗ Thất bại: ${reason}</span>`;
                }
                showToast(`Thất bại: ${reason}`, "error");
                appendTerminalLog(`[AUTH FAILED] Đích ${payload.username} thất bại: ${reason}`, "error");
            }
        } catch (e) {
            btn.textContent = "✗ Lỗi Kết Nối";
            if (hint) {
                hint.innerHTML = `<span style="color:var(--danger-text); font-weight:600;">✗ Lỗi: ${e.message}</span>`;
            }
            showToast(`Lỗi kết nối máy chủ: ${e.message}`, "error");
            appendTerminalLog(`[ERROR] Không thể kết nối máy chủ: ${e.message}`, "error");
        } finally {
            btn.disabled = false;
            setTimeout(() => {
                btn.textContent = "Kiểm Tra Đăng Nhập Đích";
            }, 4000);
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

        if (!payload.username || !payload.password) {
            showToast("Vui lòng nhập Email và Mật khẩu nguồn để quét!", "error");
            btn.disabled = false;
            btn.textContent = "Quét Dung Lượng & Cây Thư Mục";
            return;
        }

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
            const totalMb = data.total_size_mb != null
                ? data.total_size_mb
                : (data.total_size_bytes ? (data.total_size_bytes / (1024 * 1024)).toFixed(2) : "0.00");
            showToast(`Đã quét xong: ${totalMb} MB (${data.total_messages || 0} thư)`, "success");
            appendTerminalLog(`[INSPECT DONE] Tổng: ${totalMb} MB trên ${(data.folders || []).length} thư mục`, "success");
        } catch (e) {
            showToast(`Lỗi quét dung lượng: ${e.message}`, "error");
            appendTerminalLog(`[INSPECT ERROR] ${e.message}`, "error");
        } finally {
            btn.disabled = false;
            btn.textContent = "Quét Dung Lượng & Cây Thư Mục";
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
            batch_size: parseInt(document.getElementById("settingBatchSize").value) || 50,
            batch_delay_ms: parseInt(document.getElementById("settingBatchDelay").value) || 50,
            sanitize_accents: document.getElementById("settingSanitizeAccents").checked,
            force_remigrate: document.getElementById("forceRemigrateSingle") ? document.getElementById("forceRemigrateSingle").checked : false,
        };

        if (!payload.source.username || !payload.source.password || !payload.dest.username || !payload.dest.password) {
            showToast("Vui lòng điền đầy đủ tài khoản và mật khẩu cả 2 đầu!", "error");
            return;
        }

        const btn = document.getElementById("btnStartSingleMigrate");
        btn.disabled = true;
        btn.textContent = "Đang di chuyển...";

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
            listenToEventStream(data.task_id);

        } catch (e) {
            showToast(`Lỗi: ${e.message}`, "error");
            btn.disabled = false;
            btn.textContent = "Bắt Đầu Di Chuyển";
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

function renderInspectionResults(data) {
    const container = document.getElementById("inspectionResultContainer");
    container.style.display = "block";
    container.scrollIntoView({ behavior: "smooth" });

    // Robust calculation for total MB
    const totalMb = data.total_size_mb != null
        ? data.total_size_mb
        : (data.total_size_bytes ? (data.total_size_bytes / (1024 * 1024)).toFixed(2) : "0.00");

    const totalMsgs = data.total_messages != null ? data.total_messages : 0;
    const foldersCount = data.folders ? data.folders.length : 0;

    // Summary Badges
    const badgeContainer = document.getElementById("inspectionSummaryBadges");
    badgeContainer.innerHTML = `
        <span class="badge badge-neutral">Tổng: ${totalMb} MB</span>
        <span class="badge badge-neutral">${totalMsgs.toLocaleString()} Thư</span>
        <span class="badge badge-neutral">${foldersCount} Thư mục</span>
    `;

    // Quota details
    const quota = data.quota;
    const quotaFill = document.getElementById("quotaProgressFill");
    const quotaPct = document.getElementById("quotaPercentText");
    const quotaDetail = document.getElementById("quotaDetailText");

    if (quota && quota.percent != null) {
        quotaFill.style.width = `${Math.min(quota.percent, 100)}%`;
        quotaPct.textContent = `${quota.percent}%`;
        quotaDetail.textContent = `Đã dùng ${quota.usage_mb} MB / ${quota.limit_mb} MB`;
    } else {
        quotaFill.style.width = "0%";
        quotaPct.textContent = "N/A";
        quotaDetail.textContent = "Máy chủ không hỗ trợ lệnh IMAP QUOTA";
    }

    // Folders table
    const tbody = document.getElementById("foldersTableBody");
    tbody.innerHTML = "";

    (data.folders || []).forEach(f => {
        const tr = document.createElement("tr");
        const roleBadge = f.role ? `<span class="badge badge-neutral">${f.role}</span>` : `<span class="text-dim">Mặc định</span>`;
        
        const folderMb = f.size_mb != null
            ? f.size_mb
            : (f.size_bytes ? (f.size_bytes / (1024 * 1024)).toFixed(2) : "0.00");

        const targetFolder = f.destination_folder || f.mapped_target || (f.role && f.role !== "CUSTOM" ? f.role : f.name);
        const mapStatus = f.is_excluded
            ? `<span class="badge badge-neutral">Loại trừ</span>`
            : `<span class="text-primary">${targetFolder}</span>`;

        tr.innerHTML = `
            <td><strong>${f.name}</strong></td>
            <td>${roleBadge}</td>
            <td style="text-align: right; font-family: 'JetBrains Mono', monospace;">${(f.messages_count || 0).toLocaleString()}</td>
            <td style="text-align: right; font-family: 'JetBrains Mono', monospace;">${folderMb} MB</td>
            <td style="text-align: center;">${mapStatus}</td>
        `;
        tbody.appendChild(tr);
    });

    // Donut chart
    renderStorageDonutChart(data);
}

function renderStorageDonutChart(summary) {
    const svg = document.getElementById("storageDonutSvg");
    const legend = document.getElementById("chartLegend");
    const centerSize = document.getElementById("donutCenterSize");

    const totalMb = summary.total_size_mb != null
        ? summary.total_size_mb
        : (summary.total_size_bytes ? (summary.total_size_bytes / (1024 * 1024)).toFixed(2) : "0.00");

    centerSize.textContent = `${totalMb} MB`;
    svg.innerHTML = "";
    legend.innerHTML = "";

    const activeFolders = summary.folders
        .filter(f => !f.is_excluded && f.size_bytes > 0)
        .sort((a, b) => b.size_bytes - a.size_bytes);

    if (activeFolders.length === 0 || summary.total_size_bytes === 0) {
        svg.innerHTML = `<circle cx="80" cy="80" r="60" fill="none" stroke="var(--border)" stroke-width="16"/>`;
        legend.innerHTML = `<div class="legend-item"><span class="legend-color" style="background:var(--border);"></span><span>Hộp thư trống</span></div>`;
        return;
    }

    const isLight = document.documentElement.getAttribute("data-theme") === "light";
    const palette = isLight
        ? ["#09090b", "#3f3f46", "#71717a", "#a1a1aa", "#d4d4d8"]
        : ["#ffffff", "#d4d4d8", "#a1a1aa", "#71717a", "#52525b"];
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
        circle.setAttribute("stroke-width", "16");
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

// Server-Sent Events (SSE) Stream Listener with Task-ID Isolation
let currentSseSource = null;

function listenToEventStream(taskId = null) {
    if (currentSseSource) {
        currentSseSource.close();
        currentSseSource = null;
    }

    const url = taskId ? `/api/migrate/stream?task_id=${encodeURIComponent(taskId)}` : `/api/migrate/stream`;
    const evtSource = new EventSource(url);
    currentSseSource = evtSource;

    evtSource.onmessage = (event) => {
        if (!event.data || event.data.trim() === ": ping") return;
        let d;
        try {
            d = JSON.parse(event.data);
        } catch (e) {
            return;
        }

        if (d.type === "progress") {
            const pct = d.percent || 0;
            document.getElementById("progressBarFill").style.width = `${pct}%`;
            document.getElementById("progressPercentBadge").textContent = `${pct.toFixed(1)}%`;

            document.getElementById("statSuccessCount").textContent = d.success || 0;
            document.getElementById("statSkippedCount").textContent = d.skipped || 0;
            document.getElementById("statFailedCount").textContent = d.failed || 0;
            if (d.folder) {
                document.getElementById("statCurrentFolder").textContent = d.folder;
            }

            if (d.log_message) {
                appendTerminalLog(d.log_message, d.level || "info");
            }
        }

        if (d.type === "completed") {
            evtSource.close();
            currentSseSource = null;
            const btn = document.getElementById("btnStartSingleMigrate");
            btn.disabled = false;
            btn.textContent = "Bắt Đầu Di Chuyển";

            document.getElementById("progressBarFill").style.width = "100%";
            document.getElementById("progressPercentBadge").textContent = "100%";

            showToast("Hoàn tất di chuyển hộp thư!", "success");
            appendTerminalLog(`[COMPLETED] Hoàn thành: ${d.success} thư, Bỏ qua: ${d.skipped}, Lỗi: ${d.failed}`, "success");

            // Show report links
            const links = document.getElementById("reportLinksContainer");
            links.style.display = "block";
            links.innerHTML = `
                <div style="display: flex; gap: 12px; align-items: center;">
                    <a href="${d.html_report}" target="_blank" class="btn btn-primary btn-sm">Xem Báo Cáo HTML Audit</a>
                    ${d.csv_report ? `<a href="${d.csv_report}" download class="btn btn-secondary btn-sm text-danger">Tải CSV Thư Lỗi</a>` : ''}
                </div>
            `;
            loadActiveTasks();
            loadSessions();
        }

        if (d.type === "error") {
            evtSource.close();
            currentSseSource = null;
            const btn = document.getElementById("btnStartSingleMigrate");
            btn.disabled = false;
            btn.textContent = "Bắt Đầu Di Chuyển";
            showToast(`Lỗi tiến trình: ${d.message}`, "error");
            appendTerminalLog(`[ERROR] ${d.message}`, "error");
            loadActiveTasks();
        }
    };

    evtSource.onerror = () => {
        // SSE error or completed disconnect
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
        appendTerminalLog(`[BATCH CHECK] Kiểm tra mật khẩu cho ${parsedCsvData.length} tài khoản...`, "info");

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
                        cell.innerHTML = `<span class="badge badge-neutral" style="color:var(--text-primary);">HỢP LỆ (${r.latency_ms}ms)</span>`;
                    } else {
                        cell.innerHTML = `<span class="badge badge-neutral" style="color:var(--danger-text);" title="${r.provider_hint || r.error_reason}">THẤT BẠI</span>`;
                    }
                }
            });

            showToast("Hoàn tất kiểm tra mật khẩu toàn bộ danh sách CSV!", "success");
            appendTerminalLog(`[BATCH CHECK DONE] Đã kiểm tra xong toàn bộ CSV`, "success");
        } catch (e) {
            showToast(`Lỗi kiểm tra CSV: ${e.message}`, "error");
        } finally {
            btn.disabled = false;
            btn.textContent = "Kiểm Tra Toàn Bộ Mật Khẩu";
        }
    });

    // Start Batch Migration
    const btnBatch = document.getElementById("btnStartBatchMigrate");
    if (btnBatch) {
        btnBatch.addEventListener("click", async () => {
            if (parsedCsvData.length === 0) {
                showToast("Chưa có danh sách tài khoản CSV!", "error");
                return;
            }
            btnBatch.disabled = true;
            btnBatch.textContent = "Đang khởi tạo hàng đợi...";

            const sanitizeAccents = document.getElementById("sanitizeAccents") ? document.getElementById("sanitizeAccents").checked : false;
            const batchDelay = document.getElementById("batchDelayInput") ? parseInt(document.getElementById("batchDelayInput").value) : 50;

            try {
                const res = await fetch("/api/migrate/batch", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        accounts: parsedCsvData,
                        sanitize_accents: sanitizeAccents,
                        batch_delay_ms: batchDelay,
                    }),
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || "Khởi động di chuyển hàng loạt thất bại");

                showToast(`Đã đưa ${parsedCsvData.length} tài khoản vào hàng đợi di chuyển ngầm!`, "success");
                appendTerminalLog(`[BATCH QUEUED] ${data.message}`, "success");

                // Switch to Active Tasks tab automatically
                switchToTab("activeTasksTab");
                loadActiveTasks();
                listenToEventStream();
            } catch (err) {
                showToast(`Lỗi: ${err.message}`, "error");
                appendTerminalLog(`[BATCH ERROR] ${err.message}`, "error");
            } finally {
                btnBatch.disabled = false;
                btnBatch.textContent = "Bắt Đầu Di Chuyển Toàn Bộ CSV";
            }
        });
    }
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
    appendTerminalLog(`[CSV LOADED] Đã nạp thành công ${parsedCsvData.length} dòng từ file CSV`, "info");
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
            <td><code>${row.source_host || ''}</code></td>
            <td><strong>${row.dest_user || ''}</strong></td>
            <td><code>${row.dest_host || ''}</code></td>
            <td id="csvAuthCell_${idx}" style="text-align: center;"><span class="badge badge-neutral">Chưa test</span></td>
            <td id="csvMigrateCell_${idx}" style="text-align: center;"><span class="badge badge-neutral">Chờ</span></td>
        `;
        tbody.appendChild(tr);
    });
}

// Active Tasks & Background Queue Manager Logic
function initActiveTasksTab() {
    const btnMin = document.getElementById("btnMinimizeProgress");
    if (btnMin) {
        btnMin.addEventListener("click", minimizeProgressWidget);
    }

    const btnExp = document.getElementById("btnExpandProgress");
    if (btnExp) {
        btnExp.addEventListener("click", (e) => {
            e.stopPropagation();
            expandProgressWidget();
        });
    }

    const floatWidget = document.getElementById("floatingTaskWidget");
    if (floatWidget) {
        floatWidget.addEventListener("click", (e) => {
            if (e.target.closest("#btnExpandProgress")) return;
            expandProgressWidget();
        });
    }

    const btnRefresh = document.getElementById("btnRefreshTasks");
    if (btnRefresh) {
        btnRefresh.addEventListener("click", loadActiveTasks);
    }
}

let isTaskMinimizedInCurrentTab = false;

function minimizeProgressWidget() {
    isTaskMinimizedInCurrentTab = true;
    const container = document.getElementById("singleProgressContainer");
    if (container) container.style.display = "none";

    const floatWidget = document.getElementById("floatingTaskWidget");
    if (floatWidget) floatWidget.style.display = "block";

    const btn = document.getElementById("btnStartSingleMigrate");
    if (btn) {
        btn.disabled = false;
        btn.textContent = "Bắt Đầu Di Chuyển";
    }
    showToast("Tiến trình đã được thu gọn xuống góc màn hình. Bạn có thể mở tab mới hoặc tiếp tục tạo tiến trình!", "info");
    loadActiveTasks();
}

function expandProgressWidget() {
    isTaskMinimizedInCurrentTab = false;
    const floatWidget = document.getElementById("floatingTaskWidget");
    if (floatWidget) floatWidget.style.display = "none";

    switchToTab("singleTab");
    const container = document.getElementById("singleProgressContainer");
    if (container) {
        container.style.display = "block";
        container.scrollIntoView({ behavior: "smooth" });
    }
}

async function loadActiveTasks() {
    try {
        const res = await fetch("/api/tasks/active");
        if (!res.ok) return;
        const tasks = await res.json();

        // 1. Update Active Tasks Badge in Sidebar
        const runningTasks = tasks.filter(t => t.status === "RUNNING");
        const badge = document.getElementById("activeTasksBadge");
        if (badge) {
            if (runningTasks.length > 0) {
                badge.style.display = "inline-flex";
                badge.textContent = runningTasks.length;
            } else {
                badge.style.display = "none";
            }
        }

        // 2. Update Floating Widget only if minimized in THIS tab
        const floatWidget = document.getElementById("floatingTaskWidget");
        const singleContainer = document.getElementById("singleProgressContainer");
        const isSingleOpen = singleContainer && singleContainer.style.display !== "none";

        if (runningTasks.length > 0) {
            const current = runningTasks[0];
            const titleEl = document.getElementById("floatingTaskTitle");
            const folderEl = document.getElementById("floatingTaskFolder");
            const pctEl = document.getElementById("floatingTaskPercent");
            const barEl = document.getElementById("floatingProgressBarFill");

            if (titleEl) titleEl.textContent = `${current.source} ➔ ${current.dest}`;
            if (folderEl) folderEl.textContent = current.current_folder || "Đang xử lý...";
            if (pctEl) pctEl.textContent = `${(current.percent || 0).toFixed(1)}%`;
            if (barEl) barEl.style.width = `${current.percent || 0}%`;

            if (isTaskMinimizedInCurrentTab && !isSingleOpen && floatWidget) {
                floatWidget.style.display = "block";
            } else if (!isTaskMinimizedInCurrentTab && floatWidget) {
                floatWidget.style.display = "none";
            }
        } else {
            if (floatWidget && tasks.length > 0 && isTaskMinimizedInCurrentTab) {
                const lastTask = tasks[tasks.length - 1];
                if (lastTask.status === "COMPLETED") {
                    const titleEl = document.getElementById("floatingTaskTitle");
                    const pctEl = document.getElementById("floatingTaskPercent");
                    const barEl = document.getElementById("floatingProgressBarFill");
                    if (titleEl) titleEl.textContent = `Hoàn tất: ${lastTask.source}`;
                    if (pctEl) pctEl.textContent = "100%";
                    if (barEl) barEl.style.width = "100%";
                }
            } else if (floatWidget && !isTaskMinimizedInCurrentTab) {
                floatWidget.style.display = "none";
            }
        }

        // 3. Render Active Tasks Grid
        const container = document.getElementById("activeTasksList");
        if (!container) return;

        if (tasks.length === 0) {
            container.innerHTML = `
                <div class="card" style="text-align: center; color: var(--text-muted); padding: 30px;">
                    Hiện không có tiến trình nào đang chạy ngầm.
                </div>
            `;
            return;
        }

        const reversedTasks = [...tasks].reverse();
        container.innerHTML = "";

        reversedTasks.forEach(t => {
            const card = document.createElement("div");
            card.className = "card task-card";

            let statusBadge = `<span class="badge badge-neutral"><span class="status-dot"></span> Đang chạy</span>`;
            if (t.status === "COMPLETED") {
                statusBadge = `<span class="badge badge-neutral" style="color:var(--text-primary); border-color:var(--text-primary);">Hoàn thành</span>`;
            } else if (t.status === "FAILED") {
                statusBadge = `<span class="badge badge-neutral" style="color:var(--danger-text); border-color:var(--danger-text);">Lỗi</span>`;
            }

            const pct = (t.percent || 0).toFixed(1);

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
                    <div>
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                            ${statusBadge}
                            <span style="font-size: 11px; color: var(--text-dim);">${t.started_at || ''}</span>
                        </div>
                        <h4 style="font-size: 14px; margin: 0; font-family: 'JetBrains Mono', monospace;">
                            ${t.source} ➔ ${t.dest}
                        </h4>
                    </div>
                    <span class="badge badge-neutral" style="font-weight: 700;">${pct}%</span>
                </div>

                <div class="progress-bar-container" style="margin-bottom: 12px; height: 6px;">
                    <div class="progress-bar-fill" style="width: ${pct}%;"></div>
                </div>

                <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 12px;">
                    <strong>Thư mục:</strong> <code>${t.current_folder || 'Đang kết nối...'}</code>
                </div>

                <div class="stats-grid" style="grid-template-columns: repeat(3, 1fr); margin-bottom: 12px;">
                    <div class="stat-mini">
                        <span class="stat-mini-label">THÀNH CÔNG</span>
                        <span class="stat-mini-value" style="font-size: 16px;">${t.success || 0}</span>
                    </div>
                    <div class="stat-mini">
                        <span class="stat-mini-label">BỎ QUA</span>
                        <span class="stat-mini-value" style="font-size: 16px;">${t.skipped || 0}</span>
                    </div>
                    <div class="stat-mini">
                        <span class="stat-mini-label">LỖI</span>
                        <span class="stat-mini-value" style="font-size: 16px; color: var(--danger-text);">${t.failed || 0}</span>
                    </div>
                </div>

                ${t.status === "COMPLETED" && t.html_report ? `
                    <div style="display: flex; gap: 8px; justify-content: flex-end; border-top: 1px solid var(--border); padding-top: 12px;">
                        <a href="${t.html_report}" target="_blank" class="btn btn-primary btn-sm">Xem Báo Cáo Audit</a>
                        ${t.csv_report ? `<a href="/api/reports/download/${t.csv_report}" download class="btn btn-secondary btn-sm text-danger">Tải CSV Thư Lỗi</a>` : ''}
                    </div>
                ` : ''}

                ${t.status === "FAILED" && t.error_message ? `
                    <div style="font-size: 12px; color: var(--danger-text); background: rgba(239, 68, 68, 0.08); padding: 8px 12px; border-radius: 6px; border: 1px solid rgba(239, 68, 68, 0.2);">
                        ${t.error_message}
                    </div>
                ` : ''}
            `;
            container.appendChild(card);
        });
    } catch (e) {
        console.error("Error loading active tasks:", e);
    }
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

            tr.innerHTML = `
                <td><strong>#${s.id}</strong></td>
                <td>${s.source_account} ➔ ${s.dest_account}</td>
                <td style="text-align: center;"><span class="badge badge-neutral">${s.status}</span></td>
                <td style="text-align: right; font-family: 'JetBrains Mono', monospace;">${s.migrated_messages}</td>
                <td style="text-align: right; font-family: 'JetBrains Mono', monospace; color: var(--text-muted);">${s.skipped_messages}</td>
                <td style="text-align: right; font-family: 'JetBrains Mono', monospace; color: var(--danger-text);">${s.failed_messages}</td>
                <td style="font-size: 11px; color: var(--text-dim);">${s.started_at ? s.started_at.substring(0, 19) : '-'}</td>
                <td style="text-align: center;">
                    <button class="btn btn-secondary btn-sm" onclick="openReports(${s.id})">Báo cáo</button>
                    ${s.failed_messages > 0 ? `<button class="btn btn-secondary btn-sm" onclick="retrySessionPrompt(${s.id})">Thử lại</button>` : ''}
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--danger-text); padding: 20px;">Lỗi tải dữ liệu: ${e.message}</td></tr>`;
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
        toggleBtn.textContent = "Thu nhỏ Console ▼";
    } else {
        drawer.classList.remove("expanded");
        drawer.classList.add("collapsed");
        toggleBtn.textContent = "Mở rộng Console ▲";
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
    line.innerHTML = `<span class="log-time" style="color:var(--text-dim); margin-right:6px;">[${now}]</span><span class="${typeClass}">${message}</span>`;
    body.appendChild(line);

    // Auto-scroll to bottom
    body.scrollTop = body.scrollHeight;
}
