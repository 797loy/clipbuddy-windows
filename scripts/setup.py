"""安装 / 卸载辅助：桌面快捷方式、开机自启。

用法：
    python scripts/setup.py install [--no-autostart]
    python scripts/setup.py uninstall
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import autostart  # noqa: E402

LINK_NAME = "剪贴宝.lnk"


def desktop_dir():
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
        capture_output=True, text=True, encoding="utf-8")
    return out.stdout.strip() or os.path.join(os.path.expanduser("~"), "Desktop")


def make_icon():
    path = os.path.join(ROOT, "assets", "icon.ico")
    if not os.path.exists(path):
        try:
            from core.icon import make_icon as draw
            draw(256).save(path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        except Exception:
            return ""
    return path


def create_shortcut():
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    target = pyw if os.path.exists(pyw) else exe
    link = os.path.join(desktop_dir(), LINK_NAME)
    ps = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{link}');"
        "$s.TargetPath='{target}';$s.Arguments='\"{app}\"';$s.WorkingDirectory='{root}';"
        "$s.IconLocation='{icon}';$s.Description='剪贴宝 ClipBuddy';$s.Save()"
    ).format(link=link, target=target, app=os.path.join(ROOT, "app.py"), root=ROOT, icon=make_icon())
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    print("已创建桌面快捷方式:", link)


def remove_shortcut():
    link = os.path.join(desktop_dir(), LINK_NAME)
    if os.path.exists(link):
        os.remove(link)
        print("已删除桌面快捷方式")


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "install"
    if action == "install":
        create_shortcut()
        if "--no-autostart" not in sys.argv:
            autostart.set_enabled(True)
            print("已设置开机自启")
        print("完成。双击桌面「剪贴宝」即可启动，按 Ctrl+Shift+V 或 F8 呼出面板。")
    elif action == "uninstall":
        remove_shortcut()
        autostart.set_enabled(False)
        print("已取消开机自启。")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
