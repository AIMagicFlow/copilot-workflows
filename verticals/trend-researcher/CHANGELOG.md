# Changelog

## 1.4.0.0 (unreleased)

### Fixed

- `TR Process Documents` and `TR Business Case` were missing from the solution's root components, so a solution import could leave them out of the solution. Every flow is now a root component, and the build checks it.

## 1.3.0.0 (unreleased)

### Added

- **Business cases: new flow `TR Business Case`** (es `VT Caso de Negocio`). An analyst fills in an item in `BusinessCaseRequests` (es `SolicitudesCasoNegocio`, 17 columns) and sets `Status` to `Submitted`. The flow starts at its next poll (up to 5 minutes), validates the request and its 1 to 5 input digests, claims it (`Generating`), asks the AI for a structured case, validates that every citation is one of the input digests, and saves an HTML draft in `ResearchDrafts` with a Publication (`ReviewStatus=Draft`). It then sends an approval to the request's `ReviewerEmail` (14-day timeout). Approved drafts are copied to `PublishedReports` and announced to the Teams channel in `tr_NotificationAudience` (`teamId|channelId`); if that is empty, the post goes to the flow owner. Rejected or timed-out requests stay in `ResearchDrafts` and are not published. Missing financial inputs are reported as `Unknown`; ROI is never calculated without supplied values.
- **Brief schema.** `ResearchBriefs` gains `Product` (required), `Dimension` (required) and `BriefType` (`Monitoring` default, `Investigation`). **The `Dimension` choices `Market`, `Technology`, `Regulatory`, `Competition` are placeholders until the customer decides the final codes.**
- **Signal schema.** `Signals` gains `AlertTags` (`CompetitorLaunch`, `RegulatoryAlert`, `NewTechnology`) and `Objectives` (`Anticipate`, `MinimizeRisks`, `Compare`, `Innovate`, `Cooperate`). The quickstart describes one tag view per `AlertTag`.
- **Publication schema.** `Publications` gains `BriefId`, `Product`, `Dimension`, `PublicationType` (`Digest`, `BusinessCase`), `BusinessCaseRequestId`, `InputPublicationIds`, `ReviewStatus` (`Draft`, `InReview`, `Approved`, `Rejected`) and `Version`.
- **Weekly digest layout.** The digest header shows product and dimension, and signals are grouped under one heading per objective. New digests record `BriefId`, `Product`, `Dimension` and `PublicationType=Digest`.
- **Environment variables.** `tr_BusinessCaseRequestsList` (use the list title, not the GUID), `tr_ApprovedReviewers` and `tr_ApprovedAudiences` (semicolon-separated lists; empty means every request is rejected), `tr_BusinessCaseMaxInputChars` (default `60000`) and `tr_NotificationAudience`. New connection reference: Approvals.
- **Upgrading from 1.2:** see the quickstart section "Upgrading from 1.2 to 1.3" and the generated `upgrade-1.3.0.0.<locale>.md` inside the SharePoint kit zip.

### Changed

- **One name: Trend Researcher.** The solution's unique name is now `TrendResearcher` (was `TrendResearchFlow`), so the zips are `TrendResearcher_<version>_<locale>.zip`. The repo folders are now `verticals/trend-researcher/` and `releases/trend-researcher/`, and the English display names say "Trend Researcher". The publisher (`TrendResearch`, prefix `tr`) and all component names are unchanged. No customer has installed an earlier version. A dev tenant that has `TrendResearchFlow` installed must delete that solution before importing this one; otherwise both solutions would own the same flows. The 1.1.0.0 and 1.2.0.0 release folders keep their old zip names.
- **Classifier prompt v3.** It reads the brief's Product and Dimension and returns `AlertTags` and `Objectives`. The prompt version is part of `Signals.AnalysisKey`. A signal whose tag is outside the allowed list is saved without that tag, gets `Status=NeedsReview`, and the invalid tags are appended to `EvidenceNotes`. `TR Classify Items` marks a SourceItem `Classified` only when no brief failed for it.
- **Retry rule for business-case requests.** A request that failed before any Publication was created can be retried by setting `Status` back to `Submitted` with the same `Version`. A request that already has a Publication must have `Version` increased first, because the existing-publication check stops the run early. A request stuck in `Generating` is recovered the same way.
- **Reviewer edits after the request block publishing.** This is the current rule; the customer may change it.

### Upgrade notes

- **Existing digests need `PublicationType` and `Product` backfilled before they can be selected for a business case.** The flow accepts an input only if `PublicationType` is `Digest`, its `Product` equals the request's `Product` (after trimming) and its `ReportUrl` is not empty. Digests created before 1.3 have the report file but no `PublicationType` or `Product`.
- Fill in `Product` and `Dimension` on existing briefs (both required).
- Restrict `ResearchDrafts` to the requester, the reviewer and the flow account. No provisioning option does it.

### Known open points (not verified)

- The approval action shapes and the `CopyFileAsync` parameters are built from connector knowledge, not verified against a real export.
- The `Path` shape from `GetFileMetadata` and the folder-created event, and the 255-character file-link limit (both from 1.2), are still unverified.
- An edit made in the seconds between the draft check and the copy could be published (known risk).
- A pending approval holds one of the 25 trigger slots, so at most 25 requests can be pending approval at once.
- The dev-tenant acceptance run (Task B7 step 4) has not been done.
- Documentation still outstanding: `docs/architecture.md` has not been updated to list `NeedsReview` among the Signals status values (it has uncommitted edits by someone else), and `docs/environment-variables.md` has not been updated with the five new variables.

## 1.2.0.0 (unreleased)

### Added

- **Document uploads: new flow `TR Process Documents`.** It checks the `SourceUploads` library every 5 minutes for new or modified files and writes each one to Evidence and SourceItems. See [ADR-001](docs/design/adr-001-text-only-uploads.md).
  - Text files are read as UTF-8: `.txt`, `.md`, `.csv`, `.html`, `.htm` (extension check is case-insensitive). HTML is kept raw, tags included.
  - Any other file type, and any text file larger than `tr_MaxUploadBytes` (default `1000000`), becomes a SourceItem with `ContentStatus=MetadataOnly`.
  - Only folders under `/SourceUploads/PublicData/` are read. A file directly in `PublicData`, or in any other folder, is ignored. **Private documents must not be uploaded:** there is no redaction in this version.
  - Re-uploading, editing or renaming a processed file creates no second item: `ItemKey` is `<Source ID>|<list item ID>`.
- **Schema.** New library `SourceUploads` (es: `Cargas de fuentes`) with folder `PublicData`. New column `Sources.SourcePath` (Text, indexed). Sources rows for uploads use `SourceType=Upload`, `SourcePath` such as `/SourceUploads/PublicData/VendorDocuments` (no trailing slash) and `Enabled=1`.
- **Environment variables.** `tr_SourceUploadsLibrary` (default: the library title; use the library GUID if the trigger rejects the title) and `tr_MaxUploadBytes` (default `1000000`).
- **Upgrading from 1.1:** see the quickstart section "Upgrading from 1.1 to 1.2" and the generated `upgrade-1.2.0.0.<locale>.md` inside the SharePoint kit zip.
- Known open points, not verified in a tenant: the `Path` returned by `GetFileMetadata` is assumed to start with `/SourceUploads/`; a folder-created event may produce a `MetadataOnly` item; the SourceItem link is limited to 255 characters.

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
