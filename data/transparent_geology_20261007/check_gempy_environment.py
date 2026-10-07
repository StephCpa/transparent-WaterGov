from pathlib import Path
import importlib.util, subprocess, sys
p=Path(__file__).resolve().parent
req=['gempy','gempy_viewer','gempy_engine','numpy','pandas','scipy','matplotlib']
found={m:bool(importlib.util.find_spec(m)) for m in req}
lines=['# GemPy 环境检查（2026-10-07）','',f'Python：`{sys.executable}`','']
for m,v in found.items(): lines.append(f'- `{m}`：{"可用" if v else "缺失"}')
if not found['gempy']:
 lines += ['', '结论：当前独立环境尚未具备运行 GemPy 模型的完整条件。安装过程受包下载/网络限制中断，未执行模型。']
(p/'gempy_environment_check.md').write_text('\n'.join(lines),encoding='utf-8')
print('\n'.join(lines))
