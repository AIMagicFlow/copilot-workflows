# Document Sanitizer: quickstart for IT

Written for: IT administrators with rights to create resources in the customer's Azure subscription.

The Document Sanitizer is an Azure Function that turns an uploaded document into plain text or Markdown and redacts sensitive data before the text reaches SharePoint. It runs in **your** Azure subscription and region. Documents never leave your tenant.

## What you need

- An Azure subscription where you can create resource groups and role assignments. Creating role assignments requires Owner, or User Access Administrator, on the resource group.
- The Azure CLI, a current version, with the Bicep tooling (`az bicep install`).
- PowerShell 7.4 or later.
- The release folder for the version you were given. It contains `deploy.ps1`, `azuredeploy.json`, the zip, and `SHA256SUMS`.
- A region chosen by your data policy. Every resource is created in that region.

## 1. Check the release

```powershell
cd <release folder>
Get-FileHash -Algorithm SHA256 *.zip, azuredeploy.json, deploy.ps1
```

Compare each hash with the matching line in `SHA256SUMS`. Do not deploy if one differs.

## 2. Deploy

```powershell
az login
./deploy.ps1 -ResourceGroup rg-sanitizer -Location westeurope -NamePrefix dsanit01
```

The script creates the resource group, deploys the infrastructure (Function App, storage, Application Insights, Document Intelligence and a managed identity with the roles it needs), and deploys the function code. It prints the host name.

Use a prefix of 3 to 12 lowercase letters or digits. It appears in every resource name.

## 3. Get the function key

The key is the only credential the flows use. The script never prints it.

1. Open the Function App in the Azure portal.
2. Go to **Functions > sanitize_document > Function Keys**.
3. Copy the **default** key.

Give the key to the person who creates the Power Platform connection. Do not paste it into email, chat, a ticket, or the solution.

## 4. Configure Power Platform

These steps follow the vertical's own quickstart. The vertical sets the environment variables and the connection reference.

1. Set the sanitizer host environment variable (`<prefix>_SanitizerHost`) to `https://<host name from step 2>`. Leave it empty to keep the add-on off.
2. Set the profile environment variable (`<prefix>_SanitizerProfile`) to `default-pii`.
3. Create the sanitizer connection with the function key from step 3.
4. Turn on the flow.

## What the service does

- Text files (TXT, CSV, MD, JSON, XML, LOG) are decoded directly.
- HTML is cleaned of scripts, styles, comments and hidden elements, then converted.
- PDF, Word, Excel, PowerPoint and images go through Azure AI Document Intelligence `prebuilt-read`, which includes OCR.
- Redaction, in this order: the caller's literal terms (case-insensitive, whole words), then email addresses, then phone numbers.
- The response contains the sanitized text and counts. It never contains the matched values.
- Legacy Office files (DOC, XLS, PPT), macro-enabled files and encrypted files are rejected.

## Limits

| Limit | Default | Setting |
|---|---|---|
| File size | 10 MB | `SANITIZER_MAX_FILE_BYTES` |
| Extracted text | 5 MB | `SANITIZER_MAX_TEXT_BYTES` |
| PDF pages, synchronous | 100 | `SANITIZER_MAX_SYNC_PAGES` |
| Caller terms | 500, 200 characters each | fixed |
| Document Intelligence wait | 90 s | `SANITIZER_DI_TIMEOUT_SECONDS` |

## Error codes

Every error body is `{"status": "failed", "error": {"code", "message"}, "correlationId"}`.

| HTTP | Code | Meaning | The flow retries? |
|---|---|---|---|
| 400 | `INVALID_REQUEST`, `INVALID_BASE64` | Malformed request, or Base64 is invalid | no |
| 401 | (host) | Function key missing | no |
| 403 | (host) | Function key invalid | no |
| 413 | `FILE_TOO_LARGE`, `TEXT_TOO_LARGE`, `PAGE_LIMIT_EXCEEDED` | Over a limit | no |
| 415 | `UNSUPPORTED_TYPE` | Type not supported | no |
| 422 | `NOT_EXTRACTABLE`, `REDACTION_INCOMPLETE` | No text, encrypted, corrupt, or a redaction check failed | no |
| 429 | `THROTTLED` | Throttled; honor `Retry-After` | yes |
| 500 | `INTERNAL` | Unexpected error | no |
| 502 | `DEPENDENCY_ERROR` | Document Intelligence failed | yes |
| 503 | `DEPENDENCY_UNAVAILABLE` | Document Intelligence is unavailable | yes |
| 504 | `DEPENDENCY_TIMEOUT` | Document Intelligence did not finish in time | yes |

On any failure the flow fails closed: the source item is recorded as metadata only, and no content reaches SharePoint.

## Logs

Application Insights holds metadata only: correlation ID, detected type, byte count, duration, extractor, status, counts and error code. It never holds document text, file names or matched values.

## Manual acceptance checklist

These checks need a real Azure tenant. They were not run in the repository's build. Run each one before the first release to a customer, and record the result.

- [ ] `az bicep build` succeeds on `infra/main.bicep` with the Bicep version in use. (CI runs this on every change.)
- [ ] `deploy.ps1` deploys into an empty resource group in the customer region.
- [ ] The zip deploys with a remote build, which installs `requirements.txt` on Flex Consumption.
- [ ] The role-definition GUIDs in `infra/main.bicep` are the built-in roles: Storage Blob Data Owner, Storage Queue Data Contributor, Storage Table Data Contributor, Cognitive Services User. Check each against the Azure built-in roles reference.
- [ ] The identity can call Document Intelligence with `disableLocalAuth` on. A request with the function key returns 200 for a digital PDF.
- [ ] Document Intelligence `prebuilt-read` output on a digital PDF, a scanned PDF, DOCX, XLSX, PPTX and a JPEG has the shape the code reads (`content`, `pages`). `output_content_format` is accepted by the API version pinned in `requirements.txt`.
- [ ] An encrypted file and a corrupt file return 422 `NOT_EXTRACTABLE`. Confirm the HTTP status the service returns for each.
- [ ] A request without `x-functions-key` returns 401. A request with a wrong key returns 403.
- [ ] A synchronous request on a 10 MB file finishes in under 100 s.
- [ ] Application Insights contains no request bodies and no document text after a test run.
- [ ] The custom connector host placeholder is replaced per environment, and the connector accepts the key in a Spanish environment (ADR-001).
- [ ] The Application Insights connection string in the app settings is the only telemetry value stored there. Confirm the customer's policy accepts it.

## Support

Send the correlation ID from the error body, the time of the request, and the error code. Never send document content or the function key.
