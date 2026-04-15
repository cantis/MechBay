# Validation Checklist

Before finishing a forms or validation task, check the following.

## Structure
- Does the page clearly indicate what the form is for?
- Are fields grouped logically?
- Is the button area consistent with the rest of the app?

## Labels and fields
- Does every meaningful input have a visible label?
- Are `id` and `name` stable and correct?
- Is the input type appropriate for the data?

## Required fields
- Are required fields marked consistently?
- Is required validation enforced on the backend?

## Sticky values
- After a validation failure, are user-entered values preserved?
- Do selected options remain selected?
- Do checkbox/radio values remain preserved?
- Is file upload behavior handled honestly?

## Validation feedback
- Are invalid fields visually marked?
- Are field-level messages present and understandable?
- Are cross-field or general errors shown near the top?
- Are error messages specific and actionable?

## Help text
- Is help text present only where useful?
- Is it short and understandable?

## Buttons and actions
- Is the primary action clearly labeled?
- Is cancel/back available where appropriate?
- Are destructive actions visually separated?

## Accessibility
- Are labels associated with inputs?
- Can errors be understood without relying only on color?
- Is keyboard flow reasonable?
- Are heading and section structures sensible?

## Technical fit
- Are field names aligned with backend expectations?
- Are templates using the existing Flask/FastAPI conventions?
- Is validation logic kept out of the template?

## Verification
- Does the form render with blank initial values correctly?
- Does it render existing values correctly for edit mode?
- Does invalid submission show the expected feedback?
- Does valid submission succeed cleanly?
- Does the layout remain usable on smaller screens?