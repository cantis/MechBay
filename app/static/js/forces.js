/**
 * forces.js — JavaScript for the Force detail page.
 * Reads context values from data-* attributes on #forceContext.
 */
(function () {
    const ctx = document.getElementById('forceContext');
    if (!ctx) return;

    const forceId = ctx.dataset.forceId;
    const csrf = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    // ── Scroll to section after redirect (e.g. add-to-lance, variant assign) ───
    const scrollTarget = sessionStorage.getItem('mechbayScrollTo');
    if (scrollTarget) {
        sessionStorage.removeItem('mechbayScrollTo');
        document.getElementById(scrollTarget)?.scrollIntoView({ block: 'start' });
    } else if (window.location.hash) {
        const target = document.querySelector(window.location.hash);
        if (target) {
            target.scrollIntoView({ block: 'start' });
        }
    }

    // ── Inventory pool filters (hide unavailable + search) ─────────────────
    const hideUnavailable = document.getElementById('hideUnavailable');
    const inventoryPoolSearch = document.getElementById('inventoryPoolSearch');
    const inventoryPoolType = document.getElementById('inventoryPoolType');
    const inventoryPoolSummary = document.getElementById('inventoryPoolSummary');
    const inventoryPoolSearchEmpty = document.getElementById('inventoryPoolSearchEmpty');
    const hideUnavailableKey = `mechbayHideUnavailable:${forceId}`;
    const typeFilterKey = `mechbayInventoryType:${forceId}`;

    function updateInventoryPoolSummary(visibleCount, filtering) {
        if (!inventoryPoolSummary) return;

        const total = Number(inventoryPoolSummary.dataset.total || 0);
        const inForce = Number(inventoryPoolSummary.dataset.inForce || 0);
        const hasMul = inventoryPoolSummary.dataset.hasMul === 'true';
        const mulAvailable = Number(inventoryPoolSummary.dataset.mulAvailable || 0);
        const notInMul = Number(inventoryPoolSummary.dataset.notInMul || 0);
        const available = Number(inventoryPoolSummary.dataset.available || 0);

        let text;
        if (filtering && visibleCount !== total) {
            text = `Showing ${visibleCount} of ${total} miniatures (filtered)`;
        } else {
            text = `${total} miniature${total === 1 ? '' : 's'}`;
        }

        if (hasMul) {
            text += ` · ${mulAvailable} MUL available`;
            if (notInMul) text += ` · ${notInMul} not in MUL filters`;
        } else {
            text += ` · ${available} available to add`;
        }
        text += ` · ${inForce} already in force`;
        inventoryPoolSummary.textContent = text;
    }

    function rowMatchesSearch(row, query) {
        if (!query) return true;
        const prefix = row.dataset.prefix || '';
        const chassis = row.dataset.chassis || '';
        return prefix.includes(query) || chassis.includes(query);
    }

    function rowMatchesType(row, typeFilter) {
        if (!typeFilter) return true;
        return (row.dataset.type || '') === typeFilter;
    }

    function rebuildInventoryTypeOptions() {
        if (!inventoryPoolType) return;

        const stored = sessionStorage.getItem(typeFilterKey) || inventoryPoolType.value || '';
        const types = new Map();
        document.querySelectorAll('.inventory-candidate-row').forEach((row) => {
            const key = row.dataset.type || '';
            if (!key) return;
            types.set(key, row.dataset.typeLabel || key);
        });

        inventoryPoolType.replaceChildren();
        const allOption = document.createElement('option');
        allOption.value = '';
        allOption.textContent = 'All types';
        inventoryPoolType.appendChild(allOption);

        [...types.entries()]
            .sort((a, b) => a[1].localeCompare(b[1]))
            .forEach(([value, label]) => {
                const option = document.createElement('option');
                option.value = value;
                option.textContent = label;
                inventoryPoolType.appendChild(option);
            });

        if (stored && [...inventoryPoolType.options].some((opt) => opt.value === stored)) {
            inventoryPoolType.value = stored;
        }
    }

    function applyInventoryPoolFilters() {
        const hideUnavailableActive = Boolean(hideUnavailable?.checked);
        const query = (inventoryPoolSearch?.value || '').trim().toLowerCase();
        const typeFilter = inventoryPoolType?.value || '';
        let visibleCount = 0;

        document.querySelectorAll('.inventory-candidate-row').forEach(row => {
            const hidden =
                (hideUnavailableActive && row.dataset.hideWhenFiltered === 'true') ||
                !rowMatchesSearch(row, query) ||
                !rowMatchesType(row, typeFilter);
            row.classList.toggle('d-none', hidden);
            if (!hidden) visibleCount += 1;
        });

        const filtering = hideUnavailableActive || query.length > 0 || typeFilter.length > 0;
        updateInventoryPoolSummary(visibleCount, filtering);

        if (inventoryPoolSearchEmpty) {
            const hasRows = document.querySelectorAll('.inventory-candidate-row').length > 0;
            inventoryPoolSearchEmpty.classList.toggle(
                'd-none',
                !filtering || visibleCount > 0 || !hasRows
            );
        }
    }

    if (hideUnavailable) {
        hideUnavailable.checked = sessionStorage.getItem(hideUnavailableKey) === '1';
        hideUnavailable.addEventListener('change', () => {
            sessionStorage.setItem(hideUnavailableKey, hideUnavailable.checked ? '1' : '0');
            applyInventoryPoolFilters();
        });
    }

    if (inventoryPoolSearch) {
        inventoryPoolSearch.addEventListener('input', applyInventoryPoolFilters);
    }

    if (inventoryPoolType) {
        inventoryPoolType.addEventListener('change', () => {
            sessionStorage.setItem(typeFilterKey, inventoryPoolType.value);
            applyInventoryPoolFilters();
        });
    }

    rebuildInventoryTypeOptions();
    applyInventoryPoolFilters();

    // ── Add / remove lance assignments (AJAX — no full-page redirect) ─────────
    const asEnabled = ctx.dataset.asEnabled === 'true';
    const addMiniatureUrl = `/forces/${forceId}/add-miniature`;

    function getLanceOptions() {
        return Array.from(document.querySelectorAll('.sortable-lance[data-lance-id]')).map((ul) => {
            const card = ul.closest('.card');
            const header = card?.querySelector('.card-header');
            return {
                lanceId: ul.dataset.lanceId,
                name: card?.querySelector('.lance-name-text')?.textContent.trim() || 'Lance',
                color: header?.style.backgroundColor || '#e9ecef',
            };
        });
    }

    function createAvailabilityBadge(mulState) {
        const badge = document.createElement('span');
        badge.className = 'badge';
        if (mulState === 'false') {
            badge.classList.add('bg-warning', 'text-dark');
            badge.textContent = 'Not in MUL filters';
        } else if (mulState === 'true') {
            badge.classList.add('bg-success');
            badge.textContent = 'MUL available';
        } else {
            badge.classList.add('bg-success');
            badge.textContent = 'Available';
        }
        return badge;
    }

    function populateAddToLanceActions(actionsCell, miniatureId) {
        actionsCell.innerHTML = '';
        const lances = getLanceOptions();
        if (lances.length === 0) {
            const hint = document.createElement('span');
            hint.className = 'text-muted small';
            hint.textContent = 'Create a lance first';
            actionsCell.appendChild(hint);
            return;
        }

        const dropdown = document.createElement('div');
        dropdown.className = 'dropdown dropstart d-inline position-static';

        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'btn btn-sm btn-outline-primary dropdown-toggle';
        toggle.textContent = 'Add to lance';
        toggle.setAttribute('data-bs-toggle', 'dropdown');
        toggle.setAttribute('data-bs-popper-config', '{"strategy":"fixed"}');

        const menu = document.createElement('ul');
        menu.className = 'dropdown-menu';

        lances.forEach((lance) => {
            const item = document.createElement('li');
            const form = document.createElement('form');
            form.method = 'post';
            form.action = addMiniatureUrl;
            form.className = 'm-0 add-to-lance-form';
            form.dataset.lanceName = lance.name;
            form.dataset.lanceColor = lance.color;

            const miniInput = document.createElement('input');
            miniInput.type = 'hidden';
            miniInput.name = 'miniature_id';
            miniInput.value = String(miniatureId);

            const lanceInput = document.createElement('input');
            lanceInput.type = 'hidden';
            lanceInput.name = 'lance_id';
            lanceInput.value = lance.lanceId;

            const btn = document.createElement('button');
            btn.type = 'submit';
            btn.className = 'dropdown-item';

            const dot = document.createElement('span');
            dot.className = 'd-inline-block rounded-circle me-2 align-middle';
            dot.style.width = '0.75rem';
            dot.style.height = '0.75rem';
            dot.style.backgroundColor = lance.color;

            btn.appendChild(dot);
            btn.append(` ${lance.name}`);
            form.append(miniInput, lanceInput, btn);
            item.appendChild(form);
            menu.appendChild(item);
        });

        dropdown.append(toggle, menu);
        actionsCell.appendChild(dropdown);
    }

    function updateInventoryRowInForce(row, lanceName, lanceColor) {
        row.removeAttribute('data-hide-when-filtered');
        const availCell = row.querySelector('.inventory-col-availability');
        if (availCell) {
            availCell.innerHTML = '';
            const badge = document.createElement('span');
            badge.className = 'badge text-dark border';
            badge.style.backgroundColor = lanceColor;
            badge.textContent = lanceName ? `In force · ${lanceName}` : 'In force';
            availCell.appendChild(badge);
        }
        const actionsCell = row.querySelector('.inventory-col-actions');
        if (actionsCell) {
            actionsCell.innerHTML = '';
        }
    }

    function restoreInventoryRowAvailable(row, miniatureId) {
        const mulState = row.dataset.mulState || 'none';
        if (mulState === 'false') {
            row.dataset.hideWhenFiltered = 'true';
        } else {
            row.removeAttribute('data-hide-when-filtered');
        }

        const availCell = row.querySelector('.inventory-col-availability');
        if (availCell) {
            availCell.innerHTML = '';
            availCell.appendChild(createAvailabilityBadge(mulState));
        }

        const actionsCell = row.querySelector('.inventory-col-actions');
        if (actionsCell) {
            populateAddToLanceActions(actionsCell, miniatureId);
        }
    }

    function removeMiniatureFromLanceDom(listItem) {
        const lanceList = listItem.closest('.sortable-lance');
        if (!lanceList) return;

        listItem.remove();
        const remaining = lanceList.querySelectorAll('li.list-group-item:not(.empty-placeholder)');
        if (remaining.length === 0) {
            const placeholder = document.createElement('li');
            placeholder.className = 'list-group-item text-muted text-center empty-placeholder';
            placeholder.textContent = 'Empty lance';
            lanceList.appendChild(placeholder);
        }

        const countEl = lanceList.closest('.card-body')?.querySelector('small.text-muted');
        if (countEl) {
            const count = lanceList.querySelectorAll('li.list-group-item:not(.empty-placeholder)').length;
            countEl.textContent = `${count} miniatures`;
        }
    }

    function appendMiniatureToLance(lanceId, details) {
        const lanceList = document.querySelector(`.sortable-lance[data-lance-id="${lanceId}"]`);
        if (!lanceList) return;

        lanceList.querySelectorAll('.empty-placeholder').forEach(el => el.remove());

        const li = document.createElement('li');
        li.className = 'list-group-item';
        li.dataset.miniatureId = String(details.miniatureId);
        li.dataset.fmId = String(details.fmId);
        li.dataset.chassis = details.chassis;

        const row = document.createElement('div');
        row.className = 'd-flex justify-content-between align-items-start';

        const body = document.createElement('div');
        body.className = 'flex-grow-1';

        const grip = document.createElement('i');
        grip.className = 'fa-solid fa-grip-vertical text-muted me-2';
        grip.style.cursor = 'grab';
        body.appendChild(grip);

        const strong = document.createElement('strong');
        strong.textContent = details.prefix;
        body.appendChild(strong);
        body.append(` ${details.chassis} `);

        const small = document.createElement('small');
        small.className = 'text-muted';
        small.textContent = `(${details.seriesId})`;
        body.appendChild(small);

        if (asEnabled) {
            const asRow = document.createElement('div');
            asRow.className = 'ms-4 mt-1';

            const unset = document.createElement('span');
            unset.className = 'text-muted fst-italic';
            unset.textContent = 'Variant not set';
            asRow.appendChild(unset);

            const assignBtn = document.createElement('button');
            assignBtn.type = 'button';
            assignBtn.className = 'btn btn-link btn-sm p-0 ms-1 assign-variant-btn';
            assignBtn.dataset.fmId = String(details.fmId);
            assignBtn.dataset.lanceId = String(lanceId);
            assignBtn.dataset.chassis = details.chassis;
            assignBtn.textContent = 'Assign variant';
            asRow.appendChild(assignBtn);

            body.appendChild(asRow);
        }

        const removeBtn = document.createElement('button');
        removeBtn.className = 'btn btn-sm btn-link text-danger p-0';
        removeBtn.innerHTML = '<i class="fa-solid fa-times"></i>';
        removeBtn.addEventListener('click', () => removeMiniature(details.miniatureId, forceId));

        row.appendChild(body);
        row.appendChild(removeBtn);
        li.appendChild(row);
        lanceList.appendChild(li);

        const countEl = lanceList.closest('.card-body')?.querySelector('small.text-muted');
        if (countEl) {
            const count = lanceList.querySelectorAll('li.list-group-item').length;
            countEl.textContent = `${count} miniatures`;
        }
    }

    document.getElementById('force-building')?.addEventListener('submit', async (event) => {
        const form = event.target.closest('.add-to-lance-form');
        if (!form) return;
        event.preventDefault();

        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) submitBtn.disabled = true;

        const miniatureId = form.querySelector('[name="miniature_id"]')?.value;
        const lanceId = form.querySelector('[name="lance_id"]')?.value;
        const row = form.closest('.inventory-candidate-row');

        try {
            const response = await fetch(form.action, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                body: JSON.stringify({ miniature_id: miniatureId, lance_id: lanceId }),
            });
            const data = await response.json().catch(() => ({}));

            if (!response.ok || !data.success) {
                alert(data.error || 'Failed to add miniature');
                if (submitBtn) submitBtn.disabled = false;
                return;
            }

            const lanceName = form.dataset.lanceName || '';
            const lanceColor = form.dataset.lanceColor || '#e9ecef';

            if (row) {
                updateInventoryRowInForce(row, lanceName, lanceColor);
            }

            appendMiniatureToLance(lanceId, {
                miniatureId: Number(miniatureId),
                fmId: data.force_miniature_id,
                prefix: row?.dataset.prefixLabel || '',
                chassis: row?.dataset.chassisLabel || '',
                seriesId: row?.dataset.seriesId || '',
            });

            if (inventoryPoolSummary) {
                inventoryPoolSummary.dataset.inForce = String(
                    Number(inventoryPoolSummary.dataset.inForce || 0) + 1
                );
            }
            applyInventoryPoolFilters();

            const dropdownToggle = form.closest('.dropdown')?.querySelector('[data-bs-toggle="dropdown"]');
            if (dropdownToggle) {
                bootstrap.Dropdown.getInstance(dropdownToggle)?.hide();
            }
        } catch {
            alert('Network error adding miniature');
            if (submitBtn) submitBtn.disabled = false;
        }
    });

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
                }).catch(() => { alert('Network error moving miniature'); location.reload(); });
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
                    body.textContent = '';

                    const templateP = document.createElement('p');
                    templateP.append('Template: ');
                    const templateStrong = document.createElement('strong');
                    templateStrong.textContent = data.template_name;
                    templateP.append(templateStrong);
                    body.append(templateP);

                    const countP = document.createElement('p');
                    countP.textContent = `Found ${data.matched_count} of ${data.matched_count + data.missing.length} miniatures.`;
                    body.append(countP);

                    if (data.missing.length > 0) {
                        const missingP = document.createElement('p');
                        missingP.className = 'text-warning';
                        const missingStrong = document.createElement('strong');
                        missingStrong.textContent = 'Missing:';
                        missingP.append(missingStrong);
                        body.append(missingP);

                        const missingList = document.createElement('ul');
                        missingList.className = 'list-group';
                        data.missing.forEach(m => {
                            const item = document.createElement('li');
                            item.className = 'list-group-item';
                            item.textContent = m;
                            missingList.append(item);
                        });
                        body.append(missingList);

                        const partialP = document.createElement('p');
                        partialP.className = 'mt-2';
                        partialP.textContent = 'Create partial lance with available miniatures?';
                        body.append(partialP);
                    }
                    new bootstrap.Modal(document.getElementById('templateConfirmModal')).show();
                } else {
                    alert(data.error || 'Failed to apply template');
                }
            })
            .catch(() => alert('Network error applying template'));
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
                })
                .catch(() => alert('Network error confirming template'));
        };
    }

    // ── Remove miniature ──────────────────────────────────────────────────────
    window.removeMiniature = function (miniatureId, fId) {
        const modal = new bootstrap.Modal(document.getElementById('confirmRemoveModal'));
        document.getElementById('confirmRemoveBtn').onclick = async function () {
            modal.hide();
            try {
                const response = await fetch(`/forces/${fId}/remove-miniature`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                    body: JSON.stringify({ miniature_id: miniatureId }),
                });
                const data = await response.json().catch(() => ({}));

                if (!response.ok || !data.success) {
                    alert(data.error || 'Failed to remove miniature');
                    return;
                }

                const listItem = document.querySelector(
                    `.sortable-lance li.list-group-item[data-miniature-id="${miniatureId}"]`
                );
                if (listItem) {
                    removeMiniatureFromLanceDom(listItem);
                }

                const row = document.querySelector(
                    `.inventory-candidate-row[data-miniature-id="${miniatureId}"]`
                );
                if (row) {
                    restoreInventoryRowAvailable(row, miniatureId);
                }

                if (inventoryPoolSummary) {
                    inventoryPoolSummary.dataset.inForce = String(
                        Math.max(0, Number(inventoryPoolSummary.dataset.inForce || 0) - 1)
                    );
                }
                applyInventoryPoolFilters();
            } catch {
                alert('Network error removing miniature');
            }
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
                    })
                    .catch(() => alert('Failed to rename lance'));
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

    // ── Point budget: step by 10 (10, 20, 30…); clear field = no budget ────────
    const pointBudget = document.getElementById('pointBudget');
    const pointBudgetUp = document.getElementById('pointBudgetUp');
    const pointBudgetDown = document.getElementById('pointBudgetDown');
    if (pointBudget) {
        const STEP = 10;
        function adjustBudget(delta) {
            const raw = pointBudget.value.trim();
            if (!raw) {
                if (delta > 0) pointBudget.value = String(STEP);
                return;
            }
            const n = parseInt(raw, 10);
            if (Number.isNaN(n)) {
                pointBudget.value = delta > 0 ? String(STEP) : '';
                return;
            }
            const next = n + delta * STEP;
            pointBudget.value = next < STEP ? '' : String(next);
        }
        pointBudget.addEventListener('keydown', function (e) {
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                adjustBudget(1);
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                adjustBudget(-1);
            }
        });
        pointBudgetUp?.addEventListener('click', () => adjustBudget(1));
        pointBudgetDown?.addEventListener('click', () => adjustBudget(-1));
    }
})();
