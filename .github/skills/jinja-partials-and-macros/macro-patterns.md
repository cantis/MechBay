# Jinja Macro and Partial Patterns

## Suggested template structure

```text
templates/
├─ base.html
├─ macros/
│  ├─ forms.html
│  ├─ ui.html
│  └─ tables.html
└─ partials/
   ├─ _flash_messages.html
   ├─ _page_header.html
   └─ _pagination.html
```

## Partial: flash messages

```html
{# templates/partials/_flash_messages.html #}
{% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
        <div class='mb-4'>
            {% for category, message in messages %}
                <div class='alert alert-{{ category }} alert-dismissible fade show' role='alert'>
                    {{ message }}
                    <button type='button' class='btn-close' data-bs-dismiss='alert' aria-label='Close'></button>
                </div>
            {% endfor %}
        </div>
    {% endif %}
{% endwith %}
```

Usage:

```html
{% include 'partials/_flash_messages.html' %}
```

## Partial: page header

```html
{# templates/partials/_page_header.html #}
<div class='d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3 mb-4'>
    <div>
        <h1 class='h3 mb-1'>{{ page_title }}</h1>
        {% if page_subtitle %}
        <p class='text-muted mb-0'>{{ page_subtitle }}</p>
        {% endif %}
    </div>

    {% if page_actions %}
    <div class='d-flex gap-2'>
        {{ page_actions|safe }}
    </div>
    {% endif %}
</div>
```

Usage:

```html
{% set page_title = 'Employees' %}
{% set page_subtitle = 'Manage employee records and status.' %}
{% set page_actions %}
<a href="{{ url_for('employees.create') }}" class='btn btn-primary'>New Employee</a>
{% endset %}
{% include 'partials/_page_header.html' %}
```

## Partial: pagination

```html
{# templates/partials/_pagination.html #}
{% if pagination %}
<div class='d-flex justify-content-between align-items-center mt-4'>
    <small class='text-muted'>
        Showing {{ pagination.start }}-{{ pagination.end }} of {{ pagination.total }}
    </small>

    <nav aria-label='Pagination'>
        <ul class='pagination pagination-sm mb-0'>
            {% if pagination.has_prev %}
            <li class='page-item'>
                <a class='page-link' href='{{ pagination.prev_url }}'>Previous</a>
            </li>
            {% endif %}

            {% if pagination.has_next %}
            <li class='page-item'>
                <a class='page-link' href='{{ pagination.next_url }}'>Next</a>
            </li>
            {% endif %}
        </ul>
    </nav>
</div>
{% endif %}
```

Usage:

```html
{% include 'partials/_pagination.html' %}
```

## Macro file: forms

```html
{# templates/macros/forms.html #}
{% macro render_text_input(name, label, value='', type='text', required=false, help_text='', errors=None, id=None) %}
    {% set field_id = id or name %}
    {% set has_errors = errors and errors.get(name) %}
    <div class='mb-3'>
        <label for='{{ field_id }}' class='form-label'>
            {{ label }}{% if required %} <span class='text-danger'>*</span>{% endif %}
        </label>
        <input
            type='{{ type }}'
            id='{{ field_id }}'
            name='{{ name }}'
            value='{{ value }}'
            class='form-control{% if has_errors %} is-invalid{% endif %}'
            {% if required %}required{% endif %}
        >
        {% if help_text %}
        <div class='form-text'>{{ help_text }}</div>
        {% endif %}
        {% if has_errors %}
        <div class='invalid-feedback'>
            {{ errors[name][0] }}
        </div>
        {% endif %}
    </div>
{% endmacro %}

{% macro render_textarea(name, label, value='', rows=5, help_text='', errors=None, id=None) %}
    {% set field_id = id or name %}
    {% set has_errors = errors and errors.get(name) %}
    <div class='mb-3'>
        <label for='{{ field_id }}' class='form-label'>{{ label }}</label>
        <textarea
            id='{{ field_id }}'
            name='{{ name }}'
            rows='{{ rows }}'
            class='form-control{% if has_errors %} is-invalid{% endif %}'
        >{{ value }}</textarea>
        {% if help_text %}
        <div class='form-text'>{{ help_text }}</div>
        {% endif %}
        {% if has_errors %}
        <div class='invalid-feedback'>
            {{ errors[name][0] }}
        </div>
        {% endif %}
    </div>
{% endmacro %}

{% macro render_select(name, label, options, selected='', help_text='', errors=None, id=None) %}
    {% set field_id = id or name %}
    {% set has_errors = errors and errors.get(name) %}
    <div class='mb-3'>
        <label for='{{ field_id }}' class='form-label'>{{ label }}</label>
        <select
            id='{{ field_id }}'
            name='{{ name }}'
            class='form-select{% if has_errors %} is-invalid{% endif %}'
        >
            {% for option_value, option_label in options %}
            <option value='{{ option_value }}' {% if option_value == selected %}selected{% endif %}>
                {{ option_label }}
            </option>
            {% endfor %}
        </select>
        {% if help_text %}
        <div class='form-text'>{{ help_text }}</div>
        {% endif %}
        {% if has_errors %}
        <div class='invalid-feedback'>
            {{ errors[name][0] }}
        </div>
        {% endif %}
    </div>
{% endmacro %}

{% macro render_checkbox(name, label, checked=false, errors=None, id=None) %}
    {% set field_id = id or name %}
    {% set has_errors = errors and errors.get(name) %}
    <div class='form-check mb-3'>
        <input
            type='checkbox'
            id='{{ field_id }}'
            name='{{ name }}'
            value='true'
            class='form-check-input{% if has_errors %} is-invalid{% endif %}'
            {% if checked %}checked{% endif %}
        >
        <label for='{{ field_id }}' class='form-check-label'>{{ label }}</label>
        {% if has_errors %}
        <div class='invalid-feedback d-block'>
            {{ errors[name][0] }}
        </div>
        {% endif %}
    </div>
{% endmacro %}
```

Usage:

```html
{% from 'macros/forms.html' import render_text_input, render_textarea, render_select, render_checkbox %}

{{ render_text_input('name', 'Name', value=form_data.name if form_data else '', required=true, errors=field_errors) }}

{{ render_text_input('email', 'Email', value=form_data.email if form_data else '', type='email', required=true, errors=field_errors) }}

{{ render_select('status', 'Status', [('active', 'Active'), ('inactive', 'Inactive')], selected=form_data.status if form_data else '', errors=field_errors) }}

{{ render_checkbox('is_active', 'Active record', checked=form_data.is_active if form_data else false, errors=field_errors) }}

{{ render_textarea('notes', 'Notes', value=form_data.notes if form_data else '', errors=field_errors) }}
```

## Macro file: UI helpers

```html
{# templates/macros/ui.html #}
{% macro render_status_badge(status) %}
    {% if status == 'active' %}
    <span class='badge text-bg-success'>Active</span>
    {% elif status == 'inactive' %}
    <span class='badge text-bg-secondary'>Inactive</span>
    {% elif status == 'pending' %}
    <span class='badge text-bg-warning'>Pending</span>
    {% elif status == 'archived' %}
    <span class='badge text-bg-dark'>Archived</span>
    {% else %}
    <span class='badge text-bg-light'>{{ status }}</span>
    {% endif %}
{% endmacro %}

{% macro render_action_buttons(view_url=None, edit_url=None, delete_url=None) %}
    <div class='btn-group btn-group-sm'>
        {% if view_url %}
        <a href='{{ view_url }}' class='btn btn-outline-primary'>View</a>
        {% endif %}
        {% if edit_url %}
        <a href='{{ edit_url }}' class='btn btn-outline-secondary'>Edit</a>
        {% endif %}
        {% if delete_url %}
        <a href='{{ delete_url }}' class='btn btn-outline-danger'>Delete</a>
        {% endif %}
    </div>
{% endmacro %}
```

Usage:

```html
{% from 'macros/ui.html' import render_status_badge, render_action_buttons %}

<td>{{ render_status_badge(employee.status) }}</td>
<td class='text-end'>
    {{ render_action_buttons(
        view_url=url_for('employees.detail', employee_id=employee.id),
        edit_url=url_for('employees.edit', employee_id=employee.id)
    ) }}
</td>
```

## Example list page using shared pieces

```html
{% extends 'base.html' %}
{% from 'macros/ui.html' import render_status_badge, render_action_buttons %}

{% block content %}
<div class='container py-4'>
    {% set page_title = 'Employees' %}
    {% set page_subtitle = 'Manage employee records and status.' %}
    {% set page_actions %}
    <a href="{{ url_for('employees.create') }}" class='btn btn-primary'>New Employee</a>
    {% endset %}
    {% include 'partials/_page_header.html' %}

    {% include 'partials/_flash_messages.html' %}

    <div class='card shadow-sm border-0'>
        <div class='card-body'>
            <div class='table-responsive'>
                <table class='table table-striped table-hover align-middle mb-0'>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Status</th>
                            <th class='text-end'>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for employee in employees %}
                        <tr>
                            <td>{{ employee.name }}</td>
                            <td>{{ render_status_badge(employee.status) }}</td>
                            <td class='text-end'>
                                {{ render_action_buttons(
                                    view_url=url_for('employees.detail', employee_id=employee.id),
                                    edit_url=url_for('employees.edit', employee_id=employee.id)
                                ) }}
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan='3' class='text-center text-muted py-4'>No employees found.</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    {% include 'partials/_pagination.html' %}
</div>
{% endblock %}
```

## WTForms helper macro pattern

```html
{# templates/macros/wtforms.html #}
{% macro render_wtfield(field, help_text='') %}
    <div class='mb-3'>
        {{ field.label(class='form-label') }}
        {{ field(class='form-control' + (' is-invalid' if field.errors else '')) }}
        {% if help_text %}
        <div class='form-text'>{{ help_text }}</div>
        {% endif %}
        {% for error in field.errors %}
        <div class='invalid-feedback d-block'>{{ error }}</div>
        {% endfor %}
    </div>
{% endmacro %}
```

Usage:

```html
{% from 'macros/wtforms.html' import render_wtfield %}

{{ render_wtfield(form.name) }}
{{ render_wtfield(form.email, help_text='Use the employee work email.') }}
```