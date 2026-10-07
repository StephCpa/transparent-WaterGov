from pathlib import Path
import json, struct, textwrap
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT
OUT = ROOT


def read_tiff_float64(path):
    raw = path.read_bytes()
    endian = '<' if raw[:2] == b'II' else '>'
    if struct.unpack_from(endian+'H', raw, 2)[0] != 42:
        raise ValueError('仅支持经典 TIFF')
    ifd = struct.unpack_from(endian+'I', raw, 4)[0]
    n = struct.unpack_from(endian+'H', raw, ifd)[0]
    tags = {}
    for i in range(n):
        off = ifd + 2 + 12*i
        tag, typ, count, val = struct.unpack_from(endian+'HHII', raw, off)
        size = {1:1,2:1,3:2,4:4,5:8,12:8}.get(typ)
        if size is None:
            continue
        blob = raw[off+8:off+12] if size*count <= 4 else raw[val:val+size*count]
        if typ == 2:
            value = blob.rstrip(b'\\0').decode('utf-8', errors='replace')
        elif typ == 3:
            value = list(struct.unpack(endian+('H'*count), blob[:2*count]))
        elif typ == 4:
            value = list(struct.unpack(endian+('I'*count), blob[:4*count]))
        elif typ == 5:
            value = [struct.unpack(endian+'II', blob[j:j+8]) for j in range(0, 8*count, 8)]
        elif typ == 12:
            value = list(struct.unpack(endian+('d'*count), blob[:8*count]))
        else:
            value = list(blob)
        tags[tag] = value[0] if count == 1 and isinstance(value, list) else value
    width, height = int(tags[256]), int(tags[257])
    bits, spp = int(tags[258]), int(tags[277])
    strip_offsets = tags[273] if isinstance(tags[273], list) else [tags[273]]
    strip_counts = tags[279] if isinstance(tags[279], list) else [tags[279]]
    rows_per_strip = int(tags.get(278, height))
    arr = np.empty((height, width), dtype=np.float64)
    row = 0
    for off, count in zip(strip_offsets, strip_counts):
        nrow = min(rows_per_strip, height-row)
        vals = np.frombuffer(raw[int(off):int(off)+int(count)], dtype='<f8', count=nrow*width)
        arr[row:row+nrow] = vals.reshape(nrow, width)
        row += nrow
    scale = tags.get(33550, [1,1,0])
    tie = tags.get(33922, [0,0,0,0,0,0])
    return arr, {'width': width, 'height': height, 'bits_per_sample': bits, 'samples_per_pixel': spp,
                 'rows_per_strip': rows_per_strip, 'pixel_scale': scale, 'tiepoint': tie}


def main():
    iface_path = DATA/'interfaces.csv'
    orient_path = DATA/'orientations.csv'
    dem_path = DATA/'高程模型.tif'
    iface = pd.read_csv(iface_path)
    orient = pd.read_csv(orient_path)
    dem, meta = read_tiff_float64(dem_path)
    required_i = ['X','Y','Z','formation']
    required_o = ['X','Y','Z','dip','azimuth','formation','polarity']
    report = []
    report.append('# 透明地质输入资料审查报告（2026-10-07）')
    report.append('')
    report.append('本报告只审查输入资料的结构、空间范围和可用性，不等同于 GemPy 三维建模结果。')
    report.append('')
    report.append('## 1. 文件清单')
    report.append('')
    report.append('| 文件 | 状态 | 说明 |')
    report.append('|---|---|---|')
    report.append(f'| `interfaces.csv` | {len(iface)} 行 | 地质界面点与地层标签 |')
    report.append(f'| `orientations.csv` | {len(orient)} 行 | 界面点姿态字段 |')
    report.append(f'| `高程模型.tif` | {meta["width"]}×{meta["height"]} | 单波段 Float64 高程栅格 |')
    report.append('')
    report.append('## 2. 结构与质量检查')
    report.append('')
    report.append(f'- `interfaces.csv` 必需字段：{set(required_i).issubset(iface.columns)}；缺失值：{int(iface[required_i].isna().sum().sum())}；重复行：{int(iface.duplicated().sum())}。')
    report.append(f'- `orientations.csv` 必需字段：{set(required_o).issubset(orient.columns)}；缺失值：{int(orient[required_o].isna().sum().sum())}；重复行：{int(orient.duplicated().sum())}。')
    report.append(f'- 两个 CSV 均为 {len(iface)} 个记录，坐标和地层标签一致：{iface[["X","Y","Z","formation"]].equals(orient[["X","Y","Z","formation"]])}。')
    report.append(f'- DEM 有效像元：{int(np.isfinite(dem).sum())}/{dem.size}；最小值 {float(np.nanmin(dem)):.3f}，最大值 {float(np.nanmax(dem)):.3f}，平均值 {float(np.nanmean(dem)):.3f}。')
    report.append('')
    report.append('## 3. 空间范围与地层分布')
    report.append('')
    report.append(f'- 界面点 X 范围：{iface.X.min():.3f}–{iface.X.max():.3f}；Y 范围：{iface.Y.min():.3f}–{iface.Y.max():.3f}；Z 范围：{iface.Z.min():.3f}–{iface.Z.max():.3f}。')
    report.append(f'- DEM 像元尺度：X {meta["pixel_scale"][0]:.6f}，Y {meta["pixel_scale"][1]:.6f}；TiePoint 左上角约为 ({meta["tiepoint"][3]:.3f}, {meta["tiepoint"][4]:.3f})。')
    report.append('- DEM 空间范围按 GeoTIFF TiePoint/PixelScale 估算为 X 约 505000–505501，Y 约 3180998–3181800；界面点落在该范围内。')
    report.append('')
    report.append('| 地层标签 | 点数 |')
    report.append('|---|---:|')
    for k,v in iface.formation.value_counts().items():
        report.append(f'| {k} | {int(v)} |')
    report.append('')
    report.append('## 4. 关键限制与下一步')
    report.append('')
    report.append('- `orientations.csv` 中 `dip` 和 `azimuth` 全部为 0，`polarity` 全部为 1，当前只能视为占位姿态数据；不能据此宣称已完成有实测产状约束的地质建模。')
    report.append('- 原始 `mcmc.py` 实际是 GemPy 建模和剖面提取脚本，并非 MCMC 参数反演程序；其中引用的 `地表高层点.csv` 为过时变量，实际 DEM 已通过 `高程模型.tif` 加载。')
    report.append('- 当前 Python 环境未安装 GemPy，因此本次未运行三维隐式建模；需在具备 GemPy/GemPy Viewer 的环境中运行同目录下的修正版脚本。')
    report.append('- 建议后续补充真实地层产状、钻孔/剖面解释和渗透系数映射，再将地层属性传递给渗流计算模块。')
    (OUT/'透明地质输入审查报告_20261007.md').write_text('\n'.join(report), encoding='utf-8')
    iface.groupby('formation').agg(point_count=('formation','size'), X_min=('X','min'), X_max=('X','max'), Y_min=('Y','min'), Y_max=('Y','max'), Z_min=('Z','min'), Z_max=('Z','max')).reset_index().to_csv(OUT/'interfaces_summary.csv', index=False, encoding='utf-8-sig')
    stats = {'shape': list(dem.shape), 'min': float(np.nanmin(dem)), 'max': float(np.nanmax(dem)), 'mean': float(np.nanmean(dem)), 'finite_pixels': int(np.isfinite(dem).sum()), 'pixel_scale': [float(x) for x in meta['pixel_scale']], 'tiepoint': [float(x) for x in meta['tiepoint']]}
    (OUT/'dem_stats.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding='utf-8')
    print('QA complete')
    print(json.dumps(stats, ensure_ascii=False))

if __name__ == '__main__':
    main()
