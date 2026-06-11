---
name: jinja-partials-and-macros
description: Use this skill when building or refactoring reusable Jinja partials, includes, and macros for Flask or FastAPI applications using Bootstrap 5. Covers page headers, flash messages, form fields, action bars, badges, tables, pagination, and consistency-focused template reuse.
---

# Jinja Partials and Macros Skill

This skill is for creating and refining reusable template building blocks in Flask or FastAPI projects.

Target stack:
- Flask or FastAPI
- Jinja templates
- Bootstrap 5
- Clean, simple, business-style UI

Use this skill when the task involves:
- extracting repeated template markup
- creating shared partials or includes
- building reusable Jinja macros
- standardizing page headers
- standardizing form field rendering
- standardizing flash message rendering
- standardizing action bars
- standardizing badges and status display
- standardizing table row actions
- standardizing pagination controls

## Core assumptions

- Repetition in templates creates drift.
- Shared UI patterns should be extracted when they appear multiple times.
- Macros and partials should reduce duplication without becoming overly abstract.
- Template reuse should improve readability, not hide everything behind indirection.

## Design principles

- Prefer simple, obvious reuse.
- Extract only patterns that are actually repeated or clearly reusable.
- Keep macros focused and small.
- Use includes for structural fragments.
- Use macros for repeated HTML elements that vary by parameters.
- Do not build a complex template framework inside Jinja.

## When to use includes vs macros

Prefer an include when:
- the fragment is mostly static structure
- the fragment represents a larger section of a page
- the included template is readable as a standalone block
- the context is already naturally available

Examples:
- flash messages block
- page header section
- delete confirmation panel
- pagination section
- shared navbar fragment

Prefer a macro when:
- the fragment is repeated many times
- it takes a small number of parameters
- it renders a specific element or compact component
- consistent rendering matters across the application

Examples:
- form field rendering
- status badge rendering
- action button groups
- table row actions
- compact metadata rows

## Good macro characteristics

A good macro is:
- small
- readable
- explicit about inputs
- easy to call
- not overloaded with dozens of options

Avoid macros that:
- simulate full component frameworks
- require too many boolean flags
- hide business logic
- become harder to understand than the original HTML

## Naming rules

Use clear names:
- `render_text_input`
- `render_textarea`
- `render_select`
- `render_checkbox`
- `render_status_badge`
- `render_page_actions`
- `render_pagination`

Avoid vague names like:
- `render_field`
- `widget`
- `thing`

Unless the abstraction is truly generic and still readable.

## Folder organization

A reasonable structure is:

- `templates/macros/forms.html`
- `templates/macros/ui.html`
- `templates/macros/tables.html`
- `templates/partials/_flash_messages.html`
- `templates/partials/_page_header.html`
- `templates/partials/_pagination.html`

Use the project’s existing template layout if one already exists.

## Form macro rules

Form macros should:
- render label, control, help text, and errors consistently
- support Bootstrap 5 validation classes
- preserve accessibility basics
- avoid hiding field names or ids from the caller when that matters

If WTForms is used:
- macros may wrap WTForms fields directly

If manual form handling is used:
- macros should accept explicit values, errors, labels, ids, and names

## Page header partial rules

A shared page header partial should support:
- page title
- optional subtitle or supporting text
- optional action area
- clean Bootstrap spacing

Do not make the header partial overly dynamic.

## Flash message partial rules

A shared flash partial should:
- support standard categories
- render messages consistently
- align with existing Flask message conventions
- stay near the top of page content

## Table/action macro rules

Shared table/action helpers should:
- keep row actions consistent
- avoid clutter
- preserve route clarity
- not hide too much navigation logic

## Pagination rules

A pagination partial or macro should:
- render consistently across list pages
- preserve current query parameters when needed
- remain simple and readable
- not attempt to solve every pagination shape in one abstraction

## Business logic boundary

Do not put business logic into macros or partials.

Allowed:
- display logic
- conditional rendering for visual states
- simple parameter-based variation

Not allowed:
- domain rules
- data fetching behavior
- authorization logic beyond simple visibility conditions already prepared by the view

## Refactoring workflow

When applying this skill:
1. inspect templates for repeated patterns
2. identify what should become a partial vs a macro
3. extract the smallest useful reusable unit
4. update calling templates for consistency
5. keep names and parameters explicit
6. avoid over-abstraction
7. provide quick verification steps

## Output expectations

When using this skill:
- state what repeated pattern was extracted
- identify new partials/macros created
- note affected templates
- explain any naming or structure assumptions
- provide a quick manual verification path

See also:
- `macro-patterns.md`
- `macro-checklist.md`