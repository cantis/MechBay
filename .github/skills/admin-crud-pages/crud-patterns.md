# CRUD Page Patterns

## Standard list page

```html
{% extends 'base.html' %}

{% block content %}
<div class="container py-4">
    <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3 mb-4">
        <div>
            <h1 class="h3 mb-1">Employees</h1>
            <p class="text-muted mb-0">Manage employee records and status.</p>
        </div>
        <div>
            <a href="{{ url_for('employees.create') }}" class="btn btn-primary">New Employee</a>
        </div>
    </div>

    <div class="card shadow-sm border-0 mb-4">
        <div class="card-body">
            <form method="get" class="row g-3">
                <div class="col-md-5">
                    <label for="q" class="form-label">Search</label>
                    <input
                        type="text"
                        id="q"
                        name="q"
                        value="{{ request.args.get('q', '') }}"
                        class="form-control"
                        placeholder="Search by name or email"
                    >
                </div>
                <div class="col-md-3">
                    <label for="status" class="form-label">Status</label>
                    <select id="status" name="status" class="form-select">
                        <option value="">All</option>
                        <option value="active">Active</option>
                        <option value="inactive">Inactive</option>
                    </select>
                </div>
                <div class="col-md-4 d-flex align-items-end gap-2">
                    <button type="submit" class="btn btn-primary">Apply</button>
                    <a href="{{ url_for('employees.index') }}" class="btn btn-outline-secondary">Reset</a>
                </div>
            </form>
        </div>
    </div>

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
                        {% for employee in employees %}
                        <tr>
                            <td>
                                <div class="fw-semibold">{{ employee.name }}</div>
                                <div class="text-muted small">{{ employee.email }}</div>
                            </td>
                            <td>
                                {% if employee.is_active %}
                                <span class="badge text-bg-success">Active</span>
                                {% else %}
                                <span class="badge text-bg-secondary">Inactive</span>
                                {% endif %}
                            </td>
                            <td>{{ employee.updated_at.strftime('%Y-%m-%d') if employee.updated_at else '-' }}</td>
                            <td class="text-end">
                                <div class="btn-group btn-group-sm">
                                    <a href="{{ url_for('employees.detail', employee_id=employee.id) }}" class="btn btn-outline-primary">View</a>
                                    <a href="{{ url_for('employees.edit', employee_id=employee.id) }}" class="btn btn-outline-secondary">Edit</a>
                                </div>
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="4" class="text-center py-5">
                                <div class="text-muted mb-3">No employees found.</div>
                                <a href="{{ url_for('employees.create') }}" class="btn btn-primary">Create Employee</a>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        {% if pagination %}
        <div class="card-footer bg-body border-0 d-flex justify-content-between align-items-center">
            <small class="text-muted">
                Showing {{ pagination.start }}-{{ pagination.end }} of {{ pagination.total }}
            </small>
            <nav aria-label="Employees pagination">
                <ul class="pagination pagination-sm mb-0">
                    {% if pagination.has_prev %}
                    <li class="page-item">
                        <a class="page-link" href="{{ pagination.prev_url }}">Previous</a>
                    </li>
                    {% endif %}
                    {% if pagination.has_next %}
                    <li class="page-item">
                        <a class="page-link" href="{{ pagination.next_url }}">Next</a>
                    </li>
                    {% endif %}
                </ul>
            </nav>
        </div>
        {% endif %}
    </div>
</div>
{% endblock %}
```

## Standard detail page

```html
{% extends 'base.html' %}

{% block content %}
<div class="container py-4">
    <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-start gap-3 mb-4">
        <div>
            <div class="d-flex align-items-center gap-2 mb-2">
                <h1 class="h3 mb-0">{{ employee.name }}</h1>
                {% if employee.is_active %}
                <span class="badge text-bg-success">Active</span>
                {% else %}
                <span class="badge text-bg-secondary">Inactive</span>
                {% endif %}
            </div>
            <p class="text-muted mb-0">{{ employee.email }}</p>
        </div>
        <div class="d-flex gap-2">
            <a href="{{ url_for('employees.index') }}" class="btn btn-outline-secondary">Back</a>
            <a href="{{ url_for('employees.edit', employee_id=employee.id) }}" class="btn btn-primary">Edit</a>
        </div>
    </div>

    <div class="row g-4">
        <div class="col-lg-8">
            <div class="card shadow-sm border-0">
                <div class="card-body">
                    <h2 class="h5 mb-3">Details</h2>
                    <dl class="row mb-0">
                        <dt class="col-sm-3">Name</dt>
                        <dd class="col-sm-9">{{ employee.name }}</dd>

                        <dt class="col-sm-3">Email</dt>
                        <dd class="col-sm-9">{{ employee.email }}</dd>

                        <dt class="col-sm-3">Department</dt>
                        <dd class="col-sm-9">{{ employee.department or '-' }}</dd>

                        <dt class="col-sm-3">Created</dt>
                        <dd class="col-sm-9">{{ employee.created_at.strftime('%Y-%m-%d') if employee.created_at else '-' }}</dd>
                    </dl>
                </div>
            </div>
        </div>

        <div class="col-lg-4">
            <div class="card shadow-sm border-0">
                <div class="card-body">
                    <h2 class="h5 mb-3">Actions</h2>
                    <div class="d-grid gap-2">
                        <a href="{{ url_for('employees.edit', employee_id=employee.id) }}" class="btn btn-primary">Edit Record</a>
                        <a href="{{ url_for('employees.index') }}" class="btn btn-outline-secondary">Back to List</a>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

## Standard create/edit form

```html
{% extends 'base.html' %}

{% block content %}
<div class="container py-4">
    <div class="mb-4">
        <h1 class="h3 mb-1">{{ page_title }}</h1>
        <p class="text-muted mb-0">{{ page_hint }}</p>
    </div>

    <form method="post" class="card shadow-sm border-0">
        <div class="card-body">
            <div class="row g-3">
                <div class="col-md-6">
                    <label for="name" class="form-label">Name</label>
                    <input
                        type="text"
                        id="name"
                        name="name"
                        value="{{ form_data.name if form_data else '' }}"
                        class="form-control"
                        required
                    >
                </div>

                <div class="col-md-6">
                    <label for="email" class="form-label">Email</label>
                    <input
                        type="email"
                        id="email"
                        name="email"
                        value="{{ form_data.email if form_data else '' }}"
                        class="form-control"
                        required
                    >
                </div>

                <div class="col-md-6">
                    <label for="department" class="form-label">Department</label>
                    <input
                        type="text"
                        id="department"
                        name="department"
                        value="{{ form_data.department if form_data else '' }}"
                        class="form-control"
                    >
                </div>

                <div class="col-md-6">
                    <label for="is_active" class="form-label">Status</label>
                    <select id="is_active" name="is_active" class="form-select">
                        <option value="true">Active</option>
                        <option value="false">Inactive</option>
                    </select>
                </div>

                <div class="col-12">
                    <label for="notes" class="form-label">Notes</label>
                    <textarea id="notes" name="notes" rows="5" class="form-control">{{ form_data.notes if form_data else '' }}</textarea>
                </div>
            </div>
        </div>

        <div class="card-footer bg-body border-0 d-flex justify-content-end gap-2">
            <a href="{{ cancel_url }}" class="btn btn-outline-secondary">Cancel</a>
            <button type="submit" class="btn btn-primary">Save</button>
        </div>
    </form>

    {% if show_archive %}
    <div class="card shadow-sm border-0 mt-4">
        <div class="card-body">
            <h2 class="h5 text-danger">Danger Zone</h2>
            <p class="text-muted mb-3">Archive this record to remove it from active use without permanent deletion.</p>
            <form method="post" action="{{ archive_url }}">
                <button type="submit" class="btn btn-outline-danger">Archive Record</button>
            </form>
        </div>
    </div>
    {% endif %}
</div>
{% endblock %}
```

## Standard delete/archive confirmation

```html
{% extends 'base.html' %}

{% block content %}
<div class="container py-4">
    <div class="row justify-content-center">
        <div class="col-lg-6">
            <div class="card shadow-sm border-0">
                <div class="card-body">
                    <h1 class="h4 text-danger mb-3">Confirm Archive</h1>
                    <p class="mb-3">
                        You are about to archive <strong>{{ employee.name }}</strong>.
                    </p>
                    <p class="text-muted">
                        Archived records will no longer appear in normal active lists, but can still be retained for history if supported by the system.
                    </p>

                    <form method="post" class="d-flex justify-content-end gap-2 mt-4">
                        <a href="{{ cancel_url }}" class="btn btn-outline-secondary">Cancel</a>
                        <button type="submit" class="btn btn-danger">Archive</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```