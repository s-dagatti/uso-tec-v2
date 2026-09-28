import streamlit as st
import pandas as pd

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
            df,
            use_container_width=True
        )

        # --------------------------------------------
        # DESCARGA CSV
        # --------------------------------------------

        csv = df.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(

            label="📥 Descargar CSV Procesado",

            data=csv,

            file_name="automatizacion_cosecha_procesado.csv",

            mime="text/csv"

        )

    except Exception as e:

        st.error(
            f"❌ Error al procesar archivo: {e}"
        )

else:

    st.info(
        "Esperando carga del archivo de Automatización de Cosecha..."
    )
