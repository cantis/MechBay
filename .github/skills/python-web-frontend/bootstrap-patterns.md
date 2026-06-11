# Bootstrap Patterns for Python Web Apps

## Standard page shell
```html
{% extends 'base.html' %}

{% block content %}
<div class="container py-4">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <div>
            <h1 class="h3 mb-1">Page Title</h1>
            <p class="text-muted mb-0">Optional supporting text</p>
        </div>
        <div class="d-flex gap-2">
            <a href="#" class="btn btn-outline-secondary">Back</a>
            <a href="#" class="btn btn-primary">New Item</a>
        </div>
    </div>

    <div class="card shadow-sm border-0">
        <div class="card-body">
            Content here
        </div>
    </div>
</div>
{% endblock %}
```

## Standard form layout
```html
<form method="post" class="card shadow-sm border-0">
    <div class="card-body">
        <div class="row g-3">
            <div class="col-md-6">
                <label for="name" class="form-label">Name</label>
                <input id="name" name="name" class="form-control" required>
                <div class="form-text">Use a clear display name.</div>
            </div>

            <div class="col-md-6">
                <label for="status" class="form-label">Status</label>
                <select id="status" name="status" class="form-select">
                    <option>Active</option>
                    <option>Inactive</option>
                </select>
            </div>

            <div class="col-12">
                <label for="notes" class="form-label">Notes</label>
                <textarea id="notes" name="notes" rows="5" class="form-control"></textarea>
            </div>
        </div>
    </div>
    <div class="card-footer bg-body border-0 d-flex gap-2 justify-content-end">
        <a href="#" class="btn btn-outline-secondary">Cancel</a>
        <button type="submit" class="btn btn-primary">Save</button>
    </div>
</form>
```

## Standard table layout
```html
<div class="card shadow-sm border-0">
    <div class="card-body">
        <div class="table-responsive">
            <table class="table table-striped table-hover align-middle mb-0">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Status</th>
                        <th>Updated</th>
                        <th class="text-end">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in items %}
                    <tr>
                        <td>
                            <div class="fw-semibold">{{ item.name }}</div>
                            <div class="text-muted small">{{ item.description }}</div>
                        </td>
                        <td><span class="badge text-bg-secondary">{{ item.status }}</span></td>
                        <td>{{ item.updated_at }}</td>
                        <td class="text-end">
                            <div class="btn-group btn-group-sm">
                                <a href="#" class="btn btn-outline-primary">View</a>
                                <a href="#" class="btn btn-outline-secondary">Edit</a>
                            </div>
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="4" class="text-center text-muted py-4">No records found.</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>
```

## Flash message block for Flask
```html
<div class="toast-container position-fixed top-0 end-0 p-3" style="z-index: 9999;">
    {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
    {% for category, message in messages %}
    <div class="toast align-items-center text-bg-{{ category }} border-0" role="alert" aria-live="assertive"
        aria-atomic="true">
        <div class="d-flex">
            <div class="toast-body">
                {{ message }}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    </div>
    {% endfor %}
    {% endif %}
    {% endwith %}
</div>
```



