"""
claude_osd.pyw — Claude Usage OSD (desktop widget)
Reads osd-status.json every REFRESH_SEC seconds; renders a floating tkinter widget
that is pinned to the desktop (wallpaper level): not always-on-top, survives Win+D.
No console (pythonw), no network calls, no secrets.
"""

import json
import os
import sys
import time
import tkinter as tk
from tkinter import font as tkfont
from datetime import datetime
import ctypes
from ctypes import wintypes

# =============================================================================
# CONFIG — all constants here, nowhere else
# =============================================================================

# Paths
_CLAUDE_CFG_DIR = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
STATUS_FILE     = os.path.join(_CLAUDE_CFG_DIR, "osd-status.json")

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
FONT_PATH   = os.path.join(SCRIPT_DIR, "assets", "PressStart2P-Regular.ttf")
CONFIG_FILE = os.path.join(SCRIPT_DIR, "osd-config.json")

# Timing
REFRESH_SEC  = 60      # how often to re-read STATUS_FILE
UI_TICK_MS   = 1000    # how often to repaint labels (ms)
STALE_SEC    = 120     # captured_at age before "stale" warning

# Behavior
PIN_TO_DESKTOP   = False  # (Win10 only) reparent under WorkerW. On Win11 this hides the
                          #   widget behind the wallpaper, so leave it off here.
TOPMOST          = False  # static always-on-top (we instead toggle it dynamically below)
KEEP_ON_DESKTOP  = True   # dynamic desktop gadget: topmost only while the desktop is in
                          #   front (Win+D), non-topmost while a normal app is in front.
DESKTOP_WATCH_MS = 100    # how often to check which window is in front (ms; lower = less
                          #   flicker on Win+D, still negligible CPU)
START_CORNER     = "top-right"   # default position if no saved config
WIN_MARGIN       = 16            # gap from screen edge for default position

# Color thresholds
WARN_PCT = 50
CRIT_PCT = 80

# Colors  (navy bg, retro pixel palette)
COL_BG          = "#0a0e2a"   # navy background
COL_HEADER      = "#ff9900"   # orange — header / label
COL_LABEL_5H    = "#ff7a18"   # orange — "Current"
COL_LABEL_7D    = "#ffcc00"   # yellow — "Weekly"
COL_PCT         = "#ffffff"   # white  — big percentage number
COL_COUNTDOWN   = "#cfd6e6"   # light  — reset time text
COL_SYNC        = "#ff9900"   # orange — sync-at text
COL_FOOTER      = "#8899aa"   # muted  — footer text
COL_FOOTER_STALE= "#556677"   # dimmer — stale footer
COL_BAR_TRACK   = "#33405e"   # bar background track
COL_BAR_OK      = "#00cc44"   # green  — bar < WARN_PCT
COL_BAR_WARN    = "#ffcc00"   # yellow — bar WARN_PCT..CRIT_PCT
COL_BAR_CRIT    = "#ff3333"   # red    — bar >= CRIT_PCT
COL_SEPARATOR   = "#1e2a4a"   # divider line

# Window
WIN_WIDTH        = 380         # minimum width; window auto-grows to fit content
WIN_ALPHA        = 1.0         # 1.0 = solid (no layered window). <1.0 adds transparency
                               #   but makes it a layered window (harder to embed in desktop)
WIN_CORNER_RADIUS= 18          # rounded window corners (px)
WIN_PAD_X        = 14
WIN_PAD_Y        = 10

# Fonts
FONT_FAMILY_PRIMARY  = "Press Start 2P"
FONT_FAMILY_FALLBACK = "Consolas"

FS_HEADER  = 8
FS_PCT     = 20
FS_LABEL   = 8
FS_SMALL   = 7
FS_FOOTER  = 6

# Bar (rounded pill drawn on a Canvas)
BAR_HEIGHT = 16

# =============================================================================
# WIN32 SETUP (correct argtypes so 64-bit HWND/HRGN are not truncated)
# =============================================================================

if sys.platform == "win32":
    _user32 = ctypes.windll.user32
    _gdi32  = ctypes.windll.gdi32

    _user32.GetParent.restype  = wintypes.HWND
    _user32.GetParent.argtypes = [wintypes.HWND]
    _user32.FindWindowW.restype  = wintypes.HWND
    _user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    _user32.SetParent.restype  = wintypes.HWND
    _user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
    _user32.FindWindowExW.restype  = wintypes.HWND
    _user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND,
                                      wintypes.LPCWSTR, wintypes.LPCWSTR]
    _user32.SendMessageTimeoutW.restype  = ctypes.c_ssize_t   # LRESULT (LONG_PTR)
    _user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                            wintypes.LPARAM, wintypes.UINT, wintypes.UINT,
                                            ctypes.POINTER(ctypes.c_void_p)]
    _user32.EnumWindows.restype  = wintypes.BOOL
    _user32.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
    _user32.GetAncestor.restype  = wintypes.HWND
    _user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    _user32.IsWindowVisible.restype  = ctypes.c_int
    _user32.IsWindowVisible.argtypes = [wintypes.HWND]
    _user32.ShowWindow.restype  = wintypes.BOOL
    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.IsIconic.restype  = ctypes.c_int
    _user32.IsIconic.argtypes = [wintypes.HWND]
    _user32.GetForegroundWindow.restype  = wintypes.HWND
    _user32.GetForegroundWindow.argtypes = []
    _user32.SetWindowPos.restype  = wintypes.BOOL
    _user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND,
                                     ctypes.c_int, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int, wintypes.UINT]
    _user32.SetWindowRgn.restype  = ctypes.c_int
    _user32.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]
    _gdi32.CreateRoundRectRgn.restype  = wintypes.HRGN
    _gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int] * 6
else:
    _user32 = _gdi32 = None

_SWP_NOSIZE     = 0x0001
_SWP_NOMOVE     = 0x0002
_SWP_NOZORDER   = 0x0004
_SWP_NOACTIVATE = 0x0010
_SWP_SHOWWINDOW = 0x0040
_HWND_BOTTOM    = 1
_GA_ROOT        = 2
_SW_SHOWNA          = 8   # show in current state, no activate
_SW_SHOWNOACTIVATE  = 4   # restore (un-minimise) without activating
_HWND_TOPMOST       = -1
_HWND_NOTOPMOST     = -2
_DESKTOP_CLASSES    = ("Progman", "WorkerW")   # foreground == desktop (Win+D active)


# =============================================================================
# FONT LOADING
# =============================================================================

def _load_press_start_2p():
    """Load PressStart2P-Regular.ttf into GDI (FR_PRIVATE). Returns True on success."""
    if not os.path.isfile(FONT_PATH) or _gdi32 is None:
        return False
    try:
        FR_PRIVATE = 0x10
        return _gdi32.AddFontResourceExW(FONT_PATH, FR_PRIVATE, 0) > 0
    except Exception:
        return False


# =============================================================================
# HELPERS
# =============================================================================

def _epoch_to_local_str(epoch_sec):
    """UTC epoch -> local 'Jun 25 8:00 AM' (no leading zero on hour/day)."""
    try:
        dt = datetime.fromtimestamp(int(epoch_sec))   # local tz
        hour   = dt.strftime("%#I") if sys.platform == "win32" else dt.strftime("%-I")
        day    = dt.strftime("%#d") if sys.platform == "win32" else dt.strftime("%-d")
        return f'{dt.strftime("%b")} {day} {hour}:{dt.strftime("%M")} {dt.strftime("%p")}'
    except Exception:
        return "?"


def _seconds_to_countdown(diff_sec):
    """Seconds remaining -> 'Xd Yh' / 'Xh Ym' / 'Ym'."""
    diff_sec = max(0, int(diff_sec))
    days  = diff_sec // 86400
    hours = (diff_sec % 86400) // 3600
    mins  = (diff_sec % 3600) // 60
    if days >= 1:
        return f"{days}d {hours}h"
    if hours >= 1:
        return f"{hours}h {mins:02d}m"
    return f"{mins}m"


def _seconds_to_ago(diff_sec):
    """Seconds elapsed -> 'Xs ago' / 'Xm ago' / 'Xh ago'."""
    diff_sec = max(0, int(diff_sec))
    if diff_sec < 60:
        return f"{diff_sec}s ago"
    if diff_sec < 3600:
        return f"{diff_sec // 60}m ago"
    return f"{diff_sec // 3600}h ago"


def _bar_color(pct):
    if pct >= CRIT_PCT:
        return COL_BAR_CRIT
    if pct >= WARN_PCT:
        return COL_BAR_WARN
    return COL_BAR_OK


# =============================================================================
# CONFIG PERSISTENCE (window position)
# =============================================================================

def _load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_config(cfg: dict):
    tmp = CONFIG_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
        os.replace(tmp, CONFIG_FILE)
    except Exception:
        pass


# =============================================================================
# STATUS READER
# =============================================================================

def _read_status():
    """Read+validate osd-status.json. Returns dict or None on any error."""
    try:
        # utf-8-sig: PowerShell 5.1 Set-Content -Encoding UTF8 writes a BOM.
        with open(STATUS_FILE, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        fh = data.get("five_hour", {})
        sd = data.get("seven_day", {})
        return {
            "schema":      data.get("schema", 1),
            "captured_at": int(data.get("captured_at", 0)),
            "five_hour": {
                "used_percentage": int(fh.get("used_percentage", 0)),
                "resets_at":       int(fh.get("resets_at", 0)),
            },
            "seven_day": {
                "used_percentage": int(sd.get("used_percentage", 0)),
                "resets_at":       int(sd.get("resets_at", 0)),
            },
        }
    except Exception:
        return None


# =============================================================================
# MAIN OSD WIDGET
# =============================================================================

class OSDApp:

    def __init__(self, root: tk.Tk, font_ok: bool):
        self.root = root
        self.font_family = FONT_FAMILY_PRIMARY if font_ok else FONT_FAMILY_FALLBACK

        self._state = None
        self._last_read = 0.0
        self._next_read = 0.0

        self.hwnd = None
        self.reparented = False
        self._topmost_now = False
        self._win_x = WIN_MARGIN
        self._win_y = WIN_MARGIN
        self._win_w = WIN_WIDTH
        self._win_h = 0
        self._drag_off_x = 0
        self._drag_off_y = 0

        self._build_window()
        self._build_ui()
        self._finalize_window()      # size, hwnd, rounded corners, pin, position

        self._schedule_read()
        self._tick()
        self._watch_desktop()

    # ------------------------------------------------------------------ window
    def _build_window(self):
        r = self.root
        r.overrideredirect(True)
        if WIN_ALPHA < 1.0:
            r.attributes("-alpha", WIN_ALPHA)
        r.configure(bg=COL_BG)
        r.resizable(False, False)

    def _finalize_window(self):
        r = self.root
        r.update_idletasks()
        w = max(WIN_WIDTH, r.winfo_reqwidth())
        h = r.winfo_reqheight()
        self._win_w, self._win_h = w, h
        r.geometry(f"{w}x{h}")
        r.update_idletasks()

        # Real top-level HWND (Tk wraps the window; GA_ROOT gives the outer frame).
        # NOTE: Tk geometry() cannot reliably position an overrideredirect window on
        # this setup (the offset is dropped -> window stuck at 0,0), so all positioning
        # is done via SetWindowPos on this HWND instead.
        self.hwnd = None
        if _user32 is not None:
            wid = wintypes.HWND(r.winfo_id())
            root_hwnd = _user32.GetAncestor(wid, _GA_ROOT)
            self.hwnd = root_hwnd if root_hwnd else wid

        self._apply_rounded_corners(w, h)

        cfg = _load_config()
        if "x" in cfg and "y" in cfg:
            x, y = int(cfg["x"]), int(cfg["y"])
        else:
            x, y = self._default_position(w, h)

        self.reparented = False
        if PIN_TO_DESKTOP:
            self.reparented = self._pin_to_desktop()
        if not self.reparented and TOPMOST:
            r.attributes("-topmost", True)

        self._move_window(x, y)

    def _default_position(self, w, h):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        corner = START_CORNER
        x = sw - w - WIN_MARGIN if "right" in corner else WIN_MARGIN
        y = WIN_MARGIN if "top" in corner else sh - h - WIN_MARGIN
        return x, y

    def _apply_rounded_corners(self, w, h):
        if _gdi32 is None or self.hwnd is None or WIN_CORNER_RADIUS <= 0:
            return
        try:
            rgn = _gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1,
                                            WIN_CORNER_RADIUS, WIN_CORNER_RADIUS)
            _user32.SetWindowRgn(self.hwnd, rgn, True)
        except Exception:
            pass

    def _pin_to_desktop(self):
        """Reparent the widget UNDER the desktop window (Progman) so it becomes part
        of the desktop: normal app windows cover it, and Win+D / Show-Desktop leaves
        it in place (it is shown together with the desktop, never minimised).
        Tries the WorkerW behind the icons first (Win10); on Win11 (SHELLDLL_DefView
        is a direct child of Progman, no sibling WorkerW) it parents under Progman."""
        if _user32 is None or self.hwnd is None:
            return False
        try:
            progman = _user32.FindWindowW("Progman", None)
            if not progman:
                return False
            res = ctypes.c_void_p()
            _user32.SendMessageTimeoutW(progman, 0x052C, 0xD, 0x1, 0x0, 1000, ctypes.byref(res))
            _user32.SendMessageTimeoutW(progman, 0x052C, 0xD, 0x0, 0x0, 1000, ctypes.byref(res))

            target = ctypes.c_void_p(0)

            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def _enum(hwnd, lparam):
                if _user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None):
                    w = _user32.FindWindowExW(None, hwnd, "WorkerW", None)
                    if w:
                        target.value = w
                return True

            _user32.EnumWindows(_enum, 0)
            parent = target.value if target.value else progman   # Win11 -> Progman
            _user32.SetParent(self.hwnd, parent)
            return True
        except Exception:
            return False

    def _watch_desktop(self):
        """On Win11, Win+D / Show-Desktop raises the desktop ABOVE non-topmost windows
        (it does NOT minimise borderless windows). So we watch the foreground window:
        while the desktop (Progman/WorkerW) is in front we make the widget topmost so it
        shows above the raised desktop; while a normal app is in front we drop topmost so
        apps cover it. Net effect = a desktop gadget that apps hide but Win+D reveals."""
        if KEEP_ON_DESKTOP and not self.reparented and self.hwnd is not None and _user32 is not None:
            try:
                fg = _user32.GetForegroundWindow()
                buf = ctypes.create_unicode_buffer(64)
                if fg:
                    _user32.GetClassNameW(fg, buf, 64)
                desktop_front = buf.value in _DESKTOP_CLASSES
                if desktop_front and not self._topmost_now:
                    _user32.SetWindowPos(self.hwnd, wintypes.HWND(_HWND_TOPMOST), 0, 0, 0, 0,
                                         _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOACTIVATE)
                    self._topmost_now = True
                elif not desktop_front and self._topmost_now:
                    _user32.SetWindowPos(self.hwnd, wintypes.HWND(_HWND_NOTOPMOST), 0, 0, 0, 0,
                                         _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOACTIVATE)
                    self._topmost_now = False
            except Exception:
                pass
        self.root.after(DESKTOP_WATCH_MS, self._watch_desktop)

    def _move_window(self, x, y):
        # Coordinates are screen-relative; when parented to Progman/WorkerW (both
        # span the primary monitor at 0,0) these map 1:1 to desktop coordinates.
        self._win_x, self._win_y = int(x), int(y)
        if self.hwnd is not None and _user32 is not None:
            _user32.SetWindowPos(self.hwnd, None, int(x), int(y),
                                 self._win_w, self._win_h,
                                 _SWP_SHOWWINDOW | _SWP_NOZORDER | _SWP_NOACTIVATE)
        else:
            self.root.geometry(f"+{int(x)}+{int(y)}")

    # ------------------------------------------------------------------ UI
    def _fnt(self, size, bold=False):
        return (self.font_family, size, "bold" if bold else "normal")

    def _build_ui(self):
        r = self.root

        # ── Header ──
        hdr = tk.Frame(r, bg=COL_BG)
        hdr.pack(fill="x", padx=WIN_PAD_X, pady=(WIN_PAD_Y, 4))
        tk.Label(hdr, text="\U0001f47e Usage", bg=COL_BG, fg=COL_HEADER,
                 font=self._fnt(FS_HEADER, bold=True), anchor="w").pack(side="left")
        # placeholder uses full-width sample text so the window auto-sizes wide enough
        self.lbl_sync = tk.Label(hdr, text="Sync at: Mmm 30 12:00 PM", bg=COL_BG, fg=COL_SYNC,
                                 font=self._fnt(FS_SMALL), anchor="e")
        self.lbl_sync.pack(side="right")

        tk.Frame(r, bg=COL_SEPARATOR, height=1).pack(fill="x", padx=WIN_PAD_X, pady=(0, 2))

        # ── Sections ──
        self._sections = {}
        for key, text, col in [("five_hour", "Current", COL_LABEL_5H),
                               ("seven_day", "Weekly",  COL_LABEL_7D)]:
            self._sections[key] = self._build_section(r, text, col)
            if key == "five_hour":
                tk.Frame(r, bg=COL_BG, height=6).pack()

        tk.Frame(r, bg=COL_SEPARATOR, height=1).pack(fill="x", padx=WIN_PAD_X, pady=(4, 2))

        # ── Footer ──
        self.lbl_footer = tk.Label(r, text="Updated 000s ago • next in 00s",
                                   bg=COL_BG, fg=COL_FOOTER,
                                   font=self._fnt(FS_FOOTER), anchor="center")
        self.lbl_footer.pack(pady=(2, WIN_PAD_Y))

    def _build_section(self, parent, label_text, label_color):
        frame = tk.Frame(parent, bg=COL_BG)
        frame.pack(fill="x", padx=WIN_PAD_X, pady=(2, 0))

        row1 = tk.Frame(frame, bg=COL_BG)
        row1.pack(fill="x")
        lbl_pct = tk.Label(row1, text="--%", bg=COL_BG, fg=COL_PCT,
                           font=self._fnt(FS_PCT, bold=True), anchor="w")
        lbl_pct.pack(side="left")
        tk.Label(row1, text=label_text, bg=COL_BG, fg=label_color,
                 font=self._fnt(FS_LABEL, bold=True), anchor="e").pack(side="right")

        canvas = tk.Canvas(frame, height=BAR_HEIGHT, bg=COL_BG,
                           highlightthickness=0, bd=0)
        canvas.pack(fill="x", pady=(4, 3))

        lbl_cd = tk.Label(frame, text="~ 00d 00h  (Mmm 30 12:00 PM)", bg=COL_BG, fg=COL_COUNTDOWN,
                          font=self._fnt(FS_SMALL), anchor="w")
        lbl_cd.pack(fill="x")

        return {"pct": lbl_pct, "bar": canvas, "countdown": lbl_cd}

    def _draw_pill(self, canvas, x1, y1, x2, y2, fill):
        r = (y2 - y1) / 2.0
        if x2 - x1 < 2 * r:
            x2 = x1 + 2 * r
        canvas.create_oval(x1, y1, x1 + 2 * r, y2, fill=fill, outline=fill)
        canvas.create_oval(x2 - 2 * r, y1, x2, y2, fill=fill, outline=fill)
        canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline=fill)

    def _draw_bar(self, canvas, pct, color):
        w = canvas.winfo_width()
        h = BAR_HEIGHT
        if w <= 10:
            return
        canvas.delete("all")
        pad = 1
        self._draw_pill(canvas, pad, pad, w - pad, h - pad, COL_BAR_TRACK)
        if pct > 0:
            fill_w = max(h - 2 * pad, (w - 2 * pad) * pct / 100.0)
            self._draw_pill(canvas, pad, pad, pad + fill_w, h - pad, color)

    # ------------------------------------------------------------------ data
    def _schedule_read(self):
        self._do_read()
        self.root.after(REFRESH_SEC * 1000, self._schedule_read)

    def _do_read(self):
        now = time.time()
        data = _read_status()
        self._last_read = now
        self._next_read = now + REFRESH_SEC
        if data is not None:
            self._state = data

    # ------------------------------------------------------------------ tick
    def _tick(self):
        self._update_ui()
        self.root.after(UI_TICK_MS, self._tick)

    def _update_ui(self):
        state = self._state
        if state is None:
            return
        now = time.time()
        captured_at = state["captured_at"]
        age = now - captured_at
        is_stale = age > STALE_SEC

        self.lbl_sync.config(text=f"Sync at: {_epoch_to_local_str(captured_at)}")

        for key in ("five_hour", "seven_day"):
            d = state[key]
            pct = d["used_percentage"]
            widgets = self._sections[key]
            widgets["pct"].config(text=f"{pct}%")
            self._draw_bar(widgets["bar"], pct, _bar_color(pct))
            cd = _seconds_to_countdown(d["resets_at"] - now)
            widgets["countdown"].config(
                text=f'~ {cd}  ({_epoch_to_local_str(d["resets_at"])})')

        ago = _seconds_to_ago(age)
        nxt = max(0, int(self._next_read - now))
        text = f"Updated {ago} • next in {nxt}s"
        if is_stale:
            self.lbl_footer.config(text=text + " (stale)", fg=COL_FOOTER_STALE)
        else:
            self.lbl_footer.config(text=text, fg=COL_FOOTER)

    # ------------------------------------------------------------------ drag
    def _on_drag_start(self, event):
        self._drag_off_x = event.x_root - self._win_x
        self._drag_off_y = event.y_root - self._win_y

    def _on_drag_move(self, event):
        self._move_window(event.x_root - self._drag_off_x,
                          event.y_root - self._drag_off_y)

    def _on_drag_release(self, event):
        cfg = _load_config()
        cfg["x"], cfg["y"] = self._win_x, self._win_y
        _save_config(cfg)

    # ------------------------------------------------------------------ menu
    def _on_right_click(self, event):
        menu = tk.Menu(self.root, tearoff=0, bg=COL_BG, fg=COL_HEADER,
                       activebackground="#1e2a5a", activeforeground=COL_HEADER)
        menu.add_command(label="Refresh now", command=self._do_read)
        menu.add_command(label="Reset position",
                         command=lambda: self._move_window(*self._default_position(
                             self.root.winfo_width(), self.root.winfo_height())))
        menu.add_separator()
        menu.add_command(label="Close", command=self.root.destroy)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    font_ok = _load_press_start_2p()
    root = tk.Tk()
    app = OSDApp(root, font_ok)

    def _bind(widget):
        widget.bind("<Button-1>", app._on_drag_start)
        widget.bind("<B1-Motion>", app._on_drag_move)
        widget.bind("<ButtonRelease-1>", app._on_drag_release)
        widget.bind("<Button-3>", app._on_right_click)
        for child in widget.winfo_children():
            _bind(child)

    root.update_idletasks()
    _bind(root)
    root.mainloop()


if __name__ == "__main__":
    main()
