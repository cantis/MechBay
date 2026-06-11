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

    const modal = document.getElementById('variantPickerModal');
    const subtitle = document.getElementById('variantPickerSubtitle');
    const loading = document.getElementById('variantPickerLoading');
    const errorEl = document.getElementById('variantPickerError');
    const table = document.getElementById('variantPickerTable');
    const tbody = document.getElementById('variantPickerBody');

    function showLoading() {
        loading.classList.remove('d-none');
        errorEl.classList.add('d-none');
        table.classList.add('d-none');
        tbody.innerHTML = '';
    }

    function showError(message) {
        loading.classList.add('d-none');
        errorEl.textContent = message;
        errorEl.classList.remove('d-none');
        table.classList.add('d-none');
    }

    function showUnits(units) {
        loading.classList.add('d-none');
        errorEl.classList.add('d-none');
        tbody.innerHTML = '';

        if (!units.length) {
            showError('No variants found for this chassis with the current era and faction.');
            return;
        }

        units.forEach(unit => {
            const tr = document.createElement('tr');
            const pv = unit.point_value > 0 ? unit.point_value : '—';
            tr.innerHTML = `
                <td><strong>${unit.variant}</strong></td>
                <td>${unit.class_name}</td>
                <td>${unit.unit_type_name || ''}</td>
                <td>${unit.tonnage}</td>
                <td>${pv}</td>
                <td><button type="button" class="btn btn-sm btn-primary pick-variant-btn"
                    data-mul-id="${unit.id}">Select</button></td>
            `;
            tbody.appendChild(tr);
        });

        table.classList.remove('d-none');

        tbody.querySelectorAll('.pick-variant-btn').forEach(btn => {
            btn.addEventListener('click', function () {
                assignVariant(parseInt(this.dataset.mulId, 10));
            });
        });
    }

    function openPicker(fmId, chassis) {
        currentFmId = fmId;
        currentChassis = chassis;
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
                    location.reload();
                } else {
                    showError(data.error || 'Failed to assign variant');
                }
            })
            .catch(() => showError('Network error while assigning variant'));
    }

    document.querySelectorAll('.assign-variant-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            openPicker(parseInt(this.dataset.fmId, 10), this.dataset.chassis);
        });
    });
})();
