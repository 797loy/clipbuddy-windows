"""开机自启：写入 HKCU\\...\\Run（用户级，无需管理员权限）。"""
import os
import sys

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "ClipBuddy"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def launch_command(silent=True):
    """用 pythonw.exe 启动，避免弹出黑色控制台窗口。"""
    flag = " --silent" if silent else ""
    if getattr(sys, "frozen", False):  # PyInstaller 打包后的 exe
        return f'"{sys.executable}"{flag}'
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pyw):
        exe = pyw
    return f'"{exe}" "{os.path.join(ROOT, "app.py")}"{flag}'


def is_enabled():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, VALUE_NAME)
            return True
    except OSError:
        return False


def set_enabled(enabled):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            winreg.SetValueEx(k, VALUE_NAME, 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(k, VALUE_NAME)
            except FileNotFoundError:
                pass
