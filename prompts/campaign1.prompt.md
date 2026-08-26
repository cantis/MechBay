# MechBay Campaign Support — Prompt 1: Core Campaign Model

Update MechBay to introduce the persistent Campaign domain without yet implementing contracts, sorties, after-action processing, or repairs.

## Goals

Add the core persistent campaign structures needed to support BattleTech mercenary campaign play.

The existing application already has:

* physical miniature inventory
* MUL integration
* Force Builder
* MUL variant selection
* faction restrictions

Do not break or replace those existing features.

## Campaign

Add a `Campaign` concept representing a persistent mercenary command/campaign.

A Campaign should support at least:

* name
* status
* current campaign month
* optional starting BattleTech month/year for display
* current location
* starting/current Warchest
* Reputation
* Scale
* notes
* source saved Force used when the Campaign was created

Creating a Campaign from an existing saved Force should snapshot/copy the selected force members into Campaign Units.

The Campaign must not continue to depend directly on the saved Force after creation.

## Campaign Units

Add a persistent `CampaignUnit` concept.

A Campaign Unit represents the fictional in-universe unit participating in the campaign and is distinct from:

* the physical MechBay miniature
* the saved Force Builder entry

A Campaign Unit should retain references where appropriate to:

* Campaign
* physical miniature
* MUL chassis/unit
* selected MUL variant/configuration

Also support:

* current operational condition
* availability
* active / retired / destroyed state
* notes

For most units, the MUL variant selected when the Campaign is created should be treated as fixed.

For Omni units, design the model so their current configuration can later be changed between sorties. Do not yet implement Omni reconfiguration workflow.

Do not attach campaign damage state to the physical miniature record.

## Named Pilots

Add `CampaignPilot` / Named Pilot support.

A pilot belongs to the Campaign, not to the physical miniature.

Support at least:

* name
* callsign
* Gunnery
* Piloting
* Alpha Strike Skill where appropriate
* Edge tokens
* Edge Abilities
* improvement SP tracking
* wounds / injury state
* alive / dead / retired state
* notes
* preferred/default Campaign Unit

The preferred/default Campaign Unit is only a convenience. It must not represent a permanent assignment.

Do not yet implement sortie assignment.

## Warchest Ledger

Add a Campaign Warchest transaction ledger.

Do not rely only on an editable balance field.

Each transaction should support:

* campaign month
* transaction type
* description
* gross amount
* covered amount where applicable
* actual paid/received amount
* resulting balance
* optional references to related campaign entities
* notes

The Campaign may cache the current balance, but transaction history should be preserved.

## Campaign Time

Campaign time should be abstracted to months.

Support a numeric current campaign month.

Optional starting BattleTech month/year may be used to derive a display value such as:

`Campaign Month 4 — July 3152`

Do not implement day-level dates.

Advancing the campaign month should eventually become an explicit operation, but full monthly processing is out of scope for this prompt.

## Location History and Travel

The Campaign has a current location, but location must also have history.

Add a `TravelEvent` or equivalent concept that records:

* Campaign
* origin
* destination
* departure campaign month
* arrival campaign month
* number of jumps if known
* gross transportation cost
* covered amount
* actual Warchest impact
* notes

For now:

* origin/destination are manually entered
* jump count is manually entered
* do not build a BattleTech star-map or jump-route calculator

Updating/completing a Travel Event should update the Campaign's current location appropriately while preserving the historical event.

## UI

Add minimal Bootstrap/Jinja UI necessary to:

* create/view/edit Campaigns
* view Campaign roster
* manage Named Pilots
* inspect Warchest history
* inspect location/travel history

Keep the UI consistent with the existing MechBay application.

## Tests

Add pytest coverage for:

* Campaign creation from a saved Force
* Campaign Unit snapshot behaviour
* Named Pilot preferred unit behaviour
* Warchest transaction/balance logic
* campaign month handling
* Travel Event creation and location update

Do not implement Contracts, Sorties, After Action, Repair Orders, pilot healing workflows, Omni reconfiguration workflows, salvage workflows, or PDF reporting in this phase.
