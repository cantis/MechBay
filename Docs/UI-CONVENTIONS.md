# MechBay UI Conventions

Read this file before changing template structure, Jinja includes, flash message behaviour, JavaScript interaction patterns, or icon usage.

See `docs/DESIGN.md` for visual identity: colors, typography, spacing tokens, and component styling rules.

## Libraries

| Library       | Version | How loaded      |
|---------------|---------|-----------------|
| Bootstrap     | 5.3.3   | CDN (SRI hash)  |
| Font Awesome  | 6.4.0   | CDN (SRI hash)  |
| SortableJS    | latest  | CDN             |

No build pipeline. All custom CSS goes in `app/static/css/`; all custom JS goes in `app/static/js/`. Bootstrap and Font Awesome are loaded exclusively from CDN — do not bundle them locally.

## Base Template (`base.html`)

All pages extend `base.html`. It provides:

- Bootstrap CSS and JS (CDN, SRI-hashed)
- Font Awesome CSS (CDN, SRI-hashed)
- CSRF meta tag: `<meta name="csrf-token" content="{{ csrf_token() }}">`
- Navbar include: `{% include 'navbar.html' %}`
- Flash message toast container (top-right, auto-dismisses after **6 seconds**)
- `{% block content %}` for page body

### Extending base.html

```html
{% extends 'base.html' %}
{% block content %}
<div class="row">
  <!-- page content — container is already applied by base.html -->
</div>
{% endblock %}
```

There is one content block. Do not add new layout blocks without updating all existing templates.

## Navbar (`navbar.html`)

Nav items in fixed order:

1. **File** — inventory and force document open/save
2. **Inventory** → `miniatures.list_miniatures`
3. **Forces** → `forces.list_forces`
4. **Lance Templates** → `lance_templates.list_templates`
5. **About** → `about`

The current inventory filename appears at the top right of the navbar (truncated on small screens). Brand link goes to **Inventory**. Use `bg-body-tertiary border-bottom` on `<nav>` and `container-fluid` inside.

## Flash Messages

Flash messages appear in the top-right toast container in `base.html`.

**Category → Bootstrap alert class:**

| Flask category | Bootstrap class  |
|----------------|-----------------|
| `"success"`    | `alert-success` |
| `"danger"`     | `alert-danger`  |
| `"warning"`    | `alert-warning` |
| `"info"`       | `alert-info`    |

Always include `alert-dismissible fade show` classes and a close button. Messages auto-dismiss after 6 seconds.

**AJAX pattern**: When a route sets a flash message and the caller is JSON (AJAX), set the flash **before** the `if is_json` check. JavaScript uses `setTimeout(() => location.reload(), 100)` to allow the flash to persist across the reload.

## Page Layout Conventions

- The `<main class="container py-4">` wrapper is in `base.html` — do not add another `.container` inside `{% block content %}`
- Use `.row` / `.col-*` for multi-column layouts
- Page title: one `<h2>` per page
- Section headings inside cards: `<h5>` or `<h6>`
- Data tables: `.table.table-hover.table-sm` with a `.table-responsive` wrapper
- Inline / table-row action buttons: `.btn-sm`
- Primary form submit buttons: full-size `.btn`

## Icons

Use Font Awesome 6 solid icons (`fas` shorthand). Standard icon assignments:

| Purpose              | Icon class              |
|----------------------|-------------------------|
| File / save document | `fas fa-floppy-disk`    |
| Add / create         | `fas fa-plus`           |
| Edit                 | `fas fa-pencil`         |
| Delete / remove      | `fas fa-trash`          |
| Activate / confirm   | `fas fa-check-circle`   |
| Jeff's BT Tools      | `fas fa-file-export`    |
| Force / army         | `fas fa-shield-halved`  |
| Miniature / mech     | `fas fa-robot`          |
| Lance template       | `fas fa-layer-group`    |

## SortableJS Drag-and-Drop

The Forces detail page uses SortableJS for reordering miniatures between lances.

Pattern:
1. Render miniatures in `<div data-miniature-id="...">` elements within each lance container
2. Initialise `Sortable` on each lance container with `group: "lances"` to allow cross-lance dragging
3. On `onEnd` callback: collect the new order and POST to the reorder endpoint
4. Update the UI optimistically (move the DOM element) before the POST completes
5. On error, reload the page to restore server state

Always include the CSRF token from `<meta name="csrf-token">` in all fetch POST calls:

```javascript
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
fetch(url, {
    method: 'POST',
    headers: { 'X-CSRFToken': csrfToken, 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
});
```

## Inline Editable Elements

Lance names are editable inline on the Forces detail page.

Pattern:
- Elements with class `.editable-lance-name` are double-click editable
- On `dblclick`: call `prompt()` to get the new name
- On confirm: `fetch()` POST to the rename endpoint, update DOM text on success
- On error: fallback to `alert()` or display an inline error message

## Error Pages

All error pages use `app/templates/error.html`. Template variables:

| Variable  | Type   | Example                  |
|-----------|--------|--------------------------|
| `code`    | int    | `404`                    |
| `title`   | string | `"Page Not Found"`       |
| `message` | string | `"The page you..."`      |
| `icon`    | string | `"fas fa-circle-question"` |
| `color`   | string | `"warning"`              |

Error handlers in `create_app()` render this template for browser requests and return a JSON envelope for API requests (see `docs/ARCHITECTURE.md`).

## JavaScript Files

Per-area JS files in `app/static/js/`:

| File                  | Loaded by                  | Responsibility                           |
|-----------------------|----------------------------|------------------------------------------|
| `forces.js`           | `forces/detail.html`       | SortableJS init, lance rename, AJAX ops  |
| `lance_templates.js`  | `lance_templates/*.html`   | Template form interactions               |
| `miniatures.js`       | `miniatures/list.html`     | Filter/sort, AJAX miniature actions      |

Load per-page JS at the bottom of the extending template body, not in `base.html`:

```html
{% block scripts %}
<script src="{{ url_for('static', filename='js/forces.js') }}"></script>
{% endblock %}
```

Add `{% block scripts %}{% endblock %}` to `base.html` before the closing `</body>` if this pattern is not yet in place.
