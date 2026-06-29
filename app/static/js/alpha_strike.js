/**
 * alpha_strike.js — Variant picker and Alpha Strike assignment UI.
 */
(function () {
    const ctx = document.getElementById('forceContext');
    if (!ctx) return;

    const forceId = ctx.dataset.forceId;
    const csrf = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    let currentFmId = null;
    let currentChassis = null;
    let currentLanceId = null;
    let loadedUnits = [];
    let selectedUnitId = null;

    const modal = document.getElementById('variantPickerModal');
    const subtitle = document.getElementById('variantPickerSubtitle');
    const loading = document.getElementById('variantPickerLoading');
    const errorEl = document.getElementById('variantPickerError');
    const content = document.getElementById('variantPickerContent');
    const tbody = document.getElementById('variantPickerBody');
    const cardPanel = document.getElementById('variantCardPanel');

    function showLoading() {
        loading.classList.remove('d-none');
        errorEl.classList.add('d-none');
        content.classList.add('d-none');
        tbody.innerHTML = '';
        resetCardPanel();
    }

    function showError(message) {
        loading.classList.add('d-none');
        errorEl.textContent = message;
        errorEl.classList.remove('d-none');
        content.classList.add('d-none');
    }

    function resetCardPanel() {
        selectedUnitId = null;
        cardPanel.innerHTML = '';
        const hint = document.createElement('p');
        hint.className = 'text-muted text-center mb-0 small';
        hint.textContent = 'Click a variant row to preview its Alpha Strike card.';
        cardPanel.append(hint);
    }

    function statValue(value) {
        if (value === null || value === undefined || value === '') return '—';
        return String(value);
    }

    function formatDamage(value, isMin) {
        if (value === null || value === undefined) return '—';
        if (value === 0 && !isMin) return '0';
        return isMin ? `${value}+` : String(value);
    }

    function cardStats(unit) {
        return unit && typeof unit.card === 'object' && unit.card !== null ? unit.card : unit || {};
    }

    function cardStat(unit, key) {
        const card = cardStats(unit);
        if (card[key] !== undefined && card[key] !== null && card[key] !== '') {
            return card[key];
        }
        return unit ? unit[key] : undefined;
    }

    function buildStatTable(headers, values) {
        const table = document.createElement('table');
        table.className = 'table table-sm table-bordered as-stat-table mb-2';
        const headRow = table.createTHead().insertRow();
        headers.forEach(label => {
            const th = document.createElement('th');
            th.scope = 'col';
            th.textContent = label;
            headRow.appendChild(th);
        });
        const valueRow = table.createTBody().insertRow();
        values.forEach(value => {
            const td = document.createElement('td');
            td.textContent = typeof value === 'string' ? value : statValue(value);
            valueRow.appendChild(td);
        });
        return table;
    }

    function renderCard(unit) {
        cardPanel.innerHTML = '';
        const card = cardStats(unit);

        if (card.image_url) {
            const imgWrap = document.createElement('div');
            imgWrap.className = 'text-center mb-2';
            const img = document.createElement('img');
            img.src = card.image_url;
            img.alt = unit.name;
            img.className = 'img-fluid rounded';
            img.style.maxHeight = '120px';
            imgWrap.append(img);
            cardPanel.append(imgWrap);
        }

        const title = document.createElement('h6');
        title.className = 'mb-1 text-dark';
        title.textContent = unit.variant || unit.name;
        cardPanel.append(title);

        const sub = document.createElement('div');
        sub.className = 'small text-muted mb-3';
        sub.textContent = [unit.class_name, unit.role, unit.tonnage ? `${unit.tonnage} tons` : null]
            .filter(Boolean)
            .join(' · ');
        cardPanel.append(sub);

        cardPanel.append(
            buildStatTable(
                ['MV', 'TMM', 'ARM', 'STR', 'TH'],
                [
                    cardStat(unit, 'bf_move'),
                    cardStat(unit, 'bf_tmm'),
                    cardStat(unit, 'bf_armor'),
                    cardStat(unit, 'bf_structure'),
                    cardStat(unit, 'bf_threshold'),
                ]
            )
        );

        const damageTable = buildStatTable(
            ['S', 'M', 'L', 'E'],
            [
                formatDamage(cardStat(unit, 'damage_short'), cardStat(unit, 'damage_short_min')),
                formatDamage(cardStat(unit, 'damage_medium'), cardStat(unit, 'damage_medium_min')),
                formatDamage(cardStat(unit, 'damage_long'), cardStat(unit, 'damage_long_min')),
                formatDamage(cardStat(unit, 'damage_extreme'), cardStat(unit, 'damage_extreme_min')),
            ]
        );
        damageTable.classList.add('as-damage-table');
        cardPanel.append(damageTable);

        const extras = document.createElement('div');
        extras.className = 'small mb-3 text-dark';

        const ov = document.createElement('div');
        const ovLabel = document.createElement('span');
        ovLabel.className = 'text-muted';
        ovLabel.textContent = 'Overheat: ';
        ov.append(ovLabel, document.createTextNode(statValue(cardStat(unit, 'bf_overheat'))));
        extras.append(ov);

        const special = document.createElement('div');
        const specialLabel = document.createElement('span');
        specialLabel.className = 'text-muted';
        specialLabel.textContent = 'Special: ';
        special.append(specialLabel, document.createTextNode(statValue(cardStat(unit, 'bf_abilities'))));
        extras.append(special);
        cardPanel.append(extras);

        const metaParts = [card.rules, card.tro, card.rs].filter(Boolean);
        if (metaParts.length) {
            const meta = document.createElement('div');
            meta.className = 'small text-muted mb-2';
            meta.textContent = metaParts.join(' · ');
            cardPanel.append(meta);
        }

        const pv = document.createElement('div');
        pv.className = 'fs-4 fw-bold text-primary mb-3';
        pv.textContent = unit.point_value > 0 ? `${unit.point_value} PV` : 'PV not available';
        cardPanel.append(pv);

        const actions = document.createElement('div');
        actions.className = 'd-flex gap-2 flex-wrap';
        const selectBtn = document.createElement('button');
        selectBtn.type = 'button';
        selectBtn.className = 'btn btn-primary btn-sm';
        selectBtn.textContent = 'Select this variant';
        selectBtn.addEventListener('click', () => assignVariant(unit.id));
        actions.append(selectBtn);

        if (card.mul_url) {
            const mulLink = document.createElement('a');
            mulLink.href = card.mul_url;
            mulLink.target = '_blank';
            mulLink.rel = 'noopener noreferrer';
            mulLink.className = 'btn btn-outline-secondary btn-sm';
            mulLink.textContent = 'View on MUL';
            actions.append(mulLink);
        }
        cardPanel.append(actions);
    }

    function unitFromRow(row) {
        if (row && row.dataset.unit) {
            try {
                return JSON.parse(row.dataset.unit);
            } catch {
                /* fall through */
            }
        }
        const unitId = row ? parseInt(row.dataset.unitId, 10) : NaN;
        return loadedUnits.find(u => u.id === unitId);
    }

    function selectRow(unitId) {
        selectedUnitId = unitId;
        let selectedRow = null;
        tbody.querySelectorAll('tr').forEach(row => {
            const isSelected = parseInt(row.dataset.unitId, 10) === unitId;
            row.classList.toggle('table-active', isSelected);
            if (isSelected) selectedRow = row;
        });
        const unit = unitFromRow(selectedRow) || loadedUnits.find(u => u.id === unitId);
        if (unit) renderCard(unit);
    }

    function showUnits(units) {
        loading.classList.add('d-none');
        errorEl.classList.add('d-none');
        tbody.innerHTML = '';
        loadedUnits = units;

        if (!units.length) {
            showError('No variants found for this chassis with the current era and faction.');
            return;
        }

        units.forEach(unit => {
            const tr = document.createElement('tr');
            tr.dataset.unitId = String(unit.id);
            tr.dataset.unit = JSON.stringify(unit);
            tr.style.cursor = 'pointer';
            tr.title = 'Click to preview Alpha Strike card';

            const pv = unit.point_value > 0 ? unit.point_value : '—';

            [unit.variant, unit.class_name, unit.unit_type_name || '', String(unit.tonnage), String(pv)].forEach(
                text => {
                    const td = document.createElement('td');
                    if (text === unit.variant) {
                        const strong = document.createElement('strong');
                        strong.textContent = text;
                        td.append(strong);
                    } else {
                        td.textContent = text;
                    }
                    tr.append(td);
                }
            );

            const actionTd = document.createElement('td');
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'btn btn-sm btn-primary pick-variant-btn';
            btn.textContent = 'Select';
            btn.addEventListener('click', e => {
                e.stopPropagation();
                assignVariant(unit.id);
            });
            actionTd.append(btn);
            tr.append(actionTd);

            tr.addEventListener('click', () => selectRow(unit.id));
            tbody.append(tr);
        });

        content.classList.remove('d-none');
        selectRow(units[0].id);
    }

    function openPicker(fmId, chassis, lanceId) {
        currentFmId = fmId;
        currentChassis = chassis;
        currentLanceId = lanceId;
        subtitle.textContent = `Variants for ${chassis} (filtered by force era and faction)`;
        showLoading();
        bootstrap.Modal.getOrCreateInstance(modal).show();

        fetch(`/forces/${forceId}/alpha-strike/variants?fm_id=${fmId}`)
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    showUnits(data.units);
                } else {
                    showError(data.error || 'Failed to load variants');
                }
            })
            .catch(() => showError('Network error while searching Master Unit List'));
    }

    function assignVariant(mulUnitId) {
        fetch(`/forces/${forceId}/alpha-strike/assign`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
            body: JSON.stringify({
                force_miniature_id: currentFmId,
                mul_unit_id: mulUnitId,
                search_name: currentChassis,
            }),
        })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    const modalInstance = bootstrap.Modal.getInstance(modal);
                    if (modalInstance) modalInstance.hide();
                    const anchor = currentLanceId ? `lance-${currentLanceId}` : 'lances';
                    sessionStorage.setItem('mechbayScrollTo', anchor);
                    window.location.reload();
                } else {
                    showError(data.error || 'Failed to assign variant');
                }
            })
            .catch(() => showError('Network error while assigning variant'));
    }

    document.addEventListener('click', function (event) {
        const btn = event.target.closest('.assign-variant-btn');
        if (!btn) return;
        openPicker(
            parseInt(btn.dataset.fmId, 10),
            btn.dataset.chassis,
            parseInt(btn.dataset.lanceId, 10)
        );
    });
})();
