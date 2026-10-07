from pathlib import Path
import pandas as pd
p=Path(__file__).resolve().parent
f=pd.read_csv(p/'interfaces.csv')
forms=sorted(f.formation.unique())
out=pd.DataFrame({'formation':forms,'point_count':[int((f.formation==x).sum()) for x in forms]})
out['Kx_m_per_s']=''; out['Ky_m_per_s']=''; out['Kz_m_per_s']=''; out['specific_storage']=''; out['source']=''; out['status']='待补充'; out['notes']='不得用默认值替代试验或反演结果'
out.to_csv(p/'formation_hydraulic_properties_template.csv',index=False,encoding='utf-8-sig')
schema=pd.DataFrame([
 ['x','float','m','地质/渗流网格 X 坐标'],['y','float','m','地质/渗流网格 Y 坐标'],['z','float','m','高程或模型 Z 坐标'],['formation','string','-','GemPy 地层标签'],['lithology_id','int','-','模型岩性 ID'],['Kx_m_per_s','float','m/s','水平 X 向渗透系数'],['Ky_m_per_s','float','m/s','水平 Y 向渗透系数'],['Kz_m_per_s','float','m/s','竖向渗透系数'],['source','string','-','参数来源'],['uncertainty','float','-','参数不确定性或变异系数']
],columns=['field','dtype','unit','description'])
schema.to_csv(p/'seepage_attribute_schema.csv',index=False,encoding='utf-8-sig')
print(out.to_string(index=False)); print(schema.to_string(index=False))
