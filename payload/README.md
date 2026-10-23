# payload 目录

这里放 OptiScaler 的运行文件，安装时会整体复制进游戏目录。

**本目录内容不入库**（`.gitignore` 已忽略，只保留这个说明）。原因是这些二进制属于第三方：

| 文件 | 版权方 | 说明 |
|---|---|---|
| `OptiScaler/**/*.dll` | OptiScaler 项目 / AMD / Intel / NVIDIA | AMD FidelityFX、XeSS 运行库 |
| `nvngx.dll_dlssnr.dll` | dag / OptiScaler DLSSNR 构建 | 神经渲染转发器 |
| `nvngx_dlssnr.dll` | NVIDIA | 神经渲染模型，约 158 MB，需自备 |
| `OptiScaler.dll` | OptiScaler（MIT） | 可由 `patch_ui.py` 生成汉化版 |
| `OptiScaler.ini` | 本仓库 | 用 `docs/OptiScaler.ini.zh` |
| `OptiScaler/plugins/MFGUnlocker.asi` | dashdogy（MIT） | 40 系多帧生成解锁器 |

## 需要放成什么样

```
payload/
├─ OptiScaler/
│  ├─ amd_fidelityfx_framegeneration_dx12.dll
│  ├─ amd_fidelityfx_loader_dx12.dll
│  ├─ amd_fidelityfx_upscaler_dx12.dll
│  ├─ amd_fidelityfx_vk.dll
│  ├─ libxell.dll
│  ├─ libxess.dll
│  ├─ libxess_dx11.dll
│  ├─ libxess_fg.dll
│  ├─ D3D12_OptiScaler/D3D12Core.dll
│  └─ plugins/MFGUnlocker.asi
├─ Licenses/
├─ OptiScaler.dll
├─ OptiScaler.ini
├─ nvngx.dll_dlssnr.dll
└─ nvngx_dlssnr.dll
```

完整步骤见仓库根目录的 `README.md`。
