/**
 * Sentinel Intelligence — Settings Page Module
 *
 * Manages the settings SPA page: feed sources CRUD,
 * DB management (clear, stats), and manual collector trigger.
 */

const SentinelSettings = (() => {

    let _sources = [];
    let _dbStats = {};

    // --- API helpers ---

    async function _fetchSources() {
        const resp = await fetch("/api/admin/sources", {
            headers: { "X-API-Key": SentinelAPI._getKey() },
        });
        if (!resp.ok) throw new Error("Failed to fetch sources");
        return resp.json();
    }

    async function _addSource(data) {
        const resp = await fetch("/api/admin/sources", {
            method: "POST",
            headers: {
                "X-API-Key": SentinelAPI._getKey(),
                "Content-Type": "application/json",
            },
            body: JSON.stringify(data),
        });
        if (resp.status === 409) throw new Error("A source with this URL already exists.");
        if (!resp.ok) throw new Error("Failed to add source");
        return resp.json();
    }

    async function _deleteSource(id) {
        const resp = await fetch(`/api/admin/sources/${id}`, {
            method: "DELETE",
            headers: { "X-API-Key": SentinelAPI._getKey() },
        });
        if (!resp.ok) throw new Error("Failed to delete source");
        return resp.json();
    }

    async function _toggleSource(id, enabled) {
        const resp = await fetch(`/api/admin/sources/${id}`, {
            method: "PATCH",
            headers: {
                "X-API-Key": SentinelAPI._getKey(),
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ enabled }),
        });
        if (!resp.ok) throw new Error("Failed to toggle source");
        return resp.json();
    }

    async function _fetchDbStats() {
        const resp = await fetch("/api/admin/db-stats", {
            headers: { "X-API-Key": SentinelAPI._getKey() },
        });
        if (!resp.ok) throw new Error("Failed to fetch DB stats");
        return resp.json();
    }

    async function _clearDatabase() {
        const resp = await fetch("/api/admin/clear-db", {
            method: "DELETE",
            headers: { "X-API-Key": SentinelAPI._getKey() },
        });
        if (!resp.ok) throw new Error("Failed to clear database");
        return resp.json();
    }

    async function _runCollector() {
        const resp = await fetch("/api/admin/run-collector", {
            method: "POST",
            headers: { "X-API-Key": SentinelAPI._getKey() },
        });
        if (!resp.ok) throw new Error("Failed to trigger collector");
        return resp.json();
    }

    async function _stopCollector() {
        const resp = await fetch("/api/admin/stop-collector", {
            method: "POST",
            headers: { "X-API-Key": SentinelAPI._getKey() },
        });
        if (resp.status === 404) {
            return { message: "No collector process is currently running." };
        }
        if (!resp.ok) throw new Error("Failed to stop collector");
        return resp.json();
    }


    // --- Rendering ---

    function _formatBytes(bytes) {
        if (bytes === 0) return "0 B";
        const k = 1024;
        const sizes = ["B", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
    }

    function renderDbStats(stats) {
        _dbStats = stats;
        const el = document.getElementById("settings-db-stats");
        if (!el) return;

        el.innerHTML = `
            <div class="settings-stats-grid">
                <div class="settings-stat-item">
                    <span class="settings-stat-value">${stats.total_findings}</span>
                    <span class="settings-stat-label">Total Findings</span>
                </div>
                <div class="settings-stat-item">
                    <span class="settings-stat-value settings-stat-value--new">${stats.new_findings}</span>
                    <span class="settings-stat-label">New</span>
                </div>
                <div class="settings-stat-item">
                    <span class="settings-stat-value settings-stat-value--reviewed">${stats.reviewed_findings}</span>
                    <span class="settings-stat-label">Reviewed</span>
                </div>
                <div class="settings-stat-item">
                    <span class="settings-stat-value">${stats.enabled_sources} / ${stats.total_sources}</span>
                    <span class="settings-stat-label">Active Sources</span>
                </div>
                <div class="settings-stat-item">
                    <span class="settings-stat-value">${_formatBytes(stats.db_size_bytes)}</span>
                    <span class="settings-stat-label">DB Size</span>
                </div>
                <div class="settings-stat-item">
                    <span class="settings-stat-value">${stats.queue_count}</span>
                    <span class="settings-stat-label">Queue Remaining</span>
                </div>
            </div>
        `;
    }

    function renderSources(sources) {
        _sources = sources;
        const el = document.getElementById("settings-sources-list");
        if (!el) return;

        if (sources.length === 0) {
            el.innerHTML = `<p class="settings-empty">No sources configured.</p>`;
            return;
        }

        el.innerHTML = sources.map(src => `
            <div class="source-card ${src.enabled ? "" : "source-card--disabled"}" data-source-id="${src.id}">
                <div class="source-card__info">
                    <div class="source-card__header">
                        <span class="source-card__name">${_esc(src.name)}</span>
                        ${src.is_builtin ? '<span class="source-card__badge source-card__badge--builtin">Built-in</span>' : '<span class="source-card__badge source-card__badge--custom">Custom</span>'}
                        <span class="source-card__badge source-card__badge--type">${_esc(src.source_type.toUpperCase())}</span>
                    </div>
                    <div class="source-card__url">${_esc(src.url)}</div>
                </div>
                <div class="source-card__actions">
                    <label class="toggle-switch" title="${src.enabled ? 'Disable' : 'Enable'} this source">
                        <input type="checkbox" ${src.enabled ? "checked" : ""} data-action="toggle-source" data-id="${src.id}">
                        <span class="toggle-slider"></span>
                    </label>
                    <button class="settings-btn settings-btn--danger settings-btn--sm" data-action="delete-source" data-id="${src.id}" title="Delete source">✕</button>
                </div>
            </div>
        `).join("");
    }

    function _esc(str) {
        if (!str) return "";
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }


    // --- Event handlers ---

    async function handleAddSource(e) {
        e.preventDefault();
        const form = e.target;
        const btn = form.querySelector("button[type=submit]");
        const msgEl = document.getElementById("add-source-msg");

        const data = {
            name: form.querySelector("#source-name").value.trim(),
            url: form.querySelector("#source-url").value.trim(),
            source_type: form.querySelector("#source-type").value,
            selector: form.querySelector("#source-selector").value.trim() || "article",
            max_items: parseInt(form.querySelector("#source-max-items").value) || 15,
        };

        if (!data.name || !data.url) {
            msgEl.textContent = "Name and URL are required.";
            msgEl.className = "settings-msg settings-msg--error";
            return;
        }

        btn.disabled = true;
        btn.textContent = "Adding...";

        try {
            await _addSource(data);
            form.reset();
            msgEl.textContent = `✓ Source "${data.name}" added successfully.`;
            msgEl.className = "settings-msg settings-msg--success";
            await refreshSettings();
        } catch (err) {
            msgEl.textContent = `✕ ${err.message}`;
            msgEl.className = "settings-msg settings-msg--error";
        } finally {
            btn.disabled = false;
            btn.textContent = "Add Source";
        }
    }

    async function handleDeleteSource(id) {
        if (!confirm("Delete this source? This cannot be undone.")) return;
        try {
            await _deleteSource(id);
            await refreshSettings();
        } catch (err) {
            alert("Failed to delete source: " + err.message);
        }
    }

    async function handleToggleSource(id, enabled) {
        try {
            await _toggleSource(id, enabled);
            await refreshSettings();
        } catch (err) {
            alert("Failed to toggle source: " + err.message);
        }
    }

    async function handleClearDb() {
        const confirmText = prompt(
            'This will permanently delete ALL findings.\nType "DELETE" to confirm:'
        );
        if (confirmText !== "DELETE") return;

        const btn = document.getElementById("btn-clear-db");
        if (btn) { btn.disabled = true; btn.textContent = "Clearing..."; }

        try {
            const result = await _clearDatabase();
            alert(result.message);
            await refreshSettings();
        } catch (err) {
            alert("Failed to clear database: " + err.message);
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = "Clear All Findings"; }
        }
    }

    async function handleRunCollector() {
        const btn = document.getElementById("btn-run-collector");
        if (btn) { btn.disabled = true; btn.textContent = "Starting..."; }

        try {
            const result = await _runCollector();
            alert(result.message);
        } catch (err) {
            alert("Failed to start collector: " + err.message);
        } finally {
            if (btn) {
                btn.textContent = "Running...";
                setTimeout(() => {
                    btn.disabled = false;
                    btn.textContent = "▶ Run Collector Now";
                    refreshSettings();
                }, 30000);
            }
        }
    }

    async function handleStopCollector() {
        const btn = document.getElementById("btn-stop-collector");
        if (btn) { btn.disabled = true; btn.textContent = "Stopping..."; }

        try {
            const result = await _stopCollector();
            alert(result.message);
            await refreshSettings();
        } catch (err) {
            alert("Failed to stop collector: " + err.message);
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = "⏹ Stop Collector"; }
        }
    }


    // --- Main refresh ---

    async function refreshSettings() {
        try {
            const [sources, stats] = await Promise.all([
                _fetchSources(),
                _fetchDbStats(),
            ]);
            renderSources(sources);
            renderDbStats(stats);
        } catch (err) {
            console.error("[Settings] Failed to refresh:", err);
        }
    }


    // --- Init ---

    function init() {
        // Add source form
        const form = document.getElementById("add-source-form");
        if (form) form.addEventListener("submit", handleAddSource);

        // Event delegation for source list
        const sourcesList = document.getElementById("settings-sources-list");
        if (sourcesList) {
            sourcesList.addEventListener("click", (e) => {
                const deleteBtn = e.target.closest("[data-action='delete-source']");
                if (deleteBtn) {
                    handleDeleteSource(parseInt(deleteBtn.dataset.id));
                    return;
                }
            });
            sourcesList.addEventListener("change", (e) => {
                const toggle = e.target.closest("[data-action='toggle-source']");
                if (toggle) {
                    handleToggleSource(parseInt(toggle.dataset.id), toggle.checked);
                }
            });
        }

        // DB management buttons
        const clearBtn = document.getElementById("btn-clear-db");
        if (clearBtn) clearBtn.addEventListener("click", handleClearDb);

        const runBtn = document.getElementById("btn-run-collector");
        if (runBtn) runBtn.addEventListener("click", handleRunCollector);

        const stopBtn = document.getElementById("btn-stop-collector");
        if (stopBtn) stopBtn.addEventListener("click", handleStopCollector);
    }


    return { init, refreshSettings };
})();
