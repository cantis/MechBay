## Prompt 6 Addendum — Aces Campaign Time and Location Cleanup

Adjust the Aces campaign workflow so that Chaos-specific campaign time and location fields remain fully supported for Chaos Campaigns but are not required or shown for Aces Campaigns.

This is a ruleset-specific UI and validation change only.

Do not remove the existing Campaign fields from the shared model if Chaos Campaigns still rely on them.

### Aces progression model

For the current Aces ruleset, campaign progression is **Sortie-based**, not month/travel based.

An Aces Campaign should not require:

- starting year
- starting month
- current campaign month
- starting location
- current location
- travel history
- Contracts

The attached Aces campaign rules track Player Force, Named Pilots, Sorties, SP/Warchest, purchases, Story Keywords, and persistent campaign consequences, but do not require the Chaos-style strategic calendar/location/contract layer.

Use the Sortie sequence and real-world `date_played` for campaign history instead.

### Campaign creation

When creating an Aces Campaign:

- do not require starting year
- do not require starting month
- do not require starting location
- do not initialize or validate Chaos travel/location state
- do not require a Contract
- do not require current campaign month

The Aces Campaign creation form should focus on Aces-relevant setup such as:

- campaign name
- ruleset = Aces
- Campaign Difficulty
- Player Force
- Named Pilots
- starting Warchest derived from unused starting PV where applicable
- notes

Do not show irrelevant Chaos fields in the Aces creation flow.

### Aces Campaign detail UI

For Aces Campaigns, hide or omit UI for:

- starting year
- starting month
- current campaign month
- starting location
- current location
- Travel Events
- Contracts
- Contract roster
- Contract Scale
- employer
- transportation terms
- Contract Support
- monthly processing / Advance Month

Do not show empty placeholders for these fields.

The Aces Campaign summary should instead emphasize:

- Player Force
- active Player Force PV
- Named Pilots
- Warchest
- Campaign Difficulty
- Story Keywords
- Sortie History
- Next Sortie / Next Steps
- campaign notes

### Sortie dates

Keep the real-world Sortie `date_played` field for Aces.

This is the primary chronological date used in Aces campaign reporting.

Display `date_played` in:

- Campaign Sortie History
- Sortie Report
- Pilot Service History

Do not derive Aces chronology from Campaign Month.

### Aces services and validation

Aces services must not depend on Chaos time/location fields being populated.

Review Aces-specific code for assumptions such as:

- `current_campaign_month` must exist
- Campaign must have a location
- Sortie must belong to a Contract
- Travel must exist before a Sortie
- monthly processing drives availability

Remove or bypass those assumptions for Aces only.

If a shared historical/event model currently requires a campaign-month value, refactor that requirement cleanly so Aces events can use:

- Sortie relationship
- event sequence
- real-world `date_played`
- created timestamp

without inventing a fake campaign month.

Do not populate Aces Campaigns with dummy values such as:

- month = 1
- year = 0
- location = `"N/A"`

Prefer nullable/not-applicable semantics where needed.

### Chaos Campaign behaviour must remain unchanged

For `chaos` Campaigns, preserve all existing behaviour involving:

- starting year/month
- current campaign month
- starting/current location
- Travel Events
- Contracts
- Contract Scale
- transportation
- maintenance
- monthly processing
- location history

Do not weaken Chaos validation simply because those fields are optional for Aces.

Ruleset-specific validation should enforce:

- Chaos Campaign => existing Chaos requirements
- Aces Campaign => no time/location/Contract requirements

### Shared model guidance

Do not split Campaign into separate `ChaosCampaign` and `AcesCampaign` tables solely for this change.

Prefer:

- nullable shared fields where appropriate
- ruleset-aware validation
- ruleset-aware UI
- ruleset-aware services

Avoid broad schema redesign unless required by an existing non-null database constraint.

If a shared database column must become nullable to support Aces, add the necessary migration while preserving existing Chaos data.

### Reporting

Aces Campaign reporting should order Sorties using stable historical ordering such as:

1. Sortie sequence/number
2. replay attempt
3. real-world `date_played`

Do not use Campaign Month as the Aces report chronology.

Pilot Service History should likewise use:

- pilot creation
- Sortie sequence
- `date_played`
- advancement/injury/history events

### Tests

Add or update tests for at least:

- Aces Campaign can be created without starting year
- Aces Campaign can be created without starting month
- Aces Campaign can be created without starting location
- Aces Campaign does not require current campaign month
- Aces Campaign does not require Contract
- Aces Campaign UI does not show Chaos time/location controls
- Aces Sortie history uses `date_played`
- Aces Pilot Service History works without campaign-month data
- Aces After-Sortie processing does not require campaign location/time
- Chaos Campaign still requires/uses its existing time/location/Contract workflow
- existing Chaos travel/month tests continue to pass

Run the full pytest suite and Ruff after the change.

Do not accept regressions to Chaos Campaign support.

### Completion criteria

This change is complete when:

- Aces Campaigns are cleanly Sortie-based
- no fake month/year/location data is required for Aces
- real-world Sortie dates provide the campaign chronology
- Chaos Campaign time/location/travel/Contract behaviour remains intact
- shared models remain maintainable without duplicating the Campaign domain