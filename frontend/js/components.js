/**
 * Sentinel Intelligence — UI Components Module
 *
 * Pure rendering functions. Each function takes data and returns
 * DOM elements or HTML strings. No state, no side effects.
 */

const SentinelComponents = (() => {

    // --- Stat Bar ---

    function renderStatBar(stats) {
        const cards = [
            { key: "critical", label: "Critical", cls: "stat-card--critical" },
            { key: "high",     label: "High",     cls: "stat-card--high" },
            { key: "medium",   label: "Medium",   cls: "stat-card--medium" },
            { key: "low",      label: "Low",      cls: "stat-card--low" },
        ];

        cards.forEach(({ key, cls }) => {
            const el = document.querySelector(`.${cls} .stat-card__value`);
            if (el) {
                const newVal = String(stats[key] || 0).padStart(2, "0");
                el.textContent = newVal;
            }
        });
    }


    // --- Time helpers ---

    function _timeAgo(timestamp) {
        if (!timestamp) return "";
        const now = new Date();
        const then = new Date(timestamp + (timestamp.endsWith("Z") ? "" : "Z"));
        const diffMs = now - then;
        const diffMin = Math.floor(diffMs / 60000);

        if (diffMin < 1) return "just now";
        if (diffMin < 60) return `${diffMin}m ago`;

        const diffHr = Math.floor(diffMin / 60);
        if (diffHr < 24) return `${diffHr}h ago`;

        const diffDay = Math.floor(diffHr / 24);
        return `${diffDay}d ago`;
    }


    // --- Finding Card ---

    function renderFindingCard(finding) {
        const card = document.createElement("div");
        card.className = `finding-card finding-card--${finding.severity}`;
        card.dataset.id = finding.id;
        card.dataset.severity = finding.severity;
        card.dataset.status = finding.status;

        if (finding.status === "Reviewed") {
            card.classList.add("finding-card--reviewed");
        }

        // Sources links
        const sourcesHtml = (finding.sources || [])
            .map(s => `<a href="${_escHtml(s.url)}" target="_blank" rel="noopener" class="finding-card__source-link">${_escHtml(s.name)}</a>`)
            .join("");

        // Review button
        const reviewBtn = finding.status === "Reviewed"
            ? `<button class="btn-review reviewed" disabled>✓ Reviewed</button>`
            : `<button class="btn-review" data-action="review" data-id="${finding.id}">✓ Mark Reviewed</button>`;

        card.innerHTML = `
            <div class="finding-card__header">
                <div style="display:flex; align-items:center; gap:10px; flex:1; min-width:0;">
                    <span class="badge badge--${finding.severity}">${finding.severity}</span>
                    <h3 class="finding-card__title">${_escHtml(finding.title)}</h3>
                </div>
                <span class="finding-card__time">${_timeAgo(finding.timestamp)}</span>
            </div>
            <p class="finding-card__summary">${_escHtml(finding.summary)}</p>
            <div class="finding-card__meta">
                <span class="finding-card__meta-item">
                    Impact: <span class="finding-card__meta-value finding-card__meta-value--impact">${_escHtml(finding.impact)}</span>
                </span>
                <span class="finding-card__meta-item">
                    Target: <span class="finding-card__meta-value">${_escHtml(finding.target)}</span>
                </span>
                <div class="finding-card__sources">${sourcesHtml}</div>
                ${reviewBtn}
            </div>
        `;

        return card;
    }


    // --- Feed renderer ---

    function renderFeed(container, findings) {
        container.innerHTML = "";

        if (!findings || findings.length === 0) {
            container.innerHTML = `
                <div class="feed__empty">
                    <p>No findings match the current filters.</p>
                    <p style="margin-top:8px; font-size:0.8rem;">Try adjusting the filters or wait for the next collector run.</p>
                </div>
            `;
            return;
        }

        findings.forEach((finding, i) => {
            const card = renderFindingCard(finding);
            // Staggered animation delay
            card.style.animationDelay = `${i * 50}ms`;
            container.appendChild(card);
        });
    }


    // --- Utility: escape HTML ---

    function _escHtml(str) {
        if (!str) return "";
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }


    return { renderStatBar, renderFindingCard, renderFeed };
})();
