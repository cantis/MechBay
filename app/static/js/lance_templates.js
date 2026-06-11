/**
 * lance_templates.js — JavaScript for the lance template create/edit forms.
 */
(function () {
    let chassisCount = document.querySelectorAll('[name^="chassis_"]').length || 1;

    window.addChassisField = function () {
        const container = document.getElementById('chassis-list');
        const div = document.createElement('div');
        div.className = 'input-group mb-2';

        const input = document.createElement('input');
        input.type = 'text';
        input.name = `chassis_${chassisCount}`;
        input.className = 'form-control';
        input.placeholder = 'Chassis pattern';
        input.required = true;
        div.appendChild(input);

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-outline-danger';
        btn.onclick = function () { removeChassisField(this); };
        const icon = document.createElement('i');
        icon.className = 'fa-solid fa-times';
        btn.appendChild(icon);
        div.appendChild(btn);

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
