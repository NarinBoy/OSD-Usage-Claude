# Claude Usage OSD

A tiny **always-on-desktop widget for Windows** that shows your Claude Code usage —
the **5-hour session** and **7-day weekly** limits — as live percentages, styled
like a retro pixel LCD.

It sits on your desktop like a gadget: normal windows cover it, but **Win+D
(Show Desktop) reveals it**. Everything runs locally — it never sends your data
anywhere.

![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D6)
![Python](https://img.shields.io/badge/python-3.x-3776AB)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

```
┌──────────────────────────────────────────┐
│ 👾 Usage          Sync at: Jun 20 2:39 PM │
├──────────────────────────────────────────┤
│  24%                            Current   │
│  ▰▰▰▰▰▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱                      │
│  ~ 4h 39m  (Jun 20 7:20 PM)               │
│                                           │
│  10%                             Weekly   │
│  ▰▰▰▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱                      │
│  ~ 4d 17h  (Jun 25 8:00 AM)               │
├──────────────────────────────────────────┤
│        Updated 51s ago • next in 44s      │
└──────────────────────────────────────────┘
```
> Tip: drop a real screenshot at `docs/preview.png` and embed it here with
> `![preview](docs/preview.png)`.

## Why this exists

Claude Code already shows your rate-limit usage in the statusline — but only while
a session window is open. I wanted a glanceable, always-there view on my desktop,
**without sending anything to a server**. So this reuses the exact numbers the
statusline already receives and draws them as a small retro gadget.

If you had the same idea, feel free to fork it and make it yours.

## Features

- **5h ("Current")** and **7d ("Weekly")** usage — big % with rounded progress bars
- Color-coded bars: 🟢 &lt;50% · 🟡 50–79% · 🔴 ≥80%
- Reset countdown and reset time (AM/PM)
- `Updated Xs ago • next in Xs` footer
- Draggable, remembers its position; right-click for **Refresh / Reset position / Close**
- Press Start 2P pixel font, rounded window corners
- ~32 MB RAM, negligible CPU
- **No network calls, no secrets** — only the usage numbers ever touch disk

## How it works

```
Claude Code ──status JSON (stdin)──► statusline.ps1
                                       │  extracts ONLY rate_limits
                                       ▼
                %USERPROFILE%\.claude\osd-status.json
                                       │  read every 60 s
                                       ▼
                               claude_osd.pyw  (the widget)
```

The statusline script Claude Code already runs gets a JSON blob on every refresh.
We pick out **only** the `rate_limits` block, write it to a small local file, and
the widget polls that file. Nothing else is stored; no network is involved.

## Requirements

- Windows 10 / 11
- Python 3 (tested on 3.14), with `pythonw.exe` on your `PATH`
- Claude Code, configured with a custom PowerShell statusline

## Install

1. Clone or download this repo.
2. Add the block below to the **end** of your statusline script
   (`%USERPROFILE%\.claude\statusline.ps1`), just before the line that prints the
   status. It exports **only** the rate-limit numbers:

   ```powershell
   # --- OSD export: persist ONLY rate-limit numbers ---
   try {
       if ($null -ne $j.rate_limits) {
           $cfgDir = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { "$env:USERPROFILE\.claude" }
           $osd = [ordered]@{
               schema      = 1
               captured_at = [int64]([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())
               five_hour   = @{ used_percentage = [int]$j.rate_limits.five_hour.used_percentage; resets_at = [int64]$j.rate_limits.five_hour.resets_at }
               seven_day   = @{ used_percentage = [int]$j.rate_limits.seven_day.used_percentage; resets_at = [int64]$j.rate_limits.seven_day.resets_at }
           }
           $tmp = Join-Path $cfgDir 'osd-status.json.tmp'
           ($osd | ConvertTo-Json -Compress) | Set-Content -Path $tmp -Encoding UTF8
           Move-Item -Path $tmp -Destination (Join-Path $cfgDir 'osd-status.json') -Force
       }
   } catch { }
   ```

   > The widget only updates while Claude Code is running (that's when the
   > statusline writes the file). When idle, it keeps showing the last values plus
   > a `(stale)` hint.

3. Start it — double-click **`claude_osd_start.vbs`** (runs silently, no console).
4. *(Optional)* Auto-start on login: run **`install_autostart.ps1`**.

## Configuration

Everything is in the `CONFIG` block at the top of `claude_osd.pyw`:

| Setting | What it does |
|---|---|
| `REFRESH_SEC` | how often to re-read the usage file (default 60) |
| `WARN_PCT` / `CRIT_PCT` | color thresholds for the bars (50 / 80) |
| `WIN_ALPHA` | `1.0` = solid, `<1.0` = translucent |
| `START_CORNER` | default corner (`"top-right"`) |
| `COL_*` / `FS_*` | colors and font sizes |

## Uninstall

- Stop auto-start: run `uninstall_autostart.ps1`
- Close the widget: right-click it → **Close**

## Project structure

```
claude_osd.pyw          the widget (tkinter)
claude_osd_start.vbs    silent launcher (no console window)
install_autostart.ps1   add a Startup shortcut
uninstall_autostart.ps1 remove it
assets/
  PressStart2P-Regular.ttf
  OFL.txt               font license (SIL OFL 1.1)
```

## Notes for hackers

On Windows 11, Win+D raises the desktop *above* normal windows instead of
minimizing borderless ones, so the widget watches the foreground window and floats
on top only while the desktop is in front. Positioning uses `SetWindowPos` (Tk's
`geometry()` won't place a borderless window reliably here). PRs and ideas welcome.

## License

- **Code:** [MIT](LICENSE) — do whatever you like, just keep the notice.
- **Font:** *Press Start 2P* © The Press Start 2P Project Authors, licensed under the
  SIL Open Font License 1.1 — see [`assets/OFL.txt`](assets/OFL.txt).
"# OSD-Usage-Claude" 
