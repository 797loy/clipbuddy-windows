"""数据存储：历史、常用语、设置。JSON 文件，原子写入，UTF-8。"""
import json
import logging
import os
import shutil
import threading
import time
import uuid

log = logging.getLogger("clipbuddy.store")

PETS = ("cat", "dog", "bear", "rabbit", "fox", "panda", "mix", "none")

DEFAULT_SETTINGS = {
    "theme": "auto",        # auto / light / dark
    "pet": "cat",           # PETS
    "max_items": 20,        # 历史最多保留条数
    "position": "cursor",   # cursor（鼠标附近）/ center（屏幕居中）
    "auto_hide": True,      # 点击面板外自动收起
}

DEFAULT_CONFIG = {
    "hotkeys": {
        "toggle": ["ctrl+shift+v", "f8"],
        "clear": ["ctrl+shift+c"],
    },
    "max_text_length": 100000,
}


def data_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "ClipBuddy")
    os.makedirs(path, exist_ok=True)
    return path


def load_config(directory):
    """config.json 由用户手动编辑（改热键等）；不存在时生成默认文件。"""
    path = os.path.join(directory, "config.json")
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                user = json.load(f)
            hk = user.get("hotkeys", {})
            for k in ("toggle", "clear"):
                if isinstance(hk.get(k), list):
                    cfg["hotkeys"][k] = [str(x) for x in hk[k]]
            if isinstance(user.get("max_text_length"), int):
                cfg["max_text_length"] = user["max_text_length"]
        else:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
    except Exception:
        log.exception("读取 config.json 失败，使用默认配置")
    return cfg


class Store:
    def __init__(self, path):
        self.path = path
        self._lock = threading.RLock()
        self.history = []     # [{id, text, ts}] 新的在前
        self.favorites = []   # [{id, text, ts}] 新的在前
        self.settings = dict(DEFAULT_SETTINGS)
        self._cleared = []    # 最近一次清空的内容，供撤销
        self.is_new = not os.path.exists(path)
        self._load()

    # ── 持久化 ──
    def _load(self):
        if self.is_new:
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.history = [i for i in data.get("history", []) if self._valid(i)]
            self.favorites = [i for i in data.get("favorites", []) if self._valid(i)]
            for k, v in data.get("settings", {}).items():
                if k in DEFAULT_SETTINGS:
                    self.settings[k] = v
        except Exception:
            log.exception("数据文件损坏，已备份并重新开始")
            try:
                shutil.copy(self.path, self.path + ".bak")
            except OSError:
                pass

    @staticmethod
    def _valid(item):
        return isinstance(item, dict) and isinstance(item.get("text"), str) and item.get("id")

    def _save(self):
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"history": self.history, "favorites": self.favorites,
                           "settings": self.settings}, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except Exception:
            log.exception("保存失败")

    # ── 内部工具 ──
    @staticmethod
    def _new(text):
        return {"id": uuid.uuid4().hex[:10], "text": text, "ts": int(time.time())}

    def _trim(self):
        limit = int(self.settings["max_items"])
        del self.history[limit:]

    # ── 读取 ──
    def snapshot(self):
        with self._lock:
            fav_texts = {f["text"] for f in self.favorites}
            return {
                "history": [dict(i, fav=i["text"] in fav_texts) for i in self.history],
                "favorites": [dict(i) for i in self.favorites],
                "settings": dict(self.settings),
            }

    def get_text(self, source, item_id):
        with self._lock:
            for i in (self.history if source == "history" else self.favorites):
                if i["id"] == item_id:
                    return i["text"]
        return None

    # ── 历史 ──
    def add_history(self, text):
        """新增；相同内容只保留最新一条。"""
        with self._lock:
            self.history = [i for i in self.history if i["text"] != text]
            self.history.insert(0, self._new(text))
            self._trim()
            self._save()
            return True

    def touch(self, text):
        """把某条历史移到最前（粘贴/复制后）。"""
        with self._lock:
            if any(i["text"] == text for i in self.history):
                self.add_history(text)

    def delete(self, source, item_id):
        with self._lock:
            lst = self.history if source == "history" else self.favorites
            lst[:] = [i for i in lst if i["id"] != item_id]
            self._save()

    def clear_history(self):
        with self._lock:
            self._cleared = list(self.history)
            self.history = []
            self._save()
            return len(self._cleared)

    def undo_clear(self):
        with self._lock:
            have = {i["text"] for i in self.history}
            self.history = self.history + [i for i in self._cleared if i["text"] not in have]
            self._cleared = []
            self._trim()
            self._save()

    # ── 常用语 ──
    def is_fav(self, text):
        with self._lock:
            return any(f["text"] == text for f in self.favorites)

    def add_fav(self, text):
        with self._lock:
            if not self.is_fav(text):
                self.favorites.insert(0, self._new(text))
                self._save()

    def remove_fav_by_text(self, text):
        with self._lock:
            self.favorites = [f for f in self.favorites if f["text"] != text]
            self._save()

    # ── 设置 ──
    def set_setting(self, key, value):
        with self._lock:
            if key == "theme" and value in ("auto", "light", "dark"):
                self.settings[key] = value
            elif key == "pet" and value in PETS:
                self.settings[key] = value
            elif key == "max_items" and isinstance(value, int) and 1 <= value <= 500:
                self.settings[key] = value
                self._trim()
            elif key == "position" and value in ("cursor", "center"):
                self.settings[key] = value
            elif key == "auto_hide" and isinstance(value, bool):
                self.settings[key] = value
            else:
                return False
            self._save()
            return True
