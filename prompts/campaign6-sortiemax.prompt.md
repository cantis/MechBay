## Prompt 6 Addendum — Aces Sortie Maximum PV

Add an explicit **Maximum Point Value** to Aces Sortie Setup.

This applies to `aces` Campaigns only.

### Sortie Maximum PV

Each Aces Sortie must store a `max_sortie_pv` or equivalent field.

This represents the maximum Alpha Strike Point Value the Player Force may field for that specific Sortie.

The value is entered/resolved during Sortie Setup before the Sortie Force is finalized.

Do not derive the historical Sortie limit later from current Campaign state.

### Required before Ready

An Aces Sortie cannot transition to `Ready` unless:

- Maximum PV is present
- Maximum PV is greater than zero
- all selected units have valid PV
- selected Sortie Force PV is less than or equal to Maximum PV

### Sortie Force builder

Display prominently:

- `Selected PV`
- `Maximum PV`
- `Remaining PV`

Example:

`Selected: 284 PV / Maximum: 300 PV / Remaining: 16 PV`

### Enforcement

When adding a unit:

- calculate the resulting Sortie Force PV
- reject the addition if it would exceed Maximum PV
- show a clear validation message

Example:

`Cannot add Phoenix Hawk PHX-3PL: Sortie force would be 312 / 300 PV.`

Do not allow intentionally over-limit Planning forces.

Validate again when moving the Sortie to `Ready`.

### Missing PV

A Campaign Unit with no valid Alpha Strike PV cannot be added to an Aces Sortie Force.

Do not treat missing PV as zero.

### Omni configuration

If an Omni unit changes configuration during Sortie Setup:

- update the configuration snapshot
- use the selected configuration's PV
- recalculate Sortie Force total immediately
- prevent Ready state if the reconfiguration pushes the force above Maximum PV

### Named Pilots

Named Pilot Skill must not alter unit PV for Sortie-limit calculation.

Use the standard unit PV from MUL/configuration data.

### Difficulty integration

Campaign Difficulty and experienced-force modifiers may be used to calculate or suggest an appropriate Maximum PV.

However, once the Sortie's Maximum PV is set, that stored value is authoritative for force validation and historical reporting.

Do not silently recalculate a past Sortie's PV limit if Campaign Difficulty or pilot SP later changes.

### Sortie Report

Include:

- Maximum PV
- Actual fielded PV

Example:

`Player Force: 287 / 300 PV`

Preserve these values historically.

### Tests

Add or update tests for:

- Aces Sortie requires Maximum PV before Ready
- Maximum PV must be positive
- selected force may equal Maximum PV
- adding a unit above Maximum PV is rejected
- missing-PV unit is rejected
- Omni reconfiguration recalculates selected PV
- Omni reconfiguration cannot leave Ready force above Maximum PV
- Named Pilot Skill does not modify force PV
- historical Sortie Report preserves Maximum PV
- Chaos Sortie behaviour remains unchanged