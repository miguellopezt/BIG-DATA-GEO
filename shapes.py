import geopandas
import os
import pandas
from shapely.geometry import LineString
from zipfile import ZipFile


dirs = os.listdir('./migraciones_historico')
for dir in dirs:
    if dir.endswith('.zip'):
        with ZipFile('./migraciones_historico/'+ dir, 'r') as zip:
            zip.extractall(os.path.join('./migraciones_historico/',dir.split('.')[0]))

dfs_coropletico = []
dfs_flujo = []
filas= {'FIP':[],
        'Nombre':[]}

with open('fips.txt','r') as f:
    for fila in f.readlines()[72:]:
        if fila.split()[0].endswith('000') == False:
            filas['FIP'].append(fila.split()[0])
            filas['Nombre'].append(fila.split(maxsplit=1)[1].strip())

filas = pandas.DataFrame(filas)

path = os.getcwd()
for dir in dirs:
    if dir.endswith('.zip'):
        continue
    dir_path = os.path.join(path, 'migraciones_historico', dir)

    print(dir)
    print(dir_path)
    anio_inicio = '20' + dir[0:2]
    anio_fin = '20' + dir[2:4]
    fecha_str = f"{anio_inicio}-{anio_fin}"

    for archivo in os.listdir(dir_path):
        if archivo.endswith(('.xlsx', '.xls')) and 'inmigall' not in archivo:
            file_path = os.path.join(dir_path, archivo)
            df_in = pandas.read_excel(file_path, sheet_name="County Inflow",skiprows = 4)
            df_out = pandas.read_excel(file_path, sheet_name="County Outflow", skiprows = 4)
            columnas = ['Estado Origen','Condado Origen','Estado Destino','Condado Destino', 'Acrónimo State','Condado Destino Nombre', 'Returns', 'Individuals', 'AGI']
            df_in.columns = columnas
            df_out.columns = columnas
            
            cols_num = ['Returns', 'Individuals', 'AGI']
            for col in cols_num:
                df_in[col] = pandas.to_numeric(df_in[col], errors='coerce').fillna(0)
                df_out[col] = pandas.to_numeric(df_out[col], errors='coerce').fillna(0)
                
            df_in = df_in.groupby(columnas[:4], as_index=False)[cols_num].sum()
            df_out = df_out.groupby(columnas[:4], as_index=False)[cols_num].sum()
            df = df_out.merge(df_in, on= columnas[:4], how="outer", suffixes=("_out", "_in"))
            for col in [col for col in df.columns if col in ['Estado Origen','Condado Origen','Estado Destino','Condado Destino']]:
                
                df[col] = pandas.to_numeric(df[col], errors='coerce').fillna(0)
                
                if 'Estado' in col:
                    df[col] = df[col].astype(int).astype(str).str.zfill(2)
                elif 'Condado' in col:
                    df[col] = df[col].astype(int).astype(str).str.zfill(3)

            df['FIP Origen'] = df['Estado Origen'].str.strip() + df['Condado Origen'].str.strip()
            df['FIP Destino'] = df['Estado Destino'].str.strip() + df['Condado Destino'].str.strip()
            
            df = df.merge(filas, left_on = 'FIP Destino',right_on = 'FIP', how = 'inner').rename(columns = {'Nombre':'Nombre Destino'})
            df = df.merge(filas, left_on = 'FIP Origen', right_on = 'FIP', how = 'inner' ).rename(columns = {'Nombre':'Nombre Origen'})
            columnas = ['FIP Origen', 'FIP Destino','Nombre Origen', 'Nombre Destino', 'Returns_in', 'Individuals_in', 'AGI_in', 'Returns_out', 'Individuals_out', 'AGI_out']
            df = df[columnas]
            strings = ['FIP Origen', 'FIP Destino','Nombre Origen', 'Nombre Destino']
            numeric = [col for col in df.columns if col not in strings]

            for col in numeric:
                df[col] = pandas.to_numeric(df[col],errors = 'coerce').fillna(0)
            for col in strings:
                df[col] = df[col].astype(str)

            df['Saldo'] = df['Individuals_in']- df['Individuals_out']
            df['Retornos'] = df['Returns_in'] - df['Returns_out']
            df['AGI'] = df['AGI_in'] - df['AGI_out']
            df['Fecha'] = fecha_str

            df_coropletico = df.groupby(['FIP Origen','Nombre Origen'], as_index=False)[['Saldo','Retornos','AGI']].sum().rename(columns = {'FIP Origen': 'FIP','Nombre Origen':'Nombre'})
            df_coropletico['Fecha'] = fecha_str
            dfs_flujo.append(df)
        
            dfs_coropletico.append(df_coropletico)

df_flujo = pandas.concat(dfs_flujo)
df_coropletico = pandas.concat(dfs_coropletico)

shape = geopandas.read_file('tl_2022_us_county/tl_2022_us_county.shp')[['FIP','geometry']].to_crs('ESRI:102003')

df_coropletico = shape.merge(df_coropletico, how = 'inner', on = 'FIP')
df_coropletico = geopandas.GeoDataFrame(df_coropletico, geometry='geometry', crs = shape.crs)

df_flujo = shape.merge(df_flujo, 
            right_on='FIP Origen', left_on='FIP', 
            how='inner').rename(columns={'geometry':'geometry_origen'})

df_flujo = shape.merge(df_flujo, 
            right_on='FIP Destino', left_on='FIP', 
            how='inner').rename(columns={'geometry':'geometry_destino'})

df_flujo = df_flujo[(df_flujo['AGI'] > 0) & (df_flujo['Saldo'] > 0) & (df_flujo['Retornos'] > 0)]

df_flujo['geometry'] = df_flujo.apply(lambda x: LineString([x['geometry_origen'].centroid, x['geometry_destino'].centroid]),axis = 1)
df_flujo = geopandas.GeoDataFrame(df_flujo, geometry='geometry', crs = shape.crs)

df_flujo = df_flujo[['FIP Origen', 'FIP Destino', 'Nombre Origen', 'Nombre Destino', 'Saldo', 'AGI','Retornos', 'Fecha', 'geometry']]

df_coropletico.to_file('capa_coropletica/capa_coropletica.shp')
df_flujo.to_parquet('entrenamiento/capa_flujo/capa_flujo.parquet')
