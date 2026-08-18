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

# Identificación de la columna Licencia
col_licencia = 'Licencia' if 'Licencia' in df_raw.columns else ('licencia' if 'licencia' in df_raw.columns else None)

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

# Filtro: Licencia
if col_licencia:
    licencias = ["Todas"] + sorted([l for l in df_sidebar[col_licencia].dropna().unique() if str(l).strip() != ''])
    sel_licencia = st.sidebar.selectbox("Licencia", licencias)
else:
    sel_licencia = "Todas"

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

if col_licencia and sel_licencia != "Todas":
    df_filtrado_raw = df_filtrado_raw[df_filtrado_raw[col_licencia] == sel_licencia]

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
# 1. Promedio General (filtrado con AutoTrac >= 1%)
promedio_autotrac = (
    df_filtrado_autotrac["AutoTrac™ Activo"].mean()
    if not df_filtrado_autotrac.empty
    else None
)

# 2. Promedio de la última semana
max_fecha_kpi = (
    df_filtrado_autotrac["Fecha_fin_dt"].max()
    if not df_filtrado_autotrac.empty
    else None
)
inicio_ult_semana_kpi = (
    max_fecha_kpi - pd.Timedelta(days=7) if pd.notna(max_fecha_kpi) else None
)

if inicio_ult_semana_kpi is not None:
    df_kpi_ult_semana = df_filtrado_autotrac[
        df_filtrado_autotrac["Fecha_fin_dt"] >= inicio_ult_semana_kpi
    ]
    promedio_ult_semana_kpi = (
        df_kpi_ult_semana["AutoTrac™ Activo"].mean()
        if not df_kpi_ult_semana.empty
        else None
    )
else:
    promedio_ult_semana_kpi = None

# 3. Cálculo de variación (Delta)
if promedio_autotrac is not None and promedio_ult_semana_kpi is not None:
    delta_autotrac = promedio_ult_semana_kpi - promedio_autotrac
    delta_str = f"{delta_autotrac:+.2f}% vs. últ. semana"
else:
    delta_str = None

maquinas_totales = df_filtrado_raw["Número de serie de la máquina"].nunique()
maquinas_aptas = df_filtrado_aptas["Número de serie de la máquina"].nunique()

# --- RECTÁNGULOS KPI ---
kpi1, kpi2, kpi3 = st.columns(3)

with kpi1:
    st.metric(
        label="Promedio AutoTrac™ Activo",
        value=(
            f"{promedio_autotrac:.2f}%"
            if promedio_autotrac is not None
            else "Sin Datos"
        ),
        delta=delta_str,
    )

with kpi2:
    st.metric(
        label="Máquinas Totales",
        value=f"{maquinas_totales:,}".replace(",", "."),
    )

with kpi3:
    st.metric(
        label="Máquinas Aptas (≥ 23.3)",
        value=f"{maquinas_aptas:,}".replace(",", "."),
    )

# --- TABLA RESUMEN POR MÁQUINA ---
st.subheader("📊 Promedio de Uso de AutoTrac™ por Máquina")

if not df_filtrado_aptas.empty:
    # Columna auxiliar para el promedio (asigna None a los < 1%)
    df_filtrado_aptas.loc[:, "AutoTrac_Filtrado"] = df_filtrado_aptas[
        "AutoTrac™ Activo"
    ].apply(lambda x: x if (pd.notna(x) and x >= 1) else None)

    # Determinar el período de la última semana de análisis
    max_fecha_analisis = df_filtrado_aptas["Fecha_fin_dt"].max()
    inicio_ult_semana = (
        max_fecha_analisis - pd.Timedelta(days=7)
        if pd.notna(max_fecha_analisis)
        else None
    )

    if inicio_ult_semana:
        df_filtrado_aptas.loc[:, "es_ult_semana"] = (
            df_filtrado_aptas["Fecha_fin_dt"] >= inicio_ult_semana
        )
        df_ult_semana = (
            df_filtrado_aptas[df_filtrado_aptas["es_ult_semana"]]
            .groupby("Máquina")["AutoTrac_Filtrado"]
            .mean()
            .reset_index()
        )
        df_ult_semana.rename(
            columns={"AutoTrac_Filtrado": "Promedio_Ultima_Semana"}, inplace=True
        )
    else:
        df_ult_semana = pd.DataFrame(
            columns=["Máquina", "Promedio_Ultima_Semana"]
        )

    # Agrupación por máquina
    group_cols = ["Máquina", "Tipo", "Organización", "Sucursal"]
    if col_licencia and col_licencia in df_filtrado_aptas.columns:
        group_cols.append(col_licencia)

    df_promedios = df_filtrado_aptas.groupby(
        group_cols, dropna=False, as_index=False
    ).agg(
        Promedio_AutoTrac=("AutoTrac_Filtrado", "mean"),
        Períodos_Con_Uso=("AutoTrac_Filtrado", "count"),
        Total_Períodos=("Fecha_inicio_dt", "count"),
    )

    # Merge con el promedio de la última semana
    df_promedios = pd.merge(
        df_promedios, df_ult_semana, on="Máquina", how="left"
    )

    # Lógica de Evolución AutoTrac
    def evaluar_evolucion(row):
        prom_gen = row["Promedio_AutoTrac"]
        prom_ult = row["Promedio_Ultima_Semana"]

        if pd.isna(prom_gen) or pd.isna(prom_ult):
            return "⚪ Sin datos últ. semana"

        diff = prom_ult - prom_gen
        if diff > 0.05:
            return f"🟢 Genial (+{diff:.2f}%)"
        elif diff < -0.05:
            return f"🔴 Peligro ({diff:.2f}%)"
        else:
            return "➡️ Estable (0.00%)"

    df_promedios["Evolución AutoTrac"] = df_promedios.apply(
        evaluar_evolucion, axis=1
    )

    # Formateo como porcentaje
    df_promedios["AutoTrac™ Promedio (%)"] = df_promedios[
        "Promedio_AutoTrac"
    ].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "Sin Registros ( < 1% )")

    # Manejo de nombre de Licencia
    if col_licencia and col_licencia in df_promedios.columns:
        df_promedios["Licencia"] = df_promedios[col_licencia].fillna("-")
    else:
        df_promedios["Licencia"] = "-"

    # Selección y ordenamiento final de columnas
    cols_display = [
        "Máquina",
        "Tipo",
        "Organización",
        "Sucursal",
        "AutoTrac™ Promedio (%)",
        "Evolución AutoTrac",
        "Licencia",
    ]

    df_promedios_display = df_promedios.sort_values(
        by="Promedio_AutoTrac", ascending=False, na_position="last"
    )[cols_display]

    # --- FORMATO CONDICIONAL DE COLOR DE TEXTO ---
    def colorear_evolucion(val):
        if isinstance(val, str):
            if "🟢" in val:
                return "color: #2e7d32; font-weight: bold;"
            elif "🔴" in val:
                return "color: #d32f2f; font-weight: bold;"
        return ""

    if hasattr(df_promedios_display.style, "map"):
        styled_df = df_promedios_display.style.map(
            colorear_evolucion, subset=["Evolución AutoTrac"]
        )
    else:
        styled_df = df_promedios_display.style.applymap(
            colorear_evolucion, subset=["Evolución AutoTrac"]
        )

    st.dataframe(styled_df, use_container_width=True)
else:
    st.write(
        "No hay máquinas aptas con datos disponibles para mostrar en la tabla."
    )
