"""安装 / 卸载 / 完整性校验。

无损原则：
- 只写 payload 里的文件，以及把 OptiScaler.dll 改名成代理名
- 任何被覆盖的同名文件先备份到游戏目录下的 .optiscaler_backup/
- 卸载只依据 manifest 记录，绝不猜测、绝不递归删游戏目录
"""
import hashlib
import os
import shutil
from datetime import datetime

import store

PRODUCT = "OptiScaler-Manager"
VERSION = "1.0.0"
CORE_DLL = "OptiScaler.dll"
MODEL_FILE = "nvngx_dlssnr.dll"

PROXIES = [
    ("dxgi.dll", "dxgi.dll   （推荐的默认值，绝大多数 DX12 游戏）"),
    ("winmm.dll", "winmm.dll  （Vulkan 游戏、部分 UE 游戏）"),
    ("version.dll", "version.dll（XGP / MS 商店版常用）"),
    ("d3d12.dll", "d3d12.dll"),
    ("dbghelp.dll", "dbghelp.dll"),
    ("wininet.dll", "wininet.dll"),
    ("winhttp.dll", "winhttp.dll"),
    ("OptiScaler.asi", "OptiScaler.asi（本体不作代理，靠 ASI 加载器）"),
]

CHUNK = 1 << 20


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _safe(base, rel):
    """确保 rel 落在 base 之内，防路径穿越。"""
    p = os.path.normpath(os.path.join(base, rel))
    if not os.path.normcase(p).startswith(os.path.normcase(os.path.abspath(base)) + os.sep):
        raise ValueError("非法路径：%s" % rel)
    return p


def list_payload(payload_dir):
    """返回 [(相对路径, 绝对路径)]，跳过说明类文本以外的东西也照装。"""
    out = []
    base = os.path.abspath(payload_dir)
    for root, dirs, files in os.walk(base):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, base)
            out.append((rel, full))
    out.sort()
    return out


def check_target(target_dir):
    """安装前检查，返回 (ok, message)。"""
    if not target_dir or not os.path.isdir(target_dir):
        return False, "目标目录不存在"
    try:
        probe = os.path.join(target_dir, ".opti_write_test")
        with open(probe, "w") as f:
            f.write("")
        os.remove(probe)
    except OSError:
        return False, "目标目录不可写（可能需要管理员权限）"
    if store.read_manifest(target_dir):
        return False, "该目录已经装过 OptiScaler，请先在「已安装」里卸载"
    return True, ""


def install(payload_dir, target_dir, proxy, game_name, exe_name,
            progress=lambda done, total, name: None, log=print):
    ok, msg = check_target(target_dir)
    if not ok:
        raise RuntimeError(msg)

    files = list_payload(payload_dir)
    total = len(files)
    plan = []          # (rel, src, dst_rel)
    for rel, full in files:
        dst_rel = proxy if rel == CORE_DLL else rel
        plan.append((rel, full, dst_rel, os.path.getsize(full)))

    # 神经渲染模型是用户自备的大文件：目标已有同尺寸的就保留，
    # 既不备份也不复制，卸载时也就不会删掉玩家自己那份。
    skip_rels = set()
    for rel, full, dst_rel, size in plan:
        if dst_rel.lower() == MODEL_FILE:
            dst = _safe(target_dir, dst_rel)
            if os.path.exists(dst) and os.path.getsize(dst) == size:
                skip_rels.add(dst_rel)
                log("目标目录已有 %s，保留不动" % dst_rel)

    backup_root = os.path.join(target_dir, store.BACKUP_DIR)
    backups = []
    created = []
    dirs_made = []

    # 1) 备份将被覆盖的文件
    for rel, full, dst_rel, size in plan:
        if dst_rel in skip_rels:
            continue
        dst = _safe(target_dir, dst_rel)
        if os.path.exists(dst):
            os.makedirs(backup_root, exist_ok=True)
            bdst = _safe(backup_root, dst_rel)
            os.makedirs(os.path.dirname(bdst), exist_ok=True)
            shutil.copy2(dst, bdst)
            backups.append({"rel": dst_rel, "backup": os.path.relpath(bdst, target_dir)})
            log("已备份原文件：%s" % dst_rel)

    # 2) 复制
    done = 0
    skipped = []
    for rel, full, dst_rel, size in plan:
        if dst_rel in skip_rels:
            skipped.append(dst_rel)
            done += 1
            progress(done, total, dst_rel)
            continue
        dst = _safe(target_dir, dst_rel)
        parent = os.path.dirname(dst)
        if not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
            dirs_made.append(os.path.relpath(parent, target_dir))
        tmp = dst + ".optitmp"
        with open(full, "rb") as fi, open(tmp, "wb") as fo:
            while True:
                b = fi.read(CHUNK)
                if not b:
                    break
                fo.write(b)
        os.replace(tmp, dst)
        try:
            shutil.copystat(full, dst)
        except OSError:
            pass
        done += 1
        progress(done, total, dst_rel)
        created.append({"rel": dst_rel, "sha256": sha256(dst), "size": size})

    # 4) 如果游戏自带 Streamline，复制一份进 OptiScaler\streamline，
    #    否则 FGOutput=DLSSG 会报 "Can't init DLSSG Output"。
    #    只用这个游戏自己的文件，不跨游戏混用版本。
    sl_names = ("sl.interposer.dll", "sl.common.dll", "sl.dlss_g.dll", "sl.reflex.dll",
                "sl.pcl.dll", "sl.dlss.dll", "sl.dlss_d.dll", "nvngx_dlssg.dll")
    sl_avail = [n for n in sl_names if os.path.exists(os.path.join(target_dir, n))]
    if "sl.interposer.dll" in sl_avail:
        sdir = os.path.join(target_dir, "OptiScaler", "streamline")
        os.makedirs(sdir, exist_ok=True)
        for n in sl_avail:
            src = os.path.join(target_dir, n)
            dst = os.path.join(sdir, n)
            if os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src):
                continue
            shutil.copy2(src, dst)
            created.append({"rel": os.path.join("OptiScaler", "streamline", n),
                            "sha256": sha256(dst), "size": os.path.getsize(dst)})
        log("已为 DLSSG 输出准备 %d 个 Streamline 文件" % len(sl_avail))
    else:
        log("游戏目录没有 Streamline 文件，DLSSG 输出不可用（可改用 nofg）")

    manifest = {
        "product": PRODUCT,
        "version": VERSION,
        "installed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "proxy": proxy,
        "game_exe": exe_name,
        "game_name": game_name,
        "files": created,
        "skipped": skipped,
        "backups": backups,
        "dirs": sorted(set(dirs_made)),
    }
    store.write_manifest(target_dir, manifest)
    store.add_item(target_dir, game_name, exe_name, proxy, VERSION, len(created))
    log("安装完成：%d 个文件，%d 个原文件已备份" % (len(created), len(backups)))
    return manifest


def uninstall(target_dir, progress=lambda done, total, name: None, log=print):
    m = store.read_manifest(target_dir)
    if not m:
        raise RuntimeError("这个目录没有 OptiScaler 的安装记录（缺少 manifest），已中止，未改动任何文件")

    files = m.get("files", [])
    backups = m.get("backups", [])
    total = len(files) + len(backups)
    done = 0
    removed = 0
    modified = []

    # 1) 删除本工具装入的文件
    for item in files:
        rel = item.get("rel", "")
        try:
            p = _safe(target_dir, rel)
        except ValueError:
            continue
        if os.path.exists(p):
            if item.get("sha256") and sha256(p) != item["sha256"]:
                modified.append(rel)
            try:
                os.remove(p)
                removed += 1
            except OSError as e:
                log("删除失败 %s：%s" % (rel, e))
        done += 1
        progress(done, total, rel)

    # 2) 还原备份
    for b in backups:
        rel, bkp = b.get("rel", ""), b.get("backup", "")
        try:
            src = _safe(target_dir, bkp)
            dst = _safe(target_dir, rel)
        except ValueError:
            continue
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            log("已还原：%s" % rel)
        done += 1
        progress(done, total, rel)

    # 3) 清空目录（只删空的，目录集合从装入文件的相对路径反推）
    cand = set(m.get("dirs", []))
    for item in files:
        d = os.path.dirname(item.get("rel", ""))
        while d and d not in (".", ""):
            cand.add(d)
            d = os.path.dirname(d)
    cand.add(store.BACKUP_DIR)
    dirs = sorted(cand, key=lambda x: x.count(os.sep), reverse=True)
    for d in dirs:
        try:
            p = _safe(target_dir, d)
        except ValueError:
            continue
        try:
            if os.path.isdir(p) and not os.listdir(p):
                os.rmdir(p)
        except OSError:
            pass

    # 4) 删 manifest + 记录
    mp = os.path.join(target_dir, store.MANIFEST_NAME)
    if os.path.exists(mp):
        os.remove(mp)
    store.remove_item(target_dir)

    log("卸载完成：删除 %d 个文件，还原 %d 个备份" % (removed, len(backups)))
    if modified:
        log("注意：以下文件在安装后被修改过（仍按记录删除）：%s" % ", ".join(modified[:6]))
    return {"removed": removed, "restored": len(backups), "modified": modified}


def verify(target_dir):
    """检查安装完整性，返回 (ok, 问题列表)。"""
    m = store.read_manifest(target_dir)
    if not m:
        return False, ["没有安装记录"]
    issues = []
    for item in m.get("files", []):
        rel = item.get("rel", "")
        try:
            p = _safe(target_dir, rel)
        except ValueError:
            continue
        if not os.path.exists(p):
            issues.append("缺失：%s" % rel)
        elif item.get("sha256") and sha256(p) != item["sha256"]:
            issues.append("已改动：%s" % rel)
    return (not issues), issues
