---
name: forms-and-validation
description: Use this skill when building or refining forms and validation flows for Flask or FastAPI applications using Bootstrap 5 and server-rendered templates. Covers labels, layout, sticky values, field errors, validation summaries, confirmation flows, and accessible business-style forms.
---

# Forms and Validation Skill

This skill is for server-rendered forms in Python web applications.

Target stack:
- Flask or FastAPI
- Jinja or similar server-rendered templates
- Bootstrap 5
- Clean, simple, business-style UI

Use this skill when the task involves:
- create/edit forms
- search/filter forms
- validation feedback
- sticky form values after failed submission
- confirmation prompts
- field help text
- inline errors
- form organization and readability
- WTForms or manual request/form handling
- file upload forms
- boolean/status fields
- destructive confirmation inputs

## Core assumptions

- Forms are workflow surfaces, not decorative UI.
- The user should always understand:
  - what is required
  - what failed
  - what to fix next
  - whether their previous input was preserved
- Validation belongs in backend logic, but templates must render validation clearly.
- Form pages should be predictable across the application.

## Design principles

- Prefer clarity over compactness.
- Keep labels visible.
- Preserve user input on validation failure whenever possible.
- Show errors beside the field and optionally in a summary block.
- Use help text only where it reduces confusion.
- Keep required fields obvious, but do not overload the screen with warning text.
- Use consistent button order and placement.

## Form structure rules

A standard form page should include:
- page title
- short supporting hint when useful
- validation summary when errors exist
- grouped fields
- clear footer actions

For longer forms:
- group related inputs into sections
- use cards or headings
- avoid very long uninterrupted field stacks when sections would help

## Labels and inputs

Every meaningful field should have:
- a visible label
- a stable `id`
- a matching `name`
- a suitable input type
- help text only if needed

Prefer:
- text input for short text
- textarea for notes and descriptions
- select for constrained options
- checkbox or switch for boolean values
- date/time input types when supported by the app and browser expectations

Do not rely on placeholder text as the only label.

## Required fields

Required inputs should be:
- marked consistently
- validated on the backend
- visually understandable without clutter

A simple convention such as `*` on labels is acceptable if used consistently.

## Validation feedback rules

When validation fails:
- keep the submitted values in the form where safe
- highlight invalid fields
- show a clear field-level error message
- optionally show a top summary for multiple errors
- avoid vague messages like `Invalid input`

Good validation feedback is:
- specific
- brief
- actionable

Examples:
- `Email is required.`
- `Start date must be before end date.`
- `Password must be at least 12 characters.`

## Sticky values

After failed submission:
- text fields should preserve submitted values
- textarea content should be preserved
- selected options should remain selected
- checkbox/radio state should remain preserved
- file inputs usually cannot be safely repopulated by the browser, so explain this if relevant

This is a key quality bar for business forms.

## Field error display

Prefer Bootstrap 5 invalid styles when practical:
- `is-invalid` on invalid inputs
- `.invalid-feedback` for field error text

For non-field or cross-field errors:
- show a summary alert near the top of the form

## Help text

Help text should:
- appear below the input
- be muted and short
- clarify format, meaning, or consequences

Do not add help text for obvious fields.

## Button rules

Preferred order:
- primary submit action
- secondary cancel/back action
- destructive action separately, if needed

Labels should be explicit:
- `Save`
- `Create Employee`
- `Update Settings`
- `Cancel`
- `Archive Record`

Avoid vague labels like `Submit`.

## Search and filter forms

Search/filter forms should:
- be compact
- preserve current selections
- support reset/clear
- avoid over-complication

These are utility forms, not full data entry forms.

## WTForms expectations

If WTForms is in use:
- respect the existing form class structure
- render field errors cleanly
- do not duplicate validation rules into templates
- use macros where repetition is high

## Manual form handling expectations

If the app uses manual request parsing:
- preserve posted values through explicit template context
- keep validation rules in routes/services/forms, not templates
- ensure error dictionaries or messages map predictably to fields

## File upload forms

For file uploads:
- ensure `multipart/form-data` is used
- explain accepted file types when needed
- validate file presence/type/size on the backend
- display failures clearly
- do not pretend file selections were preserved after failure

## Accessibility and UX

Always check:
- labels are associated to inputs
- errors are readable and near the field
- the page can be understood without relying on color alone
- keyboard tab order is sensible
- headings and groups make sense

## Flask/FastAPI expectations

For Flask:
- support flash messages where relevant
- align with WTForms or existing request handling
- preserve Blueprint/template conventions

For FastAPI:
- follow current Jinja/template organization
- preserve route parameter and form field expectations
- keep validation rendering thin and explicit

## Output expectations

When applying this skill:
1. identify the form type
2. inspect current handling and validation flow
3. preserve field names and posted values
4. improve error rendering and structure
5. keep the result simple and consistent
6. provide quick verification steps

See also:
- `form-patterns.md`
- `validation-checklist.md`