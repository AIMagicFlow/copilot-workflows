# Flow snippets

Connector shapes for new flows. Copy the `trigger` or `action` block from a snippet instead of writing the shape from memory.

Each file has `connector`, `operationId`, `source`, `verified`, `notes` and a `trigger` or `action` block.

- `source` is `tenant-export`, `coe-starter-kit`, `pnp-samples` or `connector-docs`.
- `verified: false` means the shape has not been checked against a real export. `sharepoint/copy-file.json`, `sharepoint/delete-item.json`, `sharepoint/delete-file.json` and `sharepoint/get-file-metadata-by-path.json` are in that state, until the 1.4.0.0 acceptance run.

Tenant values never go into a snippet:

- `dataset` is `@parameters('Site URL (tr_SiteURL)')`.
- `table` is `<list-or-library-parameter>`.
- `connectionName` is the connector's short name, such as `shared_sharepointonline`.
- `metadata.nodeId` is dropped.

## Lessons from the tenant export

- The trigger's `{Identifier}` feeds the `id` of `GetFileMetadata` and `GetFileContent`. The trigger's `ID` is the file's list item ID, and it survives renames.
- **`GetFileContent` with `inferContentType: false`.** The body is then always `{"$content-type", "$content"}`, and `base64ToString(body(..)?['$content'])` is safe. The export used `true`, which can return text files as a plain string. The 1.2.0.0 acceptance run confirms the choice.
- **Extension checks use `toLower`.** `endsWith(name, '.txt')` misses `REPORT.TXT`.
- **The designer adds a trailing line break** when Enter is pressed in a field. The export's `Create_file.name` ended in one. The validator rejects a string whose only line break is at its end.
- **`SetVariable` cannot reference its own variable.** Inside a loop, use `Compose` and then `Set variable` from the Compose output.
- **A loop that sets a variable must run sequentially:** `runtimeConfiguration.concurrency.repetitions: 1`.
- **"For a selected item" is not used.** That trigger only appears in SharePoint's Automate menu for flows in the default environment. Use "When an item is created or modified" with a trigger condition instead.
- **Never write to the library a file trigger watches** with `CreateFile` or `CopyFileAsync` in the same flow. Each write fires the trigger again. The validator checks this.
