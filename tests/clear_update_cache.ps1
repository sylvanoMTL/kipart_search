# Clear or expire the update check cache from KiPart Search config.json
#
# Usage:
#   powershell -File clear_update_cache.ps1            # full clear
#   powershell -File clear_update_cache.ps1 -Expire    # expire only (forces fresh API call)

param([switch]$Expire)

$p = "$env:LOCALAPPDATA\KiPartSearch\config.json"
if (-not (Test-Path $p)) {
    Write-Host "Config not found: $p"
    exit 1
}
$d = Get-Content $p | ConvertFrom-Json

if ($Expire) {
    if ($d.PSObject.Properties['update_check'] -and $d.update_check.PSObject.Properties['check_time']) {
        $d.update_check.check_time = 0
        $d | ConvertTo-Json -Depth 10 | Set-Content $p
        Write-Host "Update cache expired (check_time set to 0)"
    } else {
        Write-Host "No update_check.check_time found (nothing to expire)"
    }
} else {
    if ($d.PSObject.Properties['update_check']) {
        $d.PSObject.Properties.Remove('update_check')
        $d | ConvertTo-Json -Depth 10 | Set-Content $p
        Write-Host "Update cache cleared"
    } else {
        Write-Host "No update_check key found (already clean)"
    }
}
