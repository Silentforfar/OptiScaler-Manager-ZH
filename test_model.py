"""验证：玩家自备的 nvngx_dlssnr.dll 不会被覆盖，也不会被卸载删掉。"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import installer
import store

TMP = tempfile.mkdtemp(prefix="opti_model_")
store.APP_DIR = os.path.join(TMP, "_appdata")
store.STORE_PATH = os.path.join(store.APP_DIR, "installed.json")

MODEL = b"FAKE_MODEL_CONTENT" * 1000


def main():
    payload = os.path.join(TMP, "payload")
    os.makedirs(payload)
    open(os.path.join(payload, "OptiScaler.dll"), "wb").write(b"CORE" * 100)
    open(os.path.join(payload, "OptiScaler.ini"), "wb").write(b"[Menu]\n")
    open(os.path.join(payload, "nvngx_dlssnr.dll"), "wb").write(MODEL)

    game = os.path.join(TMP, "game")
    os.makedirs(game)
    open(os.path.join(game, "game.exe"), "wb").write(b"GAME")
    # 玩家自己的模型文件（同尺寸）
    mine = os.path.join(game, "nvngx_dlssnr.dll")
    open(mine, "wb").write(MODEL)
    before_mtime = os.path.getmtime(mine)

    installer.install(payload, game, "dxgi.dll", "测试", "game.exe",
                      progress=lambda *a: None, log=lambda m: print("  ", m))

    m = store.read_manifest(game)
    print("manifest.skipped =", m.get("skipped"))
    assert "nvngx_dlssnr.dll" in m.get("skipped", []), "应记录为跳过"
    assert not any(f["rel"] == "nvngx_dlssnr.dll" for f in m["files"]), "不应计入已装文件"
    assert os.path.getmtime(mine) == before_mtime, "玩家文件被改动了"
    assert open(mine, "rb").read() == MODEL, "玩家文件内容变了"

    installer.uninstall(game, progress=lambda *a: None, log=lambda m: print("  ", m))
    assert os.path.exists(mine), "卸载把玩家自己的模型删掉了！"
    assert open(mine, "rb").read() == MODEL
    assert not os.path.exists(os.path.join(game, "dxgi.dll")), "本体没删"
    print("\nmodel-file protection passed")
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    main()
