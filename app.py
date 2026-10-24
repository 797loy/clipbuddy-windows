"""剪贴宝 ClipBuddy —— Windows 剪贴板历史工具（入口）。

后台常驻：监听剪贴板 → 全局热键呼出毛玻璃面板 → 点击即粘贴到原窗口。
启动：pythonw app.py（无控制台）；加 --silent 则启动后不弹面板（开机自启用）。
"""
import logging
import logging.handlers
import os
import sys
import threading
import time

APP_TITLE = "剪贴宝 ClipBuddy"
APP_VERSION = "1.1.1"
WIDTH, HEIGHT = 460, 620


def _base_dir():
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def _system_is_dark():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def _setup_logging(directory):
    handler = logging.handlers.RotatingFileHandler(
        os.path.join(directory, "clipbuddy.log"), maxBytes=512 * 1024, backupCount=1, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


class Controller:
    """面板控制 + 剪贴板监听 + 暴露给前端的 JS API。

    以下划线开头的属性/方法不会暴露给前端；公开方法即前端可调用的 API。
    """

    def __init__(self, store, config, silent):
        from core import winapi
        self._w = winapi
        self._store = store
        self._config = config
        self._silent = silent
        self._window = None
        self._hwnd = None
        self._visible = False
        self._pasting = False      # 粘贴过程中，防止"点击外部自动收起"把面板藏掉
        self._shown_at = 0.0
        self._prev = None            # 呼出面板前的前台窗口
        self._own_seq = None         # 我们自己写剪贴板后的序号，用来忽略回声
        self._tray = None
        self._round_mode = "dwm"
        self._lock = threading.RLock()
        self._log = logging.getLogger("clipbuddy.app")

    # ───────── 生命周期 ─────────
    def _attach(self, window):
        self._window = window

    def _on_started(self):
        """webview 启动后在后台线程执行。"""
        w = self._w
        for _ in range(100):
            self._hwnd = w.find_window(APP_TITLE)
            if self._hwnd:
                break
            time.sleep(0.1)
        if not self._hwnd:
            self._log.error("找不到窗口句柄")
            return
        self._window.events.loaded.wait(10)
        w.hide_from_taskbar(self._hwnd)
        self._round_mode = w.apply_rounded(self._hwnd)

        toggle = [(k, self._toggle_hotkey) for k in self._config["hotkeys"]["toggle"]]
        clear = [(k, self._clear_hotkey) for k in self._config["hotkeys"]["clear"]]
        self._hk = w.HotkeyListener(toggle + clear)
        self._hk.start()
        threading.Thread(target=self._monitor_loop, daemon=True, name="clip-monitor").start()
        threading.Thread(target=self._focus_watcher, daemon=True, name="focus-watch").start()
        self._start_tray()
        if not self._silent:
            self.show()

    # ───────── 面板显示 / 隐藏 ─────────
    def show(self, from_tray=False):
        w = self._w
        with self._lock:
            if not self._hwnd or self._visible:
                return
            fg = w.foreground()
            self._prev = None if fg == self._hwnd else fg
            self._place()
            self._window.show()
            self._visible = True
            self._shown_at = time.time()
        w.force_foreground(self._hwnd)
        self._js("window.onShow && window.onShow()")

    def _place(self):
        w = self._w
        pw, ph = w.window_size(self._hwnd)
        cx, cy = w.cursor_pos()
        left, top, right, bottom = w.work_area_at(cx, cy)
        if self._store.settings["position"] == "center":
            x, y = (left + right - pw) // 2, (top + bottom - ph) // 2
        else:
            x, y = cx - pw // 2, cy + int(16 * w.dpi_scale())
            if y + ph > bottom:           # 下方放不下就放到光标上方
                y = cy - ph - int(16 * w.dpi_scale())
        x = max(left + 8, min(x, right - pw - 8))
        y = max(top + 8, min(y, bottom - ph - 8))
        w.move_window(self._hwnd, x, y, topmost=True)
        if self._round_mode == "region":  # Win10 圆角区域需随 DPI 重算
            w.apply_rounded(self._hwnd)

    def _hide(self, restore=True):
        w = self._w
        with self._lock:
            if not self._visible:
                return
            self._visible = False
            prev = self._prev
        self._window.hide()
        if restore and prev and w.is_window(prev):
            w.force_foreground(prev)

    def _toggle(self, from_tray=False):
        if self._visible:
            self._hide(True)
        else:
            self.show(from_tray)

    def _toggle_hotkey(self):
        self._toggle()

    def _focus_watcher(self):
        """点击面板外部（焦点离开）时自动收起。粘贴过程中不收起（面板保持显示）。"""
        while True:
            time.sleep(0.25)
            try:
                if (self._visible and not self._pasting
                        and self._store.settings["auto_hide"]
                        and time.time() - self._shown_at > 0.6
                        and self._w.foreground() != self._hwnd):
                    self._hide(restore=False)
            except Exception:
                self._log.exception("focus watcher")

    def _js(self, code):
        try:
            self._window.evaluate_js(code)
        except Exception:
            pass

    # ───────── 剪贴板监听 ─────────
    def _monitor_loop(self):
        w = self._w
        last = None
        max_len = self._config["max_text_length"]
        while True:
            time.sleep(0.25)
            try:
                seq = w.clipboard_seq()
                if seq == last:
                    continue
                if seq == self._own_seq or w.clipboard_excluded():
                    last = seq
                    continue
                try:
                    text = w.get_text()
                except w.ClipboardBusy:
                    continue  # 被占用，下个周期重试
                last = seq
                if not text or not text.strip() or len(text) > max_len:
                    continue
                self._store.add_history(text)
                if self._visible:
                    self._js("window.onChanged && window.onChanged()")
            except Exception:
                self._log.exception("clipboard monitor")

    def _write_clipboard(self, text):
        ok = self._w.set_text(text)
        self._own_seq = self._w.clipboard_seq()
        return ok

    # ───────── 托盘 ─────────
    def _start_tray(self):
        try:
            import pystray
            from core.icon import make_icon
            from core import autostart
        except Exception:
            self._log.warning("未安装 pystray/Pillow，跳过托盘图标")
            return

        def toggle_autostart(icon, item):
            autostart.set_enabled(not autostart.is_enabled())

        menu = pystray.Menu(
            pystray.MenuItem("打开面板", lambda icon, item: self._toggle(from_tray=True), default=True),
            pystray.MenuItem("清空历史", lambda icon, item: self._clear_hotkey()),
            pystray.MenuItem("开机自启", toggle_autostart,
                             checked=lambda item: autostart.is_enabled()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", lambda icon, item: self.quit_app()),
        )
        self._tray = pystray.Icon("ClipBuddy", make_icon(64), APP_TITLE, menu)
        self._tray.run_detached()

    def _notify(self, msg):
        try:
            if self._tray:
                self._tray.notify(msg, APP_TITLE)
        except Exception:
            pass

    def _clear_hotkey(self):
        n = self._store.clear_history()
        self._js("window.onChanged && window.onChanged()")
        self._notify(f"已清空 {n} 条历史")

    # ───────── 粘贴 ─────────
    def _deliver_paste(self, prev):
        """把已写入剪贴板的内容粘贴到目标窗口 prev，尽量保证焦点确实切过去再发 Ctrl+V。

        面板显示时：先让出置顶，避免面板盖住目标窗口抢焦点；粘贴完成后再恢复置顶并拉回前台。
        若多次尝试仍无法让目标窗口拿到焦点（如目标为管理员权限程序），不发送按键，
        改为提示手动 Ctrl+V，避免误粘到面板自身。
        """
        w = self._w
        if self._visible:
            w.set_topmost(self._hwnd, False)   # 面板先让出置顶
        try:
            focused = False
            for _ in range(4):
                w.force_foreground(prev, retries=3)
                time.sleep(0.10)
                for _ in range(12):            # 最多再等约 0.36s 让焦点真正落到目标窗口
                    if w.foreground() == prev:
                        focused = True
                        break
                    time.sleep(0.03)
                if focused:
                    break
            if focused:
                w.send_ctrl_v()
                self._log.info("deliver: 已向目标 %s 发送 Ctrl+V", prev)
            else:
                self._log.warning("deliver: 焦点未切到目标 %s（当前前台 %s），提示手动粘贴",
                                  prev, w.foreground())
                self._js("window.toast && window.toast('未能自动粘贴，内容已复制，请手动 Ctrl+V')")
        finally:
            if self._visible:
                w.set_topmost(self._hwnd, True)
                w.force_foreground(self._hwnd)

    def _do_paste(self, text, source):
        w = self._w
        if not self._write_clipboard(text):
            self._js("window.toast && window.toast('剪贴板被占用，请重试')")
            return
        if source == "history":
            self._store.touch(text)
        prev = self._prev
        self._log.info("paste: 请求粘贴 %r（来源=%s）目标=%s 面板显示=%s", text[:24], source, prev, self._visible)
        if not self._visible:
            # 面板已隐藏（托盘/快捷键收起）：粘贴后不把面板重新拉出来
            self._hide(restore=True)
            if prev and w.is_window(prev):
                self._deliver_paste(prev)
            return

        # 面板显示：隐藏面板让置顶的 WebView2 不再抢占键盘，然后主动用 _prev
        # (打开面板时的前台窗口=用户目标) 把焦点切回目标，等其编辑框获得焦点后发
        # Ctrl+V。完成后立即弹回面板，兼顾「每次点击都能粘」与「连续粘贴填充」。
        with self._lock:
            self._pasting = True
        try:
            self._window.hide()               # 隐藏面板
            with self._lock:
                self._visible = False
            # 主动聚焦用户目标(_prev=打开面板时的前台窗口)，避免自然归位落到错误窗口
            target = prev if (prev and w.is_window(prev) and prev != self._hwnd) else None
            if target:
                w.force_foreground(target, retries=6)
            time.sleep(0.3)                   # 等目标窗口编辑框真正获得焦点
            fg = w.foreground()
            if fg and fg != self._hwnd:
                w.send_ctrl_v()               # 发给当前前台=目标窗口
                self._log.info("deliver: 已向 %s 发送 Ctrl+V", fg)
            else:
                self._log.warning("deliver: 无有效前台窗口，内容已复制")
                self._js("window.toast && window.toast('内容已复制，请手动 Ctrl+V')")
        finally:
            with self._lock:
                self._pasting = False
            if not self._visible:             # 粘贴完成，立即把面板重新显示出来
                self.show()

    # ═════════ 以下为前端可调用的 API ═════════
    def get_state(self):
        from core import autostart
        state = self._store.snapshot()
        state["settings"]["autostart"] = autostart.is_enabled()
        state["env"] = {"hotkeys": self._config["hotkeys"], "version": APP_VERSION}
        return state

    def paste(self, source, item_id):
        text = self._store.get_text(source, item_id)
        if text is None:
            return False
        threading.Thread(target=self._do_paste, args=(text, source), daemon=True).start()
        return True

    def copy_only(self, source, item_id):
        text = self._store.get_text(source, item_id)
        if text is None:
            return self.get_state()
        self._write_clipboard(text)
        if source == "history":
            self._store.touch(text)
        return self.get_state()

    def toggle_fav(self, source, item_id):
        text = self._store.get_text(source, item_id)
        if text is not None:
            if self._store.is_fav(text):
                self._store.remove_fav_by_text(text)
            else:
                self._store.add_fav(text)
        return self.get_state()

    def delete(self, source, item_id):
        self._store.delete(source, item_id)
        return self.get_state()

    def clear_history(self):
        self._store.clear_history()
        return self.get_state()

    def undo_clear(self):
        self._store.undo_clear()
        return self.get_state()

    def add_phrase(self, text):
        text = (text or "").strip()
        if text:
            self._store.add_fav(text)
        return self.get_state()

    def set_setting(self, key, value):
        from core import autostart
        if key == "autostart":
            try:
                autostart.set_enabled(bool(value))
            except OSError:
                self._log.exception("设置开机自启失败")
        else:
            self._store.set_setting(key, value)
        return self.get_state()

    def hide(self):
        self._hide(restore=True)

    def quit_app(self):
        self._log.info("退出")
        try:
            if self._tray:
                self._tray.stop()
        except Exception:
            pass
        os._exit(0)


def main():
    if sys.platform != "win32":
        print("ClipBuddy 仅支持 Windows。")
        return
    silent = "--silent" in sys.argv

    from core import winapi
    winapi.set_dpi_aware()
    from core.store import Store, data_dir, load_config

    directory = data_dir()
    _setup_logging(directory)
    log = logging.getLogger("clipbuddy.main")

    instance = winapi.SingleInstance()
    if instance.already_running:       # 已在后台运行：让它弹出面板，自己退出
        instance.notify_existing()
        return

    try:
        import webview
    except ImportError:
        winapi.message_box("缺少依赖 pywebview，请先运行 install.bat 或 pip install -r requirements.txt")
        return

    store = Store(os.path.join(directory, "data.json"))
    config = load_config(directory)
    ctl = Controller(store, config, silent)
    instance.listen(lambda: ctl.show())

    theme = store.settings["theme"]
    dark = theme == "dark" or (theme == "auto" and _system_is_dark())
    kwargs = dict(
        title=APP_TITLE,
        url=os.path.join(_base_dir(), "ui", "index.html"),
        js_api=ctl,
        width=WIDTH, height=HEIGHT,
        frameless=True, easy_drag=False, resizable=False,
        on_top=True, hidden=True,
        background_color="#1c1c1e" if dark else "#f4f0ff",   # 仅 6 位十六进制
    )
    try:
        window = webview.create_window(shadow=True, **kwargs)
    except TypeError:                  # 旧版 pywebview 没有 shadow 参数
        window = webview.create_window(**kwargs)
    ctl._attach(window)
    log.info("启动完成，silent=%s", silent)
    webview.start(ctl._on_started)


if __name__ == "__main__":
    main()
