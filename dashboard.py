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

# Conversión de fechas y tipos numéricos
df_raw['Fecha_inicio_dt'] = pd.to_datetime(df_raw['Fecha de inicio'], dayfirst=True, errors='coerce')
df_raw['Fecha_fin_dt'] = pd.to_datetime(df_raw['Fecha de terminación'], dayfirst=True, errors='coerce')

if 'AutoTrac™ Activo' in df_raw.columns:
    df_raw['AutoTrac™ Activo'] = pd.to_numeric(df_raw['AutoTrac™ Activo'], errors='coerce')

# Identificación de pantallas aptas (versión >= 23.3)
df_raw['es_valida'] = df_raw['Versión Software Monitor'].apply(es_version_valida)

# --- 4. SIDEBAR (FILTROS) ---
st.sidebar.header("🔍 Filtros de Análisis")

df_sidebar = df_raw.copy()

# Checkbox: Excluir CONCI SA
excluir_conci = st.sidebar.checkbox("Excluir valores de CONCI SA", value=False)
if excluir_conci:
    df_sidebar = df_sidebar[~df_sidebar['Organización'].fillna('').str.upper().str.contains('CONCI SA')].copy()

# Filtro: Sucursal
sucursales = ["Todas"] + sorted([s for s in df_sidebar['Sucursal'].dropna().unique() if str(s).strip() != ''])
sel_sucursal = st.sidebar.selectbox("Sucursal", sucursales)

# Filtro: Razón Social (Organización)
razones = ["Todas"] + sorted([r for r in df_sidebar['Organización'].dropna().unique() if str(r).strip() != ''])
sel_razon = st.sidebar.selectbox("Razón Social", razones)

# Filtro: Tipo de Máquina
tipos = ["Todos"] + sorted([t for t in df_sidebar['Tipo'].dropna().unique() if str(t).strip() != ''])
sel_tipo = st.sidebar.selectbox("Tipo de Máquina", tipos)

# Filtro: Slider Período de Análisis
fecha_min = df_sidebar['Fecha_inicio_dt'].min()
fecha_max = df_sidebar['Fecha_fin_dt'].max()

if pd.notna(fecha_min) and pd.notna(fecha_max):
    rango_fechas = st.sidebar.slider(
        "Período de Análisis",
        min_value=fecha_min.date(),
        max_value=fecha_max.date(),
        value=(fecha_min.date(), fecha_max.date()),
        format="DD/MM/YYYY"
    )
else:
    rango_fechas = None

# --- 5. APLICACIÓN DE FILTROS A LA BASE GENERAL ---
df_filtrado_raw = df_sidebar.copy()

if sel_sucursal != "Todas":
    df_filtrado_raw = df_filtrado_raw[df_filtrado_raw['Sucursal'] == sel_sucursal]

if sel_razon != "Todas":
    df_filtrado_raw = df_filtrado_raw[df_filtrado_raw['Organización'] == sel_razon]

if sel_tipo != "Todos":
    df_filtrado_raw = df_filtrado_raw[df_filtrado_raw['Tipo'] == sel_tipo]

if rango_fechas:
    df_filtrado_raw = df_filtrado_raw[
        (df_filtrado_raw['Fecha_inicio_dt'].dt.date >= rango_fechas[0]) & 
        (df_filtrado_raw['Fecha_fin_dt'].dt.date <= rango_fechas[1])
    ]

# Base de registros correspondientes a monitores aptos (≥ 23.3)
df_filtrado_aptas = df_filtrado_raw[df_filtrado_raw['es_valida']].copy()

# Registros aptos filtrando únicamente aquellos con uso de AutoTrac >= 1%
df_filtrado_autotrac = df_filtrado_aptas[
    pd.notna(df_filtrado_aptas['AutoTrac™ Activo']) & (df_filtrado_aptas['AutoTrac™ Activo'] >= 1)
]

# --- 6. PESTAÑA: USO DE AUTOTRAC ---
tabs = st.tabs(["🎯 Uso de AutoTrac"])

with tabs[0]:
    st.title("🎯 Uso de AutoTrac™")
    st.caption("Promedio de adopción para monitores aptos (**software ≥ 23.3**) considerando registros con **uso ≥ 1%**.")

    # --- PERÍODO EVALUADO (ARRIBA DE LOS KPIS) ---
    if not df_filtrado_raw.empty:
        primera_fecha = df_filtrado_raw['Fecha_inicio_dt'].min().strftime('%d/%m/%Y')
        ultima_fecha = df_filtrado_raw['Fecha_fin_dt'].max().strftime('%d/%m/%Y')
        st.info(f"🗓️ **Período Evaluado:** Desde **{primera_fecha}** hasta **{ultima_fecha}**")
    else:
        st.warning("⚠️ No existen datos para los filtros seleccionados en el período indicado.")

    # --- CÁLCULO DE KPIS ---
    promedio_autotrac = df_filtrado_autotrac['AutoTrac™ Activo'].mean() if not df_filtrado_autotrac.empty else None
    maquinas_totales = df_filtrado_raw['Número de serie de la máquina'].nunique()
    maquinas_aptas = df_filtrado_aptas['Número de serie de la máquina'].nunique()

    kpi1, kpi2, kpi3 = st.columns(3)

    with kpi1:
        st.metric(
            label="Promedio AutoTrac™ Activo",
            value=f"{promedio_autotrac:.2f}%" if promedio_autotrac is not None else "Sin Datos"
        )

    with kpi2:
        st.metric(
            label="Máquinas Totales",
            value=f"{maquinas_totales:,}".replace(",", ".")
        )

    with kpi3:
        st.metric(
            label="Máquinas Aptas (≥ 23.3)",
            value=f"{maquinas_aptas:,}".replace(",", ".")
        )

    st.markdown("---")

    # --- TABLA RESUMEN POR MÁQUINA ---
    st.subheader("📊 Promedio de Uso de AutoTrac™ por Máquina")
    
    if not df_filtrado_aptas.empty:
        # Columna auxiliar para el promedio asignando NaN a los valores < 1% (evita alterar los promedios)
        df_filtrado_aptas.loc[:, 'AutoTrac_Filtrado'] = df_filtrado_aptas['AutoTrac™ Activo'].apply(
            lambda x: x if (pd.notna(x) and x >= 1) else None
        )

        df_promedios = df_filtrado_aptas.groupby(
            ['Máquina', 'Tipo', 'Organización', 'Sucursal'],
            dropna=False,
            as_index=False
        ).agg(
            Promedio_AutoTrac=('AutoTrac_Filtrado', 'mean'),
            Períodos_Con_Uso=('AutoTrac_Filtrado', 'count'),
            Total_Períodos=('Fecha_inicio_dt', 'count')
        )

        # Formateo como porcentaje
        df_promedios['AutoTrac™ Promedio (%)'] = df_promedios['Promedio_AutoTrac'].apply(
            lambda x: f"{x:.2f}%" if pd.notna(x) else "Sin Registros ( < 1% )"
        )

        # Ordenar de mayor a menor según el uso de AutoTrac
        df_promedios_display = df_promedios.sort_values(
            by='Promedio_AutoTrac', ascending=False, na_position='last'
        )[[
            'Máquina', 'Tipo', 'Organización', 'Sucursal', 
            'AutoTrac™ Promedio (%)', 'Períodos_Con_Uso', 'Total_Períodos'
        ]]

        st.dataframe(df_promedios_display, use_container_width=True)
    else:
        st.write("No hay máquinas aptas con datos disponibles para mostrar en la tabla.")
