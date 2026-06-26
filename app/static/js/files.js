/** File menu actions for inventory (.mechbay) and force (.mbforce) documents. */

const INVENTORY_PICKER_TYPES = [
    {
        description: 'MechBay inventory',
        accept: { 'application/json': ['.mechbay', '.json'] },
    },
];

const FORCE_PICKER_TYPES = [
    {
        description: 'MechBay force',
        accept: { 'application/json': ['.mbforce', '.json'] },
    },
];

function csrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
}

function filePickerSupported() {
    return typeof window.showSaveFilePicker === 'function';
}

async function saveWithFilePicker(dialog) {
    const types =
        dialog.kind === 'inventory' ? INVENTORY_PICKER_TYPES : FORCE_PICKER_TYPES;
    let handle;
    try {
        handle = await window.showSaveFilePicker({
            suggestedName: dialog.default_name || 'Untitled.mechbay',
            types,
        });
    } catch (err) {
        if (err && err.name === 'AbortError') {
            return { cancelled: true };
        }
        throw err;
    }

    const exportUrl =
        dialog.kind === 'inventory'
            ? '/files/inventory/export'
            : `/files/force/${dialog.force_id}/export`;
    const response = await fetch(exportUrl);
    if (!response.ok) {
        window.alert('Failed to export file data.');
        return { cancelled: true };
    }
    const content = await response.text();
    const writable = await handle.createWritable();
    await writable.write(content);
    await writable.close();

    const saveUrl =
        dialog.kind === 'inventory'
            ? '/files/inventory/save-as'
            : `/files/force/${dialog.force_id}/save-as`;
    return postFileAction(saveUrl, { path: handle.name, client_saved: true });
}

async function openWithFilePicker(dialog) {
    const types =
        dialog.kind === 'inventory' ? INVENTORY_PICKER_TYPES : FORCE_PICKER_TYPES;
    let handles;
    try {
        handles = await window.showOpenFilePicker({ types, multiple: false });
    } catch (err) {
        if (err && err.name === 'AbortError') {
            return { cancelled: true };
        }
        throw err;
    }
    const file = await handles[0].getFile();
    const form = new FormData();
    form.append('csrf_token', csrfToken());
    form.append('file', file);
    const uploadUrl =
        dialog.kind === 'inventory' ? '/files/upload/inventory' : '/files/upload/force';
    return postFileAction(uploadUrl, form, { json: false });
}

async function handleClientDialog(payload) {
    // Browser File System Access API fallback when native dialogs are unavailable.
    if (!filePickerSupported()) {
        window.alert(
            'Use the upload menu item in your browser, or run the MechBay desktop app for native file dialogs.'
        );
        return payload;
    }
    if (payload.mode === 'save') {
        return saveWithFilePicker(payload);
    }
    if (payload.mode === 'open') {
        return openWithFilePicker(payload);
    }
    return payload;
}

async function postFileAction(url, body = {}, options = {}) {
    const useJson = options.json !== false;
    const headers = {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': csrfToken(),
        Accept: 'application/json',
    };
    if (useJson) {
        headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(url, {
        method: 'POST',
        headers,
        body: useJson ? JSON.stringify(body) : body,
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        if (payload.needs_confirm) {
            const proceed = window.confirm(
                payload.confirm_message ||
                    'You have unsaved changes. Continue without saving?'
            );
            if (proceed) {
                return postFileAction(url, { ...body, confirm: '1' }, options);
            }
            return { cancelled: true };
        }
        if (payload.cancelled) {
            return payload;
        }
        window.alert(payload.error || 'File action failed.');
        return payload;
    }

    if (payload.needs_client_dialog) {
        return handleClientDialog(payload);
    }

    if (payload.redirect) {
        window.location.href = payload.redirect;
        return payload;
    }
    if (options.reload !== false) {
        window.location.reload();
    }
    return payload;
}

async function saveInventory() {
    await postFileAction('/files/inventory/save', {});
}

async function saveInventoryAs() {
    await postFileAction('/files/inventory/save-as', {});
}

async function openInventory() {
    await postFileAction('/files/inventory/open', {});
}

async function newInventory() {
    await postFileAction('/files/inventory/new', {});
}

async function loadSampleData() {
    await postFileAction('/files/inventory/sample-data', {});
}

async function openInventoryUpload(input) {
    if (!input.files || !input.files[0]) {
        return;
    }
    const form = new FormData();
    form.append('csrf_token', csrfToken());
    form.append('file', input.files[0]);
    await postFileAction('/files/upload/inventory', form, { json: false });
    input.value = '';
}

async function openForce() {
    await postFileAction('/files/force/open', {});
}

async function openForceUpload(input) {
    if (!input.files || !input.files[0]) {
        return;
    }
    const form = new FormData();
    form.append('csrf_token', csrfToken());
    form.append('file', input.files[0]);
    await postFileAction('/files/upload/force', form, { json: false });
    input.value = '';
}

async function saveForce(forceId) {
    await postFileAction(`/files/force/${forceId}/save`, {});
}

async function saveForceAs(forceId) {
    await postFileAction(`/files/force/${forceId}/save-as`, {});
}

window.MechBayFiles = {
    saveInventory,
    saveInventoryAs,
    openInventory,
    newInventory,
    loadSampleData,
    openInventoryUpload,
    openForce,
    openForceUpload,
    saveForce,
    saveForceAs,
};
