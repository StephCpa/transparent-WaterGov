# 透明地质输入资料（2026-10-07）

本目录保存本批次原始输入、质量审查、点位核查和 GemPy 前置检查结果。

## 主要输入

- `interfaces.csv`：67 条地质界面记录；
- `orientations.csv`：67 条界面姿态记录；
- `高程模型.tif`：500×500 单波段 Float64 DEM；
- `mcmc_original.py`：收到的原始脚本；
- `gempy_build_and_section_fixed.py`：路径修正版脚本。

## 已完成检查

- `透明地质输入审查报告_20261007.md`：文件、字段、空间范围和 DEM 统计；
- `location_and_elevation_audit.png`：13 个点位、原脚本 section1 位置及界面高程检查；
- `coincident_interfaces.csv`：相同 X/Y/Z 的重合记录；
- `location_interface_elevations.csv`：按 13 个点位展开的界面高程表；
- `gempy_preflight_20261007.md`：GemPy 运行前人工确认事项；
- `gempy_environment_check.md`：当前独立环境依赖检查。

## 当前结论

现有资料可以作为透明地质建模的输入，但正式建模前应确认：

1. `P01` 位置 `GR` 与 `Basics` 重合记录的含义；
2. `dip`、`azimuth` 全为 0 是否代表水平层假设；
3. `section1` 横剖面没有直接观测点，结果将依赖插值。

当前独立虚拟环境尚未完成 GemPy 依赖安装，尚未生成三维模型或剖面 CSV。任何 `section1_data.csv`、渗流网格或模型精度结果都不能在此之前作为实测计算结果使用。

## 面向渗流计算的接口模板

- `formation_hydraulic_properties_template.csv`：按地层标签预留 Kx、Ky、Kz 和储水参数，不填入未经验证的默认值；
- `seepage_attribute_schema.csv`：GemPy 岩性结果向渗流网格传递时的字段约定；
- `section1_nearest_observations.csv`：section1 附近原始观测点，不是插值模型结果。
