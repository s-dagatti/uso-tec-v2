import io
import pandas as pd
import requests
import streamlit as st

# ---------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------

st.set_page_config(
    page_title="Agronomy Analyzer",
    page_icon="📋",
    layout="wide"
)

st.title("📋 Gestión de Proyectos Agronomy Analyzer")

# ---------------------------------------------------
# CARGA DE DATOS
# ---------------------------------------------------

@st.cache_data(ttl=60, show_spinner=False)
def cargar_base_agronomy():

    repo = st.secrets["github"]["repo"]

    token = st.secrets["github"]["token"]

    path = "datos_proyectos_agronomy_analyzer.csv"

    url = (
        f"https://api.github.com/repos/"
        f"{repo}/contents/{path}"
    )

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3.raw"
    }

    res = requests.get(
        url,
        headers=headers
    )

    if res.status_code == 200:

        return pd.read_csv(
            io.StringIO(res.text)
        )

    return pd.DataFrame()

# ---------------------------------------------------
# BASE
# ---------------------------------------------------

df = cargar_base_agronomy()

if df.empty:

    st.warning(
        "No se encontraron proyectos cargados."
    )

    st.stop()

# ---------------------------------------------------
# SIDEBAR
# ---------------------------------------------------

st.sidebar.header("🔍 Filtros")

sucursales = sorted(
    df["SUCURSAL"]
    .dropna()
    .unique()
)

sel_sucursal = st.sidebar.multiselect(
    "Sucursal",
    sucursales
)

clientes = sorted(
    df["CLIENTE"]
    .dropna()
    .unique()
)

sel_cliente = st.sidebar.multiselect(
    "Cliente",
    clientes
)

tipos = sorted(
    df["Tipo de Proyecto"]
    .dropna()
    .unique()
)

sel_tipo = st.sidebar.multiselect(
    "Tipo de Proyecto",
    tipos
)

fy = sorted(
    df["FY"]
    .dropna()
    .unique()
)

sel_fy = st.sidebar.multiselect(
    "FY",
    fy
)

# ---------------------------------------------------
# FILTROS
# ---------------------------------------------------

df_filtrado = df.copy()

if sel_sucursal:

    df_filtrado = (
        df_filtrado[
            df_filtrado["SUCURSAL"]
            .isin(sel_sucursal)
        ]
    )

if sel_cliente:

    df_filtrado = (
        df_filtrado[
            df_filtrado["CLIENTE"]
            .isin(sel_cliente)
        ]
    )

if sel_tipo:

    df_filtrado = (
        df_filtrado[
            df_filtrado["Tipo de Proyecto"]
            .isin(sel_tipo)
        ]
    )

if sel_fy:

    df_filtrado = (
        df_filtrado[
            df_filtrado["FY"]
            .isin(sel_fy)
        ]
    )

# ---------------------------------------------------
# KPIs
# ---------------------------------------------------

st.subheader("📊 Resumen")

total = len(df_filtrado)

completados = (
    df_filtrado["Generación de informe - Estado"]
    .eq("Completado")
    .sum()
)

en_proceso = (
    (
        df_filtrado["Planificación - Estado"]
        == "En Proceso"
    )
    |
    (
        df_filtrado["Recopilación de Datos - Estado"]
        == "En Proceso"
    )
    |
    (
        df_filtrado["Generación de informe - Estado"]
        == "En Proceso"
    )
).sum()

horas = (

    df_filtrado[
        [
            "Planificación - Horas",
            "Recopilación de Datos - Horas",
            "Generación de informe - Horas"
        ]
    ]

    .fillna(0)

    .sum()

    .sum()

)

k1, k2, k3, k4 = st.columns(4)

k1.metric(
    "📋 Proyectos",
    total
)

k2.metric(
    "✅ Completados",
    completados
)

k3.metric(
    "🟡 En proceso",
    en_proceso
)

k4.metric(
    "⏱ Horas",
    f"{horas:.1f}"
)

# ---------------------------------------------------
# TABLA
# ---------------------------------------------------

st.markdown("---")
st.subheader("📋 Proyectos")

columnas = [

    "CLIENTE",

    "SUCURSAL",

    "Tipo de Proyecto",

    "NOMBRE",

    "Planificación - Estado",

    "Recopilación de Datos - Estado",

    "Generación de informe - Estado",

    "FY",

    "Q PLANTEADO",

    "LINK ACCESO"

]

st.dataframe(

    df_filtrado[columnas]
    .copy(),

    use_container_width=True

)

