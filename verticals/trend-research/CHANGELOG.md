# Changelog

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
