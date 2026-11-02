# Test double for PnP.PowerShell used by tools/tests/test_build.py.
# The fake site comes from the JSON file in $env:PNP_MOCK_SITE:
#   { "libraries": ["Evidence"], "lists": [ { "title": "Fuentes", "url": "Lists/Sources",
#       "fields": [ { "InternalName": "field_1", "Title": "URL del feed", "TypeAsString": "Text", "EnforceUniqueValues": false } ] } ] }
# Every call is appended to $env:PNP_MOCK_LOG.

function Write-MockLog([string] $line) { Add-Content -Path $env:PNP_MOCK_LOG -Value $line }
function Get-MockSite { Get-Content $env:PNP_MOCK_SITE -Raw | ConvertFrom-Json }

function Connect-PnPOnline { param($Url, $ClientId, [switch] $Interactive) Write-MockLog "Connect $Url $ClientId" }
function Invoke-PnPSiteTemplate { param($Path) Write-MockLog "Invoke $Path" }

function Get-PnPList {
    param($Identity)
    $site = Get-MockSite
    if ($site.libraries -contains $Identity) { return [pscustomobject]@{ Title = $Identity; Url = $Identity } }
    $site.lists | Where-Object { $_.title -eq $Identity -or $_.url -eq $Identity } | Select-Object -First 1
}

function Get-PnPField {
    param($List)
    $List.fields
}

Export-ModuleMember -Function Connect-PnPOnline, Invoke-PnPSiteTemplate, Get-PnPList, Get-PnPField
