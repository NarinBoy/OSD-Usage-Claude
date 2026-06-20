' claude_osd_start.vbs
' Launches claude_osd.pyw silently via pythonw (no console window).
' scriptDir is derived from this file's own path — no hardcoded paths.

Dim scriptDir, pyScript, cmd
scriptDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
pyScript  = scriptDir & "claude_osd.pyw"
cmd       = "pythonw.exe """ & pyScript & """"

' Run hidden (window style 0), don't wait (False)
CreateObject("WScript.Shell").Run cmd, 0, False
