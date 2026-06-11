# CRUD Checklist

Before finishing a CRUD UI change, check the following.

## Page type
- Is this a list, detail, create, edit, or destructive confirmation page?
- Does the page match the expected CRUD pattern for that screen type?

## List pages
- Is the page title clear?
- Is the primary `New` action easy to find?
- Are the displayed columns useful and not excessive?
- Are row actions consistent?
- Is there an empty state?
- Are search and filters actually useful?

## Detail pages
- Is the record clearly identified?
- Are primary actions near the top?
- Is metadata grouped cleanly?
- Does the page avoid looking like a raw dump of fields?

## Forms
- Do labels exist for all fields?
- Are field names consistent with backend expectations?
- Is field order stable and sensible?
- Are validation errors and help text visible?
- Are save and cancel actions placed consistently?

## Destructive actions
- Is delete/archive visually separated from normal save actions?
- Is confirmation explicit?
- Is the destructive action clearly labeled?

## Styling
- Is Bootstrap 5 doing most of the work?
- Is spacing consistent?
- Is custom CSS minimal?

## UX
- Is the page easy to scan quickly?
- Is the main action obvious?
- Is there unnecessary clutter?
- Would an admin user understand what to do immediately?

## Technical fit
- Does the template extend the correct base?
- Are existing includes/macros reused?
- Are routes, URLs, and form methods correct?
- Are context variables present and named consistently?

## Verification
- Does the page render without missing values?
- Does create/edit submit successfully?
- Does the cancel path go somewhere sensible?
- Does archive/delete require confirmation?
- Does the layout still work on smaller screens?