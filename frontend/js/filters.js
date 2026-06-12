/**
 * Sentinel Intelligence — Filter Module
 *
 * Client-side filtering logic. Maintains filter state and provides
 * a pure filter function. No DOM manipulation — that's the components' job.
 */

const SentinelFilters = (() => {

    // Current active filter state
    let _state = {
        severity: null,  // null = all, or "Critical" | "High" | "Medium" | "Low"
        status: "New",   // default to "New" to hide reviewed items
    };


    // --- State management ---

    function getState() {
        return { ..._state };
    }

    function setSeverity(severity) {
        _state.severity = severity;
    }

    function setStatus(status) {
        _state.status = status;
    }

    function reset() {
        _state.severity = null;
        _state.status = "New";
    }

    function setFilter(key, value) {
        if (key === "all") {
            reset();
        } else if (["Critical", "High", "Medium", "Low"].includes(key)) {
            _state.severity = (_state.severity === key) ? null : key;
        } else if (key === "Reviewed") {
            _state.status = (_state.status === "Reviewed") ? "New" : "Reviewed";
        }
    }


    // --- Pure filter function ---

    function applyFilters(findings) {
        if (!findings) return [];

        return findings.filter(f => {
            if (_state.severity && f.severity !== _state.severity) return false;
            if (_state.status && f.status !== _state.status) return false;
            return true;
        });
    }


    // --- UI sync: update pill button active states ---

    function syncPillUI() {
        const pills = document.querySelectorAll(".filter-pill");
        pills.forEach(pill => {
            const filterKey = pill.dataset.filter;
            let isActive = false;

            if (filterKey === "all") {
                isActive = !_state.severity && (_state.status === "New");
            } else if (["Critical", "High", "Medium", "Low"].includes(filterKey)) {
                isActive = _state.severity === filterKey;
            } else if (["New", "Reviewed"].includes(filterKey)) {
                isActive = _state.status === filterKey;
            }

            pill.classList.toggle("active", isActive);
        });
    }


    return { getState, setFilter, applyFilters, syncPillUI, reset };
})();
