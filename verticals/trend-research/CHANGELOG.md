# Changelog

## 1.2.0.0 (unreleased)

### Fixes

- **Designer line breaks removed.** `TR Collect RSS` → `Build_ItemKey` wrote the ItemKey as `<SourceID>|<entry id>` followed by a line break, and `TR Weekly Digest` → `Get_Existing_Publication` had a `$filter` that ended in one. Both values are now clean.
- **Variables set inside loops now run sequentially.** `TR Collect RSS` (`Loop`, `Apply_to_each`), `TR Classify Items` (`Loop`, `Loop_2`) and `TR Weekly Digest` (`Loop_Brief`, `Loop`) set variables inside loops that had no concurrency limit. If the engine ran their iterations in parallel, two iterations could overwrite each other's `ItemKey` or `AnalysisKey`. They now use `runtimeConfiguration.concurrency.repetitions: 1`. The outer `Loop` in Collect and Classify are included because they contain a loop that sets a variable.
- **Upgrade effect of the ItemKey fix: pending dev-tenant verification.** Which of these applies depends on whether an existing SourceItem's ItemKey (`field_3`) ends with a line break, and nobody has checked yet. Pick one before release:
  - *If the stored ItemKey ends with a line break:* the first Collect run after upgrading re-creates, once, the items that are still in the feeds, because the new key no longer matches the stored one.
  - *If it does not (SharePoint strips the line break on save):* the 1.1 dedupe filter never matched, and every Collect run has been creating duplicate SourceItems. Add a cleanup note: delete the duplicates, keeping the oldest item per ItemKey.

### Build

- The build now rejects flows that: use a literal site or list in a trigger; write to a path outside the known libraries; write to the library their own file trigger watches; set a variable from itself; change variables in a loop that is not sequential; or carry a stray trailing line break. New connector snippets live in `shared/flow-snippets/`.

## 1.1.0.0 (2026-11-02)

First version built from source. It replaces the UI-built solution `TrendResearchFlow` 1.0.0.2.

### Portability

- All flows read the site URL and list identifiers from environment variables. New variables: `tr_ResearchBriefsList`, `tr_SourcesList`, `tr_SourceItemsList`, `tr_SignalsList`, `tr_PublicationsList`. Their defaults are the localized list titles. `tr_SiteURL` is now required at import.
- `TR Classify Items` reads its per-run item cap from `tr_DailyClassificationLimit` (default 50, previously hardcoded to 10).
- Removed a tenant-specific content-type ID from `TR Collect RSS → Create SourceItem`.
- Removed the exporting tenant's connection IDs (`connectionName`) from every flow's connection references. Import binds each flow to the customer's connections through the connection references.
- Removed seven connection references that no flow used (2× Approvals, Outlook, 3× RSS, 1× SharePoint). Import now asks for four connections.
- Removed the designer graph (`metadata.associatedData`) from the flow source. See [architecture](../../docs/architecture.md#the-designer-graph).

### Fixes

- **Classifier never saw the brief.** The prompt's RESEARCH BRIEF and SOURCE ITEM sections were bound to the dedupe lookup result, which is always empty at that point. They now pass the brief's title, question, keywords, exclusions, languages, geographies and version, plus the item's title, URL, publication date and content status. The prompt version moves to **2**, which is recorded in `Signals.PromptVersion` and `AnalysisKey`. Signals created before this version were classified without the brief.
- The weekly digest no longer prints the unfilled `[ACTIVE SOURCE COUNT]` and `[WINDOW SIGNAL COUNT]` placeholders.

### Localization

- English (`_en`, 1033) and Spanish (`_es`, 3082) packages. Spanish name: **Vigilante de Tendencias**. Flows are named `VT Recolectar RSS`, `VT Clasificar Elementos` and `VT Resumen Semanal`.
- Localized: digest HTML, Teams message, impact and horizon labels, classifier output language (Summary/Limitations), environment variable labels and connection reference names.
- SharePoint kit, per locale, with two provisioning options: CSV-with-schema files (browser), or a PnP provisioning template + `provision.ps1` that creates lists and libraries with guaranteed internal names and verifies every column (`-VerifyOnly` also checks CSV-created lists).

### SharePoint schema

- `Publications.SentAt` is now Date and Time (it was Number after the Excel import). No flow writes it yet.
- Dropped the stray `digest candidates choice1` column from Signals.
