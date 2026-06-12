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
    let _currentOffset = 0;
    let _hasMore = true;
    let _isLoadingMore = false;
    const LIMIT = 30;
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

    async function refreshFeed(reset = true) {
        if (reset) {
            _currentOffset = 0;
            _hasMore = true;
            _allFindings = [];
            if ($feed()) $feed().innerHTML = ''; // clear existing
        }
        
        if (!_hasMore || _isLoadingMore) return;
        _isLoadingMore = true;

        try {
            const filters = SentinelFilters.getState();
            filters.limit = LIMIT;
            filters.offset = _currentOffset;

            const newFindings = await SentinelAPI.fetchFindings(filters);
            
            if (newFindings.length < LIMIT) {
                _hasMore = false;
            }

            _allFindings = _allFindings.concat(newFindings);
            _currentOffset += newFindings.length;

            SentinelComponents.appendFeed($feed(), newFindings);
        } catch (err) {
            console.error("[App] Failed to refresh feed:", err);
        } finally {
            _isLoadingMore = false;
        }
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
        refreshFeed(true); // reset and fetch with new filters
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

            // If we are currently viewing "New" items (the default), remove it from screen instantly
            const currentStatus = SentinelFilters.getState().status;
            if (currentStatus === "New") {
                const card = btn.closest(".finding-card");
                if (card) {
                    card.style.transition = "all 0.3s ease";
                    card.style.opacity = "0";
                    card.style.transform = "scale(0.95)";
                    setTimeout(() => card.remove(), 300);
                }
            } else {
                // If we are in "Reviewed" filter (or another view), just update the button
                btn.textContent = "✓ Reviewed";
                btn.classList.add("reviewed");
            }

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


    // --- Intersection Observer for Infinite Scroll ---

    function _initIntersectionObserver() {
        // Find or create scroll trigger
        let trigger = document.getElementById("scroll-trigger");
        if (!trigger) {
            trigger = document.createElement("div");
            trigger.id = "scroll-trigger";
            trigger.style.height = "20px";
            trigger.style.marginTop = "20px";
            
            const feedContainer = $feed();
            if (feedContainer && feedContainer.parentElement) {
                // Insert after feed
                feedContainer.parentElement.insertBefore(trigger, feedContainer.nextSibling);
            }
        }

        const observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting) {
                refreshFeed(false); // load more
            }
        }, { rootMargin: "100px" });

        observer.observe(trigger);
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

        _initIntersectionObserver();

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
