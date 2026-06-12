/**
 * Sentinel Intelligence — SPA Router
 *
 * Hash-based routing: #/dashboard (default) and #/settings.
 * Shows/hides page containers without reloading.
 */

const SentinelRouter = (() => {

    const ROUTES = {
        "dashboard": "page-dashboard",
        "settings":  "page-settings",
    };

    let _currentRoute = "dashboard";
    let _onRouteChange = null;

    function _getHashRoute() {
        const hash = window.location.hash.replace("#/", "").replace("#", "");
        return ROUTES[hash] ? hash : "dashboard";
    }

    function navigate(route) {
        if (!ROUTES[route]) route = "dashboard";
        window.location.hash = "#/" + route;
    }

    function _applyRoute() {
        const route = _getHashRoute();
        _currentRoute = route;

        // Hide all pages
        Object.values(ROUTES).forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = "none";
        });

        // Show current page
        const activeEl = document.getElementById(ROUTES[route]);
        if (activeEl) activeEl.style.display = "";

        // Update nav links
        document.querySelectorAll("[data-nav]").forEach(link => {
            link.classList.toggle("active", link.dataset.nav === route);
        });

        // Fire callback
        if (_onRouteChange) _onRouteChange(route);
    }

    function init(onRouteChange) {
        _onRouteChange = onRouteChange;
        window.addEventListener("hashchange", _applyRoute);

        // Wire up nav links
        document.querySelectorAll("[data-nav]").forEach(link => {
            link.addEventListener("click", (e) => {
                e.preventDefault();
                navigate(link.dataset.nav);
            });
        });

        // Apply initial route
        _applyRoute();
    }

    function getCurrentRoute() {
        return _currentRoute;
    }

    return { init, navigate, getCurrentRoute };
})();
