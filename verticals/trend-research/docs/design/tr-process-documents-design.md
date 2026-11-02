# TR Process Documents

something important we haven't implemented yet is another workflow for another type of sources, a folder or document library, where users and other workflows would upload new documents (new source items), and the workflow does the processing of the files (normalizing from any format to text?), applies a heuristic filter for PII (emails, phones, names, addresses) and things like exact company names, exact money quantities, etc. before putting them on the "Evicence" folder and the sourceitems table we have (where it connects with the classification workflow, just like the RSS).
------

Yes. This is the main missing ingestion layer.

Our original design already anticipated approved file submissions alongside RSS/API collection, and explicitly treated browser automation and difficult document extraction as separate source adapters. The important architectural property is that every adapter converges onto the same Evidence → SourceItems → TR Classify Items contract.

I would add two adapters, but keep them independent:

                    SOURCE ADAPTERS

RSS feeds ─────────► TR Collect RSS ───────────┐
                                               │
Uploaded files ────► TR Process Documents ─────┼──► Evidence
                                               │       +
Authenticated ─────► TR Collect Browser ───────┘    SourceItems
websites                                             │
                                                    ▼
                                           TR Classify Items
                                                    │
                                                    ▼
                                                 Signals


---

Yes. That's cleaner. I would drop Quarantine entirely and make upload-source privacy a property of the folder/source.

The existing design already says that Sources carry an access classification, includes approved file submissions/internal documents as source scope, and requires public evidence to be separated from restricted internal context.

Final source-folder model

One SharePoint library:

SourceUploads/
│
├── PublicData/
│   ├── ConferenceReports/
│   ├── VendorDocuments/
│   └── UserUploads/
│
└── PrivateData/
    ├── InternalResearch/
    ├── CustomerMaterials/
    └── InternalPresentations/


Only two privacy behaviors exist:

PublicData
→ extract / normalize
→ Evidence

PrivateData
→ extract / normalize
→ redact sensitive information
→ Evidence


The original private document stays in its restricted folder. The shared Evidence layer receives only the redacted derivative. This fits the design requirement to separate public evidence from restricted internal context.

Don't put Private = Yes/No on every source

Since you want exactly two source-folder types, I'd make privacy structural:

/SourceUploads/PublicData/...
→ Public

/SourceUploads/PrivateData/...
→ Private


Then Sources only needs:

Title
SourceType = Upload
SourcePath
Enabled


For example:

Title: Internal Research
SourceType: Upload
SourcePath: /SourceUploads/PrivateData/InternalResearch
Enabled: Yes


and:

Title: Conference Reports
SourceType: Upload
SourcePath: /SourceUploads/PublicData/ConferenceReports
Enabled: Yes


Adding SourcePath is my proposed extension to the documented Sources schema. The existing schema already supports SourceType = Upload.

Revised TR Process Documents

This becomes much simpler:

File created in SourceUploads
            ↓
1. Get File Metadata
            ↓
2. Determine file path
            ↓
3. Is under PublicData or PrivateData?
            ↓
4. Lookup matching Upload Source
            ↓
5. Source enabled?
            ↓
6. Build ItemKey
            ↓
7. Duplicate?
       YES → stop
       NO
        ↓
8. Get File Content
        ↓
9. Extract Text
        ↓
10. Normalize Text
        ↓
11. Source type?
     ┌─────────────┴─────────────┐
 PublicData                  PrivateData
     │                           │
     │                      Redact PII /
     │                      sensitive data
     │                           │
     └─────────────┬─────────────┘
                   ↓
             FinalEvidenceText
                   ↓
12. Save .txt → Evidence
                   ↓
13. Create SourceItem
    Status = Ready
                   ↓
            TR Classify Items


All adapters still converge on the same Evidence + SourceItems contract, which is the architecture already defined for collection, normalization and classification.

Redaction policy for PrivateData

I'd define the first version like this:

Email address       → [EMAIL]
Phone number        → [PHONE]
Money amount        → [MONEY]
Exact company term  → [COMPANY]
Exact customer term → [CUSTOMER]
Exact project term  → [PROJECT]
Exact product term  → [PRODUCT]


The exact redaction mechanics are our proposed implementation, not something dictated by the current guide.

For exact organization/customer/project values, I still recommend a tiny configuration list:

SensitiveTerms

Title                 Replacement        Enabled
────────────────────────────────────────────────
Exact Customer Name   [CUSTOMER]         Yes
Project Falcon        [PROJECT]          Yes
Internal Product X    [PRODUCT]          Yes


That avoids asking an LLM to guess which company or project names are confidential.

I'd leave free-form person-name and postal-address detection out until we identify and validate an appropriate governed detection capability. The current design specifies the privacy boundary but not a particular PII detection engine.

I'd record redaction on SourceItems

My suggested schema extension:

WasRedacted
Yes/No

RedactionSummary
Multiple lines of text


For PublicData:

WasRedacted = No


For PrivateData:

WasRedacted = Yes

RedactionSummary:
EMAIL: 2
PHONE: 1
MONEY: 4
SENSITIVE_TERM: 3


That way the classifier/researcher knows evidence may have been deliberately stripped of identifying details.

Most importantly: one workflow for unlimited folders

Don't clone workflows per folder.

A customer adds another source by:

1. Create folder:

SourceUploads/
  PrivateData/
    CompetitiveIntelligence/

2. Add Sources record:

Title:
Competitive Intelligence

SourceType:
Upload

SourcePath:
/SourceUploads/PrivateData/CompetitiveIntelligence

Enabled:
Yes


No workflow changes.

That's exactly the kind of configuration-separated-from-implementation model we want for portability. The design already defines customer-configurable source scope and describes the deliverable as including a source-adapter catalogue and configuration templates.

So our SharePoint changes now are only

Create library:

SourceUploads


Create top-level folders:

PublicData
PrivateData


Add to Sources:

SourcePath
Single line of text


Create actual subfolders, e.g.:

PublicData/VendorDocuments
PrivateData/InternalResearch


Add one Sources row per configured subfolder.

Later, optionally add to SourceItems:

WasRedacted
RedactionSummary


Then we build TR Process Documents against any file created underSourceUploads, with PublicData/PrivateData determining whether the redaction stage runs.

----

Yes. With the final decision of one SourceUploads library, two top-level privacy zones (PublicData / PrivateData), and multiple configured source folders underneath, here's the workflow I'd build.

This remains consistent with the design: approved file submissions are a collection source, collection/normalization happens before bounded classification, evidence is stored in SharePoint, and deduplication happens before AI.

0. SharePoint setup first
SourceUploads library

Create:

SourceUploads
├── PublicData
└── PrivateData


Then create actual source folders underneath, for example:

SourceUploads
├── PublicData
│   ├── VendorDocuments
│   └── ConferenceReports
│
└── PrivateData
    ├── InternalResearch
    └── CustomerMaterials


Raw private files stay there. Only the normalized/redacted derivative reaches Evidence.

Add SourcePath to Sources

Create:

SourcePath
Type: Single line of text


Example source records:

Title:
Vendor Documents

SourceType:
Upload

SourcePath:
/SourceUploads/PublicData/VendorDocuments

Enabled:
Yes


and:

Title:
Internal Research

SourceType:
Upload

SourcePath:
/SourceUploads/PrivateData/InternalResearch

Enabled:
Yes


Upload already exists as a documented SourceType; SourcePath is our extension that makes multiple upload folders configurable without cloning workflows.

1. Final workflow structure

Create:

TR Process Documents


Target structure:

File created under SourceUploads
        ↓
1. Get File Metadata
        ↓
2. Determine Parent Source Path
        ↓
3. Get Configured Upload Source
        ↓
4. Source Found?
   ├── NO → stop/log
   └── YES
          ↓
5. Build ItemKey
          ↓
6. Check SourceItem Exists
          ↓
7. New Item?
   ├── NO → stop
   └── YES
          ↓
8. Get File Content
          ↓
9. Determine File Type
          ↓
10. Extract Text
          ↓
11. Normalize Text
          ↓
12. PrivateData?
    ├── NO
    │     ↓
    │   FinalText = NormalizedText
    │
    └── YES
          ↓
       Redact Sensitive Data
          ↓
       FinalText = RedactedText
          │
          ▼
13. Create Evidence TXT
          ↓
14. Create SourceItem
    Status = Ready
          ↓
 existing TR Classify Items


No classification Agent in this workflow. All adapters converge onto Evidence + SourceItems, exactly as the existing design intends.

2. Node 1: SharePoint trigger

Create the standard workflow:

TR Process Documents


Use the SharePoint trigger exposed in your designer for a new file created in a library.

Configure:

Site:
Trend Research

Library:
SourceUploads


We want file creation, not every metadata update.

3. Node 2: Get File Metadata

Add:

SharePoint → Get file metadata

Rename:

Get Upload Metadata


For the file identifier, use:

Trigger → Identifier


Use the dynamic-content token rather than manually constructing an identifier.

The values we need downstream are conceptually:

Identifier
Name
Path
Created


Use the actual fields your node exposes.

4. Node 3: Build Parent Source Path

Add a Compose/value node.

Rename:

Build Parent Source Path


We want this:

/SourceUploads/PrivateData/InternalResearch/report.docx


to become:

/SourceUploads/PrivateData/InternalResearch


Don't manually invent the path expression until we've inspected what the SharePoint trigger exposes. If your trigger has a ready-made Folder path, use that directly.

The target output must exactly match Sources.SourcePath.

5. Node 4: Get Upload Source

Add:

SharePoint → Get items

Rename:

Get Upload Source


Configure:

Site:
Trend Research

List:
Sources


The logical filter is:

SourceType = Upload
AND
Enabled = Yes
AND
SourcePath = current parent folder


Because your lists were originally imported from Excel, first discover the internal names for:

SourceType
Enabled
SourcePath


from:

Sources → List settings → column → Field=...

Our implementation already demonstrated why display names should not be assumed to equal SharePoint internal names.

Set:

Top Count:
1

6. Node 5: Source Found?

Add If/Else.

Condition:

length(Get Upload Source → value)


greater than:

0

NO

Stop.

Optionally we'll add an Operations record later indicating:

No configured Upload Source matched this folder.

YES

Continue.

7. Node 6: Build ItemKey

Inside YES:

Add Compose/value.

Rename:

Build ItemKey


Build:

<Source ID>|<SharePoint stable file identifier>


For example:

8|01ABCDEF...


Use:

Get Upload Source → first row → ID


plus:

Get Upload Metadata → stable Identifier


Do not use filename alone.

The existing architecture requires deterministic deduplication using source identifiers or another stable identifier rather than AI-based duplicate detection.

8. Node 7: Check SourceItem Exists

Add:

SharePoint → Get items

Rename:

Check Upload SourceItem Exists


Configure:

Site:
Trend Research

List:
SourceItems


Filter:

<ItemKey internal field> eq '<Build ItemKey>'


Remember the quotes because ItemKey is text.

Set:

Top Count:
1


This is the same dedupe pattern already validated in TR Collect RSS.

9. Node 8: New Upload?

Add If/Else:

length(Check Upload SourceItem Exists → value)


equals:

0

NO

Do nothing.

YES

Continue.

Keep the unique SharePoint ItemKey constraint as the second line of defense, just like RSS.

10. Node 9: Get Upload Content

Inside the new-item branch:

Add:

SharePoint → Get file content

Rename:

Get Upload Content


Use:

Get Upload Metadata → Identifier


This is identifier-based because we have a SharePoint file identifier.

That's different from TR Classify Items, where EvidenceUrl stores a path and therefore required Get file content using path. That distinction was observed during our implementation.

11. Node 10: determine file format

Add a Switch.

Rename:

File Type


Input:

file extension


Initial branches:

.txt
.pdf
.docx
.pptx


Default:

Unsupported


I would not claim XLSX/images/etc. are supported yet. The source material explicitly recognizes difficult document extraction as a separately scoped adapter issue; it does not give us a universal extraction action for arbitrary documents.

12. Node 11: Extract Text

Each branch must produce one common value:

ExtractedText


Conceptually:

TXT
  → plain text

PDF
  → PDF text extraction

DOCX
  → Word text extraction

PPTX
  → presentation text extraction


This is where we need to work from the actions actually exposed by your tenant. The references establish approved file submission/document extraction as part of the ingestion architecture, but don't document one universal current action for converting all of these formats.

So when you reach Node 11, search the Add-node/action picker for “extract text”, “document”, “PDF”, and “Word”. Send that screen and I'll map the supported branches from the actual actions available.

13. Node 12: Normalize Text

After all supported extraction branches converge, establish:

NormalizedText


Format:

SOURCE FILE:
<filename>

SOURCE:
<configured Source title>

SOURCE TYPE:
Upload

PRIVACY:
PublicData | PrivateData

COLLECTED:
<utcNow>

CONTENT:

<extracted text>


Don't summarize or reinterpret the document here.

Normalization is structural only.

14. Node 13: Private Data?

Add If/Else.

We can determine this from the configured SourcePath.

Condition conceptually:

SourcePath starts with
/SourceUploads/PrivateData/

NO
FinalText = NormalizedText

YES

Run the redaction pipeline.

The design explicitly requires public evidence and restricted internal context to remain separated, with source permissions/data boundaries enforced outside model instructions.

15. Private branch: redaction pipeline

For v1, keep this cheap and deterministic.

Run replacements/detection for:

emails
phones
money quantities
configured exact sensitive terms


Target behavior:

alert+email@example.com
→ [EMAIL]

+57 300 ...
→ [PHONE]

USD 4.3 million
→ [MONEY]

Exact Customer Corp
→ [CUSTOMER]


These particular redaction rules are our proposed implementation, not rules defined in the current design.

I would not implement arbitrary human-name detection with regex.

16. Add SensitiveTerms list

For exact internal entities, create a small SharePoint list:

SensitiveTerms


Columns:

Title
Replacement
Enabled


Examples:

Title:
Exact Customer Corp
Replacement:
[CUSTOMER]

Title:
Project Falcon
Replacement:
[PROJECT]

Title:
Internal Product X
Replacement:
[PRODUCT]


Then in the PrivateData branch:

Get enabled SensitiveTerms
        ↓
Loop terms
        ↓
replace exact matches


This is a new configuration component I'm recommending, rather than an existing documented list.

17. Produce FinalText

Public:

FinalText = NormalizedText


Private:

FinalText = RedactedText


The original private document stays where it is under SourceUploads/PrivateData/....

It does not get copied into Evidence.

18. Node: Create Evidence

After the Public/Private branches converge:

Add:

SharePoint → Create file

Rename:

Create Upload Evidence


Configure:

Library:
Evidence


File name:

upload-<stable-file-id>.txt


File content:

FinalText


This is the normalized artifact that enters the shared pipeline.

19. Node: Create Upload SourceItem

Immediately after Evidence succeeds:

SharePoint → Create item

Rename:

Create Upload SourceItem


List:

SourceItems


Map:

Title
original filename

SourceId
matched Sources row → ID

ExternalId
SharePoint file stable identifier

ItemKey
Build ItemKey

SourceUrl
link/path to original upload

PublishedAt

Leave blank unless the uploaded file has trustworthy publication metadata.

Don't substitute upload time for publication time.

CollectedAt

Expression:

utcNow()

EvidenceUrl

Use the path/link returned by:

Create Upload Evidence


It needs to remain compatible with the downstream Get file content using path behavior already implemented by TR Classify Items.

ContentStatus

For complete extraction:

FullText


For incomplete extraction:

MetadataOnly


Don't mark something FullText unless we actually extracted the document content.

Status
Ready


That completes the handoff to our existing classifier.

20. Optional but recommended SourceItem fields

I'd add:

WasRedacted
Yes/No

RedactionSummary
Multiple lines of text


Public source:

WasRedacted = No


Private source:

WasRedacted = Yes


Example:

EMAIL: 2
PHONE: 1
MONEY: 3
SENSITIVE_TERM: 4


This is my recommended schema extension, not part of the original SourceItems schema.

Final flow
File Created
SourceUploads
       ↓
Get Upload Metadata
       ↓
Build Parent Source Path
       ↓
Get Upload Source
       ↓
Source Found?
       ↓ yes
Build ItemKey
       ↓
Check Duplicate
       ↓ new
Get Upload Content
       ↓
File Type
       ↓
Extract Text
       ↓
Normalize Text
       ↓
PrivateData?
 ┌─────────────┴──────────────┐
 │                            │
NO                           YES
 │                            │
NormalizedText          redact email
 │                      redact phone
 │                      redact money
 │                      SensitiveTerms
 │                            │
 └──────────────┬─────────────┘
                ↓
             FinalText
                ↓
       Create Evidence.txt
                ↓
       Create SourceItem
        Status = Ready
                ↓
        TR Classify Items
                ↓
             Signals


The architectural advantage is exactly what trend-researcher-design.md calls for: separate restartable source acquisition/normalization, deterministic deduplication before AI, a shared evidence store, and downstream classification that does not care which adapter produced the SourceItem.

Build through Node 10, File Type, first. The next unknown is Node 11, document-to-text extraction, where we should use the actual actions exposed in your Copilot Studio tenant instead of inventing unsupported connector behavior.
