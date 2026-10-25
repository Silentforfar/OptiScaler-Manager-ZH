"""读取 / 修改游戏自己的画质设置。

目前只支持 CoD 系列（MW4 / BO 系列）：设置存在
%LOCALAPPDATA%\\Activision\\Call of Duty\\players\\s.<ver>.cod<yy>.txt，
格式是明文：

    // Activate Nvidia DLSS Frame Generation
    DLSSFrameGeneration@0;57752;48403 = true

    // DLSS performance mode
    DLSSPerfModeMP@0;27441;8284 = Maximum Quality // one of ...

`@` 后面那串是 profile / 设备标识，**改值时必须原样保留**，否则游戏会认为
配置项无效。注释里的 "one of ..." 是合法取值，也保留。
"""
import glob
import os
import re
import shutil
from datetime import datetime

LINE_RE = re.compile(r'^(?P<key>[A-Za-z0-9_]+)@(?P<prof>[\d;]+)\s*=\s*(?P<val>.*?)\s*(?P<cmt>//.*)?$')


def _players_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Activision", "Call of Duty", "players")


def find_cod_settings():
    """返回最新的 s.<ver>.cod*.txt，找不到返回 None。"""
    d = _players_dir()
    if not os.path.isdir(d):
        return None
    cands = [p for p in glob.glob(os.path.join(d, "s.*.cod*.txt"))
             if os.path.isfile(p)]
    if not cands:
        return None
    return max(cands, key=os.path.getmtime)


def parse(path):
    """解析成 [{key, profile, value, comment, index, desc}]。"""
    items = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    last_desc = ""
    for i, raw in enumerate(lines):
        s = raw.strip()
        if s.startswith("//"):
            last_desc = s.lstrip("/").strip()
            continue
        if not s:
            last_desc = ""
            continue
        m = LINE_RE.match(s)
        if not m:
            continue
        items.append({
            "key": m.group("key"),
            "profile": m.group("prof"),
            "value": m.group("val"),
            "comment": m.group("cmt") or "",
            "desc": last_desc,
            "index": i,
        })
    return lines, items


def set_value(path, key, profile, new_value):
    """只改指定项的值，保留 @profile、注释和其余所有行。"""
    lines, items = parse(path)
    hit = None
    for it in items:
        if it["key"] == key and it["profile"] == profile:
            hit = it
            break
    if hit is None:
        raise KeyError("找不到设置项：%s@%s" % (key, profile))
    cmt = (" " + hit["comment"]) if hit["comment"] else ""
    lines[hit["index"]] = "%s@%s = %s%s\n" % (key, profile, new_value, cmt)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.writelines(lines)
    os.replace(tmp, path)
    return hit["value"]


def backup(path):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = "%s.bak_%s" % (path, stamp)
    shutil.copy2(path, dst)
    return dst


# 面板里露出来的项：key -> (中文名, 类型, 取值范围说明)
COD_FIELDS = [
    ("DLSSFrameGeneration", "DLSS 帧生成", "bool", ""),
    ("DLSSFrameGenerationmulti", "生成帧数（1=2X 2=3X 3=4X 4=5X 5=6X）", "int", ""),
    ("DLSSFrameGenerationmultiType", "倍率模式", "choice", "Fixed,Dynamic Auto,Dynamic Manual"),
    ("DLSSPerfModeMP", "DLSS 质量", "choice",
     "Ultra Performance,Maximum Performance,Balanced,Maximum Quality,Native Resolution"),
    ("DLSSModelUI", "DLSS 模型", "choice", "CNN,TRANSFORMER"),
    ("NvidiaReflex", "NVIDIA Reflex", "choice", "Disabled,Enabled,Enabled + boost"),
    ("FSRFrameInterpolation", "FSR 帧插值", "bool", ""),
    ("DepthOfFieldQuality", "景深质量", "choice", "Low,High"),
    ("TextureQuality", "纹理质量（0 最高）", "int", ""),
]


def read_cod_panel():
    """返回 (设置文件路径, [ {key, profile, value, label, kind, options, desc} ])"""
    path = find_cod_settings()
    if not path:
        return None, []
    _, items = parse(path)
    by_key = {}
    for it in items:
        by_key.setdefault(it["key"], []).append(it)

    out = []
    for key, label, kind, opts in COD_FIELDS:
        for it in by_key.get(key, []):
            out.append({
                "key": key,
                "profile": it["profile"],
                "value": it["value"],
                "label": label,
                "kind": kind,
                "options": [o.strip() for o in opts.split(",") if o.strip()],
                "desc": it["desc"],
            })
    return path, out
