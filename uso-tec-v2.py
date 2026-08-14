import streamlit as st
import pandas as pd
import numpy as np
import datetime

# Configuración del Dashboard
st.set_page_config(page_title="Carga de Información - Conci", layout="wide")

st.title("📂 Tablero de Carga de Información")
st.markdown("Sube los archivos para procesar, limpiar y consolidar los datos de máquinas, sucursales, monitores y licencias.")

# --- SIDEBAR: Carga de archivos ---
st.sidebar.header("📁 Carga de Archivos")
uploaded_file_analizador = st.sidebar.file_uploader("1. Archivo Analizador de Máquina", type=["xlsx"])
uploaded_file_orgs = st.sidebar.file_uploader("2. Base Orgs ID y Sucursales (CSV)", type=["csv"])
uploaded_file_maquinas = st.sidebar.file_uploader("3. Archivo de Máquinas (Emparejamientos)", type=["xlsx"])
uploaded_file_activaciones = st.sidebar.file_uploader("4. Control de Activaciones Gen 4 (CSV)", type=["csv"])
uploaded_file_gen5 = st.sidebar.file_uploader("5. Licencias Gen 5 (Excel)", type=["xlsx"])

# --- FUNCIONES AUXILIARES ---
spanish_months = {
    'sept': 'Sep', 'septiembre': 'Sep',
    'ene': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'abr': 'Apr',
    'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'ago': 'Aug',
    'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dic': 'Dec'
}

def parse_spanish_date(date_str):
    """Convierte cadenas de fecha en español (ej: '21 jun 2026') a pd.Timestamp."""
    if pd.isna(date_str) or str(date_str).strip() in ['---', '-', '']:
        return pd.NaT
    s = str(date_str).strip().lower()
    for es in sorted(spanish_months.keys(), key=len, reverse=True):
        en = spanish_months[es]
        s = s.replace(es, en)
    return pd.to_datetime(s, format='%d %b %Y', errors='coerce')

def calcular_duracion_str(inicio_dt, fin_dt):
    """Calcula la duración amigable entre dos fechas en formato de meses o años."""
    if pd.isna(inicio_dt) or pd.isna(fin_dt):
        return "-"
    days = (fin_dt - inicio_dt).days
    months = round(days / 30.4375)
    if months >= 12:
        years = months // 12
        rem_months = months % 12
        if rem_months == 0:
            return f"{years} año" if years == 1 else f"{years} años"
        else:
            return f"{months} Meses"
    else:
        return f"{months} Meses"

def procesar_analizador(df):
    """
    Limpia el dataframe de Analizador: elimina columnas 'Unidad' y convierte % a numérico.
    """
    cols_to_drop = [c for c in df.columns if 'unidad' in str(c).lower()]
    df = df.drop(columns=cols_to_drop)
    
    cols_porcentuales = [c for c in df.columns if 'activo' in str(c).lower() or 'activado' in str(c).lower()]
    for col in cols_porcentuales:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', ''), errors='coerce')
        
    return df

def calcular_estado_licencia(row):
    """
    Determina el estado de la licencia: 'No tiene', 'Vencida' o 'Vigente'.
    """
    licencia = row.get('Licencia')
    if pd.isna(licencia) or str(licencia).strip() in ['', '-', 'nan']:
        return "No tiene"
    
    fin_str = str(row.get('Fin Licencia', '')).strip()
    if pd.isna(fin_str) or fin_str in ['', '-', 'nan']:
        return "Vigente"
    
    fin_dt = pd.to_datetime(fin_str, format='%d/%m/%Y', errors='coerce')
    if pd.isna(fin_dt):
        return "Vigente"
    
    today = pd.Timestamp.now().normalize()
    if fin_dt < today:
        return "Vencida"
    else:
        return "Vigente"

# --- LÓGICA PRINCIPAL ---
if uploaded_file_analizador is not None:
    try:
        # 1. LEER Y PROCESAR ARCHIVO ANALIZADOR
        df_original = pd.read_excel(uploaded_file_analizador)
        df_final = procesar_analizador(df_original.copy())
        
        # 2. CRUCE CON BASE DE ORGANIZACIONES Y SUCURSALES
        if uploaded_file_orgs is not None:
            df_orgs = pd.read_csv(uploaded_file_orgs)
            
            # Deduplicar por Org ID y seleccionar columna de sucursal
            df_orgs_unique = df_orgs.drop_duplicates(subset=['Org ID'])[['Org ID', 'SUC?']].rename(columns={'SUC?': 'Sucursal'})
            
            # Asegurar tipo de datos numérico para el cruce
            df_final['Identificador de organización'] = pd.to_numeric(df_final['Identificador de organización'], errors='coerce')
            df_orgs_unique['Org ID'] = pd.to_numeric(df_orgs_unique['Org ID'], errors='coerce')
            
            # Merge por Identificador de organización
            df_final = pd.merge(
                df_final,
                df_orgs_unique,
                left_on='Identificador de organización',
                right_on='Org ID',
                how='left'
            )
            
            if 'Org ID' in df_final.columns:
                df_final = df_final.drop(columns=['Org ID'])
        else:
            st.sidebar.warning("⚠️ Falta cargar la Base de Orgs ID (Sucursales).")

        # 3. CRUCE CON SEGUNDO ARCHIVO (EMPAREJAMIENTOS)
        if uploaded_file_maquinas is not None:
            df_maquinas = pd.read_excel(uploaded_file_maquinas, sheet_name='Emparejamientos')
            
            # Filtrar solo 'monitor' en columna Tipo
            df_monitores = df_maquinas[df_maquinas['Tipo'].astype(str).str.lower() == 'monitor'].copy()
            
            # Seleccionar y renombrar columnas
            df_monitores = df_monitores[[
                'Número de serie de emparejamiento', 
                'Número de serie',       # Nro de serie del monitor
                'Modelo',                # Modelo Monitor
                'Versión de software'    # Versión Software Monitor
            ]].rename(columns={
                'Número de serie': 'Hardware Monitor',
                'Modelo': 'Modelo Monitor',
                'Versión de software': 'Versión Software Monitor'
            })
            
            # Cruce 1: Serie de máquina vs Serie de emparejamiento
            df_final = pd.merge(
                df_final, 
                df_monitores, 
                left_on='Número de serie de la máquina', 
                right_on='Número de serie de emparejamiento', 
                how='left'
            )
            
            if 'Número de serie de emparejamiento' in df_final.columns:
                df_final = df_final.drop(columns=['Número de serie de emparejamiento'])
        else:
            st.sidebar.warning("⚠️ Falta cargar el archivo de máquinas (Emparejamientos).")

        # 4. CRUCE CON TERCER ARCHIVO (LICENCIAS / ACTIVACIONES GEN 4)
        if uploaded_file_activaciones is not None and 'Hardware Monitor' in df_final.columns:
            df_activaciones = pd.read_csv(uploaded_file_activaciones)
            
            # Filtrar solo "Monitor Gen 4"
            df_gen4 = df_activaciones[
                df_activaciones['COMPONENTE'].astype(str).str.strip().str.lower() == 'monitor gen 4'
            ].copy()
            
            # Tomar la última activación registrada por monitor
            df_gen4['Fecha_Inicio_DT'] = pd.to_datetime(df_gen4['Fecha de inicio'], format='%d/%m/%Y', errors='coerce')
            df_gen4 = df_gen4.sort_values('Fecha_Inicio_DT', ascending=True)
            df_gen4_unique = df_gen4.drop_duplicates(subset=['Tornillería'], keep='last')
            
            # Seleccionar y renombrar columnas
            df_licencias_gen4 = df_gen4_unique[[
                'Tornillería',
                'Producto',
                'Duración',
                'Fecha de inicio',
                'Fecha final'
            ]].rename(columns={
                'Producto': 'Licencia',
                'Duración': 'Duración Licencia',
                'Fecha de inicio': 'Comienzo Licencia',
                'Fecha final': 'Fin Licencia'
            })
            
            # Cruce 2: Hardware Monitor vs Tornillería
            df_final = pd.merge(
                df_final,
                df_licencias_gen4,
                left_on='Hardware Monitor',
                right_on='Tornillería',
                how='left'
            )
            
            if 'Tornillería' in df_final.columns:
                df_final = df_final.drop(columns=['Tornillería'])

        elif uploaded_file_activaciones is None:
            st.sidebar.warning("⚠️ Falta cargar el archivo CSV de activaciones Gen 4.")

        # Asegurar existencia de columnas de licencias
        for col in ['Licencia', 'Duración Licencia', 'Comienzo Licencia', 'Fin Licencia']:
            if col not in df_final.columns:
                df_final[col] = np.nan

        # 5. CRUCE CON CUARTO ARCHIVO (LICENCIAS GEN 5)
        if uploaded_file_gen5 is not None:
            df_gen5 = pd.read_excel(uploaded_file_gen5)
            
            # Parsear fechas
            df_gen5['Inicio_DT'] = df_gen5['Fecha de inicio'].apply(parse_spanish_date)
            df_gen5['Fin_DT'] = df_gen5['Fecha de terminación'].apply(parse_spanish_date)
            df_gen5['Duración_Calc'] = df_gen5.apply(lambda r: calcular_duracion_str(r['Inicio_DT'], r['Fin_DT']), axis=1)
            
            df_gen5['Comienzo_Str'] = df_gen5['Inicio_DT'].dt.strftime('%d/%m/%Y').fillna('-')
            df_gen5['Fin_Str'] = df_gen5['Fin_DT'].dt.strftime('%d/%m/%Y').fillna('-')
            
            # Tomar la activación más reciente por número de serie
            df_gen5['N.° de serie'] = df_gen5['N.° de serie'].astype(str).str.strip()
            df_gen5_sorted = df_gen5.sort_values('Inicio_DT', ascending=True)
            df_gen5_unique = df_gen5_sorted.drop_duplicates(subset=['N.° de serie'], keep='last')
            
            # Mapas de búsqueda por N.° de serie
            map_licencia = df_gen5_unique.set_index('N.° de serie')['Nombre de licencia'].to_dict()
            map_duracion = df_gen5_unique.set_index('N.° de serie')['Duración_Calc'].to_dict()
            map_comienzo = df_gen5_unique.set_index('N.° de serie')['Comienzo_Str'].to_dict()
            map_fin = df_gen5_unique.set_index('N.° de serie')['Fin_Str'].to_dict()
            
            def buscar_gen5(row, field_map):
                s_maq = str(row.get('Número de serie de la máquina', '')).strip()
                s_mon = str(row.get('Hardware Monitor', '')).strip()
                if s_maq in field_map and s_maq not in ['', 'nan', 'None']:
                    return field_map[s_maq]
                elif s_mon in field_map and s_mon not in ['', 'nan', 'None']:
                    return field_map[s_mon]
                return np.nan

            # Asignar los datos Gen 5 a los registros sin licencia previa
            for col, field_map in [
                ('Licencia', map_licencia),
                ('Duración Licencia', map_duracion),
                ('Comienzo Licencia', map_comienzo),
                ('Fin Licencia', map_fin)
            ]:
                g5_vals = df_final.apply(lambda r: buscar_gen5(r, field_map), axis=1)
                df_final[col] = df_final[col].fillna(g5_vals)

        # 6. CÁLCULO DEL ESTADO FINAL DE LA LICENCIA
        df_final['Estado Licencia'] = df_final.apply(calcular_estado_licencia, axis=1)

        # --- UI: RESULTADOS ---
        st.success("✅ Datos consolidados con éxito.")
        
        # Métricas resumidas
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Máquinas Totales", len(df_final))
        col2.metric("Columnas Resultantes", len(df_final.columns))
        
        cant_vigentes = (df_final['Estado Licencia'] == 'Vigente').sum()
        cant_vencidas = (df_final['Estado Licencia'] == 'Vencida').sum()
        cant_no_tiene = (df_final['Estado Licencia'] == 'No tiene').sum()
        
        col3.metric("🟢 Vigentes", cant_vigentes)
        col4.metric("🔴 Vencidas", cant_vencidas)
        col5.metric("⚪ No tiene", cant_no_tiene)

        st.subheader("Vista previa de los datos consolidados")
        st.dataframe(df_final, use_container_width=True)
        
        # Botón para descargar el resultado consolidado
        csv = df_final.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar datos consolidados (CSV)",
            data=csv,
            file_name='datos_consolidados_conci.csv',
            mime='text/csv',
        )
        
    except Exception as e:
        st.error(f"❌ Error al procesar los archivos: {e}")
        st.info("Asegúrate de que los archivos cargados sean válidos y tengan el formato correcto.")
else:
    st.info("Esperando a que subas al menos el primer archivo (Analizador de Máquina) para comenzar...")
