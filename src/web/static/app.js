document.addEventListener("DOMContentLoaded", () => {
    initThemeSwitcher();
    initTabs();
    initProviderChips();
    initSingleAccountTab();
    initDropZone();
    initAuthCheckTab();
    initSettingsTab();
    initActiveTasksTab();
    initSessionsTab();
    initLogDrawer();
    initModals();
    setupPasswordToggles();
    setupHistorySearch();
    updateGrafanaLink();
    loadActiveTasks();
    setInterval(loadActiveTasks, 3000);
});

// HTML escaping helper
function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

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
    let hostInput, portInput, sslSelect, hintText, userInput;
    if (target === "batchSrc") {
        hostInput = document.getElementById("batchSrcHost");
        portInput = document.getElementById("batchSrcPort");
        sslSelect = document.getElementById("batchSrcSsl");
    } else if (target === "batchDst") {
        hostInput = document.getElementById("batchDstHost");
        portInput = document.getElementById("batchDstPort");
        sslSelect = document.getElementById("batchDstSsl");
    } else {
        hostInput = document.getElementById(`${target}Host`);
        portInput = document.getElementById(`${target}Port`);
        sslSelect = document.getElementById(`${target}Ssl`);
        hintText = document.getElementById(`${target}HintText`);
        userInput = document.getElementById(`${target}User`) ? document.getElementById(`${target}User`).value.trim() : "";
    }

    if (!hostInput || !portInput || !sslSelect) return;

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
        let domain = "yourdomain.com";
        if (userInput && userInput.includes("@")) {
            domain = userInput.split("@")[1];
        }
        hostInput.value = `mail.${domain}`;
        portInput.value = 993;
        sslSelect.value = "true";
        if (hintText) hintText.textContent = `cPanel: Mặc định mail.${domain} (Port 993 SSL)`;
    } else if (provider === "custom") {
        if (hintText) hintText.textContent = "";
    }

    if (target.startsWith("batch") && typeof parsedCsvData !== "undefined" && parsedCsvData.length > 0) {
        renderCsvPreview();
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

    // 3. Inspect Source & Destination Mailbox (Dual Pre-Flight Scan)
    document.getElementById("btnInspectSrc").addEventListener("click", async () => {
        const btn = document.getElementById("btnInspectSrc");
        btn.disabled = true;
        btn.textContent = "Đang quét...";

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
            }
        };

        if (!payload.source.username || !payload.source.password) {
            showToast("Vui lòng nhập Email và Mật khẩu nguồn để quét!", "error");
            btn.disabled = false;
            btn.textContent = "Quét Dung Lượng & Cây Thư Mục";
            return;
        }

        const isDual = !!(payload.dest.username && payload.dest.password);
        appendTerminalLog(
            isDual
                ? `[INSPECT] Quét và đối chiếu cả 2 đầu: ${payload.source.username} ➔ ${payload.dest.username}...`
                : `[INSPECT] Quét hộp thư nguồn ${payload.source.username}...`,
            "info"
        );

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

            window.lastInspectionData = data;
            renderInspectionResults(data);
            const totalMb = data.total_size_mb != null
                ? data.total_size_mb
                : (data.total_size_bytes ? (data.total_size_bytes / (1024 * 1024)).toFixed(2) : "0.00");

            if (data.is_dual && data.reconciliation) {
                showToast(`Quét đối chiếu thành công: Nguồn ${totalMb} MB | Đích hiện có ${data.reconciliation.dest_existing_size_mb} MB`, "success");
                appendTerminalLog(`[INSPECT DONE] Nguồn: ${totalMb} MB (${data.total_messages} thư) | Đích hiện tại: ${data.reconciliation.dest_existing_size_mb} MB (${data.reconciliation.dest_existing_messages} thư)`, "success");
            } else {
                showToast(`Đã quét xong: ${totalMb} MB (${data.total_messages || 0} thư)`, "success");
                appendTerminalLog(`[INSPECT DONE] Tổng: ${totalMb} MB trên ${(data.folders || []).length} thư mục`, "success");
            }
        } catch (e) {
            showToast(`Lỗi quét dung lượng: ${e.message}`, "error");
            appendTerminalLog(`[INSPECT ERROR] ${e.message}`, "error");
        } finally {
            btn.disabled = false;
            btn.textContent = "Quét Dung Lượng & Cây Thư Mục";
        }
    });

    // 4. Start Single Migration (Prompt Confirmation Modal)
    document.getElementById("btnStartSingleMigrate").addEventListener("click", () => {
        const socketTimeout = parseInt(localStorage.getItem("setting_socket_timeout") || document.getElementById("settingSocketTimeout")?.value) || 60;
        const payload = {
            source: {
                host: document.getElementById("srcHost").value.trim(),
                port: parseInt(document.getElementById("srcPort").value) || 993,
                ssl: document.getElementById("srcSsl").value === "true",
                username: document.getElementById("srcUser").value.trim(),
                password: document.getElementById("srcPass").value.trim(),
                timeout: socketTimeout,
            },
            dest: {
                host: document.getElementById("dstHost").value.trim(),
                port: parseInt(document.getElementById("dstPort").value) || 993,
                ssl: document.getElementById("dstSsl").value === "true",
                username: document.getElementById("dstUser").value.trim(),
                password: document.getElementById("dstPass").value.trim(),
                timeout: socketTimeout,
            },
            batch_size: parseInt(localStorage.getItem("setting_batch_size") || document.getElementById("settingBatchSize")?.value) || 50,
            batch_delay_ms: parseInt(localStorage.getItem("setting_batch_delay") || document.getElementById("settingBatchDelay")?.value) || 50,
            sanitize_accents: document.getElementById("settingSanitizeAccents") ? document.getElementById("settingSanitizeAccents").checked : false,
            force_remigrate: document.getElementById("forceRemigrateSingle") ? document.getElementById("forceRemigrateSingle").checked : true,
        };

        if (!payload.source.username || !payload.source.password || !payload.dest.username || !payload.dest.password) {
            showToast("Vui lòng điền đầy đủ tài khoản và mật khẩu cả 2 đầu!", "error");
            return;
        }

        window.pendingMigratePayload = payload;
        document.getElementById("modalConfirmSrc").textContent = `${payload.source.username} (${payload.source.host}:${payload.source.port})`;
        document.getElementById("modalConfirmDst").textContent = `${payload.dest.username} (${payload.dest.host}:${payload.dest.port})`;

        const preScanRow = document.getElementById("modalPreScanRow");
        if (window.lastInspectionData) {
            const totalMb = window.lastInspectionData.total_size_mb || (window.lastInspectionData.total_size_bytes ? (window.lastInspectionData.total_size_bytes / (1024 * 1024)).toFixed(2) : "0");
            const totalMsgs = window.lastInspectionData.total_messages || 0;
            if (preScanRow) preScanRow.style.display = "flex";
            const confirmSizeEl = document.getElementById("modalConfirmSize");
            if (confirmSizeEl) confirmSizeEl.textContent = `${totalMb} MB (${totalMsgs.toLocaleString()} thư)`;
        } else {
            if (preScanRow) preScanRow.style.display = "none";
        }

        const modal = document.getElementById("confirmMigrateModal");
        if (modal) modal.classList.add("open");
    });
}

async function executeSingleMigrate(payload) {
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

function getFolderIcon(role, name) {
    const r = (role || "").toUpperCase();
    const n = (name || "").toUpperCase();
    if (r === "INBOX" || n === "INBOX") {
        return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2" style="flex-shrink:0;"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>`;
    } else if (r === "SENT" || n.includes("SENT") || n.includes("GỬI")) {
        return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2" style="flex-shrink:0;"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>`;
    } else if (r === "TRASH" || n.includes("TRASH") || n.includes("THÙNG RÁC")) {
        return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f43f5e" stroke-width="2" style="flex-shrink:0;"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>`;
    } else if (r === "SPAM" || r === "JUNK" || n.includes("SPAM") || n.includes("JUNK")) {
        return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2" style="flex-shrink:0;"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`;
    } else if (r === "DRAFTS" || n.includes("DRAFT") || n.includes("NHÁP")) {
        return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#a855f7" stroke-width="2" style="flex-shrink:0;"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>`;
    }
    return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0; color:var(--text-dim);"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>`;
}

function renderInspectionResults(data) {
    const container = document.getElementById("inspectionResultContainer");
    if (!container) return;
    container.style.display = "block";
    container.scrollIntoView({ behavior: "smooth" });

    // Cache current inspection data for modal/export
    window.lastInspectionData = data;

    const srcUser = document.getElementById("srcUser")?.value.trim() || (data.source ? data.source.username : "") || "Hộp thư nguồn";
    const srcHost = document.getElementById("srcHost")?.value.trim() || (data.source ? data.source.host : "") || "-";
    const dstUser = document.getElementById("dstUser")?.value.trim() || (data.dest ? data.dest.username : "") || "Hộp thư đích";
    const dstHost = document.getElementById("dstHost")?.value.trim() || (data.dest ? data.dest.host : "") || "-";

    const totalSrcMsgs = (data.source ? data.source.total_messages : data.total_messages) || 0;
    const totalSrcMb = (data.source ? data.source.total_size_mb : data.total_size_mb) || "0.00";
    const folders = (data.source ? data.source.folders : data.folders) || [];

    // Set Pillar 1: Source
    const reconSrcHost = document.getElementById("reconSourceHost");
    if (reconSrcHost) reconSrcHost.textContent = srcHost;
    const reconSrcUser = document.getElementById("reconSourceUser");
    if (reconSrcUser) reconSrcUser.textContent = srcUser;
    const reconSrcMessages = document.getElementById("reconSrcMessages");
    if (reconSrcMessages) reconSrcMessages.textContent = totalSrcMsgs.toLocaleString();
    const reconSrcSize = document.getElementById("reconSrcSize");
    if (reconSrcSize) reconSrcSize.textContent = `${totalSrcMb} MB`;
    const reconSrcFolders = document.getElementById("reconSrcFolders");
    if (reconSrcFolders) reconSrcFolders.textContent = folders.length;

    // Check Destination & Reconciliation
    const isDual = data.is_dual && data.reconciliation;
    const recon = data.reconciliation || {};

    const destMsgs = recon.dest_existing_messages || (data.dest ? data.dest.total_messages : 0) || 0;
    const destMb = recon.dest_existing_size_mb || (data.dest ? data.dest.total_size_mb : "0.00") || "0.00";
    const diffToTransfer = recon.messages_to_transfer != null ? recon.messages_to_transfer : totalSrcMsgs;

    // Set Pillar 2: Bridge
    const reconDiffEl = document.getElementById("reconDiffNumber");
    if (reconDiffEl) reconDiffEl.textContent = `~${diffToTransfer.toLocaleString()} thư`;

    // Set Pillar 3: Dest
    const reconDestHost = document.getElementById("reconDestHost");
    if (reconDestHost) reconDestHost.textContent = dstHost;
    const reconDestUser = document.getElementById("reconDestUser");
    if (reconDestUser) reconDestUser.textContent = dstUser;
    const reconDestMessages = document.getElementById("reconDestMessages");
    if (reconDestMessages) reconDestMessages.textContent = destMsgs.toLocaleString();
    const reconDestSize = document.getElementById("reconDestSize");
    if (reconDestSize) reconDestSize.textContent = `${destMb} MB`;

    // Title & Badges
    const titleEl = document.getElementById("inspectionTitle");
    const badgeContainer = document.getElementById("inspectionSummaryBadges");
    if (titleEl) {
        titleEl.textContent = isDual ? "Kết Quả Đối Chiếu Nguồn & Đích" : "Kết Quả Quét Hộp Thư Nguồn";
    }

    if (badgeContainer) {
        if (isDual) {
            badgeContainer.innerHTML = `
                <span class="badge badge-success" style="font-size:11.5px;"><span class="status-dot" style="background:#10b981;"></span> Dual-Scan Hoàn Tất</span>
                <span class="badge badge-neutral" style="font-size:11.5px; font-weight:600;">Cần chuyển ~${diffToTransfer.toLocaleString()} thư</span>
            `;
        } else {
            badgeContainer.innerHTML = `
                <span class="badge badge-neutral">Nguồn: ${totalSrcMb} MB</span>
                <span class="badge badge-neutral">${totalSrcMsgs.toLocaleString()} thư</span>
            `;
        }
    }

    // Safe Banner
    const safeBannerText = document.getElementById("safeBannerText");
    if (safeBannerText) {
        if (destMsgs > 0) {
            safeBannerText.innerHTML = `
                Máy chủ đích đang có sẵn <strong>${destMsgs.toLocaleString()} thư (${destMb} MB)</strong>.
                Hệ thống cam kết giữ nguyên 100% dữ liệu này và tự động đối chiếu Message-ID để chỉ tải lên các email mới, tuyệt đối không gây trùng lặp.
            `;
        } else {
            safeBannerText.innerHTML = `
                ${recon.safe_mode_guarantee || "Hệ thống hoạt động theo nguyên tắc Append-Only: Giữ nguyên vẹn 100% dữ liệu đang có trên máy chủ đích, tự động quét Message-ID thực tế để không xóa đè và không nạp trùng."}
            `;
        }
    }

    // Quota & Capacity Simulation
    const quota = (data.dest && data.dest.quota) ? data.dest.quota : data.quota;
    const quotaFill = document.getElementById("quotaProgressFill");
    const quotaPct = document.getElementById("quotaPercentText");
    const quotaDetail = document.getElementById("quotaDetailText");
    const quotaStatusBadge = document.getElementById("quotaStatusBadge");
    const reconDestCapacity = document.getElementById("reconDestCapacity");

    const simNeedTransfer = document.getElementById("simNeedTransferSize");
    if (simNeedTransfer) simNeedTransfer.textContent = `${totalSrcMb} MB`;

    const estimatedTotal = (parseFloat(destMb) + parseFloat(totalSrcMb)).toFixed(2);
    const simEstimated = document.getElementById("simEstimatedTotalSize");
    if (simEstimated) simEstimated.textContent = `~${estimatedTotal} MB`;

    if (quota && quota.percent != null && quota.limit_mb > 0) {
        const currentPct = quota.percent;
        if (quotaFill) quotaFill.style.width = `${Math.min(currentPct, 100)}%`;
        if (quotaPct) quotaPct.textContent = `${currentPct}%`;

        const freeMb = Math.max(0, quota.limit_mb - quota.usage_mb);
        if (quotaDetail) quotaDetail.textContent = `Đã dùng ${quota.usage_mb.toLocaleString()} MB / Hạn mức ${quota.limit_mb.toLocaleString()} MB (Còn trống ${freeMb.toLocaleString()} MB)`;

        const neededMb = parseFloat(totalSrcMb);
        if (neededMb > freeMb) {
            if (quotaStatusBadge) {
                quotaStatusBadge.className = "badge badge-danger";
                quotaStatusBadge.textContent = "Cảnh báo thiếu dung lượng!";
            }
            if (reconDestCapacity) {
                reconDestCapacity.textContent = "Thiếu dung lượng";
                reconDestCapacity.style.color = "#f43f5e";
            }
        } else {
            if (quotaStatusBadge) {
                quotaStatusBadge.className = "badge badge-success";
                quotaStatusBadge.textContent = "Đủ sức chứa";
            }
            if (reconDestCapacity) {
                reconDestCapacity.textContent = "Đủ chứa";
                reconDestCapacity.style.color = "#34d399";
            }
        }
    } else {
        if (quotaFill) quotaFill.style.width = "0%";
        if (quotaPct) quotaPct.textContent = "N/A";
        if (quotaDetail) quotaDetail.textContent = "Máy chủ không trả về thông tin hạn mức IMAP QUOTA (Không giới hạn hoặc tùy thuộc hosting)";
        if (quotaStatusBadge) {
            quotaStatusBadge.className = "badge badge-neutral";
            quotaStatusBadge.textContent = "Chưa rõ quota";
        }
    }

    // Build Destination Folder Map for Cross-referencing
    const dstFolderMap = {};
    if (data.dest && data.dest.folders) {
        data.dest.folders.forEach(df => {
            dstFolderMap[df.name.toLowerCase()] = df;
            const stripped = df.name.replace(/^inbox\./i, "").toLowerCase();
            dstFolderMap[stripped] = df;
        });
    }

    // Render Matrix Folders Table
    window.currentInspectedFolders = folders;
    renderFolderMatrixRows(folders, dstFolderMap);

    // Setup folder filter
    const filterInput = document.getElementById("folderFilterInput");
    if (filterInput) {
        filterInput.value = "";
        filterInput.oninput = (e) => {
            const query = e.target.value.toLowerCase().trim();
            const filtered = (window.currentInspectedFolders || []).filter(f =>
                f.name.toLowerCase().includes(query) ||
                (f.role && f.role.toLowerCase().includes(query)) ||
                (f.destination_folder && f.destination_folder.toLowerCase().includes(query))
            );
            renderFolderMatrixRows(filtered, dstFolderMap);
        };
    }

    // Hook Start Migration button inside inspection card
    const btnInspectStart = document.getElementById("btnInspectStartMigration");
    if (btnInspectStart) {
        btnInspectStart.onclick = () => {
            document.getElementById("btnStartSingleMigrate")?.click();
        };
    }

    // Hook Close button
    const btnCloseInspect = document.getElementById("btnCloseInspection");
    if (btnCloseInspect) {
        btnCloseInspect.onclick = () => {
            container.style.display = "none";
        };
    }

    // Donut chart
    renderStorageDonutChart(data.source || data);
}

function renderFolderMatrixRows(foldersList, dstFolderMap) {
    const tbody = document.getElementById("foldersTableBody");
    if (!tbody) return;
    tbody.innerHTML = "";

    if (!foldersList || foldersList.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-dim); padding:24px;">Không tìm thấy thư mục phù hợp</td></tr>`;
        return;
    }

    foldersList.forEach(f => {
        const tr = document.createElement("tr");
        const role = f.role || "";
        const iconSvg = getFolderIcon(role, f.name);

        const folderMb = f.size_mb != null
            ? f.size_mb
            : (f.size_bytes ? (f.size_bytes / (1024 * 1024)).toFixed(2) : "0.00");

        const targetFolder = f.destination_folder || f.mapped_target || (f.role && f.role !== "CUSTOM" ? f.role : f.name);

        // Check if destination already has this folder
        const cleanTarget = targetFolder.toLowerCase().replace(/^inbox\./i, "");
        const dstMatch = dstFolderMap ? (dstFolderMap[targetFolder.toLowerCase()] || dstFolderMap[cleanTarget]) : null;

        let dstCountHtml = '<span style="color:var(--text-dim);">-</span>';
        let actionBadge = '';

        if (f.is_excluded) {
            actionBadge = '<span class="badge badge-neutral" style="font-size:11px;">Loại trừ</span>';
        } else if (dstMatch) {
            dstCountHtml = `<strong style="color:#34d399; font-family:'JetBrains Mono',monospace;">${(dstMatch.messages_count || 0).toLocaleString()}</strong>`;
            actionBadge = '<span class="badge badge-success" style="font-size:11px;"><span class="status-dot" style="background:#10b981;"></span> Hợp nhất</span>';
        } else {
            dstCountHtml = `<span style="color:var(--text-dim); font-family:'JetBrains Mono',monospace;">0</span>`;
            actionBadge = '<span class="badge badge-neutral" style="font-size:11px; color:#818cf8; border-color:rgba(99,102,241,0.3);"><span class="status-dot" style="background:#6366f1;"></span> Tạo mới</span>';
        }

        const roleBadge = role
            ? `<span class="badge badge-neutral" style="font-size:11px;">${escapeHtml(role)}</span>`
            : `<span style="color:var(--text-dim); font-size:11.5px;">Tiêu chuẩn</span>`;

        tr.innerHTML = `
            <td>
                <div style="display:flex; align-items:center; gap:8px;">
                    ${iconSvg}
                    <strong style="font-size:13px; color:var(--text-primary); word-break:break-all;">${escapeHtml(f.name)}</strong>
                </div>
            </td>
            <td>${roleBadge}</td>
            <td style="text-align: right; font-family: 'JetBrains Mono', monospace; font-size:12.5px;">${(f.messages_count || 0).toLocaleString()}</td>
            <td style="text-align: right; font-family: 'JetBrains Mono', monospace; font-size:12.5px;">${folderMb} MB</td>
            <td>
                <div style="display:flex; align-items:center; gap:6px;">
                    <span style="color:var(--text-dim); font-size:12px;">➔</span>
                    <span class="mono-font" style="font-size:12px; color:#60a5fa; font-weight:500;">${escapeHtml(targetFolder)}</span>
                </div>
            </td>
            <td style="text-align: right;">${dstCountHtml}</td>
            <td style="text-align: center;">${actionBadge}</td>
        `;
        tbody.appendChild(tr);
    });
}

function renderStorageDonutChart(summary) {
    const svg = document.getElementById("storageDonutSvg");
    const legend = document.getElementById("chartLegend");
    const centerSize = document.getElementById("donutCenterSize");
    if (!svg || !legend || !centerSize) return;

    const totalMb = summary.total_size_mb != null
        ? summary.total_size_mb
        : (summary.total_size_bytes ? (summary.total_size_bytes / (1024 * 1024)).toFixed(2) : "0.00");

    centerSize.textContent = `${totalMb} MB`;
    svg.innerHTML = "";
    legend.innerHTML = "";

    const activeFolders = (summary.folders || [])
        .filter(f => !f.is_excluded && (f.size_bytes > 0 || (f.size_mb && parseFloat(f.size_mb) > 0)))
        .sort((a, b) => (b.size_bytes || 0) - (a.size_bytes || 0));

    if (activeFolders.length === 0 || !summary.total_size_bytes) {
        svg.innerHTML = `<circle cx="80" cy="80" r="60" fill="none" stroke="var(--border)" stroke-width="16"/>`;
        legend.innerHTML = `<div class="legend-item"><span class="legend-color" style="background:var(--border);"></span><span>Hộp thư trống hoặc chưa có dữ liệu dung lượng</span></div>`;
        return;
    }

    const palette = ["#6366f1", "#3b82f6", "#10b981", "#f59e0b", "#06b6d4", "#ec4899"];
    const radius = 60;
    const circumference = 2 * Math.PI * radius;
    let accumulatedOffset = 0;

    activeFolders.slice(0, 5).forEach((f, idx) => {
        const color = palette[idx % palette.length];
        const fraction = summary.total_size_bytes > 0 ? (f.size_bytes / summary.total_size_bytes) : 0;
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
            <span style="font-size:11.5px;"><strong>${escapeHtml(f.name)}</strong>: ${pct}% (${f.size_mb || (f.size_bytes / 1048576).toFixed(1)} MB)</span>
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
                    <a href="${d.html_report}" target="_blank" class="btn btn-primary btn-sm">Xem Báo Cáo</a>
                    ${d.csv_report ? `<a href="${d.csv_report}" download class="btn btn-secondary btn-sm text-danger">Tải CSV Lỗi</a>` : ''}
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

    // Re-render preview when batch server inputs change
    ["batchSrcHost", "batchSrcPort", "batchDstHost", "batchDstPort"].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener("input", () => {
                if (parsedCsvData.length > 0) renderCsvPreview();
            });
        }
    });

    // Check all passwords in parallel
    const btnCheck = document.getElementById("btnCheckAllPasswords");
    if (btnCheck) {
        btnCheck.addEventListener("click", async () => {
            if (parsedCsvData.length === 0) {
                showToast("Vui lòng tải file CSV danh sách tài khoản trước!", "error");
                return;
            }

            const srcHost = document.getElementById("batchSrcHost") ? document.getElementById("batchSrcHost").value.trim() : "";
            const srcPort = document.getElementById("batchSrcPort") ? parseInt(document.getElementById("batchSrcPort").value) : 993;
            const srcSsl = document.getElementById("batchSrcSsl") ? document.getElementById("batchSrcSsl").value === "true" : true;

            if (!srcHost) {
                showToast("Vui lòng nhập Host máy chủ nguồn!", "error");
                return;
            }

            btnCheck.disabled = true;
            btnCheck.textContent = "Đang kiểm tra...";
            appendTerminalLog(`[BATCH CHECK] Kiểm tra xác thực cho ${parsedCsvData.length} tài khoản qua máy chủ ${srcHost}:${srcPort}...`, "info");

            try {
                const res = await fetch("/api/check-csv", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        source_host: srcHost,
                        source_port: srcPort,
                        source_ssl: srcSsl,
                        accounts: parsedCsvData,
                    }),
                });
                const results = await res.json();

                results.forEach((r, idx) => {
                    const cell = document.getElementById(`csvAuthCell_${idx}`);
                    if (cell) {
                        if (r.is_valid) {
                            cell.innerHTML = `<span class="badge badge-success" style="color:#10b981; font-weight:600;">HỢP LỆ (${r.latency_ms}ms)</span>`;
                        } else {
                            cell.innerHTML = `<span class="badge badge-danger" style="color:var(--danger-text); font-weight:600;" title="${r.provider_hint || r.error_reason}">THẤT BẠI</span>`;
                        }
                    }
                });

                showToast("Hoàn tất kiểm tra kết nối toàn bộ danh sách CSV!", "success");
                appendTerminalLog(`[BATCH CHECK DONE] Đã kiểm tra xong toàn bộ danh sách CSV`, "success");
            } catch (e) {
                showToast(`Lỗi kiểm tra CSV: ${e.message}`, "error");
            } finally {
                btnCheck.disabled = false;
                btnCheck.textContent = "Kiểm Tra Kết Nối";
            }
        });
    }

    // Start Batch Migration
    const btnBatch = document.getElementById("btnStartBatchMigrate");
    if (btnBatch) {
        btnBatch.addEventListener("click", async () => {
            if (parsedCsvData.length === 0) {
                showToast("Chưa có danh sách tài khoản CSV!", "error");
                return;
            }

            const srcHost = document.getElementById("batchSrcHost") ? document.getElementById("batchSrcHost").value.trim() : "";
            const srcPort = document.getElementById("batchSrcPort") ? parseInt(document.getElementById("batchSrcPort").value) : 993;
            const srcSsl = document.getElementById("batchSrcSsl") ? document.getElementById("batchSrcSsl").value === "true" : true;

            const dstHost = document.getElementById("batchDstHost") ? document.getElementById("batchDstHost").value.trim() : "";
            const dstPort = document.getElementById("batchDstPort") ? parseInt(document.getElementById("batchDstPort").value) : 993;
            const dstSsl = document.getElementById("batchDstSsl") ? document.getElementById("batchDstSsl").value === "true" : true;

            if (!srcHost) {
                showToast("Vui lòng nhập Host máy chủ nguồn!", "error");
                return;
            }
            if (!dstHost) {
                showToast("Vui lòng nhập Host máy chủ đích!", "error");
                return;
            }

            btnBatch.disabled = true;
            btnBatch.textContent = "Đang khởi tạo...";

            const forceRemigrate = document.getElementById("batchForceRemigrate") ? document.getElementById("batchForceRemigrate").checked : true;
            const sanitizeAccents = document.getElementById("batchSanitizeAccents") ? document.getElementById("batchSanitizeAccents").checked : false;

            try {
                const res = await fetch("/api/migrate/batch", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        source_host: srcHost,
                        source_port: srcPort,
                        source_ssl: srcSsl,
                        dest_host: dstHost,
                        dest_port: dstPort,
                        dest_ssl: dstSsl,
                        accounts: parsedCsvData,
                        sanitize_accents: sanitizeAccents,
                        batch_delay_ms: 50,
                        force_remigrate: forceRemigrate,
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
                btnBatch.textContent = "Bắt Đầu Di Chuyển Hàng Loạt";
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
    if (lines.length < 1) {
        showToast("File CSV rỗng hoặc không có dữ liệu!", "error");
        return;
    }

    const rawHeaders = lines[0].split(",").map(h => h.trim().toLowerCase().replace(/^["']|["']$/g, ""));
    parsedCsvData = [];

    // Detect if first line is a header
    const isHeaderLine = rawHeaders.some(h =>
        h.includes("user") || h.includes("email") || h.includes("pass") || h.includes("source") || h.includes("dest")
    );

    const startIndex = isHeaderLine ? 1 : 0;

    for (let i = startIndex; i < lines.length; i++) {
        const cols = lines[i].split(",").map(c => c.trim().replace(/^["']|["']$/g, ""));
        if (cols.length >= 4) {
            let rowObj = {};
            if (isHeaderLine && rawHeaders.includes("source_user") && rawHeaders.includes("dest_user")) {
                rawHeaders.forEach((h, idx) => {
                    rowObj[h] = cols[idx] || "";
                });
            } else if (isHeaderLine && rawHeaders.includes("source_host") && cols.length >= 10) {
                rawHeaders.forEach((h, idx) => {
                    rowObj[h] = cols[idx] || "";
                });
            } else {
                rowObj = {
                    source_user: cols[0],
                    source_password: cols[1],
                    dest_user: cols[2],
                    dest_password: cols[3],
                };
            }
            if (rowObj.source_user && rowObj.dest_user) {
                parsedCsvData.push(rowObj);
            }
        }
    }

    if (parsedCsvData.length === 0) {
        showToast("Không tìm thấy dòng tài khoản hợp lệ trong file CSV! (Cần 4 cột: user nguồn, pass nguồn, user đích, pass đích)", "error");
        return;
    }

    renderCsvPreview();
    showToast(`Đã nạp ${parsedCsvData.length} tài khoản từ file CSV!`, "success");
    appendTerminalLog(`[CSV LOADED] Đã nạp thành công ${parsedCsvData.length} tài khoản từ file CSV`, "info");
}

function renderCsvPreview() {
    const section = document.getElementById("csvPreviewSection");
    if (!section) return;
    section.style.display = "block";
    document.getElementById("csvTotalCount").textContent = parsedCsvData.length;

    const srcHost = document.getElementById("batchSrcHost") ? document.getElementById("batchSrcHost").value.trim() : "imap.gmail.com";
    const srcPort = document.getElementById("batchSrcPort") ? document.getElementById("batchSrcPort").value.trim() : "993";
    const dstHost = document.getElementById("batchDstHost") ? document.getElementById("batchDstHost").value.trim() : "mail.yourdomain.com";
    const dstPort = document.getElementById("batchDstPort") ? document.getElementById("batchDstPort").value.trim() : "993";

    const tbody = document.getElementById("csvTableBody");
    tbody.innerHTML = "";

    parsedCsvData.forEach((row, idx) => {
        const displaySrc = `${row.source_host || srcHost}:${row.source_port || srcPort}`;
        const displayDst = `${row.dest_host || dstHost}:${row.dest_port || dstPort}`;

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td style="text-align: center;">${idx + 1}</td>
            <td><strong>${row.source_user || ''}</strong></td>
            <td><strong>${row.dest_user || ''}</strong></td>
            <td><code>${displaySrc}</code></td>
            <td><code>${displayDst}</code></td>
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
                        <a href="${t.html_report}" target="_blank" class="btn btn-primary btn-sm">Xem Báo Cáo</a>
                        ${t.csv_report ? `<a href="/api/reports/download/${t.csv_report}" download class="btn btn-secondary btn-sm text-danger">Tải CSV Lỗi</a>` : ''}
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

            let statusBadge = `<span class="badge badge-neutral">${s.status}</span>`;
            if (s.status === "COMPLETED") statusBadge = `<span class="status-badge status-success">COMPLETED</span>`;
            else if (s.status === "FAILED") statusBadge = `<span class="status-badge status-failed">FAILED</span>`;
            else if (s.status === "RUNNING") statusBadge = `<span class="status-badge status-skipped">RUNNING</span>`;

            tr.innerHTML = `
                <td><strong>#${s.id}</strong></td>
                <td><strong>${s.source_account}</strong> ➔ <strong>${s.dest_account}</strong></td>
                <td style="text-align: center;">${statusBadge}</td>
                <td style="text-align: right; font-family: 'JetBrains Mono', monospace; font-weight:600; color:#34d399;">${s.migrated_messages}</td>
                <td style="text-align: right; font-family: 'JetBrains Mono', monospace; color: #fbbf24;">${s.skipped_messages}</td>
                <td style="text-align: right; font-family: 'JetBrains Mono', monospace; color: var(--danger-text);">${s.failed_messages}</td>
                <td style="font-size: 11.5px; color: var(--text-dim);">${s.started_at ? s.started_at.replace('T', ' ').substring(0, 19) : '-'}</td>
                <td style="text-align: center;">
                    <div style="display:inline-flex; gap:6px;">
                        <button class="btn btn-secondary btn-sm" onclick="showSessionDetail(${JSON.stringify(s).replace(/"/g, '&quot;')})">Chi tiết</button>
                        <button class="btn btn-secondary btn-sm" onclick="openReports(${s.id})">Báo cáo</button>
                        ${s.failed_messages > 0 ? `<button class="btn btn-secondary btn-sm text-danger" onclick="retrySessionPrompt(${s.id})">Thử lại</button>` : ''}
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--danger-text); padding: 20px;">Lỗi tải dữ liệu: ${e.message}</td></tr>`;
    }
}

function initSessionsTab() {
    const btn = document.getElementById("btnRefreshSessions");
    if (btn) {
        btn.addEventListener("click", loadSessions);
    }
}

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

// --------------------------------------------------------------------------
// MODAL & POPUP CONTROLLER
// --------------------------------------------------------------------------
function initModals() {
    const confirmModal = document.getElementById("confirmMigrateModal");
    const btnDismiss = document.getElementById("btnDismissModal");
    const btnCancel = document.getElementById("btnCancelModalAction");
    const btnConfirm = document.getElementById("btnConfirmStartAction");

    const closeConfirm = () => {
        if (confirmModal) confirmModal.classList.remove("open");
    };

    if (btnDismiss) btnDismiss.addEventListener("click", closeConfirm);
    if (btnCancel) btnCancel.addEventListener("click", closeConfirm);
    if (confirmModal) {
        confirmModal.addEventListener("click", (e) => {
            if (e.target === confirmModal) closeConfirm();
        });
    }

    if (btnConfirm) {
        btnConfirm.addEventListener("click", () => {
            closeConfirm();
            if (window.pendingMigratePayload) {
                executeSingleMigrate(window.pendingMigratePayload);
            }
        });
    }

    // Session Detail Modal
    const sessionModal = document.getElementById("sessionDetailModal");
    const btnCloseSession = document.getElementById("btnCloseSessionModal");
    const btnCloseSessionFooter = document.getElementById("btnCloseSessionModalFooter");

    const closeSession = () => {
        if (sessionModal) sessionModal.classList.remove("open");
    };
    if (btnCloseSession) btnCloseSession.addEventListener("click", closeSession);
    if (btnCloseSessionFooter) btnCloseSessionFooter.addEventListener("click", closeSession);
    if (sessionModal) {
        sessionModal.addEventListener("click", (e) => {
            if (e.target === sessionModal) closeSession();
        });
    }

    // Escape key to close modals
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeConfirm();
            closeSession();
        }
    });
}

function showSessionDetail(s) {
    const modal = document.getElementById("sessionDetailModal");
    const title = document.getElementById("sessionModalTitle");
    const body = document.getElementById("sessionModalBody");
    if (!modal || !body) return;

    if (title) title.textContent = `Chi Tiết Phiên #${s.id}`;

    let statusBadge = `<span class="badge badge-neutral">${s.status}</span>`;
    if (s.status === "COMPLETED") statusBadge = `<span class="status-badge status-success">COMPLETED</span>`;
    else if (s.status === "FAILED") statusBadge = `<span class="status-badge status-failed">FAILED</span>`;
    else if (s.status === "RUNNING") statusBadge = `<span class="status-badge status-skipped">RUNNING</span>`;

    body.innerHTML = `
        <div class="modal-summary-box">
            <div class="modal-summary-row">
                <span>Tài khoản:</span>
                <strong>${s.source_account} ➔ ${s.dest_account}</strong>
            </div>
            <div class="modal-summary-row">
                <span>Trạng thái:</span>
                <div>${statusBadge}</div>
            </div>
            <div class="modal-summary-row">
                <span>Bắt đầu:</span>
                <strong>${s.started_at ? s.started_at.replace('T', ' ').substring(0, 19) : '-'}</strong>
            </div>
        </div>

        <div class="stats-grid" style="grid-template-columns: repeat(3, 1fr);">
            <div class="stat-mini text-center">
                <span class="stat-mini-label">THÀNH CÔNG</span>
                <span class="stat-mini-value" style="color:#34d399;">${s.migrated_messages}</span>
            </div>
            <div class="stat-mini text-center">
                <span class="stat-mini-label">BỎ QUA</span>
                <span class="stat-mini-value" style="color:#fbbf24;">${s.skipped_messages}</span>
            </div>
            <div class="stat-mini text-center">
                <span class="stat-mini-label">LỖI</span>
                <span class="stat-mini-value" style="color:#fb7185;">${s.failed_messages}</span>
            </div>
        </div>

        <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:10px;">
            <a href="/api/reports/view/${s.id}" target="_blank" class="btn btn-primary btn-sm">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" x2="21" y1="14" y2="3"/>
                </svg>
                <span>Xem Báo Cáo</span>
            </a>
            ${s.failed_messages > 0 ? `<button class="btn btn-secondary btn-sm text-danger" onclick="retrySessionPrompt(${s.id})">Thử lại</button>` : ''}
        </div>
    `;

    modal.classList.add("open");
}

// --------------------------------------------------------------------------
// PASSWORD VISIBILITY TOGGLE HELPER
// --------------------------------------------------------------------------
function setupPasswordToggles() {
    [
        { inputId: "srcPass", btnId: "toggleSrcPass" },
        { inputId: "dstPass", btnId: "toggleDstPass" },
        { inputId: "singleAuthPass", btnId: "toggleSingleAuthPass" }
    ].forEach(({ inputId, btnId }) => {
        const input = document.getElementById(inputId);
        const btn = document.getElementById(btnId);
        if (!input || !btn) return;
        btn.addEventListener("click", () => {
            const isPassword = input.type === "password";
            input.type = isPassword ? "text" : "password";
            btn.innerHTML = isPassword
                ? `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="m9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/>
                   </svg>`
                : `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>
                   </svg>`;
        });
    });
}

// --------------------------------------------------------------------------
// HISTORY SEARCH & FILTER HELPER
// --------------------------------------------------------------------------
function setupHistorySearch() {
    const input = document.getElementById("historySearchInput");
    if (!input) return;
    input.addEventListener("input", (e) => {
        const query = e.target.value.toLowerCase().trim();
        const rows = document.querySelectorAll("#sessionsTableBody tr");
        rows.forEach(r => {
            const text = r.textContent.toLowerCase();
            r.style.display = text.includes(query) ? "" : "none";
        });
    });
}

// --------------------------------------------------------------------------
// STANDALONE AUTH CHECKER (SINGLE & BATCH CSV)
// --------------------------------------------------------------------------
let parsedAuthCsvData = [];

function initAuthCheckTab() {
    // 1. Single Auth Check
    const btnTestSingle = document.getElementById("btnTestSingleAuth");
    if (btnTestSingle) {
        btnTestSingle.addEventListener("click", async () => {
            const host = document.getElementById("singleAuthHost")?.value.trim();
            const port = parseInt(document.getElementById("singleAuthPort")?.value) || 993;
            const ssl = document.getElementById("singleAuthSsl")?.value === "true";
            const user = document.getElementById("singleAuthUser")?.value.trim();
            const pass = document.getElementById("singleAuthPass")?.value;
            const resBox = document.getElementById("singleAuthResultBox");

            if (!host || !user || !pass) {
                showToast("Vui lòng nhập đầy đủ Host, Email và Mật khẩu", "error");
                return;
            }

            btnTestSingle.disabled = true;
            const originalHtml = btnTestSingle.innerHTML;
            btnTestSingle.innerHTML = `
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 0.8s linear infinite;">
                    <circle cx="12" cy="12" r="10" stroke-opacity="0.25"/>
                    <path d="M12 2a10 10 0 0 1 10 10"/>
                </svg>
                <span>Đang kiểm tra kết nối...</span>
            `;
            if (resBox) resBox.style.display = "none";

            const t0 = performance.now();
            try {
                const resp = await fetch("/api/check-password", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ host, port, ssl, username: user, password: pass })
                });
                const elapsed = Math.round(performance.now() - t0);
                const data = await resp.json();

                if (resBox) {
                    resBox.style.display = "block";
                    if (data.is_valid) {
                        resBox.innerHTML = `
                            <div style="padding: 14px 18px; border-radius: 10px; background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.3); display: flex; align-items: center; justify-content: space-between; gap: 12px;">
                                <div style="display: flex; align-items: center; gap: 10px;">
                                    <div style="width: 28px; height: 28px; border-radius: 50%; background: #10b981; color: #fff; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-weight: bold;">✓</div>
                                    <div>
                                        <strong style="color: #34d399; font-size: 13.5px; display: block;">Mật khẩu chính xác & Xác thực thành công!</strong>
                                        <span style="font-size: 12px; color: var(--text-dim);">Kết nối an toàn đến <code>${escapeHtml(data.host)}</code></span>
                                    </div>
                                </div>
                                <span class="badge badge-success" style="font-size: 11.5px; font-weight: 600;">${data.latency_ms || elapsed} ms</span>
                            </div>
                        `;
                        showToast("Xác thực tài khoản thành công!", "success");
                    } else {
                        resBox.innerHTML = `
                            <div style="padding: 14px 18px; border-radius: 10px; background: rgba(244, 63, 94, 0.12); border: 1px solid rgba(244, 63, 94, 0.3); display: flex; flex-direction: column; gap: 6px;">
                                <div style="display: flex; align-items: center; justify-content: space-between;">
                                    <div style="display: flex; align-items: center; gap: 8px;">
                                        <span style="color: #fb7185; font-size: 16px; font-weight: bold;">✕</span>
                                        <strong style="color: #fb7185; font-size: 13.5px;">Xác thực thất bại</strong>
                                    </div>
                                    <span class="badge badge-danger">${elapsed} ms</span>
                                </div>
                                <p style="font-size: 12.5px; color: var(--text-primary); margin: 0;">${escapeHtml(data.error_reason || "Mật khẩu không đúng hoặc máy chủ từ chối kết nối.")}</p>
                                ${data.provider_hint ? `<div style="font-size: 12px; color: var(--text-dim); margin-top: 4px; padding-top: 4px; border-top: 1px dashed rgba(244, 63, 94, 0.2);">💡 Gợi ý: ${escapeHtml(data.provider_hint)}</div>` : ''}
                            </div>
                        `;
                        showToast("Xác thực thất bại! Vui lòng kiểm tra lại thông tin.", "error");
                    }
                }
            } catch (err) {
                if (resBox) {
                    resBox.style.display = "block";
                    resBox.innerHTML = `
                        <div style="padding: 14px 18px; border-radius: 10px; background: rgba(244, 63, 94, 0.12); border: 1px solid rgba(244, 63, 94, 0.3);">
                            <strong style="color: #fb7185; font-size: 13px;">Lỗi kết nối máy chủ</strong>
                            <p style="font-size: 12px; color: var(--text-dim); margin: 4px 0 0 0;">${escapeHtml(err.message)}</p>
                        </div>
                    `;
                }
                showToast("Lỗi kết nối máy chủ: " + err.message, "error");
            } finally {
                btnTestSingle.disabled = false;
                btnTestSingle.innerHTML = originalHtml;
            }
        });
    }

    // 2. Batch CSV Drop Zone
    const authDropZone = document.getElementById("authDropZone");
    const authFileInput = document.getElementById("authCsvFileInput");

    if (authDropZone && authFileInput) {
        ["dragenter", "dragover"].forEach(name => {
            authDropZone.addEventListener(name, (e) => {
                e.preventDefault();
                e.stopPropagation();
                authDropZone.classList.add("dragover");
            });
        });
        ["dragleave", "drop"].forEach(name => {
            authDropZone.addEventListener(name, (e) => {
                e.preventDefault();
                e.stopPropagation();
                authDropZone.classList.remove("dragover");
            });
        });

        authDropZone.addEventListener("drop", (e) => {
            const files = e.dataTransfer.files;
            if (files.length > 0 && files[0].name.toLowerCase().endsWith(".csv")) {
                parseAuthCsvFile(files[0]);
            } else {
                showToast("Vui lòng tải lên file định dạng CSV (.csv)", "error");
            }
        });

        authFileInput.addEventListener("change", (e) => {
            if (e.target.files.length > 0) {
                parseAuthCsvFile(e.target.files[0]);
            }
        });
    }

    // 3. Run Batch Check
    const btnRunBatch = document.getElementById("btnRunBatchAuthCheck");
    if (btnRunBatch) {
        btnRunBatch.addEventListener("click", runBatchAuthCheck);
    }
}

function parseAuthCsvFile(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
        const text = e.target.result;
        const lines = text.split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0);
        if (lines.length === 0) {
            showToast("File CSV rỗng", "error");
            return;
        }

        parsedAuthCsvData = [];
        let startIndex = 0;
        const firstLineLower = lines[0].toLowerCase();
        if (firstLineLower.includes("email") || firstLineLower.includes("user") || firstLineLower.includes("source")) {
            startIndex = 1;
        }

        for (let i = startIndex; i < lines.length; i++) {
            const cols = lines[i].split(",").map(c => c.trim().replace(/^["']|["']$/g, ''));
            if (cols.length >= 2 && cols[0]) {
                parsedAuthCsvData.push({
                    email: cols[0],
                    password: cols[1] || "",
                    status: "pending",
                    latency_ms: null,
                    message: "Chờ kiểm tra"
                });
            }
        }

        if (parsedAuthCsvData.length === 0) {
            showToast("Không tìm thấy dữ liệu tài khoản hợp lệ trong CSV", "error");
            return;
        }

        const actionsContainer = document.getElementById("authCheckActions");
        if (actionsContainer) actionsContainer.style.display = "block";
        const totalCountEl = document.getElementById("authCheckTotalCount");
        if (totalCountEl) totalCountEl.textContent = parsedAuthCsvData.length;
        const statsEl = document.getElementById("authCheckStatsBadge");
        if (statsEl) statsEl.innerHTML = "";

        renderAuthCsvTable();
        showToast(`Đã nạp ${parsedAuthCsvData.length} tài khoản từ file CSV`, "success");
    };
    reader.readAsText(file);
}

function renderAuthCsvTable() {
    const tbody = document.getElementById("authCheckTableBody");
    if (!tbody) return;

    tbody.innerHTML = parsedAuthCsvData.map((row, idx) => {
        let statusBadge = '<span class="badge badge-neutral">Chờ kiểm tra</span>';
        if (row.status === "testing") {
            statusBadge = '<span class="badge badge-neutral"><span class="status-dot"></span> Đang thử...</span>';
        } else if (row.status === "success") {
            statusBadge = '<span class="badge badge-success"><span class="status-dot" style="background:#10b981;"></span> Hợp lệ</span>';
        } else if (row.status === "failed") {
            statusBadge = '<span class="badge badge-danger"><span class="status-dot" style="background:#f43f5e;"></span> Thất bại</span>';
        }

        const latencyText = row.latency_ms !== null ? `<span class="mono-font" style="font-size:12px;">${row.latency_ms} ms</span>` : '-';
        return `
            <tr id="authCheckRow_${idx}">
                <td style="text-align: center; color: var(--text-dim); font-size:12px;">${idx + 1}</td>
                <td style="font-weight: 500;">${escapeHtml(row.email)}</td>
                <td style="text-align: center;">${latencyText}</td>
                <td style="text-align: center;">${statusBadge}</td>
                <td style="font-size: 12px; color: ${row.status === 'failed' ? '#fb7185' : 'var(--text-muted)'};">${escapeHtml(row.message || '')}</td>
            </tr>
        `;
    }).join("");
}

async function runBatchAuthCheck() {
    if (!parsedAuthCsvData || parsedAuthCsvData.length === 0) {
        showToast("Chưa có danh sách tài khoản để kiểm tra", "error");
        return;
    }
    const host = document.getElementById("batchAuthHost")?.value.trim();
    const port = parseInt(document.getElementById("batchAuthPort")?.value) || 993;
    const ssl = document.getElementById("batchAuthSsl")?.value === "true";

    if (!host) {
        showToast("Vui lòng nhập Host máy chủ IMAP kiểm tra", "error");
        return;
    }

    const btn = document.getElementById("btnRunBatchAuthCheck");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 0.8s linear infinite;">
                <circle cx="12" cy="12" r="10" stroke-opacity="0.25"/>
                <path d="M12 2a10 10 0 0 1 10 10"/>
            </svg>
            <span>Đang kiểm tra...</span>
        `;
    }

    parsedAuthCsvData.forEach(r => {
        r.status = "testing";
        r.message = "Đang kết nối...";
    });
    renderAuthCsvTable();

    try {
        const payload = {
            source_host: host,
            source_port: port,
            source_ssl: ssl,
            accounts: parsedAuthCsvData.map(r => ({
                email: r.email,
                password: r.password
            }))
        };
        const resp = await fetch("/api/check-csv", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }
        const results = await resp.json();
        let successCount = 0;
        let failCount = 0;

        results.forEach((res, idx) => {
            if (idx < parsedAuthCsvData.length) {
                parsedAuthCsvData[idx].status = res.is_valid ? "success" : "failed";
                parsedAuthCsvData[idx].latency_ms = res.latency_ms;
                parsedAuthCsvData[idx].message = res.is_valid
                    ? "Xác thực thành công"
                    : (res.error_reason || "Mật khẩu không hợp lệ") + (res.provider_hint ? ` (${res.provider_hint})` : "");
                if (res.is_valid) successCount++; else failCount++;
            }
        });

        renderAuthCsvTable();
        const statsEl = document.getElementById("authCheckStatsBadge");
        if (statsEl) {
            statsEl.innerHTML = `
                <span class="badge badge-success" style="margin-left:8px;">${successCount} hợp lệ</span>
                ${failCount > 0 ? `<span class="badge badge-danger" style="margin-left:4px;">${failCount} lỗi</span>` : ''}
            `;
        }
        showToast(`Hoàn tất kiểm tra: ${successCount} hợp lệ, ${failCount} thất bại`, successCount > 0 ? "success" : "error");
    } catch (err) {
        showToast("Lỗi kiểm tra hàng loạt: " + err.message, "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                <span>Kiểm Tra Song Song</span>
            `;
        }
    }
}

// --------------------------------------------------------------------------
// SYSTEM SETTINGS TAB LOGIC
// --------------------------------------------------------------------------
function initSettingsTab() {
    // 1. Load saved settings from localStorage
    const savedWorkers = localStorage.getItem("setting_workers");
    if (savedWorkers && document.getElementById("settingWorkers")) {
        document.getElementById("settingWorkers").value = savedWorkers;
    }
    const savedDelay = localStorage.getItem("setting_batch_delay");
    if (savedDelay && document.getElementById("settingBatchDelay")) {
        document.getElementById("settingBatchDelay").value = savedDelay;
    }
    const savedBatchSize = localStorage.getItem("setting_batch_size");
    if (savedBatchSize && document.getElementById("settingBatchSize")) {
        document.getElementById("settingBatchSize").value = savedBatchSize;
    }
    const savedMaxMsgSize = localStorage.getItem("setting_max_msg_size");
    if (savedMaxMsgSize && document.getElementById("settingMaxMsgSize")) {
        document.getElementById("settingMaxMsgSize").value = savedMaxMsgSize;
    }

    const savedSanitizeAccents = localStorage.getItem("setting_sanitize_accents");
    if (savedSanitizeAccents !== null && document.getElementById("settingSanitizeAccents")) {
        document.getElementById("settingSanitizeAccents").checked = savedSanitizeAccents === "true";
    }
    const savedAutoInbox = localStorage.getItem("setting_auto_inbox");
    if (savedAutoInbox !== null && document.getElementById("settingAutoInboxPrefix")) {
        document.getElementById("settingAutoInboxPrefix").checked = savedAutoInbox === "true";
    }
    const savedTimeout = localStorage.getItem("setting_socket_timeout");
    if (savedTimeout && document.getElementById("settingSocketTimeout")) {
        document.getElementById("settingSocketTimeout").value = savedTimeout;
    }
    const savedMaxErrors = localStorage.getItem("setting_max_errors");
    if (savedMaxErrors && document.getElementById("settingMaxErrors")) {
        document.getElementById("settingMaxErrors").value = savedMaxErrors;
    }

    const savedSkipTrash = localStorage.getItem("setting_skip_trash");
    if (savedSkipTrash !== null && document.getElementById("settingSkipTrashSpam")) {
        document.getElementById("settingSkipTrashSpam").checked = savedSkipTrash === "true";
    }
    const savedDeduplication = localStorage.getItem("setting_deduplication");
    if (savedDeduplication !== null && document.getElementById("settingDeduplication")) {
        document.getElementById("settingDeduplication").checked = savedDeduplication === "true";
    }

    // 2. Save Settings Handler
    const btnSave = document.getElementById("btnSaveSettings");
    if (btnSave) {
        btnSave.addEventListener("click", async () => {
            const workers = document.getElementById("settingWorkers")?.value;
            const delay = document.getElementById("settingBatchDelay")?.value;
            const batchSize = document.getElementById("settingBatchSize")?.value;
            const maxMsgSize = document.getElementById("settingMaxMsgSize")?.value;
            const timeout = document.getElementById("settingSocketTimeout")?.value;
            const maxErrors = document.getElementById("settingMaxErrors")?.value;
            const sanitizeAccents = document.getElementById("settingSanitizeAccents")?.checked;
            const autoInbox = document.getElementById("settingAutoInboxPrefix")?.checked;
            const skipTrash = document.getElementById("settingSkipTrashSpam")?.checked;
            const deduplication = document.getElementById("settingDeduplication")?.checked;

            if (workers) localStorage.setItem("setting_workers", workers);
            if (delay) localStorage.setItem("setting_batch_delay", delay);
            if (batchSize) localStorage.setItem("setting_batch_size", batchSize);
            if (maxMsgSize) localStorage.setItem("setting_max_msg_size", maxMsgSize);
            if (timeout) localStorage.setItem("setting_socket_timeout", timeout);
            if (maxErrors) localStorage.setItem("setting_max_errors", maxErrors);
            localStorage.setItem("setting_sanitize_accents", sanitizeAccents);
            localStorage.setItem("setting_auto_inbox", autoInbox);
            localStorage.setItem("setting_skip_trash", skipTrash);
            localStorage.setItem("setting_deduplication", deduplication);

            // Check if admin password change was requested
            const newPass = document.getElementById("settingAdminNewPass")?.value.trim();
            const confirmPass = document.getElementById("settingAdminConfirmPass")?.value.trim();
            if (newPass) {
                if (newPass !== confirmPass) {
                    showToast("Mật khẩu mới và mật khẩu xác nhận không khớp!", "error");
                    return;
                }
                if (newPass.length < 4) {
                    showToast("Mật khẩu mới phải có tối thiểu 4 ký tự!", "error");
                    return;
                }
                try {
                    const resp = await fetch("/api/admin/change-password", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ new_password: newPass })
                    });
                    const res = await resp.json();
                    if (!resp.ok) throw new Error(res.detail || "Không thể đổi mật khẩu");
                    document.getElementById("settingAdminNewPass").value = "";
                    document.getElementById("settingAdminConfirmPass").value = "";
                    showToast(res.message || "Đã đổi mật khẩu admin thành công!", "success");
                } catch (e) {
                    showToast("Lỗi cập nhật mật khẩu: " + e.message, "error");
                    return;
                }
            }

            showToast("Đã lưu toàn bộ cài đặt hệ thống thành công!", "success");
        });
    }

    // 3. Reset Settings Handler
    const btnReset = document.getElementById("btnResetSettings");
    if (btnReset) {
        btnReset.addEventListener("click", () => {
            if (!confirm("Bạn có chắc chắn muốn đặt lại tất cả cài đặt về mặc định của hệ thống?")) return;
            localStorage.removeItem("setting_workers");
            localStorage.removeItem("setting_batch_delay");
            localStorage.removeItem("setting_batch_size");
            localStorage.removeItem("setting_max_msg_size");
            localStorage.removeItem("setting_socket_timeout");
            localStorage.removeItem("setting_max_errors");
            localStorage.removeItem("setting_sanitize_accents");
            localStorage.removeItem("setting_auto_inbox");
            localStorage.removeItem("setting_skip_trash");
            localStorage.removeItem("setting_deduplication");

            if (document.getElementById("settingWorkers")) document.getElementById("settingWorkers").value = "2";
            if (document.getElementById("settingBatchDelay")) document.getElementById("settingBatchDelay").value = "50";
            if (document.getElementById("settingBatchSize")) document.getElementById("settingBatchSize").value = "50";
            if (document.getElementById("settingMaxMsgSize")) document.getElementById("settingMaxMsgSize").value = "50";
            if (document.getElementById("settingSocketTimeout")) document.getElementById("settingSocketTimeout").value = "60";
            if (document.getElementById("settingMaxErrors")) document.getElementById("settingMaxErrors").value = "50";
            if (document.getElementById("settingSanitizeAccents")) document.getElementById("settingSanitizeAccents").checked = false;
            if (document.getElementById("settingAutoInboxPrefix")) document.getElementById("settingAutoInboxPrefix").checked = true;
            if (document.getElementById("settingSkipTrashSpam")) document.getElementById("settingSkipTrashSpam").checked = true;
            if (document.getElementById("settingDeduplication")) document.getElementById("settingDeduplication").checked = true;

            showToast("Đã khôi phục cài đặt mặc định!", "info");
        });
    }

    // 4. Clear Cache Button
    const btnClearCache = document.getElementById("btnClearAllCacheBtn");
    if (btnClearCache) {
        btnClearCache.addEventListener("click", async () => {
            btnClearCache.disabled = true;
            try {
                const resp = await fetch("/api/admin/clear-cache", { method: "POST" });
                const res = await resp.json();
                showToast(res.message || "Đã làm sạch bộ nhớ đệm!", "success");
            } catch (err) {
                showToast("Lỗi làm sạch bộ nhớ đệm", "error");
            } finally {
                btnClearCache.disabled = false;
            }
        });
    }
}

