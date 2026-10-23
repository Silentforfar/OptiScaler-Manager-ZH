"""已安装记录：全局索引 + 每个游戏目录内的 manifest 双写。"""
import json
import os
import uuid
from datetime import datetime

APP_NAME = "OptiScalerManager"
APP_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), APP_NAME)
STORE_PATH = os.path.join(APP_DIR, "installed.json")
MANIFEST_NAME = ".optiscaler_manifest.json"
BACKUP_DIR = ".optiscaler_backup"


def _ensure_dir():
    os.makedirs(APP_DIR, exist_ok=True)


def load_store():
    _ensure_dir()
    if not os.path.exists(STORE_PATH):
        return {"version": 1, "items": []}
    try:
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"version": 1, "items": []}
    data.setdefault("items", [])
    return data


def save_store(data):
    _ensure_dir()
    tmp = STORE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STORE_PATH)


def add_item(game_dir, game_name, exe_name, proxy, version, payload_files):
    data = load_store()
    game_dir = os.path.normcase(os.path.abspath(game_dir))
    data["items"] = [i for i in data["items"]
                     if os.path.normcase(i.get("game_dir", "")) != game_dir]
    data["items"].append({
        "id": uuid.uuid4().hex[:12],
        "game_name": game_name,
        "game_dir": os.path.abspath(game_dir),
        "exe": exe_name,
        "proxy": proxy,
        "version": version,
        "file_count": payload_files,
        "installed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    save_store(data)


def remove_item(game_dir):
    data = load_store()
    key = os.path.normcase(os.path.abspath(game_dir))
    data["items"] = [i for i in data["items"]
                     if os.path.normcase(i.get("game_dir", "")) != key]
    save_store(data)


def get_item(game_dir):
    key = os.path.normcase(os.path.abspath(game_dir))
    for i in load_store()["items"]:
        if os.path.normcase(i.get("game_dir", "")) == key:
            return i
    return None


def read_manifest(game_dir):
    p = os.path.join(game_dir, MANIFEST_NAME)
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def write_manifest(game_dir, data):
    p = os.path.join(game_dir, MANIFEST_NAME)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
