/**
 * miniatures.js — JavaScript for inventory list and add/edit forms.
 */
(function () {
    const csrf = document.querySelector('meta[name="csrf-token"]')
        ? document.querySelector('meta[name="csrf-token"]').getAttribute('content')
        : '';

    // ── Bulk selection ────────────────────────────────────────────────────────
    function getSelectedIds() {
        return Array.from(document.querySelectorAll('.row-check:checked')).map(cb => parseInt(cb.value));
    }

    function updateBulkToolbar() {
        const ids = getSelectedIds();
        const toolbar = document.getElementById('bulkToolbar');
        const countEl = document.getElementById('bulkCount');
        if (!toolbar) return;
        if (ids.length > 0) {
            toolbar.classList.remove('d-none');
            countEl.textContent = ids.length + ' selected';
        } else {
            toolbar.classList.add('d-none');
        }
    }

    window.clearSelection = function () {
        document.querySelectorAll('.row-check').forEach(cb => cb.checked = false);
        const sa = document.getElementById('selectAll');
        if (sa) sa.checked = false;
        updateBulkToolbar();
    };

    window.applyBulkAction = function (action, value) {
        const ids = getSelectedIds();
        if (ids.length === 0) { alert('No miniatures selected'); return; }
        if (!value) { alert('Please choose a value to apply'); return; }

        fetch('/miniatures/bulk-action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({ action, ids, value })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) { location.reload(); }
            else { alert('Bulk action failed: ' + (data.error || 'Unknown error')); }
        });
    };

    const selectAll = document.getElementById('selectAll');
    if (selectAll) {
        selectAll.addEventListener('change', function () {
            document.querySelectorAll('.row-check').forEach(cb => cb.checked = this.checked);
            updateBulkToolbar();
        });
    }
    document.querySelectorAll('.row-check').forEach(cb => {
        cb.addEventListener('change', updateBulkToolbar);
    });

    // ── Custom faction dialog (add/edit forms) ────────────────────────────────
    const factionSelect = document.getElementById('factionSelect');
    if (factionSelect) {
        factionSelect.addEventListener('change', function () {
            if (this.value === '__custom__') {
                const custom = prompt('Enter custom faction name:');
                if (custom && custom.trim()) {
                    const opt = document.createElement('option');
                    opt.value = custom.trim();
                    opt.textContent = custom.trim();
                    opt.selected = true;
                    this.insertBefore(opt, this.options[this.options.length - 1]);
                } else {
                    this.value = '';
                }
            }
        });
    }

    // ── Dynamic next unique_id on series change (add form only) ──────────────
    const seriesSelect = document.querySelector('select[name="series"]');
    const uniqueIdInput = document.querySelector('input[name="unique_id"]');
    const isPrefilled = document.getElementById('miniatureForm')
        ? document.getElementById('miniatureForm').dataset.prefilled === 'true'
        : false;

    if (seriesSelect && uniqueIdInput && !isPrefilled) {
        seriesSelect.addEventListener('change', function () {
            fetch('/miniatures/next-id/' + this.value)
                .then(r => r.json())
                .then(data => { uniqueIdInput.value = data.next_id; })
                .catch(() => {});
        });
    }
})();
