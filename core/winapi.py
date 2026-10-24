"""Windows 原生 API 封装（ctypes）。

只使用用户级 API，不依赖管理员权限，也不依赖 keyboard 之类的第三方库：
  * 剪贴板读写      OpenClipboard / GetClipboardData / SetClipboardData
  * 剪贴板变化监听  GetClipboardSequenceNumber
  * 全局热键        RegisterHotKey + GetMessage 消息循环
  * 模拟 Ctrl+V     SendInput
  * 窗口辅助        前台窗口、置顶、圆角、隐藏任务栏图标等

所有 Win32 函数都显式声明了 argtypes / restype，避免 64 位下句柄被截断。
"""
import ctypes
import logging
import sys
import threading
import time
from ctypes import wintypes as wt

log = logging.getLogger("clipbuddy.winapi")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)

LONG_PTR = ctypes.c_ssize_t
HANDLE = ctypes.c_void_p


def _sig(fn, restype, *argtypes):
    fn.restype = restype
    fn.argtypes = list(argtypes)


# ───────────────────────── 原型声明 ─────────────────────────
_sig(user32.OpenClipboard, wt.BOOL, wt.HWND)
_sig(user32.CloseClipboard, wt.BOOL)
_sig(user32.EmptyClipboard, wt.BOOL)
_sig(user32.GetClipboardData, HANDLE, wt.UINT)
_sig(user32.SetClipboardData, HANDLE, wt.UINT, HANDLE)
_sig(user32.IsClipboardFormatAvailable, wt.BOOL, wt.UINT)
_sig(user32.GetClipboardSequenceNumber, wt.DWORD)
_sig(user32.RegisterClipboardFormatW, wt.UINT, wt.LPCWSTR)

_sig(kernel32.GlobalAlloc, HANDLE, wt.UINT, ctypes.c_size_t)
_sig(kernel32.GlobalLock, ctypes.c_void_p, HANDLE)
_sig(kernel32.GlobalUnlock, wt.BOOL, HANDLE)
_sig(kernel32.GlobalFree, HANDLE, HANDLE)
_sig(kernel32.GetCurrentThreadId, wt.DWORD)
_sig(kernel32.CreateEventW, HANDLE, ctypes.c_void_p, wt.BOOL, wt.BOOL, wt.LPCWSTR)
_sig(kernel32.SetEvent, wt.BOOL, HANDLE)
_sig(kernel32.WaitForSingleObject, wt.DWORD, HANDLE, wt.DWORD)

_sig(user32.RegisterHotKey, wt.BOOL, wt.HWND, ctypes.c_int, wt.UINT, wt.UINT)
_sig(user32.UnregisterHotKey, wt.BOOL, wt.HWND, ctypes.c_int)
_sig(user32.GetMessageW, ctypes.c_int, ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT)

_sig(user32.GetForegroundWindow, wt.HWND)
_sig(user32.SetForegroundWindow, wt.BOOL, wt.HWND)
_sig(user32.BringWindowToTop, wt.BOOL, wt.HWND)
_sig(user32.IsWindow, wt.BOOL, wt.HWND)
_sig(user32.FindWindowW, wt.HWND, wt.LPCWSTR, wt.LPCWSTR)
_sig(user32.GetWindowThreadProcessId, wt.DWORD, wt.HWND, ctypes.POINTER(wt.DWORD))
_sig(user32.AttachThreadInput, wt.BOOL, wt.DWORD, wt.DWORD, wt.BOOL)
_sig(user32.GetWindowRect, wt.BOOL, wt.HWND, ctypes.POINTER(wt.RECT))
_sig(user32.SetWindowPos, wt.BOOL, wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
     ctypes.c_int, ctypes.c_int, wt.UINT)
_sig(user32.SetWindowRgn, ctypes.c_int, wt.HWND, HANDLE, wt.BOOL)
_sig(user32.GetCursorPos, wt.BOOL, ctypes.POINTER(wt.POINT))
_sig(user32.MonitorFromPoint, HANDLE, wt.POINT, wt.DWORD)
_sig(user32.MessageBoxW, ctypes.c_int, wt.HWND, wt.LPCWSTR, wt.LPCWSTR, wt.UINT)

_GetWindowLongPtr = getattr(user32, "GetWindowLongPtrW", None) or user32.GetWindowLongW
_SetWindowLongPtr = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
_sig(_GetWindowLongPtr, LONG_PTR, wt.HWND, ctypes.c_int)
_sig(_SetWindowLongPtr, LONG_PTR, wt.HWND, ctypes.c_int, LONG_PTR)

_sig(gdi32.CreateRoundRectRgn, HANDLE, ctypes.c_int, ctypes.c_int, ctypes.c_int,
     ctypes.c_int, ctypes.c_int, ctypes.c_int)
_sig(dwmapi.DwmSetWindowAttribute, ctypes.c_long, wt.HWND, wt.DWORD, ctypes.c_void_p, wt.DWORD)


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT),
                ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]


_sig(user32.GetMonitorInfoW, wt.BOOL, HANDLE, ctypes.POINTER(MONITORINFO))

# ───────────────────────── 剪贴板 ─────────────────────────
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
GMEM_ZEROINIT = 0x0040

# 密码管理器等应用会设置这个格式，表示"请勿记录这次复制"
_FMT_EXCLUDE = user32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing")


class ClipboardBusy(Exception):
    """剪贴板被其他程序占用，稍后重试。"""


def _open_clipboard(retries=10, delay=0.02):
    for _ in range(retries):
        if user32.OpenClipboard(None):
            return True
        time.sleep(delay)
    return False


def clipboard_seq():
    return user32.GetClipboardSequenceNumber()


def clipboard_excluded():
    return bool(_FMT_EXCLUDE and user32.IsClipboardFormatAvailable(_FMT_EXCLUDE))


def get_text():
    """读取剪贴板文字；没有文字返回 None；被占用抛 ClipboardBusy。"""
    if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
        return None
    if not _open_clipboard():
        raise ClipboardBusy()
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return None
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def set_text(text):
    """把文字写入剪贴板（UTF-16LE）。成功返回 True。"""
    data = text.encode("utf-16-le") + b"\x00\x00"
    if not _open_clipboard():
        return False
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(data))
        if not handle:
            return False
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            kernel32.GlobalFree(handle)
            return False
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)  # 设置失败才需要自己释放
            return False
        return True
    finally:
        user32.CloseClipboard()


# ───────────────────────── 模拟按键 ─────────────────────────
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12
VK_V = 0x56


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wt.DWORD), ("wParamL", wt.WORD), ("wParamH", wt.WORD)]


class _INPUT_UNION(ctypes.Union):
    # 必须包含最大的 MOUSEINPUT，结构体大小才正确（64 位为 40 字节）
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _INPUT_UNION)]


_sig(user32.SendInput, wt.UINT, wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int)


def _key(vk, up=False):
    i = INPUT(type=INPUT_KEYBOARD)
    i.u.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=KEYEVENTF_KEYUP if up else 0,
                        time=0, dwExtraInfo=0)
    return i


def _send(*events):
    arr = (INPUT * len(events))(*events)
    return user32.SendInput(len(events), arr, ctypes.sizeof(INPUT))


def send_ctrl_v():
    """向当前前台窗口发送 Ctrl+V。"""
    return _send(_key(VK_CONTROL), _key(VK_V), _key(VK_V, True), _key(VK_CONTROL, True))


# ───────────────────────── 全局热键 ─────────────────────────
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_HOTKEY = 0x0312

_MOD_NAMES = {"alt": MOD_ALT, "ctrl": MOD_CONTROL, "control": MOD_CONTROL,
              "shift": MOD_SHIFT, "win": MOD_WIN, "windows": MOD_WIN}
_SPECIAL_KEYS = {"esc": 0x1B, "space": 0x20, "enter": 0x0D, "tab": 0x09,
                 "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
                 "pageup": 0x21, "pagedown": 0x22, "`": 0xC0, "backspace": 0x08}


def parse_hotkey(spec):
    """'ctrl+shift+v' -> (modifiers, vk)。格式非法抛 ValueError。"""
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    if not parts:
        raise ValueError(spec)
    key, mods = parts[-1], 0
    for p in parts[:-1]:
        if p not in _MOD_NAMES:
            raise ValueError(spec)
        mods |= _MOD_NAMES[p]
    if len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    elif key[0] == "f" and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    elif key in _SPECIAL_KEYS:
        vk = _SPECIAL_KEYS[key]
    else:
        raise ValueError(spec)
    return mods, vk


class HotkeyListener(threading.Thread):
    """独立线程：RegisterHotKey + GetMessage 消息循环。"""

    def __init__(self, bindings):
        super().__init__(daemon=True, name="hotkeys")
        self.bindings = bindings  # [(热键字符串, 回调)]
        self.failed = []

    def run(self):
        callbacks = {}
        for idx, (spec, cb) in enumerate(self.bindings, start=1):
            try:
                mods, vk = parse_hotkey(spec)
            except ValueError:
                log.warning("无法解析热键: %s", spec)
                self.failed.append(spec)
                continue
            if user32.RegisterHotKey(None, idx, mods | MOD_NOREPEAT, vk):
                callbacks[idx] = cb
                log.info("已注册热键 %s", spec)
            else:
                log.warning("热键注册失败（可能被其他程序占用）: %s", spec)
                self.failed.append(spec)
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                cb = callbacks.get(msg.wParam)
                if cb:  # 回调放到新线程，避免卡住消息循环
                    threading.Thread(target=cb, daemon=True).start()


# ───────────────────────── 窗口辅助 ─────────────────────────
SWP_NOSIZE, SWP_NOZORDER, SWP_NOACTIVATE, SWP_FRAMECHANGED = 0x1, 0x4, 0x10, 0x20
SWP_NOMOVE = 0x2
HWND_TOPMOST = -1
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW, WS_EX_APPWINDOW = 0x80, 0x40000


def set_dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def dpi_scale():
    try:
        return user32.GetDpiForSystem() / 96.0
    except Exception:
        return 1.0


def find_window(title):
    return user32.FindWindowW(None, title) or None


def foreground():
    return user32.GetForegroundWindow() or None


def is_window(hwnd):
    return bool(hwnd) and bool(user32.IsWindow(hwnd))


def force_foreground(hwnd, retries=3):
    """尽力把 hwnd 切到前台（借助 AttachThreadInput 绕过前台锁），失败则重试。

    同时绑定当前前台线程与目标线程的输入队列，比只绑前台线程更可靠；
    重试若干次以提高命中率（Windows 前台切换受系统限制，未必一次成功）。
    """
    if not is_window(hwnd):
        return False
    cur = kernel32.GetCurrentThreadId()
    for _ in range(max(1, retries)):
        fg = user32.GetForegroundWindow()
        if fg == hwnd:
            return True
        fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
        tgt_tid = user32.GetWindowThreadProcessId(hwnd, None)
        attached = []
        if fg_tid and fg_tid != cur and user32.AttachThreadInput(cur, fg_tid, True):
            attached.append(fg_tid)
        if tgt_tid and tgt_tid != cur and user32.AttachThreadInput(cur, tgt_tid, True):
            attached.append(tgt_tid)
        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            if user32.GetForegroundWindow() == hwnd:
                return True
        finally:
            for tid in attached:
                user32.AttachThreadInput(cur, tid, False)
        time.sleep(0.02)
    return False


def window_size(hwnd):
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.right - r.left, r.bottom - r.top


def move_window(hwnd, x, y, topmost=True):
    flags = SWP_NOSIZE | SWP_NOACTIVATE
    if not topmost:
        flags |= SWP_NOZORDER
    user32.SetWindowPos(hwnd, HWND_TOPMOST if topmost else None, int(x), int(y), 0, 0, flags)


def set_topmost(hwnd, on):
    """置顶 / 取消置顶，不改变位置与大小。"""
    if not is_window(hwnd):
        return False
    flags = SWP_NOMOVE | SWP_NOSIZE
    if not on:
        flags |= SWP_NOZORDER
    return bool(user32.SetWindowPos(hwnd, HWND_TOPMOST if on else None, 0, 0, 0, 0, flags))


def cursor_pos():
    p = wt.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def work_area_at(x, y):
    """光标所在显示器的工作区 (left, top, right, bottom)。"""
    mon = user32.MonitorFromPoint(wt.POINT(x, y), 2)  # MONITOR_DEFAULTTONEAREST
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    user32.GetMonitorInfoW(mon, ctypes.byref(info))
    w = info.rcWork
    return w.left, w.top, w.right, w.bottom


def hide_from_taskbar(hwnd):
    style = _GetWindowLongPtr(hwnd, GWL_EXSTYLE)
    style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
    _SetWindowLongPtr(hwnd, GWL_EXSTYLE, style)
    user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)


def is_win11():
    try:
        return sys.getwindowsversion().build >= 22000
    except Exception:
        return False


def apply_rounded(hwnd, radius=18):
    """无边框窗口的圆角：Win11 用 DWM（抗锯齿），Win10 用窗口区域。"""
    if is_win11():
        pref = ctypes.c_int(2)  # DWMWCP_ROUND
        dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), 4)
        return "dwm"
    w, h = window_size(hwnd)
    r = int(radius * dpi_scale())
    rgn = gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, r * 2, r * 2)
    user32.SetWindowRgn(hwnd, rgn, True)
    return "region"


# ───────────────────────── 单实例 ─────────────────────────
ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    """命名事件：第一个实例创建并监听，后续实例触发它然后退出。"""

    NAME = "Local\\ClipBuddy.ShowPanel"

    def __init__(self):
        self.handle = kernel32.CreateEventW(None, False, False, self.NAME)
        self.already_running = ctypes.get_last_error() == ERROR_ALREADY_EXISTS

    def notify_existing(self):
        kernel32.SetEvent(self.handle)

    def listen(self, callback):
        def loop():
            while True:
                if kernel32.WaitForSingleObject(self.handle, 0xFFFFFFFF) == 0:
                    callback()
        threading.Thread(target=loop, daemon=True, name="single-instance").start()


def message_box(text, title="ClipBuddy"):
    user32.MessageBoxW(None, text, title, 0x40)
