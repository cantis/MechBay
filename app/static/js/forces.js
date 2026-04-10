/**
 * forces.js — JavaScript for the Force detail page.
 * Reads context values from data-* attributes on #forceContext.
 */
(function () {
    const ctx = document.getElementById('forceContext');
    if (!ctx) return;

    const forceId = ctx.dataset.forceId;
    const csrf = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    // ── SortableJS drag-and-drop ──────────────────────────────────────────────
    document.querySelectorAll('.sortable-lance').forEach(el => {
        new Sortable(el, {
            group: 'lances',
            animation: 150,
            handle: '.fa-grip-vertical',
            onEnd: function (evt) {
                const miniatureId = evt.item.dataset.miniatureId;
                const targetLanceId = evt.to.dataset.lanceId;
                const position = evt.newIndex;

                evt.to.querySelectorAll('.empty-placeholder').forEach(p => p.remove());

                fetch(`/forces/${forceId}/move-miniature`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                    body: JSON.stringify({ miniature_id: miniatureId, target_lance_id: targetLanceId, position })
                }).then(response => {
                    if (!response.ok) { alert('Failed to move miniature'); location.reload(); }
                });
            }
        });
    });

    // ── Template application ──────────────────────────────────────────────────
    let currentTemplateId = null;

    window.applyTemplate = function (templateId) {
        currentTemplateId = templateId;

        fetch(`/forces/${forceId}/lances/from-template`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrf },
            body: `template_id=${templateId}`
        })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else if (data.needs_confirmation) {
                    const body = document.getElementById('templateConfirmBody');
                    body.innerHTML = `
                        <p>Template: <strong>${data.template_name}</strong></p>
                        <p>Found ${data.matched_count} of ${data.matched_count + data.missing.length} miniatures.</p>
                        ${data.missing.length > 0 ? `
                            <p class="text-warning"><strong>Missing:</strong></p>
                            <ul class="list-group">
                                ${data.missing.map(m => `<li class="list-group-item">${m}</li>`).join('')}
                            </ul>
                            <p class="mt-2">Create partial lance with available miniatures?</p>
                        ` : ''}
                    `;
                    new bootstrap.Modal(document.getElementById('templateConfirmModal')).show();
                } else {
                    alert(data.error || 'Failed to apply template');
                }
            });
    };

    const confirmBtn = document.getElementById('confirmTemplateBtn');
    if (confirmBtn) {
        confirmBtn.onclick = function () {
            fetch(`/forces/${forceId}/lances/from-template`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrf },
                body: `template_id=${currentTemplateId}&confirm=true`
            })
                .then(r => r.json())
                .then(data => {
                    if (data.success) { location.reload(); }
                    else { alert(data.error || 'Failed to create lance'); }
                });
        };
    }

    // ── Remove miniature ──────────────────────────────────────────────────────
    window.removeMiniature = function (miniatureId, fId) {
        const modal = new bootstrap.Modal(document.getElementById('confirmRemoveModal'));
        document.getElementById('confirmRemoveBtn').onclick = function () {
            modal.hide();
            fetch(`/forces/${fId}/remove-miniature`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                body: JSON.stringify({ miniature_id: miniatureId })
            }).then(response => {
                if (response.ok) { setTimeout(() => location.reload(), 100); }
                else { alert('Failed to remove miniature'); }
            });
        };
        modal.show();
    };

    // ── Lance rename (double-click) ───────────────────────────────────────────
    document.querySelectorAll('.editable-lance-name').forEach(el => {
        el.ondblclick = function () {
            const lanceId = this.dataset.lanceId;
            const currentName = this.closest('.card-header').querySelector('.lance-name-text').textContent.trim();

            const renameModal = document.getElementById('renameLanceModal');
            const input = document.getElementById('renameLanceInput');
            input.value = currentName;

            const bsModal = new bootstrap.Modal(renameModal);
            document.getElementById('renameLanceSaveBtn').onclick = function () {
                const newName = input.value.trim();
                if (!newName || newName === currentName) { bsModal.hide(); return; }

                fetch(`/forces/${forceId}/lances/${lanceId}/rename`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                    body: JSON.stringify({ name: newName })
                })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            el.querySelector('.lance-name-text').textContent = data.name || 'Unnamed Lance';
                            bsModal.hide();
                        } else {
                            alert('Failed to rename lance');
                        }
                    });
            };
            bsModal.show();
            // Focus input after modal shown
            renameModal.addEventListener('shown.bs.modal', () => input.select(), { once: true });
        };
    });

    // ── Delete lance confirmation ─────────────────────────────────────────────
    document.querySelectorAll('.delete-lance-btn').forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            const form = this.closest('form');
            const modal = new bootstrap.Modal(document.getElementById('confirmDeleteLanceModal'));
            document.getElementById('confirmDeleteLanceBtn').onclick = function () {
                modal.hide();
                form.submit();
            };
            modal.show();
        });
    });
})();
