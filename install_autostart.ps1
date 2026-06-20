# install_autostart.ps1
# Creates a shortcut for claude_osd_start.vbs in the Windows Startup folder.
# Run this script once after reviewing it.
#
# To remove auto-start, run uninstall_autostart.ps1
# or delete the shortcut manually:
#   %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\ClaudeUsageOSD.lnk

$scriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$vbsPath    = Join-Path $scriptDir "claude_osd_start.vbs"
$startupDir = [Environment]::GetFolderPath("Startup")
$lnkPath    = Join-Path $startupDir "ClaudeUsageOSD.lnk"

if (-not (Test-Path $vbsPath)) {
    Write-Error "claude_osd_start.vbs not found at: $vbsPath"
    exit 1
}

$shell    = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($lnkPath)
$shortcut.TargetPath       = $vbsPath
$shortcut.WorkingDirectory = $scriptDir
$shortcut.Description      = "Claude Usage OSD auto-start"
$shortcut.Save()

Write-Host "Shortcut created: $lnkPath"
Write-Host "Claude Usage OSD will start automatically on next login."
Write-Host ""
Write-Host "To remove: run uninstall_autostart.ps1, or delete:"
Write-Host "  $lnkPath"
