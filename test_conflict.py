"""装前冲突检测：识别目录里已有的第三方注入器。"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import installer

TMP = tempfile.mkdtemp(prefix="opti_conflict_")


def main():
    # 1) 干净目录
    clean = os.path.join(TMP, "clean")
    os.makedirs(clean)
    assert installer.detect_conflicts(clean, "dxgi.dll") == [], "空目录不该报冲突"

    # 2) 大体积无版本信息 -> 判定为注入器，且与目标同名 -> danger
    risky = os.path.join(TMP, "risky")
    os.makedirs(risky)
    with open(os.path.join(risky, "dxgi.dll"), "wb") as f:
        f.write(b"\0" * (3 * 1024 * 1024))
    c = installer.detect_conflicts(risky, "dxgi.dll")
    assert len(c) == 1 and c[0]["level"] == "danger" and c[0]["replaces_target"], c
    print("  dxgi.dll -> danger（会被覆盖）")

    # 3) 不同名的大文件 -> warn（共存风险）
    with open(os.path.join(risky, "version.dll"), "wb") as f:
        f.write(b"\0" * (3 * 1024 * 1024))
    c = installer.detect_conflicts(risky, "dxgi.dll")
    names = {x["name"]: x["level"] for x in c}
    assert names.get("dxgi.dll") == "danger" and names.get("version.dll") == "warn", names
    print("  不同名注入器 -> warn（共存风险）")

    # 4) Microsoft 系统 DLL 不该被误报
    sys_dll = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "dbghelp.dll")
    if os.path.isfile(sys_dll):
        safe = os.path.join(TMP, "safe")
        os.makedirs(safe)
        shutil.copy2(sys_dll, os.path.join(safe, "dbghelp.dll"))
        c = installer.detect_conflicts(safe, "dxgi.dll")
        assert not any(x["name"] == "dbghelp.dll" for x in c), "系统 DLL 被误判"
        print("  系统 dbghelp.dll -> 正确跳过")

    # 5) ReShade 痕迹
    open(os.path.join(safe, "ReShade.ini"), "w").close()
    c = installer.detect_conflicts(safe, "dxgi.dll")
    assert any("ReShade" in x["name"] for x in c), c
    print("  ReShade 配置 -> warn")

    print("\nconflict detection passed")
    shutil.rmtree(TMP, ignore_errors=True)


if __name__ == "__main__":
    main()
