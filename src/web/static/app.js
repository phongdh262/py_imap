document.addEventListener("DOMContentLoaded", () => {
    initThemeSwitcher();
    initTabs();
    initProviderChips();
    initSingleAccountTab();
    initDropZone();
    initAuthCheckTab();
    initScanStorageTab();
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

    const setSslState = (isSsl) => {
        if (sslSelect.tagName === "SELECT") {
            if (sslSelect.querySelector('option[value="ssl"]')) {
                sslSelect.value = isSsl ? "ssl" : "none";
            } else {
                sslSelect.value = isSsl ? "true" : "false";
            }
        } else if (sslSelect.type === "checkbox") {
            sslSelect.checked = isSsl;
        }
    };

    if (provider === "gmail") {
        hostInput.value = "imap.gmail.com";
        portInput.value = 993;
        setSslState(true);
        if (hintText) hintText.textContent = "Lưu ý Gmail: Bật 2FA và tạo Mật khẩu ứng dụng (16 ký tự)";
    } else if (provider === "outlook") {
        hostInput.value = "outlook.office365.com";
        portInput.value = 993;
        setSslState(true);
        if (hintText) hintText.textContent = "Lưu ý Microsoft 365: Dùng App Password hoặc bật IMAP trong Exchange";
    } else if (provider === "yandex") {
        hostInput.value = "imap.yandex.com";
        portInput.value = 993;
        setSslState(true);
        if (hintText) hintText.textContent = "Lưu ý Yandex: Tạo Mật khẩu ứng dụng tại Yandex ID > Security";
    } else if (provider === "cpanel") {
        let domain = "yourdomain.com";
        if (userInput && userInput.includes("@")) {
            domain = userInput.split("@")[1];
        }
        hostInput.value = `mail.${domain}`;
        portInput.value = 993;
        setSslState(true);
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
let currentTaskFilter = "all";
let taskSearchTerm = "";
let cachedActiveTasks = [];

function formatSeconds(sec) {
    if (!sec || isNaN(sec) || sec < 0) return "00:00";
    const totalSec = Math.floor(sec);
    const hours = Math.floor(totalSec / 3600);
    const minutes = Math.floor((totalSec % 3600) / 60);
    const seconds = totalSec % 60;
    if (hours > 0) {
        return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
    }
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function copyTaskId(id) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(id).then(() => {
            showToast(`Đã sao chép Task ID: ${id}`, "info");
        });
    } else {
        showToast(`Task ID: ${id}`, "info");
    }
}

function viewTaskLogs(taskId, source) {
    const drawer = document.getElementById("logDrawer");
    if (drawer && drawer.classList.contains("collapsed")) {
        toggleDrawer();
    }
    appendTerminalLog(`--- Đang theo dõi tiến trình [${taskId}] ${source || ''} ---`, "info");
    const body = document.getElementById("drawerConsoleBody");
    if (body) body.scrollTop = body.scrollHeight;
}

async function stopActiveTask(taskId, source) {
    const confirmed = confirm(`Xác nhận dừng tiến trình di chuyển cho ${source || taskId}?\n\nLưu ý: Thư đã chuyển sang máy chủ đích sẽ được giữ nguyên vẹn an toàn 100%.`);
    if (!confirmed) return;

    try {
        const res = await fetch(`/api/tasks/stop/${encodeURIComponent(taskId)}`, { method: "POST" });
        if (res.ok) {
            showToast(`Đã gửi lệnh dừng tiến trình ${taskId}`, "warning");
            appendTerminalLog(`[TASK STOPPED] Đã gửi lệnh dừng tác vụ ${taskId} (${source})`, "warning");
            loadActiveTasks();
        } else {
            showToast("Không thể gửi lệnh dừng tiến trình", "error");
        }
    } catch (e) {
        showToast(`Lỗi: ${e.message}`, "error");
    }
}

async function deleteActiveTask(taskId) {
    try {
        const res = await fetch(`/api/tasks/${encodeURIComponent(taskId)}`, { method: "DELETE" });
        if (res.ok) {
            showToast("Đã gỡ tiến trình khỏi danh sách giám sát", "info");
            loadActiveTasks();
        }
    } catch (e) {
        showToast(`Lỗi: ${e.message}`, "error");
    }
}

async function clearCompletedTasks() {
    try {
        const res = await fetch("/api/tasks/clear-completed", { method: "POST" });
        if (res.ok) {
            const data = await res.json();
            showToast(`Đã dọn dẹp ${data.cleared_count || 0} tiến trình đã kết thúc`, "success");
            loadActiveTasks();
        }
    } catch (e) {
        showToast(`Lỗi: ${e.message}`, "error");
    }
}

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

    const btnClearCompleted = document.getElementById("btnClearCompletedTasks");
    if (btnClearCompleted) {
        btnClearCompleted.addEventListener("click", clearCompletedTasks);
    }

    const btnQuickNew = document.getElementById("btnQuickNewTask");
    if (btnQuickNew) {
        btnQuickNew.addEventListener("click", () => {
            switchToTab("singleTab");
        });
    }

    // Status Filter Pills
    const filterPills = document.querySelectorAll("#taskStatusFilters .filter-pill");
    filterPills.forEach(pill => {
        pill.addEventListener("click", () => {
            filterPills.forEach(p => p.classList.remove("active"));
            pill.classList.add("active");
            currentTaskFilter = pill.getAttribute("data-filter") || "all";
            renderActiveTasksCards(cachedActiveTasks);
        });
    });

    // Real-time search filter
    const searchInput = document.getElementById("taskFilterSearchInput");
    if (searchInput) {
        searchInput.addEventListener("input", (e) => {
            taskSearchTerm = e.target.value.trim().toLowerCase();
            renderActiveTasksCards(cachedActiveTasks);
        });
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
        cachedActiveTasks = tasks;

        // 1. Calculate Aggregate Metrics
        const runningTasks = tasks.filter(t => t.status === "RUNNING");
        const completedTasks = tasks.filter(t => t.status === "COMPLETED");
        const failedOrStoppedTasks = tasks.filter(t => ["FAILED", "STOPPED", "PARTIAL"].includes(t.status));

        let totalSuccess = 0;
        let totalSkipped = 0;
        let totalFailed = 0;
        tasks.forEach(t => {
            totalSuccess += (t.success || 0);
            totalSkipped += (t.skipped || 0);
            totalFailed += (t.failed || 0);
        });

        // 2. Update Header Metric Cards
        const elRunning = document.getElementById("statTotalRunning");
        const elActiveWorkers = document.getElementById("metricActiveWorkers");
        const elSuccess = document.getElementById("statTotalSuccess");
        const elSkipped = document.getElementById("statTotalSkipped");
        const elFailed = document.getElementById("statTotalFailed");

        if (elRunning) elRunning.textContent = runningTasks.length;
        if (elActiveWorkers) elActiveWorkers.textContent = `${runningTasks.length} tác vụ`;
        if (elSuccess) elSuccess.textContent = totalSuccess.toLocaleString();
        if (elSkipped) elSkipped.textContent = totalSkipped.toLocaleString();
        if (elFailed) elFailed.textContent = totalFailed.toLocaleString();

        // 3. Update Filter Counts
        const cntAll = document.getElementById("filterCountAll");
        const cntRun = document.getElementById("filterCountRunning");
        const cntComp = document.getElementById("filterCountCompleted");
        const cntFail = document.getElementById("filterCountFailed");

        if (cntAll) cntAll.textContent = tasks.length;
        if (cntRun) cntRun.textContent = runningTasks.length;
        if (cntComp) cntComp.textContent = completedTasks.length;
        if (cntFail) cntFail.textContent = failedOrStoppedTasks.length;

        // 4. Update Active Tasks Badge in Sidebar
        const badge = document.getElementById("activeTasksBadge");
        if (badge) {
            if (runningTasks.length > 0) {
                badge.style.display = "inline-flex";
                badge.textContent = runningTasks.length;
            } else {
                badge.style.display = "none";
            }
        }

        // 5. Update Floating Widget only if minimized in THIS tab
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

        // 6. Render Active Tasks Grid
        renderActiveTasksCards(tasks);
    } catch (e) {
        console.error("Error loading active tasks:", e);
    }
}

function renderActiveTasksCards(tasks) {
    const container = document.getElementById("activeTasksList");
    if (!container) return;

    if (!tasks || tasks.length === 0) {
        container.innerHTML = `
            <div class="tasks-empty-card">
                <div class="tasks-empty-icon">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                    </svg>
                </div>
                <h3>Hiện không có tiến trình nào đang chạy ngầm</h3>
                <p>Hệ thống đang rảnh rỗi và sẵn sàng xử lý các tác vụ mới. Bạn có thể bắt đầu di chuyển một tài khoản hoặc nạp danh sách CSV.</p>
                <div class="tasks-empty-actions">
                    <button type="button" class="btn btn-primary btn-sm" onclick="switchToTab('singleTab')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                            <polyline points="22,6 12,13 2,6"/>
                        </svg>
                        <span>Di Chuyển 1 Email</span>
                    </button>
                    <button type="button" class="btn btn-secondary btn-sm" onclick="switchToTab('batchTab')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                            <polyline points="14 2 14 8 20 8"></polyline>
                        </svg>
                        <span>Di Chuyển Hàng Loạt (CSV)</span>
                    </button>
                </div>
            </div>
        `;
        return;
    }

    // Filter by Tab and Search Term
    let filtered = [...tasks];
    if (currentTaskFilter === "RUNNING") {
        filtered = filtered.filter(t => t.status === "RUNNING");
    } else if (currentTaskFilter === "COMPLETED") {
        filtered = filtered.filter(t => t.status === "COMPLETED");
    } else if (currentTaskFilter === "FAILED_STOPPED") {
        filtered = filtered.filter(t => ["FAILED", "STOPPED", "PARTIAL"].includes(t.status));
    }

    if (taskSearchTerm) {
        filtered = filtered.filter(t =>
            (t.source && t.source.toLowerCase().includes(taskSearchTerm)) ||
            (t.dest && t.dest.toLowerCase().includes(taskSearchTerm)) ||
            (t.task_id && t.task_id.toLowerCase().includes(taskSearchTerm)) ||
            (t.current_folder && t.current_folder.toLowerCase().includes(taskSearchTerm))
        );
    }

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="tasks-empty-card">
                <div class="tasks-empty-icon">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="11" cy="11" r="8"></circle>
                        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                    </svg>
                </div>
                <h3>Không tìm thấy tiến trình phù hợp</h3>
                <p>Không có tác vụ nào khớp với bộ lọc "${currentTaskFilter}" hoặc từ khóa tìm kiếm "${taskSearchTerm}".</p>
            </div>
        `;
        return;
    }

    const reversedTasks = [...filtered].reverse();
    container.innerHTML = "";

    reversedTasks.forEach(t => {
        const card = document.createElement("div");

        let statusClass = "status-border-running";
        let statusBadge = `<span class="badge badge-neutral" style="background:rgba(59,130,246,0.15); color:#60a5fa; border:1px solid rgba(59,130,246,0.3);"><span class="live-pulse-dot" style="background:#3b82f6;"></span> ĐANG CHẠY</span>`;

        if (t.status === "COMPLETED") {
            statusClass = "status-border-completed";
            statusBadge = `<span class="badge badge-neutral" style="background:rgba(16,185,129,0.15); color:#34d399; border:1px solid rgba(16,185,129,0.3); font-weight:700;">✓ HOÀN TẤT</span>`;
        } else if (t.status === "PARTIAL") {
            statusClass = "status-border-partial";
            statusBadge = `<span class="badge badge-neutral" style="background:rgba(245,158,11,0.15); color:#fbbf24; border:1px solid rgba(245,158,11,0.3); font-weight:700;">⚠ MỘT PHẦN</span>`;
        } else if (t.status === "FAILED") {
            statusClass = "status-border-failed";
            statusBadge = `<span class="badge badge-neutral" style="background:rgba(239,68,68,0.15); color:#f87171; border:1px solid rgba(239,68,68,0.3); font-weight:700;">✕ THẤT BẠI</span>`;
        } else if (t.status === "STOPPED" || t.status === "STOPPING") {
            statusClass = "status-border-stopped";
            statusBadge = `<span class="badge badge-neutral" style="background:rgba(107,114,128,0.2); color:#9ca3af; border:1px solid rgba(107,114,128,0.4); font-weight:700;">⏹ ĐÃ DỪNG</span>`;
        }

        card.className = `task-card-pro ${statusClass}`;

        const pct = (t.percent || 0).toFixed(1);
        const durationFormatted = formatSeconds(t.duration_sec || 0);
        const speedFormatted = t.msg_rate ? `${t.msg_rate} thư/s` : (t.status === "RUNNING" ? "Đang tính..." : "");

        const totalItems = (t.success || 0) + (t.skipped || 0) + (t.failed || 0);

        card.innerHTML = `
            <!-- Card Header -->
            <div class="task-pro-header">
                <div class="task-pro-header-left">
                    ${statusBadge}
                    <span class="task-id-badge" onclick="copyTaskId('${t.task_id}')" title="Nhấp để sao chép Task ID">
                        #${t.task_id.length > 18 ? t.task_id.substring(0, 18) + '...' : t.task_id}
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                        </svg>
                    </span>
                </div>
                <div class="task-pro-header-right">
                    <span class="task-time-pill" title="Thời gian khởi động">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="10"></circle>
                            <polyline points="12 6 12 12 16 14"></polyline>
                        </svg>
                        ${t.started_at || ''}
                    </span>
                    <span class="task-duration-badge" title="Thời gian thực thi">
                        ⏱️ ${durationFormatted}
                    </span>
                </div>
            </div>

            <!-- Route Visual -->
            <div class="task-route-container">
                <div class="task-route-node" title="Tài khoản nguồn: ${t.source}">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                        <polyline points="22,6 12,13 2,6"/>
                    </svg>
                    <span class="task-route-email">${t.source}</span>
                </div>
                <div class="task-route-arrow">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="5" y1="12" x2="19" y2="12"></line>
                        <polyline points="12 5 19 12 12 19"></polyline>
                    </svg>
                </div>
                <div class="task-route-node" title="Tài khoản đích: ${t.dest}">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                        <polyline points="22,6 12,13 2,6"/>
                    </svg>
                    <span class="task-route-email">${t.dest}</span>
                </div>
            </div>

            <!-- Live Progress Bar & Speed -->
            <div class="task-progress-box">
                <div class="task-progress-meta">
                    <span class="task-folder-tag" title="Thư mục: ${t.current_folder || 'Đang kết nối...'}">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                        </svg>
                        ${t.current_folder || 'Đang kết nối...'}
                    </span>
                    <div style="display:flex; align-items:center; gap:8px;">
                        ${speedFormatted ? `<span class="task-speed-badge">⚡ ${speedFormatted}</span>` : ''}
                        <span class="task-pct-value">${pct}%</span>
                    </div>
                </div>

                <div class="task-progress-track">
                    <div class="task-progress-fill ${t.status === 'RUNNING' ? 'running-shimmer' : ''}" style="width: ${pct}%;"></div>
                </div>
            </div>

            <!-- 4-Pillar Count Metrics -->
            <div class="task-counts-grid">
                <div class="task-count-item">
                    <span class="task-count-label">THÀNH CÔNG</span>
                    <span class="task-count-value text-success">${(t.success || 0).toLocaleString()}</span>
                </div>
                <div class="task-count-item">
                    <span class="task-count-label">BỎ QUA</span>
                    <span class="task-count-value text-info">${(t.skipped || 0).toLocaleString()}</span>
                </div>
                <div class="task-count-item">
                    <span class="task-count-label">LỖI</span>
                    <span class="task-count-value ${t.failed > 0 ? 'text-danger' : 'text-muted'}">${(t.failed || 0).toLocaleString()}</span>
                </div>
                <div class="task-count-item">
                    <span class="task-count-label">ĐÃ XỬ LÝ</span>
                    <span class="task-count-value text-primary">${totalItems.toLocaleString()}</span>
                </div>
            </div>

            <!-- Error Notification if any -->
            ${t.error_message ? `
                <div class="task-error-box">
                    <strong>Thông báo lỗi:</strong> ${t.error_message}
                </div>
            ` : ''}

            <!-- Actions Footer -->
            <div class="task-pro-actions">
                <div class="task-actions-left">
                    <button type="button" class="btn btn-secondary btn-sm" onclick="viewTaskLogs('${t.task_id}', '${t.source}')">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="4 17 10 11 4 5"></polyline>
                            <line x1="12" y1="19" x2="20" y2="19"></line>
                        </svg>
                        <span>Logs</span>
                    </button>

                    ${t.html_report ? `
                        <a href="${t.html_report}" target="_blank" class="btn btn-primary btn-sm">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                                <polyline points="14 2 14 8 20 8"></polyline>
                            </svg>
                            <span>Báo Cáo</span>
                        </a>
                    ` : ''}

                    ${t.csv_report ? `
                        <a href="/api/reports/download/${t.csv_report}" download class="btn btn-secondary btn-sm" title="Tải file CSV chi tiết lỗi/kết quả">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                                <polyline points="7 10 12 15 17 10"></polyline>
                                <line x1="12" y1="15" x2="12" y2="3"></line>
                            </svg>
                            <span>Tải CSV</span>
                        </a>
                    ` : ''}
                </div>

                <div class="task-actions-right">
                    ${t.status === "RUNNING" ? `
                        <button type="button" class="btn btn-secondary btn-sm text-danger" onclick="stopActiveTask('${t.task_id}', '${t.source}')" title="Dừng tiến trình này một cách an toàn">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                            </svg>
                            <span>Dừng Lại</span>
                        </button>
                    ` : `
                        <button type="button" class="btn btn-secondary btn-sm text-muted" onclick="deleteActiveTask('${t.task_id}')" title="Xóa tác vụ khỏi danh sách">
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="3 6 5 6 21 6"></polyline>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                            </svg>
                            <span>Xóa</span>
                        </button>
                    `}
                </div>
            </div>
        `;

        container.appendChild(card);
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
        { inputId: "singleAuthPass", btnId: "toggleSingleAuthPass" },
        { inputId: "scanSinglePass", btnId: "toggleScanSinglePass" }
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

// --------------------------------------------------------------------------
// STANDALONE MAILBOX STORAGE & FOLDERS SCANNER (SINGLE & BATCH CSV)
// --------------------------------------------------------------------------
let lastSingleScanFolders = [];
let currentSingleScannedCreds = null;
window.lastBatchScanResults = [];

function initScanStorageTab() {
    // 1. Single Account Scan Form
    const scanSingleForm = document.getElementById("scanSingleForm");
    const btnRunSingleScan = document.getElementById("btnRunSingleScan");
    const singleResultCard = document.getElementById("singleScanResultContainer");
    const singleFolderSearch = document.getElementById("singleScanFolderSearch");
    const btnTransferFromScan = document.getElementById("btnTransferFromScan");
    const btnCloseSingleScan = document.getElementById("btnCloseSingleScan");

    if (scanSingleForm) {
        scanSingleForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const host = document.getElementById("scanSingleHost")?.value.trim();
            const port = parseInt(document.getElementById("scanSinglePort")?.value) || 993;
            const sslVal = document.getElementById("scanSingleSsl")?.value;
            const ssl = (sslVal === "ssl" || sslVal === "true");
            const username = document.getElementById("scanSingleUser")?.value.trim();
            const password = document.getElementById("scanSinglePass")?.value;

            if (!host || !username || !password) {
                showToast("Vui lòng điền đầy đủ máy chủ IMAP, tài khoản và mật khẩu", "error");
                return;
            }

            btnRunSingleScan.disabled = true;
            const origHtml = btnRunSingleScan.innerHTML;
            btnRunSingleScan.innerHTML = `
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 0.8s linear infinite;">
                    <circle cx="12" cy="12" r="10" stroke-opacity="0.25"/>
                    <path d="M12 2a10 10 0 0 1 10 10"/>
                </svg>
                <span>Đang kết nối & quét cấu trúc thư mục...</span>
            `;

            try {
                const resp = await fetch("/api/inspect", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ host, port, ssl, username, password })
                });

                if (!resp.ok) {
                    const errData = await resp.json().catch(() => ({}));
                    throw new Error(errData.detail || `Lỗi máy chủ (${resp.status})`);
                }

                const data = await resp.json();
                currentSingleScannedCreds = { host, port, ssl, username, password };
                lastSingleScanFolders = data.folders || [];

                // Title and sub
                const titleEl = document.getElementById("singleScanResultTitle");
                const subEl = document.getElementById("singleScanResultSub");
                if (titleEl) titleEl.textContent = `Kết Quả Khảo Sát: ${data.account || username}`;
                if (subEl) subEl.textContent = `Máy chủ: ${host}:${port} • Giao thức: ${ssl ? 'SSL/TLS' : 'Plaintext'}`;

                // Aggregate metrics
                const totalMsgs = data.total_messages || lastSingleScanFolders.reduce((s, f) => s + (f.messages || 0), 0);
                const totalMb = data.total_size_mb || (data.total_size_bytes ? (data.total_size_bytes / (1024 * 1024)).toFixed(2) : "0.00");
                const totalGb = data.total_size_gb || (data.total_size_bytes ? (data.total_size_bytes / (1024 * 1024 * 1024)).toFixed(2) : "0.00");

                const totalMsgsEl = document.getElementById("singleScanTotalMsgs");
                if (totalMsgsEl) totalMsgsEl.textContent = Number(totalMsgs).toLocaleString();

                const totalSizeEl = document.getElementById("singleScanTotalSize");
                if (totalSizeEl) totalSizeEl.textContent = `${totalMb} MB`;

                const totalSizeGbEl = document.getElementById("singleScanTotalSizeGb");
                const avgKb = Number(totalMsgs) > 0 ? (parseFloat(totalMb) * 1024 / Number(totalMsgs)).toFixed(1) : 0;
                if (totalSizeGbEl) totalSizeGbEl.textContent = `${totalGb} GB (${avgKb} KB/thư)`;

                const foldersCountEl = document.getElementById("singleScanFoldersCount");
                if (foldersCountEl) foldersCountEl.textContent = lastSingleScanFolders.length;

                // Quota calculation
                const quotaPctEl = document.getElementById("singleScanQuotaPct");
                const quotaTextEl = document.getElementById("singleScanQuotaText");
                const quotaBarWrap = document.getElementById("singleScanQuotaBarWrap");
                const quotaBarFill = document.getElementById("singleScanQuotaBarFill");
                const quotaBarLabel = document.getElementById("singleScanQuotaBarLabel");

                if (data.quota && data.quota.limit > 0) {
                    const usedMb = (data.quota.used / (1024 * 1024)).toFixed(1);
                    const limitMb = (data.quota.limit / (1024 * 1024)).toFixed(1);
                    const pct = Math.min(Math.round((data.quota.used / data.quota.limit) * 100), 100);

                    if (quotaPctEl) quotaPctEl.textContent = `${pct}%`;
                    if (quotaTextEl) quotaTextEl.textContent = `${usedMb} MB / ${limitMb} MB`;

                    if (quotaBarWrap) quotaBarWrap.style.display = "block";
                    if (quotaBarFill) {
                        quotaBarFill.style.width = `${pct}%`;
                        quotaBarFill.style.background = pct > 90 ? "#f43f5e" : pct > 75 ? "#fbbf24" : "#10b981";
                    }
                    if (quotaBarLabel) quotaBarLabel.textContent = `${pct}% (${usedMb} MB / ${limitMb} MB)`;
                } else {
                    if (quotaPctEl) quotaPctEl.textContent = "Không giới hạn";
                    if (quotaTextEl) quotaTextEl.textContent = "Không áp dụng hạn ngạch hoặc server không hỗ trợ QUOTA";
                    if (quotaBarWrap) quotaBarWrap.style.display = "none";
                }

                // Render folders table
                renderSingleScanFoldersTable(lastSingleScanFolders, parseFloat(totalMb));

                // Display container
                if (singleResultCard) {
                    singleResultCard.style.display = "block";
                    singleResultCard.scrollIntoView({ behavior: "smooth", block: "start" });
                }

                showToast(`Khảo sát thành công: ${lastSingleScanFolders.length} thư mục, ${totalMsgs} thư!`, "success");
            } catch (err) {
                showToast(`Khảo sát thất bại: ${err.message}`, "error");
            } finally {
                btnRunSingleScan.disabled = false;
                btnRunSingleScan.innerHTML = origHtml;
            }
        });
    }

    // Single folder search filter
    if (singleFolderSearch) {
        singleFolderSearch.addEventListener("input", (e) => {
            const query = e.target.value.toLowerCase().trim();
            const filtered = lastSingleScanFolders.filter(f => f.name.toLowerCase().includes(query) || (f.role && f.role.toLowerCase().includes(query)));
            const totalMb = parseFloat(document.getElementById("singleScanTotalSize")?.textContent || "0");
            renderSingleScanFoldersTable(filtered, totalMb);
        });
    }

    // Transfer single scan credentials to migration tab
    if (btnTransferFromScan) {
        btnTransferFromScan.addEventListener("click", () => {
            if (!currentSingleScannedCreds) {
                showToast("Chưa có thông tin khảo sát để chuyển", "warning");
                return;
            }
            const srcHost = document.getElementById("srcHost");
            const srcPort = document.getElementById("srcPort");
            const srcSsl = document.getElementById("srcSsl");
            const srcUser = document.getElementById("srcUser");
            const srcPass = document.getElementById("srcPass");

            if (srcHost) srcHost.value = currentSingleScannedCreds.host;
            if (srcPort) srcPort.value = currentSingleScannedCreds.port;
            if (srcSsl) srcSsl.value = currentSingleScannedCreds.ssl ? "true" : "false";
            if (srcUser) srcUser.value = currentSingleScannedCreds.username;
            if (srcPass) srcPass.value = currentSingleScannedCreds.password;

            switchToTab("singleTab");
            showToast("Đã chuyển tài khoản nguồn sang Cấu hình Di chuyển!", "success");
        });
    }

    if (btnCloseSingleScan) {
        btnCloseSingleScan.addEventListener("click", () => {
            if (singleResultCard) singleResultCard.style.display = "none";
        });
    }

    // 2. Batch CSV Scan - Dual Mode Tabs
    const btnCsvTabUpload = document.getElementById("btnCsvTabUpload");
    const btnCsvTabPaste = document.getElementById("btnCsvTabPaste");
    const csvUploadPane = document.getElementById("csvUploadPane");
    const csvPastePane = document.getElementById("csvPastePane");
    const scanCsvDropZone = document.getElementById("scanCsvDropZone");
    const scanCsvFileInput = document.getElementById("scanCsvFileInput");
    const scanCsvPasteArea = document.getElementById("scanCsvPasteArea");
    const btnDownloadScanSampleCsv = document.getElementById("btnDownloadScanSampleCsv");
    const btnDownloadScanSampleCsvPaste = document.getElementById("btnDownloadScanSampleCsvPaste");
    const btnRemoveScanFile = document.getElementById("btnRemoveScanFile");
    const btnClearScanPaste = document.getElementById("btnClearScanPaste");
    const scanFileLoadedBanner = document.getElementById("scanFileLoadedBanner");
    const scanCsvLiveCountText = document.getElementById("scanCsvLiveCountText");
    const csvPasteCountBadge = document.getElementById("csvPasteCountBadge");
    const btnRunBatchScan = document.getElementById("btnRunBatchScan");
    const batchResultCard = document.getElementById("batchScanResultContainer");
    const btnExportScanCsv = document.getElementById("btnExportScanCsv");
    const btnTransferBatchToMigrate = document.getElementById("btnTransferBatchToMigrate");
    const btnCloseBatchScan = document.getElementById("btnCloseBatchScan");
    const batchTableSearch = document.getElementById("batchScanTableSearch");

    // Mode Switcher Tabs
    if (btnCsvTabUpload && btnCsvTabPaste) {
        btnCsvTabUpload.addEventListener("click", () => {
            btnCsvTabUpload.classList.add("active");
            btnCsvTabPaste.classList.remove("active");
            if (csvUploadPane) csvUploadPane.style.display = "block";
            if (csvPastePane) csvPastePane.style.display = "none";
        });
        btnCsvTabPaste.addEventListener("click", () => {
            btnCsvTabPaste.classList.add("active");
            btnCsvTabUpload.classList.remove("active");
            if (csvPastePane) csvPastePane.style.display = "block";
            if (csvUploadPane) csvUploadPane.style.display = "none";
        });
    }

    const updateScanCsvCounts = () => {
        const raw = scanCsvPasteArea?.value || "";
        const accounts = parseAccountsFromCsvText(raw);
        const count = accounts.length;
        if (scanCsvLiveCountText) scanCsvLiveCountText.textContent = `${count} tài khoản hợp lệ`;
        if (csvPasteCountBadge) {
            csvPasteCountBadge.textContent = count;
            csvPasteCountBadge.style.display = count > 0 ? "inline-flex" : "none";
        }
    };

    if (scanCsvPasteArea) {
        scanCsvPasteArea.addEventListener("input", updateScanCsvCounts);
    }

    if (btnClearScanPaste) {
        btnClearScanPaste.addEventListener("click", () => {
            if (scanCsvPasteArea) scanCsvPasteArea.value = "";
            if (scanFileLoadedBanner) scanFileLoadedBanner.style.display = "none";
            if (scanCsvFileInput) scanCsvFileInput.value = "";
            updateScanCsvCounts();
            showToast("Đã xóa nội dung danh sách!", "info");
        });
    }

    if (btnRemoveScanFile) {
        btnRemoveScanFile.addEventListener("click", (e) => {
            e.stopPropagation();
            if (scanCsvFileInput) scanCsvFileInput.value = "";
            if (scanFileLoadedBanner) scanFileLoadedBanner.style.display = "none";
            if (scanCsvPasteArea) scanCsvPasteArea.value = "";
            updateScanCsvCounts();
            showToast("Đã hủy tệp tải lên!", "info");
        });
    }

    // CSV File Drag & Drop
    if (scanCsvDropZone && scanCsvFileInput) {
        scanCsvDropZone.addEventListener("click", (e) => {
            if (e.target.closest("#btnRemoveScanFile")) return;
            scanCsvFileInput.click();
        });

        ["dragenter", "dragover"].forEach(name => {
            scanCsvDropZone.addEventListener(name, (e) => {
                e.preventDefault();
                e.stopPropagation();
                scanCsvDropZone.classList.add("dragover");
            });
        });

        ["dragleave", "drop"].forEach(name => {
            scanCsvDropZone.addEventListener(name, (e) => {
                e.preventDefault();
                e.stopPropagation();
                scanCsvDropZone.classList.remove("dragover");
            });
        });

        scanCsvDropZone.addEventListener("drop", (e) => {
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleScanCsvFile(files[0]);
            }
        });

        scanCsvFileInput.addEventListener("change", (e) => {
            if (e.target.files.length > 0) {
                handleScanCsvFile(e.target.files[0]);
            }
        });
    }

    // Download Sample CSV
    const downloadSample = () => {
        const sampleContent = "email,password\nnhanvien1@congty.com,MatKhau123@#\nnhanvien2@congty.com,MatKhau456@#\nnhanvien3@congty.com,MatKhau789@#\n";
        const blob = new Blob([sampleContent], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "mau_khao_sat_dung_luong.csv";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast("Đã tải xuống file CSV mẫu!", "success");
    };

    if (btnDownloadScanSampleCsv) btnDownloadScanSampleCsv.addEventListener("click", downloadSample);
    if (btnDownloadScanSampleCsvPaste) btnDownloadScanSampleCsvPaste.addEventListener("click", downloadSample);

    // Run Batch Scan
    if (btnRunBatchScan) {
        btnRunBatchScan.addEventListener("click", async () => {
            const rawText = scanCsvPasteArea?.value.trim() || "";
            if (!rawText) {
                showToast("Vui lòng tải lên file CSV hoặc dán danh sách tài khoản cần khảo sát", "error");
                return;
            }

            const host = document.getElementById("scanBatchHost")?.value.trim();
            const port = parseInt(document.getElementById("scanBatchPort")?.value) || 993;
            const ssl = document.getElementById("scanBatchSsl")?.checked ?? true;

            if (!host) {
                showToast("Vui lòng nhập Máy chủ IMAP chung", "error");
                return;
            }

            const accounts = parseAccountsFromCsvText(rawText);

            if (accounts.length === 0) {
                showToast("Không tìm thấy dòng hợp lệ nào (định dạng email,password)", "error");
                return;
            }

            btnRunBatchScan.disabled = true;
            const origHtml = btnRunBatchScan.innerHTML;
            btnRunBatchScan.innerHTML = `
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="animation: spin 0.8s linear infinite;">
                    <circle cx="12" cy="12" r="10" stroke-opacity="0.25"/>
                    <path d="M12 2a10 10 0 0 1 10 10"/>
                </svg>
                <span>Đang khảo sát song song ${accounts.length} hòm thư...</span>
            `;

            try {
                const resp = await fetch("/api/scan/batch", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        source_host: host,
                        source_port: port,
                        source_ssl: ssl,
                        accounts: accounts
                    })
                });

                if (!resp.ok) {
                    const err = await resp.json().catch(() => ({}));
                    throw new Error(err.detail || `Lỗi máy chủ (${resp.status})`);
                }

                const results = await resp.json();
                window.lastBatchScanResults = results;

                // Update aggregate metrics
                const totalAccounts = results.length;
                const validAccounts = results.filter(r => r.is_valid).length;
                const failedAccounts = results.filter(r => !r.is_valid).length;
                const totalMsgs = results.reduce((s, r) => s + (r.total_messages || 0), 0);
                const totalGb = results.reduce((s, r) => s + (parseFloat(r.total_size_gb) || 0), 0).toFixed(2);
                const totalMb = results.reduce((s, r) => s + (parseFloat(r.total_size_mb) || 0), 0);
                const avgMb = validAccounts > 0 ? (totalMb / validAccounts).toFixed(1) : "0";

                const accEl = document.getElementById("batchScanTotalAccounts");
                if (accEl) accEl.textContent = totalAccounts;
                const validEl = document.getElementById("batchScanValidAccounts");
                if (validEl) validEl.textContent = `${validAccounts} hợp lệ (${failedAccounts} lỗi)`;

                const sizeEl = document.getElementById("batchScanTotalSize");
                if (sizeEl) sizeEl.textContent = `${totalGb} GB`;
                const avgEl = document.getElementById("batchScanAvgSize");
                if (avgEl) avgEl.textContent = `Trung bình: ${avgMb} MB / hòm thư`;

                const msgsEl = document.getElementById("batchScanTotalMsgs");
                if (msgsEl) msgsEl.textContent = totalMsgs.toLocaleString();

                const failedEl = document.getElementById("batchScanFailedAccounts");
                if (failedEl) failedEl.textContent = failedAccounts;

                // Render accounts table
                renderBatchScanTable(results);

                // Show container
                if (batchResultCard) {
                    batchResultCard.style.display = "block";
                    batchResultCard.scrollIntoView({ behavior: "smooth", block: "start" });
                }

                showToast(`Đã hoàn tất khảo sát ${totalAccounts} tài khoản!`, "success");
            } catch (err) {
                showToast(`Lỗi khảo sát hàng loạt: ${err.message}`, "error");
            } finally {
                btnRunBatchScan.disabled = false;
                btnRunBatchScan.innerHTML = origHtml;
            }
        });
    }

    // Filter batch table
    if (batchTableSearch) {
        batchTableSearch.addEventListener("input", (e) => {
            const query = e.target.value.toLowerCase().trim();
            const filtered = (window.lastBatchScanResults || []).filter(r => (r.account || "").toLowerCase().includes(query));
            renderBatchScanTable(filtered);
        });
    }

    // Export batch scan CSV
    if (btnExportScanCsv) {
        btnExportScanCsv.addEventListener("click", () => {
            if (!window.lastBatchScanResults || window.lastBatchScanResults.length === 0) {
                showToast("Chưa có dữ liệu để xuất CSV", "warning");
                return;
            }
            let csv = "Email,Trang_Thai,Tong_So_Thu,Dung_Luong_MB,Dung_Luong_GB,So_Thu_Muc,Han_Ngach_Quota,Ghi_Chu_Loi\n";
            window.lastBatchScanResults.forEach(r => {
                const status = r.is_valid ? "Hop_Le" : "Loi";
                const msgs = r.total_messages || 0;
                const mb = r.total_size_mb || 0;
                const gb = r.total_size_gb || 0;
                const fCount = r.folders_count || 0;
                const quota = r.quota ? `${r.quota.used}/${r.quota.limit}` : "Khong_Gioi_Han";
                const err = (r.error_message || "").replace(/[\r\n,]/g, " ");
                csv += `"${r.account}","${status}",${msgs},${mb},${gb},${fCount},"${quota}","${err}"\n`;
            });

            const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `bao_cao_khao_sat_dung_luong_${new Date().toISOString().slice(0, 10)}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showToast("Đã tải xuống file báo cáo khảo sát CSV!", "success");
        });
    }

    // Transfer Batch Accounts to Migration Tab
    if (btnTransferBatchToMigrate) {
        btnTransferBatchToMigrate.addEventListener("click", () => {
            const host = document.getElementById("scanBatchHost")?.value.trim();
            const port = document.getElementById("scanBatchPort")?.value.trim();
            const ssl = document.getElementById("scanBatchSsl")?.checked;

            if (host && document.getElementById("batchSrcHost")) document.getElementById("batchSrcHost").value = host;
            if (port && document.getElementById("batchSrcPort")) document.getElementById("batchSrcPort").value = port;
            if (document.getElementById("batchSrcSsl")) document.getElementById("batchSrcSsl").value = ssl ? "true" : "false";

            switchToTab("batchTab");
            showToast("Đã chuyển cấu hình máy chủ sang Di Chuyển CSV! Vui lòng tải file CSV đích để bắt đầu.", "info");
        });
    }

    if (btnCloseBatchScan) {
        btnCloseBatchScan.addEventListener("click", () => {
            if (batchResultCard) batchResultCard.style.display = "none";
        });
    }

    // Modal close buttons
    const btnCloseScanModal = document.getElementById("btnCloseScanModal");
    const btnCloseScanModalFooter = document.getElementById("btnCloseScanModalFooter");
    const modal = document.getElementById("scanFolderDetailModal");
    const closeModal = () => modal?.classList.remove("open");

    if (btnCloseScanModal) btnCloseScanModal.addEventListener("click", closeModal);
    if (btnCloseScanModalFooter) btnCloseScanModalFooter.addEventListener("click", closeModal);
    if (modal) {
        modal.addEventListener("click", (e) => {
            if (e.target === modal) closeModal();
        });
    }
}

function parseAccountsFromCsvText(rawText) {
    if (!rawText) return [];
    const lines = rawText.split(/\r?\n/).map(l => l.trim()).filter(l => l.length > 0);
    let startIndex = 0;
    if (lines.length > 0) {
        const firstLine = lines[0].toLowerCase();
        if (firstLine.includes("email") || firstLine.includes("user")) {
            startIndex = 1;
        }
    }
    const accounts = [];
    for (let i = startIndex; i < lines.length; i++) {
        const cols = lines[i].split(",").map(c => c.trim().replace(/^["']|["']$/g, ''));
        if (cols.length >= 2 && cols[0]) {
            accounts.push({
                email: cols[0],
                password: cols[1]
            });
        }
    }
    return accounts;
}

function handleScanCsvFile(file) {
    if (!file.name.toLowerCase().endsWith(".csv")) {
        showToast("Vui lòng tải lên tệp có định dạng .CSV", "error");
        return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
        const text = e.target.result;
        const pasteArea = document.getElementById("scanCsvPasteArea");
        if (pasteArea) pasteArea.value = text;
        const accounts = parseAccountsFromCsvText(text);

        // Update file loaded banner
        const banner = document.getElementById("scanFileLoadedBanner");
        const nameEl = document.getElementById("scanFileName");
        const metaEl = document.getElementById("scanFileMeta");
        if (nameEl) nameEl.textContent = file.name;
        if (metaEl) metaEl.textContent = `${accounts.length} tài khoản (${(file.size / 1024).toFixed(1)} KB)`;
        if (banner) banner.style.display = "flex";

        const liveCount = document.getElementById("scanCsvLiveCountText");
        const countBadge = document.getElementById("csvPasteCountBadge");
        if (liveCount) liveCount.textContent = `${accounts.length} tài khoản hợp lệ`;
        if (countBadge) {
            countBadge.textContent = accounts.length;
            countBadge.style.display = accounts.length > 0 ? "inline-flex" : "none";
        }

        showToast(`Đã nạp file "${file.name}" thành công (${accounts.length} tài khoản)!`, "success");
    };
    reader.readAsText(file);
}

function renderSingleScanFoldersTable(folders, totalMb) {
    const tbody = document.getElementById("singleScanFoldersTableBody");
    if (!tbody) return;

    if (!folders || folders.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:20px; color:var(--text-dim);">Không tìm thấy thư mục nào phù hợp.</td></tr>`;
        return;
    }

    tbody.innerHTML = folders.map((f, idx) => {
        const fSizeMb = f.size_mb || (f.size_bytes ? (f.size_bytes / (1024 * 1024)).toFixed(2) : "0.00");
        const fraction = (totalMb > 0 && parseFloat(fSizeMb) > 0) ? Math.min(Math.round((parseFloat(fSizeMb) / totalMb) * 100), 100) : 0;

        let roleBadge = `<span class="badge badge-neutral">${escapeHtml(f.role || 'Thư mục')}</span>`;
        if (f.role === 'INBOX') roleBadge = `<span class="badge badge-primary">Hộp thư đến</span>`;
        else if (f.role === 'Sent') roleBadge = `<span class="badge badge-success">Đã gửi</span>`;
        else if (f.role === 'Trash') roleBadge = `<span class="badge badge-danger">Thùng rác</span>`;
        else if (f.role === 'Spam' || f.role === 'Junk') roleBadge = `<span class="badge badge-warning">Spam/Rác</span>`;
        else if (f.role === 'Drafts') roleBadge = `<span class="badge badge-neutral">Bản nháp</span>`;

        return `
            <tr>
                <td style="text-align:center; color:var(--text-dim); font-size:12px;">${idx + 1}</td>
                <td><strong>${escapeHtml(f.name)}</strong></td>
                <td>${roleBadge}</td>
                <td style="text-align:right; font-family:'JetBrains Mono', monospace; font-weight:600;">${(f.messages || 0).toLocaleString()}</td>
                <td style="text-align:right; font-family:'JetBrains Mono', monospace; color:#38bdf8;">${fSizeMb} MB</td>
                <td style="text-align:right;">
                    <div style="display:flex; align-items:center; justify-content:flex-end; gap:6px;">
                        <span class="mono-font" style="font-size:11.5px; color:var(--text-dim);">${fraction}%</span>
                        <div style="width:40px; height:5px; background:rgba(255,255,255,0.08); border-radius:3px; overflow:hidden;">
                            <div style="width:${fraction}%; height:100%; background:var(--primary);"></div>
                        </div>
                    </div>
                </td>
                <td style="text-align:center;">
                    <span class="status-badge status-success" style="font-size:11px;">Khả dụng</span>
                </td>
            </tr>
        `;
    }).join("");
}

function renderBatchScanTable(list) {
    const tbody = document.getElementById("batchScanTableBody");
    if (!tbody) return;

    if (!list || list.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:20px; color:var(--text-dim);">Không có tài khoản nào để hiển thị.</td></tr>`;
        return;
    }

    tbody.innerHTML = list.map((r, idx) => {
        let statusBadge = `<span class="badge badge-success" style="font-size:11.5px;"><span class="status-dot" style="background:#10b981;"></span> Sẵn sàng</span>`;
        if (!r.is_valid) {
            statusBadge = `<span class="badge badge-danger" style="font-size:11.5px;" title="${escapeHtml(r.error_message || '')}"><span class="status-dot" style="background:#f43f5e;"></span> Lỗi</span>`;
        }

        const mb = r.total_size_mb || (r.total_size_bytes ? (r.total_size_bytes / 1048576).toFixed(2) : "0.00");
        const gb = r.total_size_gb || (r.total_size_bytes ? (r.total_size_bytes / 1073741824).toFixed(2) : "0.00");

        let quotaText = `<span style="color:var(--text-dim); font-size:11.5px;">Không giới hạn</span>`;
        if (r.quota && r.quota.limit > 0) {
            const qPct = Math.round((r.quota.used / r.quota.limit) * 100);
            quotaText = `<span class="badge ${qPct > 90 ? 'badge-danger' : 'badge-neutral'}" style="font-size:11px;">${qPct}% (${(r.quota.used / 1048576).toFixed(0)}/${(r.quota.limit / 1048576).toFixed(0)} MB)</span>`;
        }

        let actionHtml = `<span style="color:#fb7185; font-size:11.5px;" title="${escapeHtml(r.error_message || '')}">Không kết nối</span>`;
        if (r.is_valid && r.folders && r.folders.length > 0) {
            actionHtml = `<button type="button" class="btn btn-secondary btn-sm" onclick="openScanFolderModal(${idx})" style="font-size:11px; padding:3px 8px;">📂 Xem Thư Mục</button>`;
        }

        return `
            <tr>
                <td style="text-align:center; color:var(--text-dim); font-size:12px;">${idx + 1}</td>
                <td><strong>${escapeHtml(r.account)}</strong></td>
                <td>${statusBadge}</td>
                <td style="text-align:right; font-family:'JetBrains Mono', monospace; font-weight:600; color:#34d399;">${(r.total_messages || 0).toLocaleString()}</td>
                <td style="text-align:right;">
                    <span class="mono-font" style="color:#38bdf8;">${mb} MB</span>
                    <span style="font-size:11px; color:var(--text-dim);">(${gb} GB)</span>
                </td>
                <td style="text-align:center;">${quotaText}</td>
                <td style="text-align:center;">
                    <span class="badge badge-neutral" style="font-size:11.5px;">${r.folders_count || 0} mục</span>
                </td>
                <td style="text-align:center;">${actionHtml}</td>
            </tr>
        `;
    }).join("");
}

window.openScanFolderModal = function(index) {
    const item = window.lastBatchScanResults ? window.lastBatchScanResults[index] : null;
    if (!item) return;

    const modal = document.getElementById("scanFolderDetailModal");
    const title = document.getElementById("scanModalAccountTitle");
    const msgsEl = document.getElementById("scanModalTotalMsgs");
    const sizeEl = document.getElementById("scanModalTotalSize");
    const quotaEl = document.getElementById("scanModalQuota");
    const tbody = document.getElementById("scanModalTableBody");

    if (title) title.textContent = `Cấu Trúc Thư Mục: ${item.account}`;
    if (msgsEl) msgsEl.textContent = Number(item.total_messages || 0).toLocaleString();
    if (sizeEl) sizeEl.textContent = `${item.total_size_mb || 0} MB (${item.total_size_gb || 0} GB)`;
    if (quotaEl) {
        quotaEl.textContent = item.quota && item.quota.limit > 0
            ? `${Math.round((item.quota.used / item.quota.limit) * 100)}% (${(item.quota.used / 1048576).toFixed(1)} / ${(item.quota.limit / 1048576).toFixed(1)} MB)`
            : "Không giới hạn";
    }

    if (tbody) {
        const folders = item.folders || [];
        if (folders.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:16px; color:var(--text-dim);">Không có thư mục nào.</td></tr>`;
        } else {
            tbody.innerHTML = folders.map((f, i) => {
                const fSize = f.size_mb || (f.size_bytes ? (f.size_bytes / 1048576).toFixed(2) : "0.00");
                let roleBadge = `<span class="badge badge-neutral">${escapeHtml(f.role || 'Thư mục')}</span>`;
                if (f.role === 'INBOX') roleBadge = `<span class="badge badge-primary">Hộp thư đến</span>`;
                else if (f.role === 'Sent') roleBadge = `<span class="badge badge-success">Đã gửi</span>`;
                else if (f.role === 'Trash') roleBadge = `<span class="badge badge-danger">Thùng rác</span>`;
                else if (f.role === 'Spam' || f.role === 'Junk') roleBadge = `<span class="badge badge-warning">Spam</span>`;
                else if (f.role === 'Drafts') roleBadge = `<span class="badge badge-neutral">Bản nháp</span>`;

                return `
                    <tr>
                        <td style="text-align:center; color:var(--text-dim); font-size:12px;">${i + 1}</td>
                        <td><strong>${escapeHtml(f.name)}</strong></td>
                        <td>${roleBadge}</td>
                        <td style="text-align:right; font-family:'JetBrains Mono', monospace;">${(f.messages || 0).toLocaleString()}</td>
                        <td style="text-align:right; font-family:'JetBrains Mono', monospace; color:#38bdf8;">${fSize} MB</td>
                    </tr>
                `;
            }).join("");
        }
    }

    if (modal) modal.classList.add("open");
};

