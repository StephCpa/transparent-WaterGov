import gempy as gp
import gempy_viewer as gpv
import gempy_engine as gpe
import  numpy as np
import os
import matplotlib.pyplot as plt
from gempy.core.data.gempy_engine_config import GemPyEngineConfig
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
surface_points_file = "interfaces.csv"
orientations_file = "orientations.csv"
topography_file = "地表高层点.csv"
topography_path = os.path.join(script_dir, topography_file)
surface_points_path = os.path.join(script_dir, surface_points_file)
orientations_path = os.path.join(script_dir, orientations_file)
path_dem = os.path.join(script_dir, "高程模型.tif")
geo_model: gp.data.GeoModel = gp.create_geomodel(
    project_name='Single_layer_topo',
    extent=[505000, 505500, 3181000, 3181800, 10, 42],
    resolution=[50, 50, 50],
    refinement=4,
    importer_helper=gp.data.ImporterHelper(
        path_to_orientations=orientations_path,
        path_to_surface_points=surface_points_path,
    )
)
gp.map_stack_to_surfaces(
    gempy_model=geo_model,
    mapping_object={
        "EarlyGranite_Series": ('FT','MCN1','FS','MCN2','FS2','GR'),
        "BIF_Series": ('Basics',)
    }
)
gp.set_topography_from_file(
    grid=geo_model.grid,
    filepath=path_dem
)
gp.set_section_grid(
    grid=geo_model.grid,
    section_dict={
        'section1': ([505000, 3181450], [505500, 3181450], [50,50])
    }  # p1,p2,resolution
)
gp.compute_model(geo_model)
gpv.plot_3d(geo_model,section_names=['section1'],show_data=False,ve=3,show_topography=True,show_boundaries=True)
gpv.plot_2d(geo_model,section_names=['section1'],show_data=False,ve=3,show_topography=True,show_boundaries=True)
plt.show()

# ========== 提取剖面数据用于渗流计算 ==========
import pandas as pd

def extract_section_to_dataframe(geo_model, section_name='section1'):
    """
    从 GemPy 2024 模型中提取指定剖面的网格数据
    
    参数:
        geo_model: GemPy 地质模型对象
        section_name: 剖面名称
        
    返回:
        DataFrame: 包含 x, y, z, lithology_id, lithology_name 列
    """
    # 1. 获取剖面网格坐标
    section_grid = geo_model.grid.sections
    
    # GemPy 2024: section_grid.values 是 (n_points, 3) 的数组，包含所有剖面的点
    section_coords = section_grid.values
    
    # 确保是 2D 数组
    if section_coords.ndim == 1:
        # 如果是1D数组，说明数据存储方式不同，尝试reshape
        n_points = len(section_coords) // 3
        section_coords = section_coords.reshape(n_points, 3)
    
    # 2. 获取岩性数据
    # GemPy 2024: 检查 solutions 中可用的数组
    print(f"\n[调试] solutions.raw_arrays 可用属性:")
    for attr in dir(geo_model.solutions.raw_arrays):
        if not attr.startswith('_'):
            try:
                val = getattr(geo_model.solutions.raw_arrays, attr)
                if hasattr(val, 'shape'):
                    print(f"  - {attr}: shape={val.shape}")
                elif hasattr(val, '__len__'):
                    print(f"  - {attr}: len={len(val)}")
            except:
                pass
    
    # 方法1: 尝试从 raw_arrays 中找剖面数据
    section_lith = None
    
    # 检查是否有专门的 sections 数组
    if hasattr(geo_model.solutions.raw_arrays, 'sections'):
        section_lith = geo_model.solutions.raw_arrays.sections
        print(f"\n[调试] 找到 sections 数组，shape: {section_lith.shape if hasattr(section_lith, 'shape') else len(section_lith)}")
    
    # 方法2: 使用插值从常规网格获取剖面岩性
    if section_lith is None or len(section_lith) == 0:
        print(f"\n[调试] 使用插值方法获取剖面岩性...")
        from scipy.interpolate import NearestNDInterpolator
        
        # 获取常规网格的坐标和岩性
        regular_coords = geo_model.grid.regular_grid.values
        lith_block = geo_model.solutions.raw_arrays.lith_block
        
        # 创建插值器（最近邻插值）
        interpolator = NearestNDInterpolator(regular_coords, lith_block)
        
        # 对剖面点进行插值
        section_lith = interpolator(section_coords)
        print(f"  - 插值后剖面岩性唯一值: {np.unique(section_lith)}")
    
    # 3. 从 structural_elements 动态构建岩性名称映射（与 lith_block ID 一致）
    lith_mapping = {0: 'Unknown'}
    
    try:
        # 步骤1：提取构造框架的单元列表（对应 lith_block 的 1-N）
        elements = geo_model.structural_frame.structural_elements
        
        # 步骤2：构建「局部ID → 名称」的映射
        # lith_block 的局部ID是 1-based 索引（从1开始），与 elements 顺序一致
        for local_id, elem in enumerate(elements, start=1):
            # 获取单元的全局ID（对应 element_id_name_map 的键）
            global_id = elem.id if hasattr(elem, 'id') else elem.element_id
            # 从 element_id_name_map 匹配名称
            elem_name = geo_model.structural_frame.element_id_name_map.get(
                int(global_id),  # 统一数据类型（避免int32/int64冲突）
                f"Unknown_{local_id}"
            )
            lith_mapping[local_id] = elem_name
        
        # 步骤3：验证映射（关联 lith_block 的 ID）
        lith_block = geo_model.solutions.raw_arrays.lith_block
        unique_lith_ids = np.unique(lith_block)
        missing_ids = [int(lid) for lid in unique_lith_ids if int(lid) not in lith_mapping]
        if missing_ids:
            raise RuntimeError(f"lith_block 中存在未映射的局部ID: {sorted(missing_ids)}")

        print("  - lith_block 局部ID ↔ 地质单元名称:")
        for lid in sorted(unique_lith_ids):
            lid_int = int(lid)
            print(f"      {lid_int} -> {lith_mapping[lid_int]}")
    except Exception as e:
        raise RuntimeError("无法从 structural_elements 获取岩性映射，已停止以避免生成错误的 section1_data.csv") from e
    
    # 4. 组装 DataFrame
    df = pd.DataFrame({
        'x': section_coords[:, 0],
        'y': section_coords[:, 1],
        'z': section_coords[:, 2],
        'lithology_id': section_lith.astype(int)
    })
    
    # 添加岩性名称列
    df['lithology_name'] = df['lithology_id'].map(lith_mapping).fillna('Unknown')
    
    return df

# 提取 section1 的数据
try:
    section_df = extract_section_to_dataframe(geo_model, 'section1')
    print("\n========== 剖面数据提取成功 ==========")
    print(f"数据维度: {section_df.shape}")
    print(f"\n前 10 行数据:")
    print(section_df.head(10))
    print(f"\n岩性统计:")
    print(section_df['lithology_name'].value_counts())
    
    # 保存到 CSV 文件（可选）
    output_file = "section1_data.csv"
    section_df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n数据已保存到: {output_file}")
    
    # ========== 绘制剖面图 ==========
    print("\n正在绘制剖面图...")
    
    # 定义岩性颜色映射（与GemPy一致）
    color_by_name = {
        'FT': '#8B4513',
        'MCN1': '#4ECDC4',
        'FS': '#FFE66D',
        'MCN2': '#95E1D3',
        'FS2': '#F38181',
        'GR': '#AA96DA',
        'Basics': '#5F9EA0',
        'Unknown': '#CCCCCC'
    }
    id_name_pairs = section_df[['lithology_id', 'lithology_name']].drop_duplicates().values
    lith_to_color = {int(lid): color_by_name.get(str(name), '#CCCCCC') for lid, name in id_name_pairs}
    lith_to_color[0] = '#FFFFFF'

    # 获取剖面分辨率（从section_dict中定义的是 [nx, nz]）
    nx, nz = 50, 50  # 你的剖面定义是 [50, 50]
    
    # Reshape 数据为 2D 网格 (nz行 × nx列)
    # 数据是按列存储的：前nz个点是第一列(x=x0, z变化)
    x_grid = section_df['x'].values.reshape(nx, nz).T  # 转置使其变为 (nz, nx)
    z_grid = section_df['z'].values.reshape(nx, nz).T
    lith_grid = section_df['lithology_id'].values.reshape(nx, nz).T
    
    # 创建颜色数组
    color_array = np.zeros((nz, nx, 3))
    for i in range(nz):
        for j in range(nx):
            lith_id = int(lith_grid[i, j])
            color_hex = lith_to_color.get(lith_id, '#FFFFFF')
            # 转换 hex 到 RGB
            color_array[i, j] = [int(color_hex[k:k+2], 16)/255 for k in (1, 3, 5)]
    
    # 创建图形
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    # 图1: 使用 imshow 显示网格（类似GemPy）
    im = ax1.imshow(color_array, extent=[x_grid.min(), x_grid.max(), z_grid.min(), z_grid.max()],
                    aspect='auto', origin='lower', interpolation='nearest')
    ax1.set_xlabel('X 坐标 (m)', fontsize=12)
    ax1.set_ylabel('Z 高程 (m)', fontsize=12)
    ax1.set_title(f'地质剖面图 (Y={section_df["y"].iloc[0]:.1f}m)', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3, color='white', linewidth=0.5)
    
    # 添加图例
    from matplotlib.patches import Patch
    legend_elements = []
    for lith_name in section_df['lithology_name'].unique():
        lith_id = section_df[section_df['lithology_name']==lith_name]['lithology_id'].iloc[0]
        color_hex = lith_to_color.get(lith_id, '#FFFFFF')
        legend_elements.append(Patch(facecolor=color_hex, label=lith_name))
    ax1.legend(handles=legend_elements, loc='upper right', framealpha=0.9)
    
    # 图2: 散点图（用于验证数据）
    for lith_name in section_df['lithology_name'].unique():
        lith_data = section_df[section_df['lithology_name'] == lith_name]
        lith_id = lith_data['lithology_id'].iloc[0]
        color_hex = lith_to_color.get(lith_id, '#FFFFFF')
        ax2.scatter(lith_data['x'], lith_data['z'], c=color_hex, 
                   label=lith_name, s=5, alpha=0.6)
    
    ax2.set_xlabel('X 坐标 (m)', fontsize=12)
    ax2.set_ylabel('Z 高程 (m)', fontsize=12)
    ax2.set_title('散点图验证', fontsize=12)
    ax2.legend(loc='upper right', framealpha=0.9, markerscale=2)
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # 保存图片
    section_output = "section1_comparison.png"
    plt.savefig(section_output, dpi=300, bbox_inches='tight')
    print(f"剖面图已保存到: {section_output}")
    
    plt.show()
    
except Exception as e:
    print(f"\n提取剖面数据时出错: {e}")
    print("正在使用备用方案...")
    
    # 备用方案：直接访问网格和解
    import traceback
    traceback.print_exc()
