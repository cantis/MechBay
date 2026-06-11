# Macro and Partial Checklist

Before finishing a Jinja partial or macro refactor, check the following.

## Extraction quality
- Was a truly repeated pattern extracted?
- Did the extraction reduce duplication meaningfully?
- Is the new shared block easier to maintain than the repeated markup?

## Abstraction level
- Is the macro or partial simple enough to understand quickly?
- Does it avoid too many optional flags and edge cases?
- Would a future developer understand when to use it?

## Includes vs macros
- Was an include used for a structural fragment?
- Was a macro used for a compact reusable element?
- Was the right tool chosen?

## Naming
- Are filenames clear?
- Are macro names explicit and specific?
- Do parameter names make sense?

## Bootstrap consistency
- Do shared blocks render Bootstrap 5 classes consistently?
- Are spacing and validation styles preserved?
- Are button and badge patterns aligned across pages?

## Accessibility
- Are labels still associated with inputs?
- Are error states still readable?
- Are buttons and links clearly labeled?
- Does the abstraction preserve sensible HTML structure?

## Technical fit
- Does the new structure match the app's existing template organization?
- Are context variables passed clearly?
- Did the refactor avoid introducing hidden dependencies on implicit context where possible?

## Business logic boundary
- Is business logic still outside templates?
- Did the macro stay focused on display logic only?
- Were authorization or domain rules left in the view/service layer?

## Verification
- Do all updated templates still render?
- Do forms still post the correct field names?
- Do action links still target the correct routes?
- Do empty states, flash messages, and pagination still work?