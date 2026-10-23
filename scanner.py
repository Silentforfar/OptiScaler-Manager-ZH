"""游戏目录扫描：Steam / Epic / GOG，以及手动目录下主程序推断。"""
import json
import os
import re

try:
    import winreg
except ImportError:  # 非 Windows
    winreg = None

SKIP_EXE = (
    "unins", "crashpad", "crashhandler", "crashlogs", "unitycrash", "vcredist",
    "dxwebsetup", "dxsetup", "dotnet", "redist", "easyanticheat", "battleye",
    "steamerrorreporter", "setup", "install", "activation", "report",
    "benchmark_launcher", "ue4prereqsetup", "ue5prereqsetup", "prereq",
    "launcher_installer", "broker", "attestation", "downloader", "cleaner",
    "wizard", "telemetry", "7za", "unpack", "bootstrapper",
    "start_protected", "startup", "playrdr", "crs-video", "crs-handler",
)

# 体积分上限（MB）与每档步长
_SCORE_STEP_MB = 25
_SCORE_MAX_SIZE = 30


def _score_exe(rel, name, size):
    """给候选 exe 打分。分数只用于排序和默认选中，最终由用户确认。

    依据 OptiScaler 官方安装说明：必须放在「真正加载图形 API 的 exe」旁边，
    不能放在启动器旁边；UE 游戏要进 Binaries\\Win64 找 *-Win64-Shipping.exe。
    """
    low = name.lower()
    parts = [p.lower() for p in rel.split(os.sep)]
    score = 0
    tag = ""

    if low.endswith(("-win64-shipping.exe", "-wingdk-shipping.exe")):
        score += 60
        tag = "UE 主体"
    elif low.endswith("-shipping.exe"):
        score += 45
        tag = "Shipping"

    if "binaries" in parts:
        score += 20

    if parts and parts[0] == "engine":
        score -= 120
        tag = "引擎工具"

    if any(k in low for k in SKIP_EXE):
        score -= 120
        tag = tag or "辅助程序"

    if "launcher" in low:
        score -= 40
        tag = "启动器"

    # 分模块游戏的特征：子目录名出现在 exe 名里，例如 sp26\sp26-cod.exe、
    # cod24\cod24-cod.exe。这类 exe 才是真正跑该模式的那一个。
    stem = low[:-4] if low.endswith(".exe") else low
    if len(parts) >= 2 and parts[-2] and parts[-2] in stem:
        score += 12
        tag = tag or "子模块"

    score += min(size // (_SCORE_STEP_MB * 1024 * 1024), _SCORE_MAX_SIZE)
    score -= max(len(parts) - 1, 0) * 3
    return score, tag


def list_executables(game_dir, max_depth=4, min_size=300 * 1024):
    """列出目录下所有可作为注入目标的 exe，按可能性排序。

    返回 [{'rel','full','dir','name','size','score','tag'}]
    """
    base = os.path.abspath(game_dir)
    out = []
    skip_dirs = {"engine", "content", "saved", "logs", "cache", ".git", "__pycache__",
                 "redist", "support", "_commonredist", "directx", "vcredist", "dotnet"}
    for root, dirs, files in os.walk(base):
        rel_root = os.path.relpath(root, base)
        depth = 0 if rel_root == "." else rel_root.count(os.sep) + 1
        if depth >= max_depth:
            dirs[:] = []
        dirs[:] = [d for d in dirs if d.lower() not in skip_dirs]
        if depth > 0 and rel_root.split(os.sep)[0].lower() == "engine":
            continue
        for f in files:
            if not f.lower().endswith(".exe"):
                continue
            full = os.path.join(root, f)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            if size < min_size:
                continue
            rel = os.path.relpath(full, base)
            score, tag = _score_exe(rel, f, size)
            if score < -50:
                continue
            out.append({"rel": rel, "full": full, "dir": root, "name": f,
                        "size": size, "score": score, "tag": tag})
    out.sort(key=lambda x: (-x["score"], -x["size"]))
    return out


def find_main_exe(game_dir, max_depth=4):
    """兼容接口：取评分最高的那个。"""
    cands = list_executables(game_dir, max_depth=max_depth)
    return cands[0]["full"] if cands else None


def _reg(path, name):
    if not winreg:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        pass
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def scan_steam(log):
    out = []
    steam = _reg(r"Software\Valve\Steam", "SteamPath") or _reg(r"Software\WOW6432Node\Valve\Steam", "InstallPath")
    if not steam or not os.path.isdir(steam):
        return out
    libs = []
    vdf = os.path.join(steam, "steamapps", "libraryfolders.vdf")
    if os.path.exists(vdf):
        try:
            text = open(vdf, "r", encoding="utf-8", errors="ignore").read()
            for m in re.finditer(r'"path"\s*"([^"]+)"', text):
                libs.append(m.group(1).replace("\\\\", "\\"))
        except OSError:
            pass
    if steam not in libs:
        libs.append(steam)
    log("Steam: 找到 %d 个库目录" % len(libs))
    for lib in libs:
        common = os.path.join(lib, "steamapps", "common")
        if not os.path.isdir(common):
            continue
        try:
            names = os.listdir(common)
        except OSError:
            continue
        for name in names:
            gdir = os.path.join(common, name)
            if not os.path.isdir(gdir):
                continue
            exe = find_main_exe(gdir)
            if exe:
                out.append({"name": name, "dir": os.path.dirname(exe),
                            "root": gdir, "exe": os.path.basename(exe), "source": "Steam"})
    return out


def scan_epic(log):
    out = []
    base = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"),
                        "Epic", "EpicGamesLauncher", "Data", "Manifests")
    if not os.path.isdir(base):
        return out
    for f in os.listdir(base):
        if not f.endswith(".item"):
            continue
        try:
            data = json.load(open(os.path.join(base, f), "r", encoding="utf-8"))
        except Exception:
            continue
        loc = data.get("InstallLocation")
        name = data.get("DisplayName") or os.path.basename(loc or "")
        if not loc or not os.path.isdir(loc):
            continue
        exe = find_main_exe(loc)
        if exe:
            out.append({"name": name, "dir": os.path.dirname(exe),
                        "root": loc, "exe": os.path.basename(exe), "source": "Epic"})
    log("Epic: %d 个" % len(out))
    return out


def scan_gog(log):
    out = []
    if not winreg:
        return out
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\GOG.com\Games")
    except OSError:
        return out
    n = winreg.QueryInfoKey(key)[0]
    for i in range(n):
        try:
            sub = winreg.EnumKey(key, i)
            with winreg.OpenKey(key, sub) as k:
                path = winreg.QueryValueEx(k, "path")[0]
                name = winreg.QueryValueEx(k, "gameName")[0]
        except OSError:
            continue
        if path and os.path.isdir(path):
            exe = find_main_exe(path)
            if exe:
                out.append({"name": name, "dir": os.path.dirname(exe),
                            "root": path, "exe": os.path.basename(exe), "source": "GOG"})
    log("GOG: %d 个" % len(out))
    return out


def scan_all(log=print):
    """扫一遍所有已知平台，去重后返回。"""
    items = []
    for fn in (scan_steam, scan_epic, scan_gog):
        try:
            items.extend(fn(log))
        except Exception as e:
            log("%s 扫描失败：%s" % (fn.__name__, e))
    seen, uniq = set(), []
    for it in items:
        k = os.path.normcase(os.path.abspath(it["dir"]))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(it)
    uniq.sort(key=lambda x: x["name"].lower())
    return uniq
