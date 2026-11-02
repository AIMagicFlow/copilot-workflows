# Trend Researcher: quick start

This guide installs Trend Researcher in your Microsoft 365 tenant in about 45 minutes. When you finish you have three automated flows:

| Flow | Runs (UTC) | What it does |
|---|---|---|
| **TR Collect RSS** | Daily, 11:00 | Reads enabled RSS sources and saves every new article as evidence. |
| **TR Classify Items** | Daily, 16:00 | Scores each new article against every enabled research brief and writes a signal. |
| **TR Weekly Digest** | Mondays, 08:00 | Publishes one HTML digest per brief and notifies you in Teams. |

## What you need

- The two release files from `releases/trend-research/<version>/`:
  - `TrendResearchFlow_<version>_en.zip`: the Power Platform solution. **Do not unzip it.**
  - `TrendResearchFlow_<version>_en_sharepoint.zip`: the SharePoint kit. **Unzip it.**
- A Power Platform environment with Dataverse and a Copilot Studio license (agent flows).
- Permission to create SharePoint sites, or ownership of an existing site.

## 1. Create the SharePoint site

1. In SharePoint select **Create site → Team site**. Name it, for example, `Trend Research`, and set privacy to **Private**.
2. Copy the site URL, for example `https://contoso.sharepoint.com/sites/TrendResearch`. You need it in steps 2 and 3.

## 2. Create the lists and libraries (choose one option)

The flows depend on each column's **internal name** (for example `field_3`), not its display name. Both options create the same five lists (`ResearchBriefs`, `Sources`, `SourceItems`, `Signals`, `Publications`) and four libraries (`Evidence`, `PublishedReports`, `ResearchDrafts`, `SourceUploads`).

| | Option A: CSV files | Option B: PnP PowerShell |
|---|---|---|
| For | Any site owner | IT team with PowerShell |
| Tools | A browser | PowerShell 7.4+, the PnP.PowerShell module and an Entra ID app |
| Internal names | Depend on how SharePoint imports the CSV, so they must be checked | **Guaranteed** by the template and checked automatically |
| Libraries | Created by hand | Created for you |
| Future upgrades | Add columns by hand | Run the script again |

### Option A: CSV files

**Libraries.** The flows write to `/Evidence`, `/PublishedReports` and `/ResearchDrafts`, and `TR Process Documents` watches `/SourceUploads`. For each: **New → Document library → Blank library**, enter the name exactly as written, select **Create**. You can rename the display title later. The URL stays the same.

**Upload folder.** Open the `SourceUploads` library and create a folder named exactly `PublicData`. The flow only reads files under this folder. (Option B creates it for you.)

**Lists.** The kit's `lists/` folder has one file per list. Each file carries the full schema, including internal names. For each file:

1. In the site select **New → List → From CSV**.
2. Upload the file. Keep the list name **identical to the file name** (for example `Sources`).
3. Check the proposed column types and select **Create**.

`Sources` and `ResearchBriefs` include sample rows: nine public RSS feeds and one voice-AI brief. Edit or delete them in step 5.

**Verify internal names (required).** If your IT team has PnP PowerShell, run `pnp/provision.ps1 ... -VerifyOnly` (see option B). It checks every column and changes nothing. Otherwise check one column per list by hand:

1. Open the list → **Settings → List settings**.
2. Select the column and look at the browser URL. It must end with the `Field=` value shown.

| List | Column | URL must end with |
|---|---|---|
| Sources | FeedUrl | `Field=field_1` |
| ResearchBriefs | Enabled | `Field=field_7` |
| SourceItems | Status | `Field=field_9` |
| Signals | Status | `Field=field_11` |
| Publications | PublicationKey | `Field=field_1` |

Also confirm that **ItemKey** (SourceItems), **AnalysisKey** (Signals) and **PublicationKey** (Publications) have **Enforce unique values: Yes**. That constraint is what prevents duplicates.

If a `Field=` value differs, **stop**: the flows will not find that column. Delete that list and use option B, or send us a screenshot of the URL.

### Option B: PnP PowerShell

The kit's `pnp/` folder contains the template (`sharepoint-template.pnp.xml`) and `provision.ps1`. The script applies the template, then checks every list, library, column and unique-value constraint. Running it again is safe: it keeps what already exists.

**One-time setup per tenant:**

1. Install PowerShell 7.4 or later. On Windows: `winget install Microsoft.PowerShell`.
2. In PowerShell 7: `Install-Module PnP.PowerShell -Scope CurrentUser`.
3. Register an Entra ID app for PnP. This needs the **Application Developer** or **Global Administrator** role, and granting consent may need a **Global Administrator**:

   ```powershell
   Register-PnPEntraIDAppForInteractiveLogin -ApplicationName "PnP.PowerShell" -Tenant <tenant>.onmicrosoft.com
   ```

   Note the **Application (client) ID** it prints. If your tenant already has a PnP app, use that one.

**Run:**

```powershell
cd <kit folder>/pnp
./provision.ps1 -SiteUrl https://contoso.sharepoint.com/sites/TrendResearch -ClientId <application id>
```

Sign in when the browser opens. It should end with **All lists, libraries and columns match the expected schema.** If any line is red, fix it and run the script again.

With option B, lists live at stable English URLs (`/Lists/Sources`). The flows use the list title.

## 3. Import the solution

1. Open [make.powerapps.com](https://make.powerapps.com) and pick the right environment (top right).
2. Go to **Solutions → Import solution → Browse**, choose `TrendResearchFlow_<version>_en.zip` and select **Next**.
3. **Connections.** For each connection reference, pick an existing connection or create one with the agreed service account:

   | Reference | Connector | Account |
   |---|---|---|
   | Trend Researcher - SharePoint | SharePoint | Read/write on the site from step 1 |
   | Trend Researcher - RSS | RSS | No account needed |
   | Trend Researcher - Teams | Microsoft Teams | The person who receives the digest notice |
   | Trend Researcher - AI classifier | Copilot Studio agent | The account with the Copilot Studio license |

4. **Environment variables.**

   | Variable | Value |
   |---|---|
   | Site URL | The URL from step 1, no trailing slash |
   | Research Briefs / Sources / Source Items / Signals / Publications list | Prefilled with the list names. Change them only if you named the lists differently. A list ID (GUID) also works. |
   | Daily Classification Limit | `50` (maximum items classified per day). Each item is classified once per enabled brief. |
   | Source Uploads library | Prefilled with the library title (`Source Uploads`). If the flow's trigger rejects the title, enter the library's ID (GUID) instead. |
   | Maximum upload size (bytes) | `1000000`. Larger files are recorded by name only (see step 5). |

   The other variables are reserved for future versions. Leave them empty.

5. Select **Import** and wait for the success message (1–2 minutes).

## 4. Turn the flows on

1. In **Solutions**, open **Trend Researcher → Cloud flows**.
2. Check that **TR Collect RSS**, **TR Classify Items**, **TR Weekly Digest** and **TR Process Documents** are **On**. If one is off, select it and choose **Turn on**.

The same flows appear in Copilot Studio under **Flows**.

## 5. Configure your research

- **ResearchBriefs**: edit the sample brief or add your own. Fill in *Question*, *Keywords*, *Exclusions*, *Languages* and *Geographies*. Set *Enabled* to `1` to run the brief and `0` to stop it. If you change an existing brief's question, increase *BriefVersion*: new items are then analyzed under the new version.
- **Sources**: keep only approved RSS feeds. Set *Enabled* to `1` to collect from a source and `0` to pause it. Set *SourceType* to `RSS`.
- **Uploaded documents (optional).** Add one **Sources** row per upload subfolder:
  1. In `SourceUploads/PublicData`, create a subfolder for the source, for example `VendorDocuments`.
  2. In **Sources**, add a row with *Title* (the source name), *SourceType* `Upload`, *SourcePath* `/SourceUploads/PublicData/VendorDocuments` (library URL name plus folder path, no trailing slash) and *Enabled* `1`.
  3. Upload files into that subfolder. `TR Process Documents` checks for new or changed files every 5 minutes.

  What the flow does with an upload:
  - **Text files are read.** `.txt`, `.md`, `.csv`, `.html` and `.htm` (any capitalization) are read as UTF-8 text. HTML is kept as is, tags included.
  - **Everything else is recorded by name only.** PDF, Word, Excel, PowerPoint and any other type get a SourceItem with *ContentStatus* `MetadataOnly`: the classifier sees the file name and folder, not the content.
  - **Size limit.** A text file larger than *Maximum upload size* (default 1,000,000 bytes) is also `MetadataOnly`.
  - **Only subfolders of `PublicData` are read.** A file placed directly in `PublicData`, or in any other folder, is ignored. Each subfolder needs its own enabled `Upload` row in Sources, or its files are ignored.
  - **Do not upload private documents.** This version has no redaction. See [ADR-001](design/adr-001-text-only-uploads.md).
  - **No duplicates.** Uploading the same file again, editing it or renaming it does not create a second item. The flow identifies a file by its SharePoint item ID.
  - Each processed file adds a text file to **Evidence** named `upload-<item ID>.txt` and a SourceItem with *Status* `Ready`. The next **TR Classify Items** run classifies it.

  Known limits, not yet verified in a tenant: the flow assumes the file path it receives starts with `/SourceUploads/`; a folder created in the library may also produce a `MetadataOnly` item; and the file link stored in the SourceItem is limited to 255 characters.

## 6. Test end to end

Run each flow once with **Test → Manually**, in this order:

1. **TR Collect RSS** → rows appear in **SourceItems** with *Status* `Ready`, and `.txt` files appear in **Evidence**.
2. **TR Classify Items** → rows appear in **Signals**. Processed items switch to `Classified`.
3. **TR Weekly Digest** → an HTML file appears in **PublishedReports**, a row appears in **Publications**, and you get a Teams message. If no signal reached relevance 70 or higher in the last 7 days, no digest is produced. That is expected.
4. **TR Process Documents** (if you added an `Upload` source) runs by itself when a file is added. Upload a small `.txt` file to the source's subfolder and wait about 5 minutes. A SourceItem with *ContentStatus* `FullText` and a file in **Evidence** appear.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `List not found` | The list name doesn't match the environment variable. Fix the variable (or use the list GUID), then turn the flow **off and on**. |
| `Column 'field_N' does not exist` | The column doesn't have the expected internal name. Run `provision.ps1 -VerifyOnly`, or see step 2. |
| An environment variable change has no effect | Turn the flow off and on again. Changes can take up to an hour to propagate. |
| `Input exceeds the maximum length of 255` | A multi-line column was created as single-line text. Run `provision.ps1 -VerifyOnly` to find it. |

## Upgrading

Import the new zip with **Solutions → Import solution**, as in step 3. The solution is updated in place. Lists, data and environment variable values are kept. If you used option B, run the new kit's `provision.ps1` again: it adds new columns. With option A, add them by hand from the release notes.

### Upgrading from 1.1 to 1.2

1.2.0.0 adds the `TR Process Documents` flow, the `SourceUploads` library and the `SourcePath` column on **Sources**. Follow the generated `upgrade-1.2.0.0.en.md`, inside the SharePoint kit zip: it lists what to add by hand if you used option A. Then:

1. Create the `SourceUploads` library and its `PublicData` folder (option B does this when you run `provision.ps1`).
2. Import the new solution. It asks for the two new environment variables, *Source Uploads library* and *Maximum upload size*.
3. Turn **TR Process Documents** on and add `Upload` rows to **Sources** (step 5).
4. Read the 1.2.0.0 entry in `CHANGELOG.md` before upgrading. It describes the ItemKey fix in `TR Collect RSS`; its effect on existing items is pending dev-tenant verification.

