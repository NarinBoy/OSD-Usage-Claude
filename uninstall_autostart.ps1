# uninstall_autostart.ps1
# Removes the Claude Usage OSD shortcut from the Windows Startup folder.

$startupDir = [Environment]::GetFolderPath("Startup")
$lnkPath    = Join-Path $startupDir "ClaudeUsageOSD.lnk"

if (Test-Path $lnkPath) {
    Remove-Item -Path $lnkPath -Force
    Write-Host "Removed: $lnkPath"
    Write-Host "Claude Usage OSD will no longer start automatically."
} else {
    Write-Host "Shortcut not found (already removed or never installed):"
    Write-Host "  $lnkPath"
}
