# TR Clean Up Signals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A monthly flow that deletes old `Rejected` and `Monitor` signals, and the evidence files no signal uses any more, released as Trend Researcher 1.4.0.0.

**Architecture:**
- One new agent flow, `TRCleanupSignals`. It uses only SharePoint connector actions and no new connection reference.
- One new environment variable, `tr_RetentionDays`.
- Two new column indexes on **Signals**.
- A one-line-per-flow fix to `solution.xml`, so every flow is a solution root component, plus a build rule that keeps it that way.

**Tech Stack:** Power Automate flow JSON (source in `verticals/trend-researcher/solution/`), the YAML SharePoint schema, `tools/build.py`, and `unittest`.

**Spec:** [`verticals/trend-researcher/docs/design/2026-11-02-tr-cleanup-signals-design.md`](../design/2026-11-02-tr-cleanup-signals-design.md)

## Global Constraints

- **Statuses deleted:** exactly `Rejected` and `Monitor`. `Digest` and `NeedsReview` are never deleted.
- **SourceItems rows are never deleted.** A purged row gets `field_7` (EvidenceUrl) = `""` and `field_8` (ContentStatus) = `Purged`.
- **An evidence file is deleted only when no Signal with the same `field_1` (SourceItemId) is left.**
- **Schedule:** monthly, `monthDays: [1]`, `hours: [3]`, `minutes: [0]`, UTC (no `timeZone`).
- **`tr_RetentionDays`:** Number (`<type>100000001</type>`), default `90`; `0` turns the cleanup off. The flow parameter name is `Signal retention (days) (tr_RetentionDays)` and its type is `Int`.
- **Batch:** `$top` 500 per status.
- **Loops:** both loops run with `runtimeConfiguration.concurrency.repetitions: 1`.
- **Flow identity:**
  - WorkflowId `{07c37191-9c6e-4a13-b193-49594db1a239}`;
  - source file `solution/Workflows/TRCleanupSignals.json`;
  - built file `Workflows/TRCleanupSignals-07C37191-9C6E-4A13-B193-49594DB1A239.json`;
  - `IntroducedVersion` `1.4.0.0`.
- **Names:** en `TR Clean Up Signals`, es `VT Limpiar Señales`.
- **Flow JSON follows `shared/flow-snippets/README.md`:**
  - copy the action shapes from the snippets;
  - no `metadata.nodeId`;
  - no tenant `connectionName` in `connectionReferences`;
  - no stray trailing `\n`.
- **Files not to touch:** `verticals/trend-researcher/prompts/`, other flows' JSON, `releases/trend-researcher/1.3.0.0/`.
- **Don't commit unless the user asks.** When committing, use the git identity rules in the user's CLAUDE.md.

Run all tests with:

`PWSH=<path-to-pwsh> python3 -m unittest discover -s tools/tests`

Without `PWSH`, the PnP tests skip.

## Review Focus

1. **A source item shared with another brief.** Its `Digest` or `NeedsReview` signal must keep the evidence file. This is pinned by `test_evidence_only_when_no_signal_left` (Task 3).
2. **A source item with no EvidenceUrl, or a row someone deleted by hand.** For example, a `MetadataOnly` upload. The evidence branch must be skipped, not fail. This is pinned by `test_missing_source_item_or_evidence_is_skipped` (Task 3).
3. **`tr_RetentionDays` = 0.** Nothing is queried or deleted. This is pinned by `test_retention_zero_turns_off` (Task 3).
4. **Lists over 5,000 items.** Both filtered Signals columns must be indexed in new sites, and the upgrade notes tell existing sites to add them. This is pinned by `test_signals_cleanup_columns_indexed` (Task 2); the docs are in Task 4.
5. **An evidence file already deleted by hand.** That iteration fails and the others continue. This can't be tested offline; it is acceptance item 4 in Task 4.

---

### Task 1: Every flow is a solution root component

`solution.xml` lists only the three 1.1 flows as `RootComponent type="29"`. The tenant export (`brainstorm/tr-exported-solution/Workflows/solution.xml`) lists every flow, including TRDocTest. `TRProcessDocuments` (`{58bca39f-6f0f-4947-ba05-d2291ea1e08d}`) and `TRBusinessCase` (`{9373450f-fa1e-44c2-ace2-2d86ca9249c7}`) are missing.

**Files:**
- Modify: `tools/build.py` (`validate_solution`)
- Modify: `verticals/trend-researcher/solution/solution.xml` (`<RootComponents>`)
- Test: `tools/tests/test_build.py` (ValidationTests)

**Interfaces:**
- Produces: the validator error text `workflow {<id>} is not a RootComponent in solution.xml`. Task 3 relies on this rule when it adds the new flow.

- [ ] **Step 1: Write the failing tests** in the ValidationTests class of `test_build.py`, following the pattern of `test_tenant_connection_name_fails`:
  - `test_workflow_not_root_component_fails`: remove the `RootComponent` line for `{f73f937f-667a-8edc-33bf-30cddb0276b6}` from the rendered `solution.xml`, then `assertRaisesRegex(build.BuildError, "not a RootComponent")`.
  - `test_every_workflow_is_root_component`: for `en` and `es`, collect the `WorkflowId`s from `customizations.xml` and the `RootComponent[@type='29']` ids from `solution.xml`, both lower-cased. Assert the first set is a subset of the second.

- [ ] **Step 2: Run the tests** and check that both fail:

  `python3 -m unittest test_build -k root_component` (run from `tools/tests`)

- [ ] **Step 3: Add the rule to `validate_solution`.** Parse `files["solution.xml"]`, collect the `RootComponent` ids where `type == "29"`, compare them case-insensitively with each `Workflow`'s `WorkflowId`, and append the error above for each one that is missing.

- [ ] **Step 4: Add the two missing entries to `solution.xml`.** Add `<RootComponent type="29" id="{58bca39f-6f0f-4947-ba05-d2291ea1e08d}" behavior="0" />` and the same line for `{9373450f-fa1e-44c2-ace2-2d86ca9249c7}`. Keep the ids sorted, as the export does.

- [ ] **Step 5: Run the full suite.** Expected: all tests pass.

- [ ] **Step 6: Add a CHANGELOG entry.** Under a new `## 1.4.0.0 (unreleased)` → `### Fixed` heading, write: `TR Process Documents` and `TR Business Case` were missing from the solution's root components, so a solution import could leave them out of the solution. Every flow is now a root component, and the build checks it.

### Task 2: Signals indexes and `tr_RetentionDays`

**Files:**
- Modify: `verticals/trend-researcher/sharepoint/lists/04-Signals.yaml` (add `indexed: true` to `field_1` and `field_11`)
- Create: `verticals/trend-researcher/solution/environmentvariabledefinitions/tr_RetentionDays/environmentvariabledefinition.xml`, a copy of `tr_MaxUploadBytes` with:
  - `defaultvalue` `90`;
  - `introducedversion` `1.4.0.0`;
  - the `tr_RetentionDays` i18n keys.
- Modify: `verticals/trend-researcher/i18n/en.yaml`, `es.yaml` (`env.tr_RetentionDays`)
- Modify: `verticals/trend-researcher/settings/deployment-settings.example.json` (add `{ "SchemaName": "tr_RetentionDays", "Value": "90" }`)
- Test: `tools/tests/test_trend_researcher_flows.py`

**Interfaces:**
- Produces:
  - the env var schema name `tr_RetentionDays`;
  - the Signals fields `field_1` and `field_11` rendered with `Indexed="TRUE"`.

- [ ] **Step 1: Write the failing tests.**
  - `test_signals_cleanup_columns_indexed` (new class `CleanupSchemaTests`): `build.Vertical(build.ROOT, "trend-researcher").list_by_key("Signals")` has `indexed: True` on `field_1` and on `field_11`. Also, for `en`, `build.render_pnp_template(...)` contains `Indexed="TRUE"` in the `<Field` elements whose `Name` is `field_1` and `field_11` of the Signals list.
  - `test_retention_days_env_var`: the built `en` files contain `environmentvariabledefinitions/tr_RetentionDays/environmentvariabledefinition.xml`, with `<defaultvalue>90</defaultvalue>` and `<type>100000001</type>`.
  - Add `"tr_RetentionDays"` to the tuple in `DeploymentSettingsExampleTests`.

- [ ] **Step 2: Run the tests.** Expected: the three tests fail.

- [ ] **Step 3: Make the changes** listed under **Files**. Use this i18n text:
  - **en name:** `Signal retention (days)`
  - **en description:** `Rejected and Monitor signals older than this are deleted on the 1st of each month, with their evidence file once no other signal uses it. 0 turns the cleanup off.`
  - **es name:** `Retención de señales (días)`
  - **es description:** `Las señales Rejected y Monitor más antiguas que este número de días se eliminan el día 1 de cada mes, junto con su archivo de evidencia cuando ninguna otra señal lo usa. 0 desactiva la limpieza.`

- [ ] **Step 4: Run the full suite.** Expected: all tests pass. If a test in `test_build.py` pins the Signals CSV or PnP output byte for byte, update its expected text to include the index.

### Task 3: Flow `TRCleanupSignals`

**Files:**
- Create: `verticals/trend-researcher/solution/Workflows/TRCleanupSignals.json`
- Create: three snippets, `shared/flow-snippets/sharepoint/delete-item.json`, `delete-file.json` and `get-file-metadata-by-path.json`. Use the format of `get-file-metadata.json`, with `"source": "connector-docs"` and `"verified": false`.
- Modify: `shared/flow-snippets/README.md`. The `verified: false` line names all four unverified snippets and says they stay unverified "until the 1.4.0.0 acceptance run".
- Modify: `verticals/trend-researcher/solution/customizations.xml`. Add a `<Workflow>` entry copied from `TRProcessDocuments`, with the WorkflowId, the JSON file name `/Workflows/TRCleanupSignals.json`, `IntroducedVersion` `1.4.0.0` and the keys `flows.cleanupSignals.name` and `flows.cleanupSignals.description`.
- Modify: `verticals/trend-researcher/solution/solution.xml` (the `RootComponent` for the new id)
- Modify: `verticals/trend-researcher/i18n/en.yaml`, `es.yaml` (`flows.cleanupSignals`)
- Modify: `tools/tests/test_build.py` (`test_build`: 5 → 6 workflows; `test_workflow_files_get_export_names`: add `"TRCleanupSignals.json"` to the sorted list)
- Test: `tools/tests/test_trend_researcher_flows.py` (new class `CleanupSignalsTests`, with `CLEANUP = "Workflows/TRCleanupSignals-07C37191-9C6E-4A13-B193-49594DB1A239.json"`)

**Interfaces:**
- Consumes: `tr_RetentionDays` (Task 2) and the root-component rule (Task 1).
- Consumes: the existing parameters `Site URL (tr_SiteURL)`, `Signals list (tr_SignalsList)` and `Source Items list (tr_SourceItemsList)`. Copy their `definition.parameters` entries verbatim from `TRClassifyItems.json`.
- Consumes: the connection reference block `shared_sharepointonline`, copied from `TRProcessDocuments.json`.

**Flow structure.** These are the exact action names. `SP` means a SharePoint `OpenApiConnection` with `dataset` = `@parameters('Site URL (tr_SiteURL)')`. Signals is `@parameters('Signals list (tr_SignalsList)')` and SourceItems is `@parameters('Source Items list (tr_SourceItemsList)')`.

| Action (parent) | Type / operationId | Key inputs |
|---|---|---|
| `Recurrence` (trigger) | Recurrence | `{"frequency": "Month", "interval": 1, "schedule": {"monthDays": [1], "hours": [3], "minutes": [0]}}` |
| `If_Retention_Enabled` (root) | If | `{"and": [{"greater": ["@parameters('Signal retention (days) (tr_RetentionDays)')", 0]}]}`; no `else` actions |
| `Cutoff` (If_Retention_Enabled) | Compose | `@formatDateTime(addDays(utcNow(), mul(-1, parameters('Signal retention (days) (tr_RetentionDays)'))), 'yyyy-MM-ddTHH:mm:ssZ')` |
| `Loop_Statuses` (If_Retention_Enabled, after Cutoff) | Foreach, repetitions 1 | `foreach`: `@createArray('Rejected', 'Monitor')` |
| `Get_Old_Signals` (Loop_Statuses) | SP GetItems | table Signals; `$filter`: `field_11 eq '@{items('Loop_Statuses')}' and Created lt '@{outputs('Cutoff')}'`; `$top`: `500` |
| `Loop_Signals` (Loop_Statuses, after Get_Old_Signals) | Foreach, repetitions 1 | `foreach`: `@outputs('Get_Old_Signals')?['body/value']` |
| `Delete_Signal` (Loop_Signals) | SP DeleteItem | table Signals; `id`: `@items('Loop_Signals')?['ID']` |
| `Get_Remaining_Signals` (Loop_Signals, after Delete_Signal) | SP GetItems | table Signals; `$filter`: `field_1 eq @{items('Loop_Signals')?['field_1']}`; `$top`: `1` |
| `If_No_Signals_Left` (Loop_Signals, after Get_Remaining_Signals) | If | `{"and": [{"empty": ["@outputs('Get_Remaining_Signals')?['body/value']"]}]}` |
| `Get_Source_Item` (If_No_Signals_Left) | SP GetItems | table SourceItems; `$filter`: `ID eq @{items('Loop_Signals')?['field_1']}`; `$top`: `1` |
| `If_Has_Evidence` (If_No_Signals_Left, after Get_Source_Item) | If | `{"and": [{"not": {"empty": ["@first(outputs('Get_Source_Item')?['body/value'])?['field_7']"]}}]}` |
| `Get_Evidence_File` (If_Has_Evidence) | SP GetFileMetadataByPath | `path`: `@first(outputs('Get_Source_Item')?['body/value'])?['field_7']` |
| `Delete_Evidence_File` (If_Has_Evidence, after Get_Evidence_File) | SP DeleteFile | `id`: `@outputs('Get_Evidence_File')?['body/Id']` |
| `Mark_Source_Item_Purged` (If_Has_Evidence, after Delete_Evidence_File `Succeeded`) | SP PatchItem | table SourceItems; `id`: `@first(outputs('Get_Source_Item')?['body/value'])?['ID']`; `item/field_7`: `""`; `item/field_8`: `Purged` |

Each action gets a one-line `metadata.description` explaining why the step exists, as the other flows do. For example, `Get_Remaining_Signals` gets "Another brief's signal still uses this evidence".

- [ ] **Step 1: Write the failing tests** in `CleanupSignalsTests`, using `load_built`, `find_action`, `params`, `path_to` and `run_after` from `flowtest`:
  - `test_monthly_schedule`: the trigger's `recurrence` equals the dict in the table, and it has no `timeZone`.
  - `test_retention_zero_turns_off`:
    - `If_Retention_Enabled.expression` equals the table value;
    - `path_to(doc, "Loop_Statuses") == ["If_Retention_Enabled"]`;
    - the flow's root `actions` keys are exactly `{"If_Retention_Enabled"}`.
  - `test_only_rejected_and_monitor`:
    - `Loop_Statuses.foreach == "@createArray('Rejected', 'Monitor')"`;
    - the `Get_Old_Signals` `$filter` equals the table value, its `$top` is 500 and its `table` is the Signals parameter;
    - the strings `'Digest'` and `'NeedsReview'` appear nowhere in the flow JSON.
  - `test_cutoff_uses_retention_days`: the `Cutoff` inputs contain `addDays(utcNow(), mul(-1, parameters('Signal retention (days) (tr_RetentionDays)')))`.
  - `test_loops_sequential`: both Foreach actions have `runtimeConfiguration.concurrency.repetitions == 1`.
  - `test_evidence_only_when_no_signal_left`:
    - `run_after(doc, "Get_Remaining_Signals") == {"Delete_Signal": ["Succeeded"]}`;
    - the `Get_Remaining_Signals` `$filter` and `$top` equal the table values;
    - `path_to(doc, "Delete_Evidence_File")` ends with `["If_No_Signals_Left", "If_Has_Evidence"]`.
  - `test_missing_source_item_or_evidence_is_skipped`:
    - `If_Has_Evidence.expression` equals the table value (`first(...)?['field_7']` is null-safe for an empty result);
    - the `Get_Source_Item` `$filter` uses `ID eq`.
  - `test_source_item_kept_as_tombstone`:
    - every action with operationId `DeleteItem` has `table` equal to the Signals parameter;
    - the `Mark_Source_Item_Purged` params have `item/field_7 == ""` and `item/field_8 == "Purged"`;
    - its `runAfter` is `{"Delete_Evidence_File": ["Succeeded"]}`.
  - `test_cleanup_localized`: `customizations.xml` built for `en` has a Workflow named `TR Clean Up Signals`, and the one built for `es` has `VT Limpiar Señales`.

- [ ] **Step 2: Run the tests.** Expected: they fail with `KeyError` (the file isn't in the built solution).

- [ ] **Step 3: Write the snippets**, then the flow JSON from the table, then the `customizations.xml` and `solution.xml` entries and the i18n strings:
  - **en description:** `Monthly. Deletes Rejected and Monitor signals older than tr_RetentionDays, and the evidence file of a source item once none of its signals is left. SourceItems rows are kept and marked Purged.`
  - **es description:** `Mensual. Elimina las señales Rejected y Monitor más antiguas que tr_RetentionDays y el archivo de evidencia de un elemento fuente cuando ya no le queda ninguna señal. Las filas de SourceItems se conservan y se marcan como Purged.`

- [ ] **Step 4: Run the full suite.** Expected: all tests pass, including the build validator (field names in `$filter`, parameters, root components, lint).

### Task 4: Docs and release 1.4.0.0

**Files:**
- Modify: `verticals/trend-researcher/vertical.yaml` (`version: 1.4.0.0`)
- Modify: `verticals/trend-researcher/CHANGELOG.md` (the 1.4.0.0 section from Task 1)
- Modify: `verticals/trend-researcher/docs/quickstart.en.md` and `quickstart.es.md`
- Modify: `docs/environment-variables.md` (a `tr_RetentionDays` row)
- Create: `releases/trend-researcher/1.4.0.0/` (generated)

- [ ] **Step 1: Write the CHANGELOG 1.4.0.0 section.**
  - **Added:** the flow, with a one-paragraph summary of the spec's table; `tr_RetentionDays`; indexes on Signals `SourceItemId` and `Status`; the `ContentStatus` value `Purged`.
  - **Upgrade notes:**
    - add the two indexes by hand on existing sites;
    - set `tr_RetentionDays` before turning the flow on (it defaults to 90).
  - **Known open points:** the four acceptance items from the spec.

- [ ] **Step 2: Update both quickstarts.**
  - Add a row for the flow in the flow table at the top ("Monthly (day 1)").
  - Add the flow to the "Turn the flows on" list in section 4.
  - Mention `Purged` wherever the `ContentStatus` values are listed.
  - Add `### Upgrading from 1.3 to 1.4`:
    1. Import the solution.
    2. On **Signals**, open *List settings → Indexed columns → Create a new index* and create one for *SourceItemId* and one for *Status*.
    3. Optionally change `tr_RetentionDays`.
    4. Turn **TR Clean Up Signals** on.

    Add one sentence saying that deleted signals and files go to the site recycle bin. Mark it "to verify" until acceptance item 1 is done.

- [ ] **Step 3: Release.** Run `python3 tools/build.py trend-researcher --release`, then the full suite. Expected:
  - `releases/trend-researcher/1.4.0.0/` exists, with `SHA256SUMS`;
  - all tests pass;
  - `releases/trend-researcher/1.3.0.0/` is unchanged (`git status` shows no change there).

- [ ] **Step 4: Run the acceptance check in a dev tenant.** The user does this; it is recorded in the CHANGELOG once done.
  1. Import 1.4.0.0 over 1.3 and add the indexes.
  2. Set `tr_RetentionDays` to `1` and run the flow manually.
  3. Confirm:
     - only `Rejected` and `Monitor` signals older than a day are gone;
     - a source item that still has a `Digest` signal keeps its evidence file;
     - purged source items show `Purged` and an empty `EvidenceUrl`;
     - the deleted items are in the site recycle bin.
  4. Delete one evidence file by hand before a run. Confirm that only that iteration fails.
  5. Mark the three new snippets `verified: true` if their shapes match an export of the flow.
