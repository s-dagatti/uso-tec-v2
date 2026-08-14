import streamlit as st
import pandas as pd
import numpy as np
import datetime
import requests
import base64
import io

# Configuración del Dashboard
st.set_page_config(page_title="Centro de Control de Datos - Conci", layout="wide")

st.title("🚜 Centro de Control y Serie Histórica - Conci")
st.markdown("Consolidación automática de datos de maquinaria, monitores, licencias y sucursales con persistencia en GitHub.")

# --- DICCIONARIO DE MESES ---
spanish_months = {
    'sept': 'Sep', 'septiembre': 'Sep',
    'ene': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'abr': 'Apr',
    'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'ago': 'Aug',
    'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dic': 'Dec'
}

def parse_spanish_date(date_str):
    if pd.isna(date_str) or str(date_str).strip() in ['---', '-', '']:
        return pd.NaT
    s = str(date_str).strip().lower()
    for es in sorted(spanish_months.keys(), key=len, reverse=True):
        en = spanish_months[es]
        s = s.replace(es, en)
    return pd.to_datetime(s, format='%d %b %Y', errors='coerce')

def calcular_duracion_str(inicio_dt, fin_dt):
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
    cols_to_drop = [c for c in df.columns if 'unidad' in str(c).lower()]
    df = df.drop(columns=cols_to_drop)
    
    cols_porcentuales = [c for c in df.columns if 'activo' in str(c).lower() or 'activado' in str(c).lower()]
    for col in cols_porcentuales:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', ''), errors='coerce')
        
    return df

def calcular_estado_licencia(row):
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

def obtener_ultima_fecha(df):
    """Obtiene la fecha más reciente registrada en la columna 'Fecha de terminación'."""
    if df is None or df.empty or 'Fecha de terminación' not in df.columns:
        return "Sin datos"
    dates = pd.to_datetime(df['Fecha de terminación'].astype(str), dayfirst=True, errors='coerce')
    max_d = dates.max()
    if pd.notna(max_d):
        return max_d.strftime('%d/%m/%Y %H:%M')
    return "Sin datos"

# --- FUNCIONES DE GITHUB ---
@st.cache_data(ttl=30, show_spinner=False)
def cargar_base_github(repo, path, token):
    """Descarga la base de datos histórica guardada en GitHub."""
    try:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3.raw"
        }
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            df = pd.read_csv(io.StringIO(res.text))
            return df
        return None
    except Exception:
        return None

def guardar_en_github(df, repo, path, token, commit_msg="Actualización de base de datos consolidada"):
    """Sube/Actualiza el CSV consolidado en GitHub."""
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    csv_bytes = df.to_csv(index=False).encode('utf-8')
    content_b64 = base64.b64encode(csv_bytes).decode('utf-8')
    
    res_get = requests.get(url, headers=headers)
    sha = res_get.json().get('sha') if res_get.status_code == 200 else None
    
    payload = {
        "message": commit_msg,
        "content": content_b64
    }
    if sha:
        payload["sha"] = sha
        
    res_put = requests.put(url, headers=headers, json=payload)
    if res_put.status_code in [200, 201]:
        return True, "Base de datos actualizada con éxito en GitHub."
    else:
        msg = res_put.json().get('message', 'Error desconocido')
        return False, f"Error al guardar en GitHub: {msg}"

# --- 1. CARGA INICIAL DE LA BASE HISTÓRICA DESDE GITHUB ---
df_historico = None
try:
    gh_token = st.secrets["github"]["token"]
    gh_repo = st.secrets["github"]["repo"]
    gh_path = st.secrets["github"].get("path", "datos_consolidados_conci.csv")
    
    df_historico = cargar_base_github(gh_repo, gh_path, gh_token)
except Exception:
    st.sidebar.info("💡 Tip: Configura `[github]` en `st.secrets` para lectura/escritura automática.")

st.subheader("📦 Estado Actual de la Base Histórica en GitHub")
if df_historico is not None and not df_historico.empty:
    col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns(5)
    col_h1.metric("Registros Históricos", len(df_historico))
    col_h2.metric("Última Actualización", obtener_ultima_fecha(df_historico))
    
    if 'Estado Licencia' in df_historico.columns:
        col_h3.metric("🟢 Vigentes", (df_historico['Estado Licencia'] == 'Vigente').sum())
        col_h4.metric("🔴 Vencidas", (df_historico['Estado Licencia'] == 'Vencida').sum())
        col_h5.metric("⚪ Sin Licencia", (df_historico['Estado Licencia'] == 'No tiene').sum())

    with st.expander("👁️ Ver base histórica guardada en GitHub", expanded=False):
        st.dataframe(df_historico, use_container_width=True)
else:
    st.info("ℹ️ Aún no hay una base histórica cargada en GitHub o no se ha configurado la conexión.")

st.markdown("---")

# --- 2. SIDEBAR: CARGA DE NUEVOS ARCHIVOS ---
st.sidebar.header("📁 Cargar Nuevos Archivos")
uploaded_file_analizador = st.sidebar.file_uploader("1. Archivo Analizador de Máquina", type=["xlsx"])
uploaded_file_orgs = st.sidebar.file_uploader("2. Base Orgs ID y Sucursales (CSV)", type=["csv"])
uploaded_file_maquinas = st.sidebar.file_uploader("3. Archivo de Máquinas (Emparejamientos)", type=["xlsx"])
uploaded_file_activaciones = st.sidebar.file_uploader("4. Control de Activaciones Gen 4 (CSV)", type=["csv"])
uploaded_file_gen5 = st.sidebar.file_uploader("5. Licencias Gen 5 (Excel)", type=["xlsx"])

# --- 3. LÓGICA DE PROCESAMIENTO Y ACOPLAMIENTO ---
if uploaded_file_analizador is not None:
    try:
        # A. ANALIZADOR
        df_original = pd.read_excel(uploaded_file_analizador)
        df_nuevo = procesar_analizador(df_original.copy())
        
        # B. SUCURSALES (ORGS ID)
        if uploaded_file_orgs is not None:
            df_orgs = pd.read_csv(uploaded_file_orgs)
            df_orgs_unique = df_orgs.drop_duplicates(subset=['Org ID'])[['Org ID', 'SUC?']].rename(columns={'SUC?': 'Sucursal'})
            
            df_nuevo['Identificador de organización'] = pd.to_numeric(df_nuevo['Identificador de organización'], errors='coerce')
            df_orgs_unique['Org ID'] = pd.to_numeric(df_orgs_unique['Org ID'], errors='coerce')
            
            df_nuevo = pd.merge(df_nuevo, df_orgs_unique, left_on='Identificador de organización', right_on='Org ID', how='left')
            if 'Org ID' in df_nuevo.columns:
                df_nuevo = df_nuevo.drop(columns=['Org ID'])
        else:
            st.sidebar.warning("⚠️ Falta cargar la Base de Orgs ID (Sucursales).")

        # C. EMPAREJAMIENTOS (MÁQUINAS / MONITORES)
        if uploaded_file_maquinas is not None:
            df_maquinas = pd.read_excel(uploaded_file_maquinas, sheet_name='Emparejamientos')
            df_monitores = df_maquinas[df_maquinas['Tipo'].astype(str).str.lower() == 'monitor'].copy()
            df_monitores = df_monitores[[
                'Número de serie de emparejamiento', 
                'Número de serie',       
                'Modelo',                
                'Versión de software'    
            ]].rename(columns={
                'Número de serie': 'Hardware Monitor',
                'Modelo': 'Modelo Monitor',
                'Versión de software': 'Versión Software Monitor'
            })
            
            df_nuevo = pd.merge(df_nuevo, df_monitores, left_on='Número de serie de la máquina', right_on='Número de serie de emparejamiento', how='left')
            if 'Número de serie de emparejamiento' in df_nuevo.columns:
                df_nuevo = df_nuevo.drop(columns=['Número de serie de emparejamiento'])
        else:
            st.sidebar.warning("⚠️ Falta cargar el archivo de máquinas (Emparejamientos).")

        # D. ACTIVACIONES GEN 4
        if uploaded_file_activaciones is not None and 'Hardware Monitor' in df_nuevo.columns:
            df_activaciones = pd.read_csv(uploaded_file_activaciones)
            df_gen4 = df_activaciones[df_activaciones['COMPONENTE'].astype(str).str.strip().str.lower() == 'monitor gen 4'].copy()
            
            df_gen4['Fecha_Inicio_DT'] = pd.to_datetime(df_gen4['Fecha de inicio'], format='%d/%m/%Y', errors='coerce')
            df_gen4 = df_gen4.sort_values('Fecha_Inicio_DT', ascending=True)
            df_gen4_unique = df_gen4.drop_duplicates(subset=['Tornillería'], keep='last')
            
            df_licencias_gen4 = df_gen4_unique[[
                'Tornillería', 'Producto', 'Duración', 'Fecha de inicio', 'Fecha final'
            ]].rename(columns={
                'Producto': 'Licencia',
                'Duración': 'Duración Licencia',
                'Fecha de inicio': 'Comienzo Licencia',
                'Fecha final': 'Fin Licencia'
            })
            
            df_nuevo = pd.merge(df_nuevo, df_licencias_gen4, left_on='Hardware Monitor', right_on='Tornillería', how='left')
            if 'Tornillería' in df_nuevo.columns:
                df_nuevo = df_nuevo.drop(columns=['Tornillería'])

        # Asegurar columnas de licencias
        for col in ['Licencia', 'Duración Licencia', 'Comienzo Licencia', 'Fin Licencia']:
            if col not in df_nuevo.columns:
                df_nuevo[col] = np.nan

        # E. LICENCIAS GEN 5
        if uploaded_file_gen5 is not None:
            df_gen5 = pd.read_excel(uploaded_file_gen5)
            df_gen5['Inicio_DT'] = df_gen5['Fecha de inicio'].apply(parse_spanish_date)
            df_gen5['Fin_DT'] = df_gen5['Fecha de terminación'].apply(parse_spanish_date)
            df_gen5['Duración_Calc'] = df_gen5.apply(lambda r: calcular_duracion_str(r['Inicio_DT'], r['Fin_DT']), axis=1)
            
            df_gen5['Comienzo_Str'] = df_gen5['Inicio_DT'].dt.strftime('%d/%m/%Y').fillna('-')
            df_gen5['Fin_Str'] = df_gen5['Fin_DT'].dt.strftime('%d/%m/%Y').fillna('-')
            
            df_gen5['N.° de serie'] = df_gen5['N.° de serie'].astype(str).str.strip()
            df_gen5_sorted = df_gen5.sort_values('Inicio_DT', ascending=True)
            df_gen5_unique = df_gen5_sorted.drop_duplicates(subset=['N.° de serie'], keep='last')
            
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

            for col, field_map in [
                ('Licencia', map_licencia),
                ('Duración Licencia', map_duracion),
                ('Comienzo Licencia', map_comienzo),
                ('Fin Licencia', map_fin)
            ]:
                g5_vals = df_nuevo.apply(lambda r: buscar_gen5(r, field_map), axis=1)
                df_nuevo[col] = df_nuevo[col].fillna(g5_vals)

        # F. ESTADO FINAL DE LAS NUEVAS FILAS
        df_nuevo['Estado Licencia'] = df_nuevo.apply(calcular_estado_licencia, axis=1)

        # CÁLCULO DE INCREMENTOS (DELTAS) DEL NUEVO LOTE
        nuevas_filas = len(df_nuevo)
        nuevas_vigentes = (df_nuevo['Estado Licencia'] == 'Vigente').sum()
        nuevas_vencidas = (df_nuevo['Estado Licencia'] == 'Vencida').sum()
        nuevas_no_tiene = (df_nuevo['Estado Licencia'] == 'No tiene').sum()

        # G. CONCATENACIÓN CON BASE HISTÓRICA
        if df_historico is not None and not df_historico.empty:
            df_final = pd.concat([df_historico, df_nuevo], ignore_index=True)
            df_final = df_final.drop_duplicates()
        else:
            df_final = df_nuevo.copy()

        # H. UI & RESUMEN DE LA NUEVA BASE CONSOLIDADA CON DELTAS
        st.success("✅ Nuevos datos procesados y acoplados exitosamente a la serie histórica.")
        
        st.subheader("📊 Métricas Consolidadas (Base Final)")
        c1, c2, c3, c4, c5 = st.columns(5)
        
        c1.metric(
            label="Máquinas Totales", 
            value=len(df_final), 
            delta=f"+{nuevas_filas} agregadas"
        )
        
        c2.metric(
            label="Nueva Fecha de Actualización", 
            value=obtener_ultima_fecha(df_final)
        )
        
        tot_vigentes = (df_final['Estado Licencia'] == 'Vigente').sum()
        c3.metric(
            label="🟢 Licencias Vigentes", 
            value=tot_vigentes, 
            delta=f"+{nuevas_vigentes} nuevas"
        )
        
        tot_vencidas = (df_final['Estado Licencia'] == 'Vencida').sum()
        c4.metric(
            label="🔴 Licencias Vencidas", 
            value=tot_vencidas, 
            delta=f"+{nuevas_vencidas} nuevas"
        )
        
        tot_no_tiene = (df_final['Estado Licencia'] == 'No tiene').sum()
        c5.metric(
            label="⚪ Sin Licencia", 
            value=tot_no_tiene, 
            delta=f"+{nuevas_no_tiene} nuevas"
        )

        st.subheader("Vista previa de la base histórica actualizada")
        st.dataframe(df_final, use_container_width=True)
        
        # I. ACCIONES: GUARDAR EN GITHUB / DESCARGAR
        st.markdown("---")
        st.subheader("📌 Guardar Serie Histórica Actualizada")
        
        col_gh, col_dl = st.columns([1, 1])
        
        with col_gh:
            if st.button("🚀 Actualizar Serie Histórica en GitHub", type="primary"):
                try:
                    token = st.secrets["github"]["token"]
                    repo = st.secrets["github"]["repo"]
                    path = st.secrets["github"].get("path", "datos_consolidados_conci.csv")
                    
                    with st.spinner("Guardando serie histórica en GitHub..."):
                        exito, mensaje = guardar_en_github(df_final, repo, path, token)
                        if exito:
                            st.success(f"✅ {mensaje}")
                            st.cache_data.clear() # Limpia la caché para que refresque al momento
                        else:
                            st.error(f"❌ {mensaje}")
                except Exception as e:
                    st.error(f"⚠️ Error de configuración de secretos: {e}")
                    st.info("Asegúrate de configurar `[github]` en `st.secrets`.")

        with col_dl:
            csv = df_final.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar copia local (CSV)",
                data=csv,
                file_name='serie_historica_conci.csv',
                mime='text/csv',
            )
        
    except Exception as e:
        st.error(f"❌ Error al procesar los archivos: {e}")
        st.info("Verifica los formatos de los archivos e inténtalo de nuevo.")
else:
    st.info("Esperando a que subas el archivo del Analizador de Máquina para iniciar el proceso...")
