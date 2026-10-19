/**
 * Campaign roster page: drag units between lances (and within a lance) to organise them.
 * Reads the campaign id from #rosterContext and posts each move to the server.
 */
(function () {
    'use strict';

    const ctx = document.getElementById('rosterContext');
    if (!ctx || typeof Sortable === 'undefined') return;

    const campaignId = ctx.dataset.campaignId;
    const csrf = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    const moveUrl = `/campaigns/${campaignId}/roster/move`;

    function units(list) {
        return Array.from(list.querySelectorAll('.roster-unit'));
    }

    function refreshList(list) {
        const rows = units(list);
        const pv = rows.reduce((sum, row) => sum + Number(row.dataset.pv || 0), 0);
        const card = list.closest('.roster-lance');
        const countEl = card?.querySelector('[data-lance-count]');
        const pvEl = card?.querySelector('[data-lance-pv]');
        if (countEl) countEl.textContent = `${rows.length} unit${rows.length === 1 ? '' : 's'}`;
        if (pvEl) pvEl.textContent = String(pv);

        // A lance can only be deleted while it is empty.
        const deleteBtn = card?.querySelector('.lance-delete-btn');
        if (deleteBtn) {
            deleteBtn.disabled = rows.length > 0;
            const wrap = deleteBtn.closest('[data-delete-wrap]');
            if (wrap) {
                if (rows.length > 0) wrap.title = "Move this lance's units elsewhere to delete it";
                else wrap.removeAttribute('title');
            }
        }

        let placeholder = list.querySelector('.roster-empty');
        if (rows.length === 0 && !placeholder) {
            placeholder = document.createElement('li');
            placeholder.className = 'list-group-item text-muted text-center roster-empty';
            placeholder.textContent = 'Drop units here';
            list.appendChild(placeholder);
        } else if (rows.length > 0 && placeholder) {
            placeholder.remove();
        }
    }

    function refreshTotals() {
        const all = document.querySelectorAll('.roster-list .roster-unit');
        const pv = Array.from(all).reduce((sum, row) => sum + Number(row.dataset.pv || 0), 0);
        const totalEl = document.getElementById('rosterTotalPv');
        const countEl = document.getElementById('rosterTotalUnits');
        if (totalEl) totalEl.textContent = String(pv);
        if (countEl) countEl.textContent = String(all.length);
    }

    document.querySelectorAll('.roster-list').forEach((list) => {
        new Sortable(list, {
            group: 'roster',
            animation: 150,
            handle: '.roster-grip',
            draggable: '.roster-unit',
            onEnd(evt) {
                const target = evt.to;
                const body = {
                    unit_id: Number(evt.item.dataset.unitId),
                    lance_id: target.dataset.lanceId ? Number(target.dataset.lanceId) : null,
                    ordered_ids: units(target).map((row) => Number(row.dataset.unitId)),
                };
                refreshList(evt.from);
                refreshList(target);
                refreshTotals();
                fetch(moveUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                    body: JSON.stringify(body),
                })
                    .then((response) => response.json().catch(() => ({ success: false })))
                    .then((data) => {
                        if (!data.success) {
                            alert(data.error || 'Could not move the unit');
                            location.reload();
                        }
                    })
                    .catch(() => {
                        alert('Network error moving the unit');
                        location.reload();
                    });
            },
        });
    });
})();
