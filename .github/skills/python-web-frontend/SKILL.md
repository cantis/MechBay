---
name: python-web-frontend
description: Use this skill when working on Flask or FastAPI front ends using Bootstrap 5 with a clean, simple style. Covers layouts, forms, tables, partials, navigation, validation, and light styling.
---

# Python Web Frontend Skill

This skill is for frontend work in Python web applications that use:
- Flask or FastAPI
- Server-rendered templates, usually Jinja
- Bootstrap 5
- A clean, simple visual style

Use this skill when the task involves:
- page layout
- template creation or cleanup
- forms
- tables and lists
- navbars and sidebars
- detail pages
- dashboard pages
- search/filter bars
- flash/status messages
- pagination
- responsive improvements
- light CSS refinement

## Core design rules

- Prefer server-rendered HTML over adding frontend framework complexity.
- Use Bootstrap 5 first; write custom CSS only when Bootstrap utilities are not enough.
- Keep the interface clean, quiet, and functional.
- Favor consistency over cleverness.
- Prefer readable spacing and obvious hierarchy.
- Avoid over-designed gradients, shadows, or dense control clusters.
- Use semantic HTML.

## Visual style

The desired style is:
- neutral
- professional
- uncluttered
- readable
- lightly structured

Default layout approach:
- centered container or container-fluid depending on data density
- page header with title and optional action buttons
- content divided into cards or clearly spaced sections
- restrained use of accent color
- muted secondary text for metadata and hints

## Bootstrap guidance

Prefer these patterns:
- `container` or `container-fluid`
- `row` / `col-*` grid for layout
- `card` for grouped content
- `table table-striped table-hover` for data tables when appropriate
- `btn btn-primary`, `btn btn-outline-secondary`, `btn btn-sm`
- `form-label`, `form-control`, `form-select`, `form-text`
- `alert` for flash messages and important status
- `badge` for lightweight status indicators
- spacing via utilities like `mb-3`, `mt-4`, `py-2`, `gap-2`

Avoid:
- deep nesting without purpose
- excessive inline styles
- mixing many button variants in one area
- custom CSS for what Bootstrap already solves
- icon dependence unless the project already uses an icon set

## Template structure rules

For Flask:
- respect `base.html`
- reuse existing includes and macros
- keep Blueprint template organization intact

For FastAPI:
- check how `Jinja2Templates` is configured
- follow current template directory conventions
- preserve route/template naming consistency

When creating a page, prefer:
1. extending the shared base template
2. defining a clear content block
3. adding a page header section
4. grouping related content into sections or cards
5. keeping per-page scripts minimal

## Form rules

Every form should:
- have visible labels
- preserve backend field names
- show validation errors clearly
- group related fields logically
- include help text only where it reduces ambiguity
- use appropriate input types
- use consistent button placement

For edit/create forms:
- primary action first
- secondary cancel/back action nearby
- destructive actions visually separated

## Table rules

Tables should:
- have clear column names
- avoid too many columns
- align actions consistently
- use truncation carefully for long text
- move metadata to smaller muted text where useful
- support empty states

When a table gets dense:
- consider a compact summary card list on small screens
- consider moving minor actions into a details page

## Detail page rules

A good detail page should contain:
- title and key identifiers
- primary actions near the top
- metadata in a compact section
- main content in one obvious reading flow
- related items in secondary sections

## Flash/status messaging

For Flask flash messages or equivalent:
- success -> `alert-success`
- warning -> `alert-warning`
- error -> `alert-danger`
- info -> `alert-info`

Messages should be:
- visible near the top of main content
- dismissible only if that matches the existing app style

## CSS rules

If custom CSS is necessary:
- keep it in a small dedicated file or existing site stylesheet
- prefer class-based styling
- do not style elements globally unless the codebase already does
- avoid magic numbers where possible
- do not override Bootstrap broadly without reason

## Accessibility and UX

Always check:
- labels are associated with inputs
- buttons have clear text
- links are distinguishable
- heading order is sensible
- contrast remains readable
- keyboard flow is reasonable

## Workflow

When using this skill:
1. inspect the current template/layout structure
2. identify reuse points
3. implement the smallest coherent UI change
4. verify route names, form names, and template inheritance
5. note any assumptions
6. recommend a quick manual test path

## Deliverable format

When completing a task, provide:
- what changed
- files changed
- any assumptions
- quick verification steps

See also:
- `bootstrap-patterns.md`
- `frontend-checklist.md`