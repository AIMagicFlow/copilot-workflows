# ADR-001: Uploads are plain-text, public documents only (1.2.0.0)

- Status: accepted (Boss, 2026-11-02)
- Applies to: `TR Process Documents`, release 1.2.0.0
- Design: [tr-process-documents-design.md](tr-process-documents-design.md)

## Context

The design asked for text extraction "by the actions actually exposed by your tenant", and for redaction of private documents before anything reaches Evidence.

A test flow built by Boss showed that flow expressions cannot do the redaction. `replace()` matches exact-case keywords only, one keyword per action. There is no case-insensitive or regex replacement without Dataverse actions or an Azure Function. Extraction of PDF and Office files has the same dependency.

## Decision

1.2.0.0 reads plain text from public uploads and nothing else:

- `.txt`, `.md`, `.csv`, `.html` and `.htm` are read as UTF-8 text. The extension check is case-insensitive. `.htm` was added as the same format as `.html`.
- Any other file type becomes a `MetadataOnly` SourceItem. The classifier sees the file name and folder, not the content.
- A text file larger than `tr_MaxUploadBytes` (default `1000000`) is also `MetadataOnly`. The cap keeps runs cheap and predictable.
- The flow reads only files whose folder is under `/SourceUploads/PublicData/`. A file directly in `PublicData`, a file in any other folder (including `PrivateData`), and a file whose folder has no enabled `Upload` row in Sources are ignored. The flow ignores private folders, and any folder outside `PublicData`, even when a Sources row points at them.
- There is no redaction. Private documents must not be uploaded.
- Dedupe uses the file's list item ID: `ItemKey` = `<Source ID>|<list item ID>`. Re-uploading, editing or renaming a processed file creates no second item.

## Consequences

- PDF, Word, Excel, PowerPoint and other binary files are `MetadataOnly`.
- HTML is kept raw, tags included. Nothing strips the markup.
- Private documents need the add-on described below. Until then the `PrivateData` rule in the design cannot hold, so the flow does not read private folders.
- Public sources keep the design's `PublicData/<source>` layout, so source paths do not change when private uploads arrive.
- Acceptance in a tenant is manual (see the 1.2.0.0 acceptance checklist).

## Add-on (not scheduled)

Redaction and document conversion are decided but not scheduled. They belong to the Document Sanitizer add-on, designed under `docs/addons/` and not yet committed. The options are a customer-hosted Azure Function released separately, with the solution carrying a custom connector, environment variables and flow branches, and a Dataverse plug-in as a possible "no Azure" tier.

It plugs into `TR Process Documents` in two places:

- the else branch of `If_Text_File`, to convert binary files to text;
- a new private branch beside `If_Public_Path`, to redact private documents.

It gets its own implementation plan when a customer needs it. Nothing in 1.2.0.0 depends on it.
