# MechBay Campaign Support — Prompt 2: Contracts and Sorties

Extend the Campaign system added in the previous phase with Contracts and Sorties.

Do not redesign the existing Campaign, CampaignUnit, CampaignPilot, Warchest ledger, campaign month, or TravelEvent concepts unless required to support this phase cleanly.

## Contract

Add `Contract` as a first-class Campaign entity.

A Campaign may have many historical Contracts and normally one active Contract.

Support at least:

* Campaign
* contract name
* contract number
* employer
* destination/location
* type of action
* Scale
* length in months
* start campaign month
* end campaign month
* Base Pay percentage
* Support percentage
* Transportation percentage
* Salvage rights
* Command rights
* status
* notes

Contract fields should be user-editable because not every campaign will use identical rules.

## Contract Force

When accepting/activating a Contract, support selecting which Campaign Units are committed to it.

This is distinct from the force later selected for an individual Sortie.

Units not brought on the Contract should remain part of the Campaign but unavailable for its Sorties.

Preserve Contract Scale independently from Sortie Scale.

## Contract Accounting

Use the existing Warchest ledger.

Support the general pattern:

`gross amount -> contract coverage -> actual Campaign/Warchest impact`

Use that pattern for transportation and prepare the model for later repair/support costs.

Do not assume employer transportation payment always equals actual transportation expense.

## Travel to Contract

Allow a Contract to have a destination.

Use the existing TravelEvent system for movement from the Campaign's current location to the Contract location.

A Contract may pay some, all, or none of the transportation expense.

Do not make location history part of the Contract itself; it remains Campaign history.

## Sortie

Add `Sortie` as MechBay's term for one tabletop battle.

Document that a Sortie is equivalent to a Track in Hot Spots: Draconis Reach / Chaos Campaign terminology.

A Sortie normally belongs to:

* Campaign
* active Contract

Support at least:

* name/title
* campaign month
* Contract
* Sortie Scale
* scenario/track type
* location
* notes
* outcome
* status

Suggested lifecycle:

`Planning -> Ready -> Fought -> After Action -> Closed`

Do not yet implement full After Action processing.

## Sortie Force

Build a Sortie force from Campaign Units committed to the Contract.

Only currently available Campaign Units may be selected.

Support:

* selected Campaign Units
* current MUL variant/configuration snapshot
* named pilot assignment
* generic/default crew where no named pilot is assigned
* preferred/default pilot/unit pairing as a suggested preselection
* ability to override any preferred pairing

A pilot must not be permanently attached to a unit.

The Sortie record should snapshot the actual pilot/unit/configuration used so later Campaign changes do not alter historical Sorties.

## Availability

Prepare the Sortie builder to exclude units/pilots that are unavailable.

Do not yet implement the full repair/healing system; use the availability state already present in the Campaign model.

## Scale

Keep Contract Scale separate from Sortie Scale.

The Sortie Scale must not exceed the Contract Scale.

Integrate with the existing MUL/PV/BV force-building behaviour where possible rather than duplicating it.

## Notes

Support free-form notes on both:

* Contract
* Sortie

These notes should be retained for eventual campaign-history/report generation.

## UI

Add screens/workflows for:

* create/edit/view Contracts
* activate/complete Contracts
* select Contract force
* create a Sortie
* prepare Sortie force
* assign pilots
* mark Sortie as fought

Keep styling consistent with the existing Bootstrap application.

## Tests

Add tests for:

* Contract creation/history
* one active Contract behaviour where applicable
* Contract force selection
* Contract Scale vs Sortie Scale
* transportation coverage calculation
* Sortie creation
* eligible unit filtering
* named pilot assignment
* preferred unit preselection
* Sortie snapshot behaviour

Do not yet implement After Action damage, Repair Orders, healing, salvage processing, Omni reconfiguration, monthly automation, or PDF reports.
