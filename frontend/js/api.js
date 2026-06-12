/**
 * Sentinel Intelligence — API Client Module
 *
 * All HTTP communication with the backend.
 * Uses relative paths (same origin — served by FastAPI).
 */

const SentinelAPI = (() => {
    const API_BASE = "/api";

    // Read API key from a meta tag or prompt the user once
    let _apiKey = null;

    function _getApiKey() {
        if (_apiKey) return _apiKey;

        // Try reading from a meta tag first
        const meta = document.querySelector('meta[name="api-key"]');
        if (meta && meta.content) {
            _apiKey = meta.content;
            return _apiKey;
        }

        // Fall back to localStorage
        _apiKey = localStorage.getItem("sentinel_api_key");
        if (_apiKey) return _apiKey;

        // Prompt user
        _apiKey = prompt("Enter your Sentinel API Key:");
        if (_apiKey) {
            localStorage.setItem("sentinel_api_key", _apiKey);
        }
        return _apiKey;
    }

    async function _request(path, options = {}) {
        const url = `${API_BASE}${path}`;
        const headers = {
            "X-API-Key": _getApiKey(),
            "Content-Type": "application/json",
            ...options.headers,
        };

        try {
            const response = await fetch(url, { ...options, headers });

            if (response.status === 403) {
                // API key invalid — clear and ask again
                localStorage.removeItem("sentinel_api_key");
                _apiKey = null;
                throw new Error("Invalid API key. Refresh the page to re-enter.");
            }

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (err) {
            console.error(`[API] ${options.method || "GET"} ${url} failed:`, err);
            throw err;
        }
    }

    // --- Public methods ---

    async function fetchFindings(filters = {}) {
        const params = new URLSearchParams();
        if (filters.severity) params.set("severity", filters.severity);
        if (filters.status) params.set("status", filters.status);
        if (filters.limit) params.set("limit", filters.limit);

        const query = params.toString();
        return _request(`/findings${query ? "?" + query : ""}`);
    }

    async function fetchStats() {
        return _request("/stats");
    }

    async function markReviewed(findingId) {
        return _request(`/findings/${findingId}`, {
            method: "PATCH",
            body: JSON.stringify({ status: "Reviewed" }),
        });
    }

    async function healthCheck() {
        // Health endpoint does not require auth
        const response = await fetch(`${API_BASE}/health`);
        return response.json();
    }

    return { fetchFindings, fetchStats, markReviewed, healthCheck, _getKey: _getApiKey };
})();
