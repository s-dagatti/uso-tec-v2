import pandas as pd
import streamlit as st
import re

st.set_page_config(page_title="Dashboard - Uso de AutoTrac", layout="wide")

# --- 1. CARGA Y FILTRADO DE DATOS ---
@st.cache_data
def load_and_filter_data(file_path):
    # Cargar base de datos
    df = pd.read_csv(file_path)
    
    # Nombres de columnas esperados (ajustar si difieren en el CSV)
    col_ver = 'version_software'
    col_fecha = 'fecha_terminacion'
    
    # Convertir fechas a formato datetime
    if col_fecha in df.columns:
        df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce')
    
    # Filtro de versión de software del monitor >= 23.3
    def parse_version(val):
        if pd.isna(val):
            return 0.0
        match = re.search(r'(\d+\.\d+)', str(val))
        return float(match.group(1)) if match else 0.0

    if col_ver in df.columns:
        df['ver_num'] = df[col_ver].apply(parse_version)
        df = df[df['ver_num'] >= 23.3].drop(columns=['ver_num'])
        
    return df

# Ruta al CSV
CSV_PATH = "datos_consolidados_conci.csv"
df_base = load_and_filter_data(CSV_PATH)

# --- 2. SIDEBAR (FILTROS) ---
st.sidebar.title("Filtros de Control")

# Filtro: Sucursal
col_sucursal = 'sucursal'
sucursales = ["Todas"] + sorted(df_base[col_sucursal].dropna().unique().tolist()) if col_sucursal in df_base.columns else ["Todas"]
sel_sucursal = st.sidebar.selectbox("Sucursal", sucursales)

# Filtro: Razón Social
col_razon = 'razon_social'
razones = ["Todas"] + sorted(df_base[col_razon].dropna().unique().tolist()) if col_razon in df_base.columns else ["Todas"]
sel_razon = st.sidebar.selectbox("Razón Social", razones)

# Filtro: Tipo de Máquina
col_tipo = 'tipo_maquina'
tipos = ["Todos"] + sorted(df_base[col_tipo].dropna().unique().tolist()) if col_tipo in df_base.columns else ["Todos"]
sel_tipo = st.sidebar.selectbox("Tipo de Máquina", tipos)

# Filtro: Slider Fecha de Terminación
col_fecha = 'fecha_terminacion'
if col_fecha in df_base.columns and df_base[col_fecha].notna().any():
    min_date = df_base[col_fecha].min().date()
    max_date = df_base[col_fecha].max().date()
    
    sel_fechas = st.sidebar.slider(
        "Fecha de Terminación",
        min_value=min_date,
        max_value=max_date,
        value=(min_date, max_date)
    )
else:
    sel_fechas = None

# --- 3. APLICACIÓN DE FILTROS ---
df_filtered = df_base.copy()

if sel_sucursal != "Todas":
    df_filtered = df_filtered[df_filtered[col_sucursal] == sel_sucursal]

if sel_razon != "Todas":
    df_filtered = df_filtered[df_filtered[col_razon] == sel_razon]

if sel_tipo != "Todos":
    df_filtered = df_filtered[df_filtered[col_tipo] == sel_tipo]

if sel_fechas and col_fecha in df_filtered.columns:
    df_filtered = df_filtered[
        (df_filtered[col_fecha].dt.date >= sel_fechas[0]) & 
        (df_filtered[col_fecha].dt.date <= sel_fechas[1])
    ]

# --- 4. VISTA PRINCIPAL: USO DE AUTOTRAC ---
st.title("Uso de AutoTrac")

col_autotrac = 'uso_autotrac_pct'

if not df_filtered.empty and col_autotrac in df_filtered.columns:
    # Promedio histórico excluyendo nulos explícitamente para evitar distorsión
    promedio_autotrac = df_filtered[col_autotrac].dropna().mean()
    
    kpi1, kpi2, kpi3 = st.columns(3)
    
    with kpi1:
        st.metric(
            label="Promedio Histórico AutoTrac",
            value=f"{promedio_autotrac:.2f}%" if pd.notna(promedio_autotrac) else "Sin Datos"
        )
    with kpi2:
        st.metric(
            label="Registros Evaluados",
            value=len(df_filtered)
        )
    with kpi3:
        st.metric(
            label="Monitores Compatibles (≥ 23.3)",
            value=len(df_base)
        )
else:
    st.warning("No se encontraron datos que coincidan con los criterios de búsqueda seleccionados.")
