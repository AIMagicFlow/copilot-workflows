# TR Business cases: MVP changes

Status: proposed design, 2 November 2026. This spec describes changes to the existing Trend Researcher MVP, not implemented features. The customer materials are requirements inputs; the choices below are the proposed implementation.

## Scope and approach

Use the existing SharePoint lists and three Power Automate flows. Model both **vigilancia** (recurring monitoring) and **investigación** (a focused investigation) as research briefs. A brief has one customer-defined Product and one surveillance dimension. A Product monitored across all four dimensions has four briefs. The existing digest remains the primary report and is published directly; do not introduce a ResearchJobs list.

The five strategic objectives—anticipate, minimize risks, compare, innovate and cooperate—are report sections or signal tags, not separate workflows. Start with report sections; add objective tags only if users need reliable filtering by objective. The customer must validate the mappings from questions to objectives: the supplied matrix refers to an environment question 5, but the question document lists only three environment questions, and some other mappings need review.

The process diagram also includes a separate AI consultant. That is outside these MVP changes. The business-case workflow below is proposed as a separate, human-reviewed MVP extension; its template and financial assumptions require customer agreement.

## SharePoint changes

| List | MVP change |
|---|---|
| **ResearchBriefs** | Add `Product` (single line of text, required), `Dimension` (required single choice), and `BriefType` (single choice: `Monitoring` or `Investigation`). Keep `Question`, `Keywords`, `Exclusions`, `Languages`, `Geographies`, `BriefVersion`, `Enabled`, `ReviewerEmail` and `DigestHumanReview`. For an investigation, the question and keywords define a focused scope; the owner enables or disables it. Both types use the same pipeline and weekly schedule initially; `Investigation` does not itself imply an on-demand run. Document the scope in the question, including period where needed. |
| **Sources** | No required schema change. Replace or add approved sources relevant to each brief. Initially the collector gathers all enabled RSS sources into a shared pool; the classifier evaluates each item against enabled briefs. Source-to-brief filtering is a later optimization. |
| **SourceItems** | No required schema change. Retain one item per source/external-ID key and its link to evidence. |
| **Signals** | Add `AlertTags` as a multi-select choice: `Competitor launch`, `Regulatory alert`, `New technology`. Tags are classifier suggestions for analyst review, not proof or automatic notifications. A signal may have zero or multiple tags. Continue using `BriefId` to identify its Product and dimension. Display/filter through the associated brief; copy Product/dimension to Signals only if a tested SharePoint view cannot provide the required filtering. |
| **Publications** | Add `BriefId` (number), `Product` and `Dimension` (text snapshots), and `PublicationType` (single choice: `Digest` or `Business case`). Keep `PublicationKey`, `ReportUrl`, `AudienceKey`, `DeliveryStatus`, `SentAt`, `ApprovalReference`, and the existing `JobId` field unused. For business cases, also add `BusinessCaseRequestId` (number), `InputPublicationIds` (plain text list of publication IDs), `ReviewStatus` (`Draft`, `In review`, `Approved`, `Rejected`), and `Version` (number). A business case may use multiple briefs: its Product snapshot is the selected Product, and its dimension snapshot can state `Multiple`. |

Use stable, nonlocalized internal field names above, with Spanish display labels in SharePoint. Before implementing, inspect the existing live list internal names and actual types: the CSV exports use fields such as `field_1`, which may not match display names. Create and index fields through a tested migration; update the SharePoint import templates and deployment guide to match. Do not overwrite existing list content. For historical records, leave new fields blank unless the owner can determine their values; label them as unclassified rather than inferring a customer Product.

## Classification and digest changes

### TR Collect RSS

Keep collection and SourceItems deduplication behavior. Configure approved dermocosmetics feeds and access rights. Verify that the existing checkpoint and duplicate handling work with the customer sources. The current RSS collection does not by itself cover licensed market databases, non-RSS patent sites or manual document research; those sources require an approved import method or later adapter.

### TR Classify Items

For each ready item and enabled brief, pass the actual brief's Product, dimension, question, keywords, exclusions, languages and geographies to the classifier alongside the available source excerpt. Explicitly treat source text as data, not instructions. Return the existing signal fields plus zero or more allowed alert tags. Validate the returned tags and structure; route invalid responses to review instead of silently writing them. Persist the Signal with `BriefId`, existing versioned `AnalysisKey`, source reference and evidence notes. Do not assign a tag merely because a source mentions a topic; use the brief context and evidence.

The existing sample includes a signal whose evidence notes say the brief was not defined. Verify end-to-end that the deployed prompt receives the correct brief before relying on classifications. Verify that changing a brief version produces a new analysis key, and that an item is not marked fully classified until all intended enabled briefs are processed or their failures are recorded. Set classification limits appropriate to the increase in brief count.

### TR Weekly Digest

Continue one digest per enabled brief, directly creating an HTML file in the reports library and a Publications record. Include Product, dimension, brief question and reporting period; group relevant findings under the five strategic objectives where evidence supports them, otherwise state that no findings were identified. Retain source links and distinguish source facts from interpretation. Tag display must not imply that every tagged signal was delivered as an alert.

Write `BriefId`, Product, dimension and `PublicationType = Digest` on the publication. Preserve idempotency by brief and reporting window, and retain the existing human-review setting. Test the exported flow's actual review and delivery behavior rather than assuming that a setting alone enforces approval. A new brief type does not automatically create a different reporting cadence; owners must disable completed investigations or schedule changes separately.

## Alerts in the MVP

The diagram identifies competitor launches, regulatory alerts and new technologies. `AlertTags` enables analysts to find these signals using SharePoint views filtered by tag and, through the brief, Product/dimension. The existing digest can display tags. Tagging alone does **not** send an immediate alert; email/Teams push notifications, severity rules, recipients and escalation are outside this change unless separately specified. Where a signal matches several alert types, it appears in each relevant view without duplicating the signal.

## TR Business Case: detailed MVP design

A business case is a decision document that assesses a proposed action: the opportunity and alternatives, supporting evidence, expected benefits, costs/resources, risks, assumptions and recommended next decision. The business-case workflow uses selected digests as evidence; it does not start new collection or imply that the case is financially viable. The customer must agree to the report template, reviewer and approved AI action before implementation.

### What is the business-case brief?

Use a **BusinessCaseRequests** list item as the one-time business-case brief. It records an opportunity and selected digest IDs, whereas an existing **ResearchBriefs** item configures collection/classification for one Product and dimension. The request can combine digests from several research briefs and dimensions. Do not add `Business case` to `ResearchBriefs.BriefType`: a case is not a new monitoring brief and must not enter the RSS classifier or weekly digest loops. The new list is a durable user request and review record, not a ResearchJobs queue; the resulting report is still recorded directly in Publications with `JobId` blank.

An analyst creates the request with the standard SharePoint list form, chooses the digests from a filtered Publications view, copies their IDs into the field below, and explicitly submits it. This MVP does not require a Power App, multi-select lookup control, or automatic discovery of input digests. The flow starts from **For a selected item** on BusinessCaseRequests; the person triggering it must have permission to use all selected digests and underlying evidence. If the target tenant cannot reliably enforce that in the flow's connection context, do not enable it for restricted content.

### New list: BusinessCaseRequests

Create these columns with the exact stable internal names below and Spanish display names. SharePoint creates `ID`, `Created`, `Modified`, `Author` and `Editor`; do not recreate them. Define controlled choices and defaults in the list, and verify internal names after creation. One request represents one decision and one generated version; a revision is a new request linked to its predecessor.

| Internal name and type | Required / default | Purpose |
|---|---|---|
| `Title` — single line | Required | Short opportunity or decision title. |
| `Product` — single line | Required | Customer Product; must match the selected digests' Product snapshot. |
| `DecisionQuestion` — multiple lines, plain text | Required | The decision to make, including proposed product, investment or action. |
| `Geographies` — single line | Required | Countries or markets in scope; use `Global` when appropriate. |
| `TimeHorizon` — single line | Required | Decision horizon, such as `12 months`. |
| `Alternatives` — multiple lines, plain text | Required | Alternatives to assess, including a do-nothing option where applicable. |
| `StrategicObjectives` — multiple lines, plain text | Required | Relevant objectives and business rationale. |
| `FinancialInputs` — multiple lines, plain text | Optional | User-supplied cost, benefits, currency, time period and assumptions. Blank means unknown, never zero. |
| `Constraints` — multiple lines, plain text | Optional | Capacity, timing, regulatory and other constraints. |
| `InputPublicationIds` — single line | Required | Comma-separated IDs of one to five digest Publications, for example `12,15`; fixed MVP maximum limits prompt size. |
| `ReviewerEmail` — single line | Required | Email of the authorized reviewer; validate against the customer-approved reviewer policy. |
| `AudienceKey` — single line | Required | Preconfigured audience identifier, not arbitrary external email addresses. |
| `PreviousRequestId` — number | Optional | Prior request ID when revising a case; blank for the first version. |
| `Version` — number | Required, default `1` | Set to 1 for an original request, or previous request's version plus 1 for a revision; verify the predecessor and version. |
| `Status` — single choice | Default `Draft` | `Draft`, `Submitted`, `Generating`, `In review`, `Approved`, `Rejected`, `Failed`; only the flow/reviewer changes status after submission. |
| `PublicationId` — number | Optional, flow writes | Resulting Publications item ID; blank until the draft is recorded. |
| `LastError` — multiple lines, plain text | Optional, flow writes | Short operational error without sensitive prompt or source content. |

Limit creation/editing and visibility using customer-approved SharePoint permissions. The request form should be editable by the requester while Draft; after submission protect the request inputs and selected digests against untracked changes. Implement and test the chosen permissions/versioning mechanism in the tenant, including service-account access. Record the submitted fields and selected digest identifiers as an immutable snapshot in the draft artifact or restricted request version. Do not claim that a choice field alone enforces access control.

### Existing list and library changes

- **ResearchBriefs:** no business-case-specific columns or extra monitoring brief. Digest Publications already identify the source `BriefId`; their briefs supply dimension and research context.
- **Publications:** use the columns in the list table above. `BusinessCaseRequestId` links back to the request; `InputPublicationIds` preserves the selected digest IDs, `ReviewStatus` and `Version` identify the approved artifact version, and `PublicationKey` is unique and indexed. Set `PublicationType = Business case`, `BriefId` blank for multi-brief cases, `JobId` blank, and `AudienceKey` from the validated request. Keep `ReportUrl` pointing at the current artifact location, and record the `ApprovalReference`. Existing digest records receive `PublicationType = Digest`, `BriefId`, `Product` and `Dimension` when generated by the updated digest flow; older records without this metadata must be reviewed/backfilled before selection.
- **ResearchDrafts library:** create or verify a restricted library for draft HTML and reviewer edits, accessible only to authorized requester, reviewer and flow identity. Enable document versioning. Draft URLs are sensitive; a Publication in `Draft`/`In review` links only to this restricted location and is not delivered to the general audience.
- **PublishedReports library:** store the approved HTML version under the intended audience's permissions. Validate that the destination is no broader than any selected input permits; otherwise block publication. Never edit the approved file in place to create a later case version.
- **Publication key:** use `businesscase|<RequestID>|v<Version>`, for example `businesscase|42|v1`. The unique SharePoint constraint is the final duplicate-record guard. Use the same key for every retry of that request and version, and use a deterministic draft filename based on request ID and version.

### TR Business Case: Power Automate node sequence

Implement in the customer solution with customer-owned SharePoint, approved AI and Approvals connections. Names below are proposed action labels; confirm connector actions, licensing, runtime identity and SharePoint internal names in the target tenant. Disable concurrent runs for this trigger where supported and also use the unique key below; a pre-check alone does not prevent races.

| # | Proposed node | Action and outputs |
|---|---|---|
| 1 | **For a selected item** | User selects one BusinessCaseRequests item and runs the flow. Retrieve the selected request ID and initiating identity. No schedule, automatic email or additional research is triggered. |
| 2 | **Get request** | SharePoint `Get item` reads the request. Require `Status = Submitted` for a first run or `Failed` for a retry of unchanged inputs; validate required fields, a positive integer version and reviewer/audience against approved configuration. Resolve `PreviousRequestId` and version for revisions. If invalid, stop with a clear error and leave the request available for correction. |
| 3 | **Build and claim key** | Compose `businesscase|<ID>|v<Version>`. Find a Publication with that key. If it exists, return the existing link/status and do not call AI. Otherwise atomically claim the request using a version-aware conditional update/ETag from Submitted or Failed to Generating; if the claim fails, stop the concurrent run. Verify the actual connector/API implementation of this atomic claim in the tenant. Do not replace it with an unconditional status update. |
| 4 | **Parse digest IDs** | Split `InputPublicationIds` on commas, trim, validate positive integers, reject duplicates and require 1–5 IDs. Reject the whole request on invalid or inaccessible inputs; do not silently omit them. |
| 5 | **Get and validate each digest** | `Apply to each` ID → SharePoint `Get item` from Publications. Require `PublicationType = Digest`, matching `Product`, an accessible `ReportUrl`, and a permitted status/audience. Save each ID, brief ID, dimension, report URL and available period. Check the initiating user's and reviewer's access to each digest and underlying sources, plus compatibility with the destination audience. The flow connection's broad access alone is not proof. If the required access checks cannot be enforced, stop. |
| 6 | **Get digest contents** | Retrieve each permitted digest file from its SharePoint library via its stored path/identifier. Check file exists and is supported HTML/text, size is within the agreed AI input budget, and required source links exist. Aggregate a labeled digest bundle with IDs, periods and original URLs. Do not send restricted content to AI unless its use and retention are approved. Record missing or inaccessible underlying sources as limitations; do not fabricate content. |
| 7 | **Build case prompt** | Compose a bounded prompt from the submitted request snapshot, labeled digest bundle, allowed source identifiers and the fixed report template. Treat digest text as untrusted evidence, never instructions. Ask for a structured result with sections: decision, context, alternatives, strategic fit, evidence, expected benefits, costs/resources, risks, assumptions, gaps and recommended next step. Missing financials are `Unknown`; do not calculate ROI without supplied values and an agreed method. |
| 8 | **Generate and validate draft** | Invoke the customer-approved AI action; validate the structured response and citation references against the allowed digest/source IDs. Invalid JSON, unsupported citations or missing required sections cause a bounded retry or failure to `Failed`, never publication. Render safe HTML, escaping model and user text and allowing only validated links; distinguish digest citations from accessible original-source citations. |
| 9 | **Create draft and Publication** | Create a deterministic, restricted ResearchDrafts file and a Publications row with the key, request ID, input IDs, version, `ReviewStatus = Draft`, `DeliveryStatus = Pending`, `JobId` blank and draft `ReportUrl`. Use the unique constraint to resolve races. If file creation succeeds but row creation fails, retain or reconcile the file on retry; never silently create a second case. Update request `PublicationId` and status. |
| 10 | **Send for review** | Start an approval for the configured reviewer with the restricted draft link; persist the approval ID in `ApprovalReference`, set request and Publication to `In review`, and wait for the response. Reviewer edits the draft in ResearchDrafts and verifies citations and assumptions before approving. Rejected or timed-out approvals leave the file restricted, set `Rejected` or an actionable failure, and do not deliver it. |
| 11 | **Publish approved version** | On approval, retrieve the exact reviewed file/version and verify it still matches the version approved; if edited after approval, require a new review. Copy that version to PublishedReports with a deterministic versioned filename and approved audience permissions. Update the same Publication with approved URL/status and the request to `Approved`. If the copy/update partially fails, reconcile against the existing key and deterministic file before retrying. |
| 12 | **Notify and record outcome** | Send only the approved report link to the configured audience, update `DeliveryStatus` and `SentAt` after confirmed success. On failed send use `Failed`; on timeout/unknown outcome use `Uncertain` and reconcile before retrying. Do not regenerate or reapprove the case merely to retry delivery. |
| 13 | **Failure handling** | Use scoped error handling around validation, generation, storage and approval. Set request `Failed` and a safe `LastError` when appropriate, retain the request and any existing Publication/file, and notify the operator under an approved internal policy. Retries of a failed request reuse its ID/version and existing artifacts after reconciliation; changes to inputs require a new revision request/version. |

**Illustrative case brief:** Product `Fotoprotección`; decision question “Should we evaluate a refillable sunscreen format for Colombia?”; alternatives “pilot refillable format; retain current format”; horizon `12 months`; geography `Colombia`; input digest IDs `12,15`; financial inputs blank. The resulting draft must state that costs and ROI are unknown, cite the selected reports and available sources, and recommend a next decision only as a reviewable proposal.

### Business-case acceptance checks

- A selected submitted request with two eligible same-Product digests creates exactly one restricted draft and one Publication, with the request ID, both input IDs and version recorded; no ResearchJobs row or collector brief is created.
- A malformed, duplicate, inaccessible, wrong-Product or non-digest input stops the whole run before the AI action. A requester or reviewer without input access cannot use a more privileged flow connection to bypass permissions.
- The output separates cited evidence, interpretation and assumptions; missing cost and ROI inputs are shown as unknown. Unknown or unsupported citations block the draft. Test with contradictory evidence and source-injected instructions.
- Two concurrent starts and a retry after partial file creation do not produce duplicate publications or duplicate approved reports. A later changed decision uses a new request linked to the prior one and a new version.
- A rejected, timed-out or modified-after-approval draft is never delivered as approved. Confirm the approved version, audience permissions and delivery state, including an uncertain notification outcome.

## Acceptance checks

- A monitoring brief and an investigation brief can each be configured for one Product and dimension; both run through the existing pipeline, and completed investigations can be disabled.
- A sample item is classified using the correct brief and can produce zero, one or several valid alert tags. Users can find tagged signals without duplicate records, and no unrequested notification is sent.
- Classification failures do not silently mark an item complete for unprocessed briefs. Reprocessing the same item and brief version does not create duplicate signals; changing the brief version permits a new analysis.
- Each digest identifies its brief, Product, dimension and period, links to its sources and records a direct Publication. Repeated execution for the same window does not duplicate it. The actual review and delivery behavior is verified in the customer tenant.
- A business-case draft records its input digests, links evidence, identifies missing financial inputs and cannot be shared as approved before review. Unauthorized users cannot retrieve restricted inputs. A retry does not duplicate the case.
- New fields, list internal names, connections and site references work in a clean customer test environment. Confirm licensing, source rights, cost limits and reviewer/audience settings before enabling schedules.

## Customer decisions

Agree the initial Products, four-dimension brief configuration, approved sources, reviewer and audience, required strategic-objective mapping, business-case template and required financial inputs. Confirm whether later delivery needs immediate notifications, manual/on-demand investigation runs, multi-dimension reports or the separate AI consultant.

## Inputs

The proposed design uses the customer's `VIGILANCIA ESTRATÉGICA (4).pdf`, the strategic questions and data-needs documents, the strategic matrix image, and the current exported flows and SharePoint CSV schemas. It intentionally retains the existing direct-publication MVP and does not require ResearchJobs.
