/**
 * Sentinel Intelligence — App Orchestrator
 *
 * Entry point. Wires up the API, components, filters, router, and settings.
 * Manages state, auto-refresh, and event delegation.
 */

const SentinelApp = (() => {

    // --- State ---
    let _allFindings = [];
    let _refreshInterval = null;
    const REFRESH_MS = 60 * 1000; // 60 seconds


    // --- DOM refs ---
    const $ = (sel) => document.querySelector(sel);
    const $feed = () => $("#findings-feed");
    const $syncTime = () => $("#sync-time");
    const $spinner = () => $(".header__sync-spinner");


    // --- Data fetching ---

    async function refreshStats() {
        try {
            const stats = await SentinelAPI.fetchStats();
            SentinelComponents.renderStatBar(stats);
        } catch (err) {
            console.error("[App] Failed to refresh stats:", err);
        }
    }

    async function refreshFeed() {
        try {
            _allFindings = await SentinelAPI.fetchFindings();
            _renderFilteredFeed();
        } catch (err) {
            console.error("[App] Failed to refresh feed:", err);
        }
    }

    function _renderFilteredFeed() {
        const filtered = SentinelFilters.applyFilters(_allFindings);
        SentinelComponents.renderFeed($feed(), filtered);
    }

    async function refreshAll() {
        const spinner = $spinner();
        if (spinner) spinner.classList.add("active");

        await Promise.all([refreshStats(), refreshFeed()]);

        if (spinner) spinner.classList.remove("active");
        _updateSyncTime();
    }

    function _updateSyncTime() {
        const el = $syncTime();
        if (el) {
            const now = new Date();
            el.textContent = now.toLocaleString();
        }
    }


    // --- Event handlers ---

    function _onFilterClick(e) {
        const pill = e.target.closest(".filter-pill");
        if (!pill) return;

        const filterKey = pill.dataset.filter;
        SentinelFilters.setFilter(filterKey);
        SentinelFilters.syncPillUI();
        _renderFilteredFeed();
    }

    async function _onReviewClick(e) {
        const btn = e.target.closest("[data-action='review']");
        if (!btn) return;

        const id = parseInt(btn.dataset.id, 10);
        if (!id) return;

        btn.disabled = true;
        btn.textContent = "Updating...";

        try {
            await SentinelAPI.markReviewed(id);

            // Update local state
            const finding = _allFindings.find(f => f.id === id);
            if (finding) finding.status = "Reviewed";

            _renderFilteredFeed();
        } catch (err) {
            console.error("[App] Failed to mark reviewed:", err);
            btn.disabled = false;
            btn.textContent = "✓ Mark Reviewed";
        }
    }


    // --- Route change handler ---

    function _onRouteChange(route) {
        if (route === "dashboard") {
            refreshAll();
            // Restart auto-refresh
            if (_refreshInterval) clearInterval(_refreshInterval);
            _refreshInterval = setInterval(refreshAll, REFRESH_MS);
        } else if (route === "settings") {
            // Stop auto-refresh on settings page
            if (_refreshInterval) clearInterval(_refreshInterval);
            _refreshInterval = null;
            SentinelSettings.refreshSettings();
        }
    }


    // --- Initialisation ---

    async function init() {
        console.log("[Sentinel] Dashboard initialising...");

        // Wire up filter clicks
        const filterBar = $(".filters");
        if (filterBar) {
            filterBar.addEventListener("click", _onFilterClick);
        }

        // Wire up review button clicks (event delegation on feed)
        const feed = $feed();
        if (feed) {
            feed.addEventListener("click", _onReviewClick);
        }

        // Set "All" filter as active by default
        SentinelFilters.reset();
        SentinelFilters.syncPillUI();

        // Init settings module
        SentinelSettings.init();

        // Init SPA router (this triggers the initial route)
        SentinelRouter.init(_onRouteChange);

        console.log("[Sentinel] Dashboard ready. SPA routing active.");
    }


    // --- Boot ---
    document.addEventListener("DOMContentLoaded", init);

    return { init, refreshAll };
})();
