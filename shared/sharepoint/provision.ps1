<#
.SYNOPSIS
    {{t:provision.synopsis}}

.DESCRIPTION
    {{t:provision.description}}

.PARAMETER SiteUrl
    {{t:provision.paramSiteUrl}}

.PARAMETER ClientId
    {{t:provision.paramClientId}}

.PARAMETER VerifyOnly
    {{t:provision.paramVerifyOnly}}

.EXAMPLE
    ./provision.ps1 -SiteUrl https://contoso.sharepoint.com/sites/TrendResearch -ClientId 00000000-0000-0000-0000-000000000000

.EXAMPLE
    ./provision.ps1 -SiteUrl https://contoso.sharepoint.com/sites/TrendResearch -ClientId 00000000-0000-0000-0000-000000000000 -VerifyOnly
#>
#Requires -Version 7.4

param(
    [Parameter(Mandatory)] [string] $SiteUrl,
    [Parameter(Mandatory)] [string] $ClientId,
    [switch] $VerifyOnly
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Module -ListAvailable -Name PnP.PowerShell)) {
    throw '{{t:provision.missingModule}}'
}

$template = Join-Path $PSScriptRoot 'sharepoint-template.pnp.xml'
$expected = Get-Content (Join-Path $PSScriptRoot 'expected-schema.json') -Raw -Encoding utf8 | ConvertFrom-Json

Connect-PnPOnline -Url $SiteUrl -ClientId $ClientId -Interactive

if (-not $VerifyOnly) {
    Write-Host '{{t:provision.applying}}'
    Invoke-PnPSiteTemplate -Path $template
}

Write-Host '{{t:provision.verifying}}'
$problems = [System.Collections.Generic.List[string]]::new()

foreach ($library in $expected.libraries) {
    if (-not (Get-PnPList -Identity $library.url -ErrorAction SilentlyContinue)) {
        $problems.Add("$($library.title) [$($library.url)]: {{t:provision.missingLibrary}}")
    }
}

foreach ($list in $expected.lists) {
    # Lists created by the template live at Lists/<EnglishName>; lists created from CSV
    # live at a URL derived from their title. Find either one by title first.
    $spList = Get-PnPList -Identity $list.title -ErrorAction SilentlyContinue
    if (-not $spList) { $spList = Get-PnPList -Identity $list.url -ErrorAction SilentlyContinue }
    if (-not $spList) {
        $problems.Add("$($list.title): {{t:provision.missingList}}")
        continue
    }
    $fields = Get-PnPField -List $spList
    foreach ($field in $list.fields) {
        $actual = $fields | Where-Object { $_.InternalName -ceq $field.name } | Select-Object -First 1
        $label = "$($list.title) / $($field.display) [$($field.name)]"
        if (-not $actual) {
            $sameTitle = $fields | Where-Object { $_.Title -eq $field.display } | Select-Object -First 1
            $hint = if ($sameTitle) { " ({{t:provision.foundAs}} $($sameTitle.InternalName))" } else { '' }
            $problems.Add("${label}: {{t:provision.missingColumn}}$hint")
            continue
        }
        if ($actual.TypeAsString -ne $field.type) {
            $problems.Add("${label}: {{t:provision.wrongType}} $($actual.TypeAsString) -> $($field.type)")
        }
        if ($field.unique -and -not $actual.EnforceUniqueValues) {
            $problems.Add("${label}: {{t:provision.notUnique}}")
        }
    }
}

if ($problems.Count -gt 0) {
    $problems | ForEach-Object { Write-Host "  x $_" -ForegroundColor Red }
    Write-Host '{{t:provision.failed}}' -ForegroundColor Red
    exit 1
}
Write-Host '{{t:provision.ok}}' -ForegroundColor Green
