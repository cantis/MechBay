/**
 * lance_templates.js — JavaScript for the lance template create/edit forms.
 */
(function () {
    let chassisCount = document.querySelectorAll('[name^="chassis_"]').length || 1;

    window.addChassisField = function () {
        const container = document.getElementById('chassis-list');
        const div = document.createElement('div');
        div.className = 'input-group mb-2';
        div.innerHTML = `
            <input type="text" name="chassis_${chassisCount}" class="form-control" placeholder="Chassis pattern" required>
            <button type="button" class="btn btn-outline-danger" onclick="removeChassisField(this)">
                <i class="fa-solid fa-times"></i>
            </button>
        `;
        container.appendChild(div);
        chassisCount++;
    };

    window.removeChassisField = function (button) {
        const container = document.getElementById('chassis-list');
        if (container && container.querySelectorAll('.input-group').length > 1) {
            button.closest('.input-group').remove();
        }
    };
})();
