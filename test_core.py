"""无损安装/卸载的自动化验证（不需要 GUI）。"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import installer
import store

TMP = tempfile.mkdtemp(prefix="opti_test_")
store.APP_DIR = os.path.join(TMP, "_appdata")
store.STORE_PATH = os.path.join(store.APP_DIR, "installed.json")


def build_payload():
    p = os.path.join(TMP, "payload")
    os.makedirs(os.path.join(p, "OptiScaler", "plugins"))
    os.makedirs(os.path.join(p, "Licenses"))
    files = {
        "OptiScaler.dll": b"CORE_DLL_CONTENT" * 100,
        "OptiScaler.ini": b"[Menu]\nUseHQFont=true\n",
        "OptiScaler/plugins/MFGUnlocker.asi": b"ASI" * 50,
        "Licenses/lic.txt": b"license text",
    }
    for rel, data in files.items():
        full = os.path.join(p, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        open(full, "wb").write(data)
    return p


def build_game():
    g = os.path.join(TMP, "Game", "bin", "x64")
    os.makedirs(g)
    open(os.path.join(g, "game.exe"), "wb").write(b"GAME_EXE")
    open(os.path.join(g, "dxgi.dll"), "wb").write(b"ORIGINAL_DXGI")   # 冲突文件
    open(os.path.join(g, "readme.txt"), "wb").write(b"game own file")
    return g


def show(gdir):
    out = []
    for root, dirs, files in os.walk(gdir):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), gdir)
            out.append(rel)
    return sorted(out)


def main():
    payload = build_payload()
    game = build_game()
    print("游戏目录初始文件：", show(game))

    installer.install(payload, game, "dxgi.dll", "测试游戏", "game.exe",
                      progress=lambda *a: None, log=lambda m: print("   install:", m))
    after = show(game)
    print("安装后文件：", after)
    assert "dxgi.dll" in after
    assert os.path.getsize(os.path.join(game, "dxgi.dll")) == len(b"CORE_DLL_CONTENT" * 100), "本体未正确改名"
    assert os.path.exists(os.path.join(game, ".optiscaler_backup", "dxgi.dll")), "冲突文件未备份"
    assert open(os.path.join(game, ".optiscaler_backup", "dxgi.dll"), "rb").read() == b"ORIGINAL_DXGI"
    assert os.path.exists(os.path.join(game, store.MANIFEST_NAME))
    assert os.path.exists(os.path.join(game, "game.exe")), "游戏本体被动了"

    ok, issues = installer.verify(game)
    print("校验：", ok, issues)
    assert ok, issues

    # 模拟用户改了 ini
    open(os.path.join(game, "OptiScaler.ini"), "wb").write(b"[Menu]\nchanged\n")
    ok2, issues2 = installer.verify(game)
    print("改动后校验：", ok2, issues2)
    assert not ok2 and any("已改动" in i for i in issues2)

    installer.uninstall(game, progress=lambda *a: None, log=lambda m: print("   uninstall:", m))
    final = show(game)
    print("卸载后文件：", final)
    assert final == ["dxgi.dll", "game.exe", "readme.txt"], final
    assert open(os.path.join(game, "dxgi.dll"), "rb").read() == b"ORIGINAL_DXGI", "备份未还原"
    assert not os.path.exists(os.path.join(game, "OptiScaler")), "OptiScaler 目录未清理"
    assert not os.path.exists(os.path.join(game, "Licenses")), "Licenses 目录未清理"
    assert not os.path.exists(os.path.join(game, store.MANIFEST_NAME)), "manifest 未删"
    assert not os.path.exists(os.path.join(game, ".optiscaler_backup")), "备份目录未清"

    # 记录应已移除
    assert not store.load_store()["items"], "全局记录未清理"

    # 再次卸载应报错
    try:
        installer.uninstall(game, log=lambda m: None)
        raise AssertionError("重复卸载没有报错")
    except RuntimeError as e:
        print("重复卸载正确拒绝：", e)

    print("\nall assertions passed")
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    main()
