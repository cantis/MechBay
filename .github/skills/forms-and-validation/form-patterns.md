# Form Patterns

## Standard form page shell

```html
{% extends 'base.html' %}

{% block content %}
<div class="container py-4">
    <div class="mb-4">
        <h1 class="h3 mb-1">{{ page_title }}</h1>
        {% if page_hint %}
        <p class="text-muted mb-0">{{ page_hint }}</p>
        {% endif %}
    </div>

    {% if form_errors %}
    <div class="alert alert-danger" role="alert">
        <div class="fw-semibold mb-2">Please correct the following:</div>
        <ul class="mb-0">
            {% for error in form_errors %}
            <li>{{ error }}</li>
            {% endfor %}
        </ul>
    </div>
    {% endif %}

    <form method="post" class="card shadow-sm border-0">
        <div class="card-body">
            <!-- fields -->
        </div>
        <div class="card-footer bg-body border-0 d-flex justify-content-end gap-2">
            <a href="{{ cancel_url }}" class="btn btn-outline-secondary">Cancel</a>
            <button type="submit" class="btn btn-primary">{{ submit_label or 'Save' }}</button>
        </div>
    </form>
</div>
{% endblock %}
```

## Manual field with sticky value and inline error

```html
<div class="mb-3">
    <label for="email" class="form-label">Email <span class="text-danger">*</span></label>
    <input
        type="email"
        id="email"
        name="email"
        value="{{ form_data.email if form_data else '' }}"
        class="form-control{% if field_errors and field_errors.get('email') %} is-invalid{% endif %}"
        aria-describedby="email-help{% if field_errors and field_errors.get('email') %} email-error{% endif %}"
        required
    >
    <div id="email-help" class="form-text">Use the employee's primary work email.</div>
    {% if field_errors and field_errors.get('email') %}
    <div id="email-error" class="invalid-feedback">
        {{ field_errors['email'][0] }}
    </div>
    {% endif %}
</div>
```

## Textarea with sticky value

```html
<div class="mb-3">
    <label for="notes" class="form-label">Notes</label>
    <textarea
        id="notes"
        name="notes"
        rows="5"
        class="form-control{% if field_errors and field_errors.get('notes') %} is-invalid{% endif %}"
    >{{ form_data.notes if form_data else '' }}</textarea>
    {% if field_errors and field_errors.get('notes') %}
    <div class="invalid-feedback">
        {{ field_errors['notes'][0] }}
    </div>
    {% endif %}
</div>
```

## Select with preserved selected value

```html
<div class="mb-3">
    <label for="status" class="form-label">Status</label>
    <select
        id="status"
        name="status"
        class="form-select{% if field_errors and field_errors.get('status') %} is-invalid{% endif %}"
    >
        <option value="">Choose status</option>
        <option value="active" {% if form_data and form_data.status == 'active' %}selected{% endif %}>Active</option>
        <option value="inactive" {% if form_data and form_data.status == 'inactive' %}selected{% endif %}>Inactive</option>
        <option value="archived" {% if form_data and form_data.status == 'archived' %}selected{% endif %}>Archived</option>
    </select>
    {% if field_errors and field_errors.get('status') %}
    <div class="invalid-feedback">
        {{ field_errors['status'][0] }}
    </div>
    {% endif %}
</div>
```

## Checkbox with preserved value

```html
<div class="form-check mb-3">
    <input
        class="form-check-input{% if field_errors and field_errors.get('is_active') %} is-invalid{% endif %}"
        type="checkbox"
        id="is_active"
        name="is_active"
        value="true"
        {% if form_data and form_data.is_active %}checked{% endif %}
    >
    <label class="form-check-label" for="is_active">
        Active record
    </label>
    {% if field_errors and field_errors.get('is_active') %}
    <div class="invalid-feedback d-block">
        {{ field_errors['is_active'][0] }}
    </div>
    {% endif %}
</div>
```

## Search and filter utility form

```html
<form method="get" class="card shadow-sm border-0 mb-4">
    <div class="card-body">
        <div class="row g-3">
            <div class="col-md-5">
                <label for="q" class="form-label">Search</label>
                <input
                    type="text"
                    id="q"
                    name="q"
                    value="{{ request.args.get('q', '') }}"
                    class="form-control"
                    placeholder="Search records"
                >
            </div>
            <div class="col-md-3">
                <label for="status" class="form-label">Status</label>
                <select id="status" name="status" class="form-select">
                    <option value="">All</option>
                    <option value="active" {% if request.args.get('status') == 'active' %}selected{% endif %}>Active</option>
                    <option value="inactive" {% if request.args.get('status') == 'inactive' %}selected{% endif %}>Inactive</option>
                </select>
            </div>
            <div class="col-md-4 d-flex align-items-end gap-2">
                <button type="submit" class="btn btn-primary">Apply</button>
                <a href="{{ reset_url }}" class="btn btn-outline-secondary">Reset</a>
            </div>
        </div>
    </div>
</form>
```

## File upload form

```html
<form method="post" enctype="multipart/form-data" class="card shadow-sm border-0">
    <div class="card-body">
        <div class="mb-3">
            <label for="document" class="form-label">Upload document</label>
            <input
                type="file"
                id="document"
                name="document"
                class="form-control{% if field_errors and field_errors.get('document') %} is-invalid{% endif %}"
                aria-describedby="document-help"
            >
            <div id="document-help" class="form-text">Accepted formats: PDF, DOCX. Maximum size: 10 MB.</div>
            {% if field_errors and field_errors.get('document') %}
            <div class="invalid-feedback">
                {{ field_errors['document'][0] }}
            </div>
            {% endif %}
        </div>
    </div>
    <div class="card-footer bg-body border-0 d-flex justify-content-end gap-2">
        <a href="{{ cancel_url }}" class="btn btn-outline-secondary">Cancel</a>
        <button type="submit" class="btn btn-primary">Upload</button>
    </div>
</form>
```

## WTForms example pattern

```html
<form method="post" novalidate class="card shadow-sm border-0">
    <div class="card-body">
        {{ form.hidden_tag() }}

        <div class="mb-3">
            {{ form.name.label(class='form-label') }}
            {{ form.name(class='form-control' + (' is-invalid' if form.name.errors else '')) }}
            {% if form.name.description %}
            <div class="form-text">{{ form.name.description }}</div>
            {% endif %}
            {% for error in form.name.errors %}
            <div class="invalid-feedback d-block">{{ error }}</div>
            {% endfor %}
        </div>

        <div class="mb-3">
            {{ form.email.label(class='form-label') }}
            {{ form.email(class='form-control' + (' is-invalid' if form.email.errors else '')) }}
            {% for error in form.email.errors %}
            <div class="invalid-feedback d-block">{{ error }}</div>
            {% endfor %}
        </div>
    </div>

    <div class="card-footer bg-body border-0 d-flex justify-content-end gap-2">
        <a href="{{ cancel_url }}" class="btn btn-outline-secondary">Cancel</a>
        {{ form.submit(class='btn btn-primary') }}
    </div>
</form>
```

## Confirmation form for destructive action

```html
{% extends 'base.html' %}

{% block content %}
<div class="container py-4">
    <div class="row justify-content-center">
        <div class="col-lg-6">
            <form method="post" class="card shadow-sm border-0">
                <div class="card-body">
                    <h1 class="h4 text-danger mb-3">Confirm Delete</h1>
                    <p class="mb-3">
                        Type <strong>{{ expected_confirmation }}</strong> to confirm deletion of
                        <strong>{{ record_name }}</strong>.
                    </p>

                    <div class="mb-3">
                        <label for="confirmation_text" class="form-label">Confirmation</label>
                        <input
                            type="text"
                            id="confirmation_text"
                            name="confirmation_text"
                            value="{{ form_data.confirmation_text if form_data else '' }}"
                            class="form-control{% if field_errors and field_errors.get('confirmation_text') %} is-invalid{% endif %}"
                            required
                        >
                        {% if field_errors and field_errors.get('confirmation_text') %}
                        <div class="invalid-feedback">
                            {{ field_errors['confirmation_text'][0] }}
                        </div>
                        {% endif %}
                    </div>
                </div>
                <div class="card-footer bg-body border-0 d-flex justify-content-end gap-2">
                    <a href="{{ cancel_url }}" class="btn btn-outline-secondary">Cancel</a>
                    <button type="submit" class="btn btn-danger">Delete</button>
                </div>
            </form>
        </div>
    </div>
</div>
{% endblock %}
```