import streamlit as st
import pandas as pd
import requests
import base64
import io

# ---------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------

st.set_page_config(
    page_title="HarvestLab / Picadoras",
    layout="wide"
)

st.title("🌿 HarvestLab y Picadoras")
st.markdown(
    """
    Construcción de la serie histórica de calidad de forraje y operación de picadoras.
    """
)

# ---------------------------------------------------
# FUNCIONES GITHUB
# ---------------------------------------------------

@st.cache_data(ttl=30, show_spinner=False)
def cargar_base_github(repo, path, token):

    try:

        url = f"https://api.github.com/repos/{repo}/contents/{path}"

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3.raw"
        }

        res = requests.get(url, headers=headers)

        if res.status_code == 200:

            return pd.read_csv(
                io.StringIO(res.text)
            )

        return None

    except Exception:

        return None


def guardar_en_github(df, repo, path, token, commit_msg):

    url = f"https://api.github.com/repos/{repo}/contents/{path}"

    headers = {

        "Authorization": f"token {token}",

        "Accept": "application/vnd.github.v3+json"

    }

    csv_bytes = (
        df
        .to_csv(index=False)
        .encode("utf-8")
    )

    content_b64 = base64.b64encode(
        csv_bytes
    ).decode("utf-8")

    res_get = requests.get(
        url,
        headers=headers
    )

    sha = (
        res_get.json().get("sha")
        if res_get.status_code == 200
        else None
    )

    payload = {

        "message": commit_msg,

        "content": content_b64

    }

    if sha:

        payload["sha"] = sha

    res_put = requests.put(
        url,
        headers=headers,
        json=payload
    )

    if res_put.status_code in [200, 201]:

        return (
            True,
            "Base histórica actualizada correctamente."
        )

    else:

        return (
            False,
            res_put.json().get(
                "message",
                "Error inesperado"
            )
        )

# ---------------------------------------------------
# GITHUB
# ---------------------------------------------------

gh_token = st.secrets["github"]["token"]

gh_repo = st.secrets["github"]["repo"]

gh_path = "datos_picadoras_harvestlab.csv"

# ---------------------------------------------------
# CARGA HISTÓRICO
# ---------------------------------------------------

df_historico = cargar_base_github(
    gh_repo,
    gh_path,
    gh_token
)

st.subheader("📦 Estado de la Serie Histórica")

if (
    df_historico is not None
    and
    not df_historico.empty
):

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Registros Históricos",
            len(df_historico)
        )

    with col2:

        st.metric(
            "Clientes",
            df_historico["Clientes"]
            .nunique()
        )

    with col3:

        if (
            "Fecha de inicio" in df_historico.columns
            and
            "Fecha de terminación" in df_historico.columns
        ):
    
            fechas_inicio = pd.to_datetime(
                df_historico["Fecha de inicio"],
                format="mixed",
                errors="coerce"
            )
    
            fechas_fin = pd.to_datetime(
                df_historico["Fecha de terminación"],
                format="mixed",
                errors="coerce"
            )
    
            ultima_fecha_fin = fechas_fin.max()
    
            if pd.notna(ultima_fecha_fin):
    
                mascara_ultimo_periodo = (
                    fechas_fin == ultima_fecha_fin
                )
    
                ultima_fecha_inicio = (
                    fechas_inicio[mascara_ultimo_periodo]
                    .min()
                )
    
                ultimo_periodo = (
                    f"{ultima_fecha_inicio.strftime('%d/%m/%Y')} - "
                    f"{ultima_fecha_fin.strftime('%d/%m/%Y')}"
                )
    
                st.metric(
                    "📅 Último Período",
                    ultimo_periodo
                )
    
            else:
    
                st.metric(
                    "📅 Último Período",
                    "Sin datos"
                )


else:

    st.info(
        "Todavía no existe "
        "datos_picadoras_harvestlab.csv"
    )

# ---------------------------------------------------
# CARGA ARCHIVOS
# ---------------------------------------------------

st.subheader("📁 Carga de Archivos")

uploaded_file = st.file_uploader(
    "1️⃣ Archivo HarvestLab",
    type=["xlsx"]
)

uploaded_file_orgs = st.file_uploader(
    "2️⃣ Base Org ID y Sucursales",
    type=["csv"]
)

# ---------------------------------------------------
# FECHAS
# ---------------------------------------------------

st.subheader("📅 Período Analizado")

col_f1, col_f2 = st.columns(2)

with col_f1:

    fecha_inicio = st.date_input(
        "Fecha de inicio"
    )

with col_f2:

    fecha_fin = st.date_input(
        "Fecha de terminación"
    )

# ---------------------------------------------------
# PROCESAMIENTO
# ---------------------------------------------------

if uploaded_file is not None:

    try:

        # --------------------------------------------
        # LECTURA
        # --------------------------------------------

        df = pd.read_excel(
            uploaded_file
        )

        filas_originales = len(df)

        st.success(
            "✅ Archivo cargado correctamente"
        )

        # --------------------------------------------
        # LIMPIEZA
        # --------------------------------------------

        df = df.replace(
            "---",
            pd.NA
        )

        df = df.dropna(
            how="all"
        )

        # --------------------------------------------
        # CRUCE SUCURSAL
        # --------------------------------------------

        if uploaded_file_orgs is not None:

            df_orgs = pd.read_csv(
                uploaded_file_orgs
            )

            df_orgs_unique = (

                df_orgs

                .drop_duplicates(
                    subset=["Org ID"]
                )

                [["Org ID", "SUC?"]]

                .rename(
                    columns={
                        "SUC?": "Sucursal"
                    }
                )

            )

            if (
                "ID de organización"
                in df.columns
            ):

                df["ID de organización"] = pd.to_numeric(
                    df["ID de organización"],
                    errors="coerce"
                )

                df_orgs_unique["Org ID"] = pd.to_numeric(
                    df_orgs_unique["Org ID"],
                    errors="coerce"
                )

                df = pd.merge(

                    df,

                    df_orgs_unique,

                    left_on="ID de organización",

                    right_on="Org ID",

                    how="left"

                )

                if "Org ID" in df.columns:

                    df.drop(
                        columns=["Org ID"],
                        inplace=True
                    )

        # --------------------------------------------
        # FECHAS DEL PERÍODO
        # --------------------------------------------

        df["Fecha de inicio"] = pd.to_datetime(
            fecha_inicio
        )

        df["Fecha de terminación"] = pd.to_datetime(
            fecha_fin
        )

        df["Fecha de carga"] = (
            pd.Timestamp.now()
        )

        df["Lote de Actualización"] = (
            pd.Timestamp.now()
            .strftime("%Y%m%d_%H%M")
        )

        df["Semana Analizada"] = (
            pd.to_datetime(fecha_inicio)
            .strftime("%Y-%m-%d")
            +
            " a "
            +
            pd.to_datetime(fecha_fin)
            .strftime("%Y-%m-%d")
        )

        # --------------------------------------------
        # CONCATENAR
        # --------------------------------------------

        if (
            df_historico is not None
            and
            not df_historico.empty
        ):

            df_final = pd.concat(
                [
                    df_historico,
                    df
                ],
                ignore_index=True
            )

            df_final = (
                df_final
                .drop_duplicates()
            )

        else:

            df_final = df.copy()

        # --------------------------------------------
        # KPIs
        # --------------------------------------------

        st.markdown("---")
        st.subheader("📊 Resumen")

        c1, c2, c3 = st.columns(3)

        with c1:

            st.metric(
                "Registros",
                len(df)
            )

        with c2:

            if "Clientes" in df.columns:

                st.metric(
                    "Clientes",
                    df["Clientes"]
                    .nunique()
                )

        with c3:

            if "Equipo" in df.columns:

                st.metric(
                    "Máquinas",
                    df["Equipo"]
                    .nunique()
                )

        # --------------------------------------------
        # VISTA PREVIA
        # --------------------------------------------

        st.subheader("👁️ Vista Previa")

        st.dataframe(
            df_final,
            use_container_width=True
        )

        # --------------------------------------------
        # GUARDAR GITHUB
        # --------------------------------------------

        st.markdown("---")

        if st.button(
            "🚀 Actualizar Serie Histórica",
            type="primary"
        ):

            exito, mensaje = guardar_en_github(

                df_final,

                gh_repo,

                gh_path,

                gh_token,

                commit_msg=(
                    "Actualización HarvestLab"
                )

            )

            if exito:

                st.success(
                    mensaje
                )

                st.cache_data.clear()

            else:

                st.error(
                    mensaje
                )

        # --------------------------------------------
        # DESCARGA
        # --------------------------------------------

        csv = (
            df_final
            .to_csv(index=False)
            .encode("utf-8")
        )

        st.download_button(

            label="📥 Descargar CSV",

            data=csv,

            file_name=(
                "datos_picadoras_harvestlab.csv"
            ),

            mime="text/csv"

        )

    except Exception as e:

        st.error(
            f"❌ Error al procesar archivo: {e}"
        )
