
# Frontend Checklist

Before finishing a frontend task, check:

## Structure
- Does the template extend the correct base?
- Are existing partials/macros reused?
- Is the page broken into clear sections?

## Styling
- Is Bootstrap 5 doing most of the work?
- Is spacing consistent?
- Is custom CSS minimal and local?

## Forms
- Do labels exist for each input?
- Do names/ids match backend expectations?
- Are validation and help text visible where needed?

## Data display
- Is the table or list readable?
- Is there an empty state?
- Are actions easy to find?

## UX
- Is the main action obvious?
- Is secondary navigation clear?
- Does the page feel clean rather than crowded?

## Technical fit
- Does this match Flask/FastAPI conventions already in the repo?
- Were route names, template names, and field bindings preserved?
- Did we avoid pushing logic into the template?

## Verification
- Can the page render without missing context variables?
- Do forms submit to the correct endpoint?
- Does the layout still work on narrower screens?