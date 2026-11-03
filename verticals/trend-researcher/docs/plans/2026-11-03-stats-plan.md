# TR Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Trend Researcher 1.5.0.0 with three things: a **Stats** list of 19 classifier-tuning metrics, refreshed daily by a new flow **TR Refresh Stats**; and relevance thresholds that can be tuned through environment variables.

**Architecture:** One new SharePoint list and one new agent flow that is the only writer to that list. The flow reads Signals once per status, counts in memory and creates or updates one row per metric. TR Classify Items reads its two thresholds from new env vars instead of literals. No new connection reference.

**Tech Stack:** Power Automate flow JSON (source in `verticals/trend-researcher/solution/`), the YAML SharePoint schema, `tools/build.py`, `unittest`.

**Spec:** [`verticals/trend-researcher/docs/design/2026-11-03-tr-stats-design.md`](../design/2026-11-03-tr-stats-design.md)

## Global Constraints

- **Version:** `1.5.0.0`. Every new component has `IntroducedVersion` / `introducedversion` / `since` `1.5.0.0`.
- **New flow:**
  - WorkflowId `{3f6c2a8e-5b1d-4e7a-9c40-8d2f61b7a913}`.
  - Source `solution/Workflows/TRRefreshStats.json`.
  - Built `Workflows/TRRefreshStats-3F6C2A8E-5B1D-4E7A-9C40-8D2F61B7A913.json`.
  - Names: en `TR Refresh Stats`, es `VT Actualizar Estadísticas`.
- **New list:** `Stats`, at URL `Lists/Stats`. Titles: en `Stats`, es `Estadísticas`. Schema file `sharepoint/lists/08-Stats.yaml`.
- **New env vars:**

  | Variable | Type | Default | Flow parameter name |
  |---|---|---|---|
  | `tr_StatsList` | String (`100000000`) | `{{list:Stats}}` | `Stats list (tr_StatsList)` |
  | `tr_RejectBelow` | Number (`100000001`) | `40` | `Reject below relevance (tr_RejectBelow)`, `Int` |
  | `tr_DigestFrom` | Number (`100000001`) | `70` | `Digest from relevance (tr_DigestFrom)`, `Int` |
- **Status codes:** exactly `Digest`, `Monitor`, `Rejected`, `NeedsReview`.
- **Tag codes:** exactly `CompetitorLaunch`, `RegulatoryAlert`, `NewTechnology`.
- **Signals fields:** `field_7` is Relevance, `field_11` is Status, and `AlertTags` is a multi-choice column.
- **Flow JSON follows `shared/flow-snippets/README.md`:**
  - copy action shapes from the snippets;
  - no `metadata.nodeId`;
  - no `connectionName` in `connectionReferences`;
  - no stray trailing `\n`;
  - a loop that sets variables runs with `repetitions: 1`;
  - `SetVariable` never reads its own variable.
- **Releases:** zips are not committed. `--release` writes to `dist/release/`, and the user publishes the GitHub Release after the merge (see README "Build and release").
- **Commits:** don't commit unless the user asks. Use the git identity rules in the user's CLAUDE.md.

**Test command:**

```bash
PWSH=<path-to-pwsh> python3 -m unittest discover -s tools/tests
```

Without `PWSH`, the PnP tests skip.

## Review Focus

1. **Duplicate signals across briefs.** Two signals with the same Created second, status, relevance and tags (common when one item is classified for several briefs) would be merged by `union()` when the per-status arrays are joined. The projection carries `ID` so they stay distinct. Pinned by `test_projection_keeps_id` (Task 3).
2. **Relevance that is empty or a decimal** (`85` or `85.0`). The bucket must be `-1` (no bucket) or `floor/10` clamped to 0–9, and must never fail the run. Pinned by `test_bucket_expression` (Task 3).
3. **First run, or a Stats row deleted by hand.** The row must be created, not updated. Pinned by `test_missing_row_is_created` (Task 3).
4. **A status with no signals in the window.** Its row is still written, with zeros, because the 19 metrics come from a fixed list rather than from the data. Pinned by `test_nineteen_metrics_in_order` (Task 3).
5. **A signal created exactly 7 days ago.** It counts in Last 7 days (`>=`) and not in Previous 7 days (`<`). Pinned by `test_window_boundaries` (Task 3).

These need a tenant and go to acceptance (Task 4):
- more than 5,000 signals of one status;
- the `AlertTags` output shape of `GetItems`.

---

### Task 1: Tunable thresholds in TR Classify Items

**Files:**
- Create: `verticals/trend-researcher/solution/environmentvariabledefinitions/tr_RejectBelow/environmentvariabledefinition.xml` and `.../tr_DigestFrom/environmentvariabledefinition.xml`. Copy `tr_RetentionDays` and change the default and the keys.
- Modify: `verticals/trend-researcher/solution/Workflows/TRClassifyItems.json`:
  - add two `definition.parameters` entries;
  - in `Create_Signal`'s `item/field_11`, replace the literal `40` with `parameters('Reject below relevance (tr_RejectBelow)')` and `70` with `parameters('Digest from relevance (tr_DigestFrom)')`.
- Modify: `verticals/trend-researcher/i18n/en.yaml`, `es.yaml` (`env.tr_RejectBelow`, `env.tr_DigestFrom`)
- Modify: `verticals/trend-researcher/settings/deployment-settings.example.json` (`"40"`, `"70"`)
- Modify: `docs/environment-variables.md` (two rows, in the style of `tr_RetentionDays`)
- Test: `tools/tests/test_trend_researcher_flows.py` (new class `ThresholdTests`)

**Interfaces:**
- Produces: the env vars `tr_RejectBelow` and `tr_DigestFrom`. Task 4 documents them.

- [ ] **Step 1: Write the failing tests.**
  - `test_thresholds_from_env_vars`: `params(load_built("en", CLASSIFY), "Create_Signal")["item/field_11"]` contains both parameter expressions above and does not match `re.search(r"\b(40|70)\b", ...)`.
  - `test_needs_review_checked_first`: the same expression still starts with `@if(` and has `'NeedsReview'` before `'Rejected'`.
  - `test_threshold_env_defaults`: the built env var XML has `<defaultvalue>40</defaultvalue>` and `<defaultvalue>70</defaultvalue>`, both `<type>100000001</type>`.
  - In `DeploymentSettingsExampleTests`, add `"tr_RejectBelow"` and `"tr_DigestFrom"` to the tuple.
- [ ] **Step 2: Run the tests.** Expected: the new tests fail.
- [ ] **Step 3: Make the changes** listed under Files. Use this i18n text:
  - **en `tr_RejectBelow`:** name `Reject below relevance`; description `Signals with a relevance below this value get Status Rejected. Applies to items classified after a change; existing signals keep their status.`
  - **en `tr_DigestFrom`:** name `Digest from relevance`; description `Signals with a relevance at or above this value get Status Digest; values between the two thresholds get Monitor. Keep it above tr_RejectBelow, or no signal gets Monitor.`
  - **es `tr_RejectBelow`:** `Rechazar por debajo de relevancia` / `Las señales con relevancia inferior a este valor reciben el estado Rejected. Se aplica a los elementos clasificados después del cambio; las señales existentes conservan su estado.`
  - **es `tr_DigestFrom`:** `Resumen desde relevancia` / `Las señales con relevancia igual o superior a este valor reciben el estado Digest; los valores entre los dos umbrales reciben Monitor. Manténgalo por encima de tr_RejectBelow o ninguna señal recibirá Monitor.`
- [ ] **Step 4: Run the full suite.** Expected: all tests pass. If an existing classifier test pins the literal expression, update it to the new one.

### Task 2: Stats list and `tr_StatsList`

**Files:**
- Create: `verticals/trend-researcher/sharepoint/lists/08-Stats.yaml`, with `list: Stats` and `since: "1.5.0.0"`. Readable internal names, in this order:
  - `Title` (builtin);
  - `MetricKey` (Text, `unique: true`, `indexed: true`);
  - `MetricGroup` (Text);
  - `SortOrder` (Number);
  - `Last7Days`, `Previous7Days`, `Last30Days` (Number);
  - `UpdatedAt` (DateTime).

  Every field has `since: "1.5.0.0"`. The en display names equal the internal names, and `Title` displays as `Metric`. The es display names are `Métrica`, `Clave`, `Grupo`, `Orden`, `Últimos 7 días`, `7 días anteriores`, `Últimos 30 días`, `Actualizado`. The list description is: en `Classifier tuning metrics, refreshed daily by TR Refresh Stats. Do not edit by hand.`, es `Métricas para ajustar el clasificador; TR Refresh Stats las actualiza cada día. No las edite a mano.`
- Create: `verticals/trend-researcher/solution/environmentvariabledefinitions/tr_StatsList/environmentvariabledefinition.xml`, copied from `tr_BusinessCaseRequestsList`.
- Modify: `verticals/trend-researcher/i18n/en.yaml`, `es.yaml` (`env.tr_StatsList`: `Stats list` / `Title or ID (GUID) of the Stats list.`; es `Lista de estadísticas` / `Título o ID (GUID) de la lista de estadísticas.`)
- Modify: `verticals/trend-researcher/settings/deployment-settings.example.json`, `docs/environment-variables.md`
- Test: `tools/tests/test_trend_researcher_flows.py` (new class `StatsSchemaTests`)

**Interfaces:**
- Produces: list key `Stats`; the field names above; env var `tr_StatsList`. Task 3 writes exactly these field names.

- [ ] **Step 1: Write the failing tests.**
  - `test_stats_list_schema`: `build.Vertical(build.ROOT, "trend-researcher").list_by_key("Stats")` has the field names in the order above, and `MetricKey` is unique and indexed.
  - `test_stats_list_env_var`: the built XML default is `Stats`, the resolved list title for `en`.
  - In `DeploymentSettingsExampleTests`, add `"tr_StatsList"`.
- [ ] **Step 2: Run the tests.** Expected: the new tests fail.
- [ ] **Step 3: Make the changes.**
- [ ] **Step 4: Run the full suite.** Expected: all tests pass. Update the counts in `test_build.py` that pin the number of lists or fields, if any change.

### Task 3: Flow `TRRefreshStats`

**Files:**
- Create: `verticals/trend-researcher/solution/Workflows/TRRefreshStats.json`
- Modify: `verticals/trend-researcher/solution/customizations.xml`. Add a `<Workflow>` entry copied from `TRCleanupSignals`, with the WorkflowId, `/Workflows/TRRefreshStats.json`, `IntroducedVersion` `1.5.0.0` and the keys `flows.refreshStats.*`.
- Modify: `verticals/trend-researcher/solution/solution.xml` (the `RootComponent type="29"` for the new id)
- Modify: `verticals/trend-researcher/i18n/en.yaml`, `es.yaml` (`flows.refreshStats`, `stats.*`)
- Modify: `tools/tests/test_build.py` (workflow count 6 → 7, and add `"TRRefreshStats.json"` to the sorted source list)
- Test: `tools/tests/test_trend_researcher_flows.py` (new class `RefreshStatsTests`, `STATS = "Workflows/TRRefreshStats-3F6C2A8E-5B1D-4E7A-9C40-8D2F61B7A913.json"`)

**Interfaces:**
- Consumes:
  - `tr_StatsList` and the Stats field names (Task 2);
  - the existing parameters `Site URL (tr_SiteURL)` and `Signals list (tr_SignalsList)`, with their `definition.parameters` entries copied from `TRCleanupSignals.json`;
  - the `shared_sharepointonline` connection reference block, copied from `TRCleanupSignals.json`.

**i18n strings** (`stats.*`):

| Key | en | es |
|---|---|---|
| `stats.groupSignals` | `Signals` | `Señales` |
| `stats.groupRelevance` | `Relevance` | `Relevancia` |
| `stats.groupAlertTags` | `Alert tags` | `Etiquetas de alerta` |
| `stats.total` | `total` | `total` |
| `stats.alertTag` | `Alert tag` | `Etiqueta de alerta` |
| `stats.anyTag` | `any` | `cualquiera` |

**Flow description:**
- en: `Daily. Counts signals of the last 30 days by status, relevance band and alert tag, and writes the totals to the Stats list for tuning the classifier.`
- es: `Diario. Cuenta las señales de los últimos 30 días por estado, franja de relevancia y etiqueta de alerta, y escribe los totales en la lista de estadísticas para ajustar el clasificador.`

**Flow structure.** These are the exact names. `SP` means a SharePoint `OpenApiConnection` with `dataset` `@parameters('Site URL (tr_SiteURL)')`; `Signals` and `Stats` stand for the list parameters.

| Action (parent, runAfter) | Type / operationId | Key inputs |
|---|---|---|
| `Recurrence` (trigger) | Recurrence | `{"frequency": "Day", "interval": 1, "schedule": {"hours": [17], "minutes": [0]}}`; trigger `runtimeConfiguration.concurrency.runs: 1` |
| `Now` (root) | Compose | `@utcNow()` |
| `Since30`, `Since14`, `Since7` (root, chained after Now) | Compose | `@formatDateTime(addDays(outputs('Now'), -30), 'yyyy-MM-ddTHH:mm:ssZ')`, with `-14` and `-7` |
| `Init_Signals` (root, after Since7) | InitializeVariable | `{"name": "Signals", "type": "array", "value": []}` |
| `Loop_Statuses` (root, after Init_Signals) | Foreach, repetitions 1 | `@createArray('Digest', 'Monitor', 'Rejected', 'NeedsReview')` |
| `Get_Signals` (Loop_Statuses) | SP GetItems | table Signals; `$filter` `field_11 eq '@{items('Loop_Statuses')}' and Created ge '@{outputs('Since30')}'`; `$top` 5000; `runtimeConfiguration.paginationPolicy.minimumItemCount` 5000 |
| `Project_Signals` (Loop_Statuses) | Select | from `@outputs('Get_Signals')?['body/value']`; map below |
| `Join_Signals` (Loop_Statuses) | Compose | `@union(variables('Signals'), body('Project_Signals'))` |
| `Set_Signals` (Loop_Statuses) | SetVariable | `Signals` = `@outputs('Join_Signals')` |
| `Get_Stats_Rows` (root, after Loop_Statuses) | SP GetItems | table Stats; `$top` 100 |
| `Metrics` (root, after Get_Stats_Rows) | Compose | the fixed 19-object array below |
| `Loop_Metrics` (root, after Metrics) | Foreach, repetitions 1 | `@outputs('Metrics')` |
| `Filter_Metric` (Loop_Metrics) | Query (Filter array) | from `@variables('Signals')`; where-expression below |
| `Filter_Last7` (Loop_Metrics) | Query | from `@body('Filter_Metric')`; `@greaterOrEquals(ticks(item()?['Created']), ticks(outputs('Since7')))` |
| `Filter_Previous7` (Loop_Metrics) | Query | from `@body('Filter_Metric')`; `@and(greaterOrEquals(ticks(item()?['Created']), ticks(outputs('Since14'))), less(ticks(item()?['Created']), ticks(outputs('Since7'))))` |
| `Find_Row` (Loop_Metrics) | Query | from `@outputs('Get_Stats_Rows')?['body/value']`; `@equals(item()?['MetricKey'], items('Loop_Metrics')?['Key'])` |
| `If_Row_Exists` (Loop_Metrics) | If | `{"and": [{"not": {"empty": ["@body('Find_Row')"]}}]}` |
| `Update_Row` (If_Row_Exists) | SP PatchItem | table Stats; `id` `@first(body('Find_Row'))?['ID']`; the row fields below |
| `Create_Row` (If_Row_Exists `else`) | SP PostItem | table Stats; the row fields below |

**`Project_Signals` map:**

```json
{
  "ID": "@item()?['ID']",
  "Created": "@item()?['Created']",
  "Status": "@item()?['field_11']",
  "Bucket": "@if(empty(string(item()?['field_7'])), -1, min(max(div(int(first(split(string(item()?['field_7']), '.'))), 10), 0), 9))",
  "TagsText": "@string(coalesce(item()?['AlertTags'], json('[]')))",
  "HasTag": "@not(empty(coalesce(item()?['AlertTags'], json('[]'))))"
}
```

The tag codes are distinct words that never appear in the multi-choice JSON wrapper, so `contains(TagsText, code)` is safe.

**`Metrics` items:** each item is `{"Key", "Label", "Group", "Order", "Kind", "Value"}`. The 19 items, in `Order` 1–19:

| Order | Key | Label | Group | Kind | Value |
|---|---|---|---|---|---|
| 1 | `signals-total` | `{{t:stats.groupSignals}}: {{t:stats.total}}` | `{{t:stats.groupSignals}}` | `all` | `""` |
| 2–5 | `status-Digest`, `status-Monitor`, `status-Rejected`, `status-NeedsReview` | `{{t:stats.groupSignals}}: <code>` | `{{t:stats.groupSignals}}` | `status` | the status code |
| 6–15 | `relevance-0` … `relevance-9` | `{{t:stats.groupRelevance}} 0–9`, …, `90–100` | `{{t:stats.groupRelevance}}` | `bucket` | `0` … `9` (number) |
| 16–18 | `tag-CompetitorLaunch`, `tag-RegulatoryAlert`, `tag-NewTechnology` | `{{t:stats.alertTag}}: <code>` | `{{t:stats.groupAlertTags}}` | `tag` | the tag code |
| 19 | `tag-Any` | `{{t:stats.alertTag}}: {{t:stats.anyTag}}` | `{{t:stats.groupAlertTags}}` | `anytag` | `""` |

**`Filter_Metric` where-expression:**

```text
@or(
  equals(items('Loop_Metrics')?['Kind'], 'all'),
  and(equals(items('Loop_Metrics')?['Kind'], 'status'), equals(item()?['Status'], items('Loop_Metrics')?['Value'])),
  and(equals(items('Loop_Metrics')?['Kind'], 'bucket'), equals(item()?['Bucket'], items('Loop_Metrics')?['Value'])),
  and(equals(items('Loop_Metrics')?['Kind'], 'tag'), contains(item()?['TagsText'], string(items('Loop_Metrics')?['Value']))),
  and(equals(items('Loop_Metrics')?['Kind'], 'anytag'), item()?['HasTag'])
)
```

Write it on one line in the JSON, because the validator rejects a value whose only line break is at its end.

**Row fields** (the same for `Update_Row` and `Create_Row`):
- `item/Title` = `@items('Loop_Metrics')?['Label']`
- `item/MetricKey` = `@items('Loop_Metrics')?['Key']`
- `item/MetricGroup` = `@items('Loop_Metrics')?['Group']`
- `item/SortOrder` = `@items('Loop_Metrics')?['Order']`
- `item/Last7Days` = `@length(body('Filter_Last7'))`
- `item/Previous7Days` = `@length(body('Filter_Previous7'))`
- `item/Last30Days` = `@length(body('Filter_Metric'))`
- `item/UpdatedAt` = `@outputs('Now')`

Each action gets a one-line `metadata.description` saying why it exists. For example, `Project_Signals` gets: "Keep ID so union() does not merge identical signals of different briefs".

- [ ] **Step 1: Write the failing tests** in `RefreshStatsTests`, using `flowtest` helpers:
  - `test_daily_schedule_single_run`: the trigger's `recurrence` equals the table value, and the trigger's `runtimeConfiguration.concurrency.runs == 1`.
  - `test_reads_each_status_once`:
    - `Loop_Statuses.foreach == "@createArray('Digest', 'Monitor', 'Rejected', 'NeedsReview')"`;
    - the `Get_Signals` `$filter` equals the table value;
    - exactly one action in the flow has operationId `GetItems` with `table` = the Signals parameter.
  - `test_projection_keeps_id`: the `Project_Signals` `select` has exactly the keys `ID`, `Created`, `Status`, `Bucket`, `TagsText`, `HasTag`.
  - `test_bucket_expression`: `select["Bucket"]` equals the map value above.
  - `test_nineteen_metrics_in_order`: `find_action(doc, "Metrics")["inputs"]`, built for `en`, is a list of 19 items. Its `Key`s are, in order: `signals-total`, `status-Digest`, `status-Monitor`, `status-Rejected`, `status-NeedsReview`, `relevance-0`…`relevance-9`, `tag-CompetitorLaunch`, `tag-RegulatoryAlert`, `tag-NewTechnology`, `tag-Any`. Its `Order`s are 1–19, and the label of `relevance-9` is `Relevance 90–100`.
  - `test_metrics_localized`: built for `es`, the label of `status-Monitor` is `Señales: Monitor` and the one of `tag-Any` is `Etiqueta de alerta: cualquiera`.
  - `test_window_boundaries`: the `Filter_Last7` `where` uses `greaterOrEquals` against `Since7`; the `Filter_Previous7` `where` uses `greaterOrEquals` against `Since14` and `less` against `Since7`.
  - `test_missing_row_is_created`:
    - `Create_Row` is in the `else` branch of `If_Row_Exists` (`path_to` ends with `"If_Row_Exists/else"`);
    - its operationId is `PostItem` and its table is the Stats parameter;
    - `Update_Row` is `PatchItem`, with `id` `@first(body('Find_Row'))?['ID']`.
  - `test_row_fields`: both write actions have the same eight `item/...` keys, with the values above.
  - `test_only_stats_is_written`: every `PostItem`, `PatchItem` and `DeleteItem` in the flow targets the Stats parameter.
  - `test_refresh_stats_localized`: built `customizations.xml` has `TR Refresh Stats` for `en` and `VT Actualizar Estadísticas` for `es`.
- [ ] **Step 2: Run the tests.** Expected: `KeyError` (the file isn't built yet).
- [ ] **Step 3: Write the flow JSON** from the table, then the `customizations.xml` and `solution.xml` entries and the i18n strings.
- [ ] **Step 4: Run the full suite.** Expected: all tests pass, including the build validator, which checks `$filter` and `item/` field names against the list schemas, parameters, root components and lint rules.

### Task 4: Docs and release 1.5.0.0

**Files:**
- Modify: `verticals/trend-researcher/vertical.yaml` (`version: 1.5.0.0`)
- Modify: `verticals/trend-researcher/CHANGELOG.md` (new `## 1.5.0.0 (unreleased)`)
- Modify: `verticals/trend-researcher/docs/quickstart.en.md`, `quickstart.es.md`
- Modify: `README.md` (the Trend Researcher row, as the release step requires)

- [ ] **Step 1: Add `test_stats_in_upgrade_notes` to `StatsSchemaTests`.** The rendered `upgrade-1.5.0.0.en.md` in the `en` SharePoint kit lists the new list `Stats`; follow how the existing upgrade-notes tests call `render_upgrade_notes`. It fails until the bump, so bump the version and run the full suite. Expected: all tests pass.
- [ ] **Step 2: Update the CHANGELOG.**
  - **Added:** the flow, the Stats list, the three env vars.
  - **Changed:** TR Classify Items reads its thresholds from `tr_RejectBelow` and `tr_DigestFrom`, with the same defaults, so behavior is unchanged.
  - **Upgrade notes:**
    - create the **Stats** list (see the generated `upgrade-1.5.0.0.<locale>.md`);
    - turn on **TR Refresh Stats**.
  - **Known open points:**
    - the four acceptance items from the spec;
    - the `AlertTags` shape returned by `GetItems`;
    - the 5,000-per-status limit.
- [ ] **Step 3: Update both quickstarts.**
  - Add a row to the flow table at the top ("Daily, 17:00 UTC").
  - Add the flow to the "Turn the flows on" list in section 4.
  - Add the two threshold variables and `tr_StatsList` to the environment-variables table in section 3.
  - Add a new subsection at the end of section 5, `### Tune the classifier`:
    - how to put **Stats** on the site home (List web part; a view sorted by `SortOrder` showing Title, Last7Days, Previous7Days, Last30Days and UpdatedAt; optionally grouped by `MetricGroup`);
    - how to read it: Monitor share, relevance rows next to the thresholds, a tag on everything or on nothing, NeedsReview meaning invented tags;
    - that the thresholds apply only to new classifications;
    - the warning not to set `tr_RejectBelow` above `tr_DigestFrom`.
  - Add a Troubleshooting entry: "`UpdatedAt` stopped moving" means a status passed 5,000 signals, or the flow is off.
  - Add `### Upgrading from 1.4 to 1.5`:
    1. Import the solution.
    2. Create **Stats**: with option A, follow the generated upgrade notes; with option B, re-run `provision.ps1`.
    3. Turn **TR Refresh Stats** on and run it once by hand.
    4. Add the web part.
- [ ] **Step 4: Release.** Run `python3 tools/build.py trend-researcher --release`, then the full suite, then update the README row as the README's "Build and release" section says. Expected:
  - `dist/release/trend-researcher/1.5.0.0/` exists, with `SHA256SUMS`;
  - all tests pass;
  - nothing under `releases/` changes.

  The user publishes the GitHub Release after merging.
- [ ] **Step 5: Run the acceptance check in a dev tenant.** The user does this, and the result is recorded in the CHANGELOG. Run the four acceptance checks from the spec, and confirm that the tag rows count correctly. That second check confirms the `AlertTags` shape.
