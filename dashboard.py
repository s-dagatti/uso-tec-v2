import streamlit as st
import pandas as pd
import requests
import io
import re

# Configuración inicial de la página
st.set_page_config(page_title="Dashboard Uso de Tecnología - Conci", layout="wide")

# --- 1. LECTURA DESDE GITHUB (s-dagatti/uso-tec-v2) ---
@st.cache_data(ttl=60, show_spinner=False)
def cargar_base_datos():
    repo = st.secrets.get("github", {}).get("repo", "s-dagatti/uso-tec-v2")
    path = st.secrets.get("github", {}).get("path", "datos_consolidados_conci.csv")
    token = st.secrets.get("github", {}).get("token", None)
    
    # Lectura vía GitHub API con Token
    if token:
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3.raw"
        }
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            return pd.read_csv(io.StringIO(res.text))
            
    # Fallback a URL Raw del repositorio
    raw_url = f"https://raw.githubusercontent.com/{repo}/main/{path}"
    return pd.read_csv(raw_url)

# --- 2. FILTRO DE VERSIÓN DE SOFTWARE (≥ 23.3) ---
def es_version_valida(version_str):
    if pd.isna(version_str):
        return False
    # Normaliza separadores '23-3' -> '23.3'
    limpio = str(version_str).strip().split()[0].replace('-', '.')
    match = re.match(r'^(\d+)\.(\d+)', limpio)
    if match:
        major, minor = int(match.group(1)), int(match.group(2))
        return (major, minor) >= (23, 3)
    return False

# --- 3. CARGA Y PREPROCESAMIENTO ---
try:
    df_raw = cargar_base_datos()
except Exception as e:
    st.error(f"❌ Error al conectar con la base de datos en GitHub (`s-dagatti/uso-tec-v2`): {e}")
    st.stop()

# Conversión de fechas de la serie histórica
df_raw['Fecha_dt'] = pd.to_datetime(df_raw['Fecha de terminación'], dayfirst=True, errors='coerce')

# Filtrado inicial: Solo pantallas con versión >= 23.3
df_base = df_raw[df_raw['Versión Software Monitor'].apply(es_version_valida)].copy()

# --- 4. SIDEBAR (FILTROS) ---
st.sidebar.header("🔍 Filtros de Análisis")

# Filtro: Sucursal
sucursales = ["Todas"] + sorted([s for s in df_base['Sucursal'].dropna().unique() if str(s).strip() != ''])
sel_sucursal = st.sidebar.selectbox("Sucursal", sucursales)

# Filtro: Razón Social (Organización)
razones = ["Todas"] + sorted([r for r in df_base['Organización'].dropna().unique() if str(r).strip() != ''])
sel_razon = st.sidebar.selectbox("Razón Social", razones)

# Filtro: Tipo de Máquina
tipos = ["Todos"] + sorted([t for t in df_base['Tipo'].dropna().unique() if str(t).strip() != ''])
sel_tipo = st.sidebar.selectbox("Tipo de Máquina", tipos)

# Filtro: Slider Fecha de Terminación
fecha_min = df_base['Fecha_dt'].min()
fecha_max = df_base['Fecha_dt'].max()

if pd.notna(fecha_min) and pd.notna(fecha_max):
    rango_fechas = st.sidebar.slider(
        "Fecha de Terminación",
        min_value=fecha_min.date(),
        max_value=fecha_max.date(),
        value=(fecha_min.date(), fecha_max.date()),
        format="DD/MM/YYYY"
    )
else:
    rango_fechas = None

# --- 5. APLICACIÓN DE FILTROS ---
df_filtrado = df_base.copy()

if sel_sucursal != "Todas":
    df_filtrado = df_filtrado[df_filtrado['Sucursal'] == sel_sucursal]

if sel_razon != "Todas":
    df_filtrado = df_filtrado[df_filtrado['Organización'] == sel_razon]

if sel_tipo != "Todos":
    df_filtrado = df_filtrado[df_filtrado['Tipo'] == sel_tipo]

if rango_fechas:
    df_filtrado = df_filtrado[
        (df_filtrado['Fecha_dt'].dt.date >= rango_fechas[0]) & 
        (df_filtrado['Fecha_dt'].dt.date <= rango_fechas[1])
    ]

# --- 6. PESTAÑA: USO DE AUTOTRAC ---
tab_autotrac, = st.tabs(["🎯 Uso de AutoTrac"])

with tab_autotrac:
    st.title("🎯 Uso de AutoTrac™")
    st.caption("Promedio histórico de adopción para monitores con versión de software **23.3 o superior**.")

    # Cálculo del promedio excluyendo valores nulos
    serie_autotrac = df_filtrado['AutoTrac™ Activo'].dropna()
    promedio_autotrac = serie_autotrac.mean() if not serie_autotrac.empty else None

    # KPI Principal y Métricas Complementarias
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
        st.metric(
            label="Promedio AutoTrac™ Activo",
            value=f"{promedio_autotrac:.2f}%" if promedio_autotrac is not None else "Sin Datos"
        )

    with kpi2:
        st.metric(
            label="Registros Evaluados",
            value=f"{len(df_filtrado):,}".replace(",", ".")
        )

    with kpi3:
        st.metric(
            label="Máquinas Únicas",
            value=f"{df_filtrado['Número de serie de la máquina'].nunique():,}".replace(",", ".")
        )

    with kpi4:
        st.metric(
            label="Base Elegible (≥ 23.3)",
            value=f"{len(df_base):,}".replace(",", ".")
        )

    st.markdown("---")

    # Tabla de Detalle
    st.subheader("📋 Registros Filtrados")
    st.dataframe(
        df_filtrado[[
            'Máquina', 'Tipo', 'Organización', 'Sucursal', 
            'Fecha de terminación', 'AutoTrac™ Activo', 'Versión Software Monitor'
        ]],
        use_container_width=True
    )
