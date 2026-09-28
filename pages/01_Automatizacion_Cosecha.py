import streamlit as st
import pandas as pd
import requests
import base64
import io

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

        res = requests.get(
            url,
            headers=headers
        )

        if res.status_code == 200:

            return pd.read_csv(
                io.StringIO(res.text)
            )

        return None

    except Exception:

        return None


def guardar_en_github(
    df,
    repo,
    path,
    token,
    commit_msg
):

    url = f"https://api.github.com/repos/{repo}/contents/{path}"

    headers = {

        "Authorization": f"token {token}",

        "Accept": "application/vnd.github.v3+json"

    }

    csv_bytes = df.to_csv(
        index=False
    ).encode("utf-8")

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
# CONFIGURACIÓN
# ---------------------------------------------------

st.set_page_config(
    page_title="Automatización de Cosecha",
    layout="wide"
)

st.title("🌽 Automatización de Cosecha")
st.markdown(
    """
    Construcción de la serie histórica de Automatización de Cosecha.
    """
)

# ---------------------------------------------------
# CONFIG GITHUB
# ---------------------------------------------------

gh_token = st.secrets["github"]["token"]

gh_repo = st.secrets["github"]["repo"]

gh_path_cosecha = (
    "datos_automatizacion_cosecha.csv"
)

# ---------------------------------------------------
# HISTÓRICO
# ---------------------------------------------------

df_historico = cargar_base_github(

    gh_repo,

    gh_path_cosecha,

    gh_token

)

st.subheader(
    "📦 Estado de la Serie Histórica"
)

if (
    df_historico is not None
    and
    not df_historico.empty
):

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "📦 Registros Históricos",
            len(df_historico)
        )

    with col2:

        if "Número de serie" in df_historico.columns:

            st.metric(
                "🚜 Máquinas Únicas",
                df_historico["Número de serie"].nunique()
            )

    with col3:

        if "Fecha de carga" in df_historico.columns:

            ultima_fecha = pd.to_datetime(
                df_historico["Fecha de carga"],
                errors="coerce"
            ).max()

            if pd.notna(ultima_fecha):

                st.metric(
                    "🕒 Última Actualización",
                    ultima_fecha.strftime(
                        "%d/%m/%Y %H:%M"
                    )
                )


else:

    st.info(
        "Todavía no existe "
        "datos_automatizacion_cosecha.csv"
    )

# ---------------------------------------------------
# CARGA DE ARCHIVOS
# ---------------------------------------------------

st.subheader("📁 Carga de Archivos")

uploaded_file = st.file_uploader(
    "1️⃣ Archivo de Automatización de Cosecha",
    type=["xlsx"]
)

uploaded_file_orgs = st.file_uploader(
    "2️⃣ Base Org ID y Sucursales",
    type=["csv"]
)

# ---------------------------------------------------
# FECHAS DEL PERÍODO
# ---------------------------------------------------

st.subheader("📅 Período Analizado")

col1, col2 = st.columns(2)

with col1:
    fecha_inicio = st.date_input(
        "Fecha de inicio"
    )

with col2:
    fecha_fin = st.date_input(
        "Fecha de terminación"
    )

# ---------------------------------------------------
# PROCESAMIENTO
# ---------------------------------------------------

if uploaded_file is not None:

    try:

        # --------------------------------------------
        # LECTURA DEL EXCEL
        # --------------------------------------------

        df = pd.read_excel(uploaded_file)

        st.success("✅ Archivo cargado correctamente")

        filas_originales = len(df)

        # --------------------------------------------
        # LIMPIEZA
        # --------------------------------------------

        df = df.dropna(how="all")

        if "Número de serie" in df.columns:

            df = df[
                df["Número de serie"].notna()
            ]

        filas_limpias = len(df)

        # --------------------------------------------
        # CRUCE CON SUCURSALES
        # --------------------------------------------

        if uploaded_file_orgs is not None:

            try:

                df_orgs = pd.read_csv(uploaded_file_orgs)

                if (
                    "Ident de organización" in df.columns
                    and
                    "Org ID" in df_orgs.columns
                ):

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

                    df["Ident de organización"] = pd.to_numeric(
                        df["Ident de organización"],
                        errors="coerce"
                    )

                    df_orgs_unique["Org ID"] = pd.to_numeric(
                        df_orgs_unique["Org ID"],
                        errors="coerce"
                    )

                    df = pd.merge(

                        df,

                        df_orgs_unique,

                        left_on="Ident de organización",

                        right_on="Org ID",

                        how="left"

                    )

                    if "Org ID" in df.columns:

                        df = df.drop(
                            columns=["Org ID"]
                        )

                    st.success(
                        "✅ Sucursales incorporadas correctamente"
                    )

                else:

                    st.warning(
                        "⚠️ No se encontró la columna "
                        "'Identificador de organización'"
                    )

            except Exception as e:

                st.warning(
                    f"⚠️ No se pudo realizar el cruce con sucursales: {e}"
                )

        else:

            st.info(
                "ℹ️ Sin base de sucursales cargada."
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

        df["Fecha de carga"] = pd.Timestamp.now()

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

        # ---------------------------------------------------
        # CONCATENAR HISTÓRICO
        # ---------------------------------------------------
        
        if (
        
            df_historico is not None
        
            and
        
            not df_historico.empty
        
        ):
        
            df_final = pd.concat(
                [df_historico, df],
                ignore_index=True
            )
        
            df_final = df_final.drop_duplicates()
        
        else:
        
            df_final = df.copy()


        # --------------------------------------------
        # MÉTRICAS
        # --------------------------------------------

        st.markdown("---")
        st.subheader("📊 Resumen del Lote")

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.metric(
                "Filas Originales",
                filas_originales
            )

        with c2:
            st.metric(
                "Filas Válidas",
                filas_limpias
            )

        with c3:

            if "Número de serie" in df.columns:

                st.metric(
                    "Máquinas Únicas",
                    df["Número de serie"].nunique()
                )

        with c4:

            if "Nombre de organización" in df.columns:

                st.metric(
                    "Organizaciones",
                    df["Nombre de organización"].nunique()
                )

        # --------------------------------------------
        # VISTA PREVIA
        # --------------------------------------------

        st.markdown("---")
        st.subheader("👁️ Vista Previa")

        st.dataframe(
            df_final,
            use_container_width=True
        )

        st.markdown("---")

        st.subheader(
            "📌 Guardar Serie Histórica"
        )
        
        if st.button(
        
            "🚀 Actualizar Serie Histórica en GitHub",
        
            type="primary"
        
        ):
        
            with st.spinner(
                "Guardando serie histórica..."
            ):
        
                exito, mensaje = guardar_en_github(
        
                    df_final,
        
                    gh_repo,
        
                    gh_path_cosecha,
        
                    gh_token,
        
                    commit_msg=(
                        "Actualización "
                        "Automatización de Cosecha"
                    )
        
                )
        
                if exito:
        
                    st.success(mensaje)
        
                    st.cache_data.clear()
        
                else:
        
                    st.error(mensaje)


        # --------------------------------------------
        # DESCARGA CSV
        # --------------------------------------------

        csv = (
            df_final
            .to_csv(index=False)
            .encode("utf-8")
        )


    except Exception as e:

        st.error(
            f"❌ Error al procesar archivo: {e}"
        )

else:

    st.info(
        "Esperando carga del archivo de Automatización de Cosecha..."
    )
