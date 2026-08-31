import io
import re
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st

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

# Identificación dinámica de columnas de Licencia, Vencimiento y Estado Licencia
col_licencia = 'Licencia' if 'Licencia' in df_raw.columns else ('licencia' if 'licencia' in df_raw.columns else None)
col_fin_licencia = 'Fin Licenicia' if 'Fin Licenicia' in df_raw.columns else ('Fin Licencia' if 'Fin Licencia' in df_raw.columns else None)

col_estado_licencia = None
for c in ['Estado Licencia', 'estado licencia', 'Estado de Licencia', 'Estado de la licencia', 'Estado_Licencia']:
    if c in df_raw.columns:
        col_estado_licencia = c
        break

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

# Filtro: Estado Licencia (directo de la columna de la base de datos)
if col_estado_licencia and col_estado_licencia in df_sidebar.columns:
    estados_licencia = ["Todos"] + sorted([str(e).strip() for e in df_sidebar[col_estado_licencia].dropna().unique() if str(e).strip() != ''])
    sel_estado_licencia = st.sidebar.selectbox("Estado Licencia", estados_licencia)
else:
    sel_estado_licencia = "Todos"

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

if col_estado_licencia and sel_estado_licencia != "Todos":
    df_filtrado_raw = df_filtrado_raw[df_filtrado_raw[col_estado_licencia].astype(str).str.strip() == sel_estado_licencia]

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
tab_autotrac, tab_guiado = st.tabs(["🎯 Uso de AutoTrac", "🛰️ Guiado Avanzado"])

with tab_autotrac:
    st.title("🎯 Uso de AutoTrac™")
    st.caption("Promedio de adopción para monitores aptos (**software ≥ 23.3**) considerando registros con **uso ≥ 1%**.")

    # --- PERÍODO EVALUADO ---
    if not df_filtrado_raw.empty:
        primera_fecha = df_filtrado_raw['Fecha_inicio_dt'].min().strftime('%d/%m/%Y')
        ultima_fecha = df_filtrado_raw['Fecha_fin_dt'].max().strftime('%d/%m/%Y')
        st.info(f"🗓️ **Período Evaluado:** Desde **{primera_fecha}** hasta **{ultima_fecha}**")
    else:
        st.warning("⚠️ No existen datos para los filtros seleccionados en el período indicado.")

    # --- CÁLCULO DE KPIS ---
    promedio_autotrac = (
        df_filtrado_autotrac["AutoTrac™ Activo"].mean()
        if not df_filtrado_autotrac.empty
        else None
    )

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

    if promedio_autotrac is not None and promedio_ult_semana_kpi is not None:
        delta_autotrac = promedio_ult_semana_kpi - promedio_autotrac
        delta_str = f"{delta_autotrac:+.2f}% vs. últ. semana"
    else:
        delta_str = None

    maquinas_totales = df_filtrado_raw["Número de serie de la máquina"].nunique()
    maquinas_aptas = df_filtrado_aptas["Número de serie de la máquina"].nunique()

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
        df_filtrado_aptas.loc[:, "AutoTrac_Filtrado"] = df_filtrado_aptas[
            "AutoTrac™ Activo"
        ].apply(lambda x: x if (pd.notna(x) and x >= 1) else None)

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

        # Extraer los últimos datos del período para Sucursal, Licencia, Vencimiento y Estado Licencia
        cols_ultimos = ["Sucursal"]
        if col_licencia and col_licencia in df_filtrado_aptas.columns:
            cols_ultimos.append(col_licencia)
        if col_fin_licencia and col_fin_licencia in df_filtrado_aptas.columns:
            cols_ultimos.append(col_fin_licencia)
        if col_estado_licencia and col_estado_licencia in df_filtrado_aptas.columns:
            cols_ultimos.append(col_estado_licencia)

        df_ultimos_datos = (
            df_filtrado_aptas.sort_values("Fecha_fin_dt")
            .groupby("Máquina")[cols_ultimos]
            .last()
            .reset_index()
        )

        group_cols = ["Máquina", "Tipo", "Organización"]

        df_promedios = df_filtrado_aptas.groupby(
            group_cols, dropna=False, as_index=False
        ).agg(
            Promedio_AutoTrac=("AutoTrac_Filtrado", "mean"),
            Períodos_Con_Uso=("AutoTrac_Filtrado", "count"),
            Total_Períodos=("Fecha_inicio_dt", "count"),
        )

        df_promedios = pd.merge(
            df_promedios, df_ultimos_datos, on="Máquina", how="left"
        )

        df_promedios = pd.merge(
            df_promedios, df_ult_semana, on="Máquina", how="left"
        )

        # --- SLIDER DE FILTRADO POR % DE USO PROMEDIO ---
        col_slider, _ = st.columns([2, 1])
        with col_slider:
            rango_uso = st.slider(
                "🎚️ Filtrar por % de uso promedio de AutoTrac™",
                min_value=0.0,
                max_value=100.0,
                value=(0.0, 100.0),
                step=1.0,
                format="%.0f%%"
            )

        min_uso, max_uso = rango_uso

        # Condición de filtro: dentro del rango, o sin registros si el mínimo es 0%
        condicion_rango = (df_promedios["Promedio_AutoTrac"] >= min_uso) & (df_promedios["Promedio_AutoTrac"] <= max_uso)
        if min_uso == 0.0:
            condicion_rango = condicion_rango | df_promedios["Promedio_AutoTrac"].isna()

        df_promedios = df_promedios[condicion_rango].copy()

        def evaluar_evolucion(row):
            prom_gen = row["Promedio_AutoTrac"]
            prom_ult = row["Promedio_Ultima_Semana"]

            if pd.isna(prom_gen) or pd.isna(prom_ult):
                return "⚪ Sin datos últ. semana"

            diff = prom_ult - prom_gen
            # Cambio directo en puntos porcentuales reales
            if diff > 0.5:
                return f"🟢 Genial (+{diff:.2f}%)"
            elif diff < -0.5:
                return f"🔴 Peligro ({diff:.2f}%)"
            else:
                return "➡️ Estable (0.00%)"

        df_promedios["Evolución AutoTrac"] = df_promedios.apply(
            evaluar_evolucion, axis=1
        )

        df_promedios["AutoTrac™ Promedio (%)"] = df_promedios[
            "Promedio_AutoTrac"
        ].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "Sin Registros ( < 1% )")

        if col_licencia and col_licencia in df_promedios.columns:
            df_promedios["Licencia"] = df_promedios[col_licencia].fillna("-")
        else:
            df_promedios["Licencia"] = "-"

        if col_fin_licencia and col_fin_licencia in df_promedios.columns:
            df_promedios["Vencimiento Licencia"] = pd.to_datetime(
                df_promedios[col_fin_licencia], dayfirst=True, errors="coerce"
            ).dt.strftime("%d/%m/%Y").fillna("-")
        else:
            df_promedios["Vencimiento Licencia"] = "-"

        if col_estado_licencia and col_estado_licencia in df_promedios.columns:
            df_promedios["Estado Licencia"] = df_promedios[col_estado_licencia].fillna("-")
        else:
            df_promedios["Estado Licencia"] = "-"

        cols_display = [
            "Máquina",
            "Tipo",
            "Organización",
            "Sucursal",
            "AutoTrac™ Promedio (%)",
            "Evolución AutoTrac",
            "Licencia",
            "Vencimiento Licencia",
            "Estado Licencia",
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

        def colorear_estado_licencia(val):
            if isinstance(val, str):
                val_lower = val.lower().strip()
                if "vigente" in val_lower:
                    return "color: #2e7d32; font-weight: bold;"
                elif "vencid" in val_lower:
                    return "color: #d32f2f; font-weight: bold;"
                elif "sin licencia" in val_lower or val == "-":
                    return "color: #757575;"
            return ""

        styled_df = df_promedios_display.style

        if hasattr(styled_df, "map"):
            styled_df = (
                styled_df.map(colorear_evolucion, subset=["Evolución AutoTrac"])
                .map(colorear_estado_licencia, subset=["Estado Licencia"])
            )
        else:
            styled_df = (
                styled_df.applymap(colorear_evolucion, subset=["Evolución AutoTrac"])
                .applymap(colorear_estado_licencia, subset=["Estado Licencia"])
            )

        st.dataframe(styled_df, use_container_width=True)

        # --- 7. ANÁLISIS DEL ESTADO DE KITS PUK (LICENCIAS RENOVABLES) ---
        st.markdown("---")
        st.subheader("📦 Análisis del Estado de Kits PUK (Licencias Renovables)")
        st.caption(
            "Los PUKs incluyen licencias **Renovable Esencial** y **Renovable"
            " Avanzada**, las cuales requieren estar activas para operar AutoTrac™."
        )

        def es_licencia_puk(lic_val):
            if pd.isna(lic_val):
                return False
            val_str = str(lic_val).lower().strip()
            return (
                ("renovable" in val_str)
                or ("esencial" in val_str)
                or ("escencial" in val_str)
                or ("avanzada" in val_str)
            )

        def normalizar_tipo_puk(lic_val):
            val_str = str(lic_val).lower()
            if "avanzada" in val_str:
                return "Renovable Avanzada"
            return "Renovable Esencial"

        df_puk = df_promedios[
            df_promedios["Licencia"].apply(es_licencia_puk)
        ].copy()

        if not df_puk.empty:
            col_fecha_origen = (
                col_fin_licencia
                if col_fin_licencia in df_puk.columns
                else "Vencimiento Licencia"
            )

            df_puk["Fecha_venc_dt"] = pd.to_datetime(
                df_puk[col_fecha_origen], dayfirst=True, errors="coerce"
            )

            df_puk["Tipo_PUK"] = df_puk["Licencia"].apply(normalizar_tipo_puk)

            hoy = pd.Timestamp.today().normalize()
            proximo_mes = hoy + pd.Timedelta(days=30)

            if "Estado Licencia" in df_puk.columns:
                estado_clean = (
                    df_puk["Estado Licencia"].astype(str).str.lower().str.strip()
                )
                puk_activas = df_puk[estado_clean == "vigente"]
                puk_vencidas = df_puk[
                    (estado_clean.str.contains("vencid", na=False))
                    | (estado_clean.str.contains("no tiene", na=False))
                ]
            else:
                puk_activas = df_puk[df_puk["Fecha_venc_dt"] >= hoy]
                puk_vencidas = df_puk[
                    (df_puk["Fecha_venc_dt"] < hoy)
                    | (df_puk["Vencimiento Licencia"] == "-")
                ]

            puk_por_vencer = df_puk[
                (df_puk["Fecha_venc_dt"] >= hoy)
                & (df_puk["Fecha_venc_dt"] <= proximo_mes)
            ]

            col_puk1, col_puk2, col_puk3 = st.columns(3)

            with col_puk1:
                st.metric(
                    label="🟢 Licencias Activas (PUK)", value=len(puk_activas)
                )

            with col_puk2:
                st.metric(
                    label="🔴 Licencias Vencidas / Sin Lic. (PUK)",
                    value=len(puk_vencidas),
                )

            with col_puk3:
                st.metric(
                    label="⚠️ Por Vencer Próximo Mes", value=len(puk_por_vencer)
                )

            # --- GRÁFICO DE VENCIMIENTOS EN EL TIEMPO ---
            df_puk_chart = df_puk.dropna(subset=["Fecha_venc_dt"]).copy()

            if not df_puk_chart.empty:
                df_puk_chart["Año_Mes"] = (
                    df_puk_chart["Fecha_venc_dt"].dt.to_period("M").astype(str)
                )

                df_grouped = (
                    df_puk_chart.groupby(["Año_Mes", "Tipo_PUK"])
                    .size()
                    .reset_index(name="Cantidad")
                    .sort_values("Año_Mes")
                )

                fig_puk = px.bar(
                    df_grouped,
                    x="Año_Mes",
                    y="Cantidad",
                    color="Tipo_PUK",
                    barmode="group",
                    title="📅 Cronograma Histórico y Futuro de Vencimientos PUK",
                    labels={
                        "Año_Mes": "Mes de Vencimiento",
                        "Cantidad": "Cantidad de Licencias",
                        "Tipo_PUK": "Tipo de Licencia",
                    },
                    color_discrete_map={
                        "Renovable Esencial": "#2b5c8f",
                        "Renovable Avanzada": "#367c2b",
                    },
                    text="Cantidad",
                )

                fig_puk.update_layout(
                    xaxis_type="category",
                    xaxis_title="Mes de Vencimiento",
                    yaxis_title="Cantidad de Licencias",
                    legend_title_text="Tipo de PUK",
                    hovermode="x unified",
                )

                st.plotly_chart(fig_puk, use_container_width=True)
            else:
                st.info("No hay fechas de vencimiento válidas registradas para graficar.")

            # --- TABLA DETALLE DE PUKS ---
            st.markdown("##### 📋 Detalle de Equipos con Licencia PUK")

            df_puk["Vencimiento Licencia"] = df_puk["Fecha_venc_dt"].apply(
                lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else "-"
            )

            df_puk_display = df_puk.sort_values(
                by="Fecha_venc_dt", ascending=True, na_position="last"
            )[cols_display]

            styled_puk = df_puk_display.style

            if hasattr(styled_puk, "map"):
                styled_puk = styled_puk.map(
                    colorear_evolucion, subset=["Evolución AutoTrac"]
                ).map(colorear_estado_licencia, subset=["Estado Licencia"])
            else:
                styled_puk = styled_puk.applymap(
                    colorear_evolucion, subset=["Evolución AutoTrac"]
                ).applymap(colorear_estado_licencia, subset=["Estado Licencia"])

            st.dataframe(styled_puk, use_container_width=True)

        else:
            st.info(
                "ℹ️ No se encontraron máquinas con licencias PUK (Renovable"
                " Esencial / Avanzada) para los filtros seleccionados."
            )

        # --- 8. GRÁFICO HISTÓRICO SEMANAL DE ADOPCIÓN DE AUTOTRAC ---
        st.markdown("---")
        st.subheader("📈 Evolución Semanal del Uso de AutoTrac™")
        st.caption(
            "Evolución semanal de la cantidad de máquinas aptas que utilizaron"
            " AutoTrac™ (≥ 1%) y el porcentaje promedio de uso registrado."
        )

        df_hist_semanal = df_filtrado_aptas.dropna(subset=["Fecha_fin_dt"]).copy()

        if not df_hist_semanal.empty:
            df_hist_semanal["Semana_Inicio"] = df_hist_semanal[
                "Fecha_fin_dt"
            ].dt.to_period("W").dt.start_time

            df_autotrac_semanal = df_hist_semanal[
                pd.notna(df_hist_semanal["AutoTrac™ Activo"])
                & (df_hist_semanal["AutoTrac™ Activo"] >= 1)
            ]

            df_semanal = (
                df_autotrac_semanal.groupby("Semana_Inicio")
                .agg(
                    Cant_Maquinas=("Máquina", "nunique"),
                    Promedio_AutoTrac=("AutoTrac™ Activo", "mean"),
                )
                .reset_index()
                .sort_values("Semana_Inicio")
            )

            df_semanal["Semana_Str"] = df_semanal["Semana_Inicio"].dt.strftime(
                "%d/%m/%Y"
            )

            if not df_semanal.empty:
                fig_semanal = make_subplots(specs=[[{"secondary_y": True}]])

                fig_semanal.add_trace(
                    go.Bar(
                        x=df_semanal["Semana_Str"],
                        y=df_semanal["Cant_Maquinas"],
                        name="Máquinas con AutoTrac™",
                        marker_color="#2b5c8f",
                        text=df_semanal["Cant_Maquinas"],
                        textposition="auto",
                    ),
                    secondary_y=False,
                )

                fig_semanal.add_trace(
                    go.Scatter(
                        x=df_semanal["Semana_Str"],
                        y=df_semanal["Promedio_AutoTrac"],
                        name="% Promedio AutoTrac™",
                        mode="lines+markers+text",
                        line=dict(color="#367c2b", width=3),
                        marker=dict(size=8),
                        text=df_semanal["Promedio_AutoTrac"].apply(
                            lambda x: f"{x:.1f}%"
                        ),
                        textposition="top center",
                    ),
                    secondary_y=True,
                )

                fig_semanal.update_layout(
                    title="📅 Tendencia Semanal: Equipos Activos vs. % de Adopción",
                    xaxis_title="Semana",
                    hovermode="x unified",
                    legend=dict(
                        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
                    ),
                    margin=dict(t=50, b=40, l=10, r=10),
                )

                fig_semanal.update_yaxes(
                    title_text="Cantidad de Máquinas", secondary_y=False
                )
                fig_semanal.update_yaxes(
                    title_text="% Promedio AutoTrac™",
                    secondary_y=True,
                    range=[0, 110],
                )

                st.plotly_chart(fig_semanal, use_container_width=True)
            else:
                st.info(
                    "No se registraron equipos con uso de AutoTrac™ ≥ 1% en el"
                    " período seleccionado."
                )
        else:
            st.info("No existen fechas válidas registradas para agrupar por semana.")

        # ==============================================================================
        # PESTAÑA: GUIADO AVANZADO
        # ==============================================================================
        with tab_guiado:

            # Columnas exactas de Guiado Avanzado
            cols_guiado_avanzado = [
                "AutoPath™ Activo",
                "Automatización de maniobras AutoTrac™ Activo",
                "Guiado pasivo de implemento AutoTrac™ Activo",
                "John Deere Machine Sync Vehículo guía activo",
            ]
            
            nombres_cortos = {
                "AutoPath™ Activo": "AutoPath™",
                "Automatización de maniobras AutoTrac™ Activo": "Turn Automation",
                "Guiado pasivo de implemento AutoTrac™ Activo": "Implement Guidance",
                "John Deere Machine Sync Vehículo guía activo": "Machine Sync",
            }
            
            # Filtrar únicamente las columnas que existen en la base
            cols_presentes = [c for c in cols_guiado_avanzado if c in df_filtrado_raw.columns]
            
            if cols_presentes:
                # 1. Monitores aptos (software >= 23.3) dentro del período seleccionado
                df_ga = df_filtrado_raw[df_filtrado_raw["es_valida"]].copy()
            
                if not df_ga.empty:
                    col_sn = "Número de serie de la máquina" if "Número de serie de la máquina" in df_ga.columns else "Máquina"
                    
                    # 2. Limpieza y conversión numérica inicial
                    cols_clean = []
                    for col in cols_presentes:
                        clean_col = f"{col}_clean"
                        cols_clean.append(clean_col)
                        df_ga[col] = pd.to_numeric(df_ga[col], errors="coerce")
                        df_ga[clean_col] = df_ga[col].fillna(0.0) # Nulos a 0 para que los períodos sin registro cuenten como 0 si la máquina ya es adoptada
            
                    if col_sn in df_ga.columns:
                        # 3. FILTRO DE ADOPCIÓN: Identificar qué máquinas alguna vez superaron el 1% por tecnología
                        # Creamos una copia de trabajo para filtrar por este criterio histórico
                        df_adoptadas_mask = pd.DataFrame(index=df_ga.index)
                        
                        for col, clean_col in zip(cols_presentes, cols_clean):
                            # Identificar series de máquinas que en algún registro del período tuvieron > 1% en esta tecnología
                            maq_superaron = df_ga.groupby(col_sn)[clean_col].transform(lambda x: (x > 0.1).any())
                            # Si superó alguna vez, filtramos sus registros: mantenemos sus datos (incluso si bajan a 0 después). Si jamás superó, se vuelve NaN/0
                            df_adoptadas_mask[clean_col] = df_ga[clean_col].where(maq_superaron, np.nan)
                        
                        # Reemplazamos las columnas _clean con las que ya aplican el filtro de adopción histórica
                        for clean_col in cols_clean:
                            df_ga[clean_col] = df_adoptadas_mask[clean_col]

                    # Identificar la última semana dentro del período seleccionado
                    max_fecha_ga = df_ga["Fecha_fin_dt"].max()
                    inicio_ult_semana = max_fecha_ga - pd.Timedelta(days=7) if pd.notna(max_fecha_ga) else None
            
                    df_ga_ult_semana = (
                        df_ga[df_ga["Fecha_fin_dt"] >= inicio_ult_semana]
                        if inicio_ult_semana is not None
                        else pd.DataFrame()
                    )
            
                    # ------------------------------------------------------------------
                    # BLOQUE 1: KPIS GENERALES (PROMEDIO ENTRE LAS 4 TECNOLOGÍAS)
                    # ------------------------------------------------------------------
                    st.subheader("🌐 Resumen General de Guiado Avanzado")
            
                    # Promedio individual de cada tecnología (considerando ceros de máquinas ya adoptadas)
                    medias_periodo_cols = [df_ga[c].mean() for c in cols_clean]
                    medias_periodo_cols_num = [m if pd.notna(m) else 0.0 for m in medias_periodo_cols]
                    
                    prom_gen_periodo = sum(medias_periodo_cols_num) / len(cols_guiado_avanzado) if len(cols_guiado_avanzado) > 0 else None
            
                    # Lo mismo para la última semana
                    if not df_ga_ult_semana.empty:
                        medias_semana_cols = [df_ga_ult_semana[c].mean() for c in cols_clean]
                        medias_semana_cols_num = [m if pd.notna(m) else 0.0 for m in medias_semana_cols]
                        prom_gen_semana = sum(medias_semana_cols_num) / len(cols_guiado_avanzado) if len(cols_guiado_avanzado) > 0 else None
                    else:
                        prom_gen_semana = None
            
                    tiene_datos_global = any(pd.notna(m) for m in medias_periodo_cols)
            
                    val_gen_str = f"{prom_gen_periodo:.2f}%" if (prom_gen_periodo is not None and tiene_datos_global) else "Sin Datos"
                    if prom_gen_periodo is not None and prom_gen_semana is not None and tiene_datos_global:
                        delta_gen = prom_gen_semana - prom_gen_periodo
                        delta_gen_str = f"{delta_gen:+.2f}% vs. últ. semana"
                    else:
                        delta_gen_str = None
            
                    # B. Cantidad de Máquinas Activas en el Período (máquinas adoptadas en al menos una tecnología)
                    mask_periodo = df_ga[cols_clean].notna().any(axis=1)
                    cant_maq_periodo = df_ga.loc[mask_periodo, col_sn].nunique() if col_sn in df_ga.columns else 0
            
                    if not df_ga_ult_semana.empty and col_sn in df_ga_ult_semana.columns:
                        mask_semana = df_ga_ult_semana[cols_clean].notna().any(axis=1)
                        cant_maq_semana = df_ga_ult_semana.loc[mask_semana, col_sn].nunique()
                        diff_maq = cant_maq_semana - cant_maq_periodo
                        delta_maq_str = f"{diff_maq:+d} máq. vs. últ. semana"
                    else:
                        delta_maq_str = None
            
                    kpi_gen1, kpi_gen2 = st.columns(2)
            
                    with kpi_gen1:
                        st.metric(
                            label="Promedio General Guiado Avanzado (Período)",
                            value=val_gen_str,
                            delta=delta_gen_str,
                        )
            
                    with kpi_gen2:
                        st.metric(
                            label="Máquinas Activas (Con adopción > 1% en período)",
                            value=f"{cant_maq_periodo:,}".replace(",", "."),
                            delta=delta_maq_str,
                        )
            
                    st.markdown("---")
            
                    # ------------------------------------------------------------------
                    # BLOQUE 2: KPIS INDIVIDUALES POR TECNOLOGÍA
                    # ------------------------------------------------------------------
                    st.subheader("📊 % de Uso Promedio por Tecnología (Período Completo)")
            
                    cols_widgets = st.columns(len(cols_presentes))
            
                    for idx, col in enumerate(cols_presentes):
                        clean_col = f"{col}_clean"
                        with cols_widgets[idx]:
                            nombre_kpi = nombres_cortos.get(col, col)
            
                            prom_periodo = df_ga[clean_col].mean()
                            prom_semana = (
                                df_ga_ult_semana[clean_col].mean()
                                if not df_ga_ult_semana.empty
                                else None
                            )
            
                            val_act_str = f"{prom_periodo:.2f}%" if pd.notna(prom_periodo) else "Sin Datos"
            
                            if pd.notna(prom_periodo) and pd.notna(prom_semana):
                                diff = prom_semana - prom_periodo
                                delta_str = f"{diff:+.2f}% vs. últ. semana"
                            else:
                                delta_str = None
            
                            st.metric(
                                label=nombre_kpi,
                                value=val_act_str,
                                delta=delta_str,
                            )
            
                    # ------------------------------------------------------------------
                    # BLOQUE 3: TABLA DETALLE POR MÁQUINA (SOLO MÁQUINAS ADOPTADAS EN AUTOPATH)
                    # ------------------------------------------------------------------
                    st.markdown("---")
                    st.subheader("📋 Detalle de AutoPath™ y Licencias por Máquina")
            
                    col_maq = "Máquina" if "Máquina" in df_ga.columns else ("Número de serie de la máquina" if "Número de serie de la máquina" in df_ga.columns else None)
                    col_tipo = "Tipo" if "Tipo" in df_ga.columns else ("Tipo de máquina" if "Tipo de máquina" in df_ga.columns else None)
                    col_org = "Organización" if "Organización" in df_ga.columns else ("Organizacion" if "Organizacion" in df_ga.columns else None)
                    col_suc = "Sucursal" if "Sucursal" in df_ga.columns else None
            
                    group_keys = [c for c in [col_maq, col_tipo, col_org, col_suc] if c and c in df_ga.columns]
            
                    if group_keys and "AutoPath™ Activo_clean" in df_ga.columns:
                        # Agrupamos por máquina considerando ya el filtro de adopción aplicado en el _clean
                        ap_periodo = df_ga.groupby(group_keys)["AutoPath™ Activo_clean"].mean().reset_index()
                        ap_periodo.rename(columns={"AutoPath™ Activo_clean": "AutoPath™ Activo"}, inplace=True)
            
                        # FILTRO PARA LA TABLA: Solo mantener las máquinas que tienen datos válidos (es decir, que superaron alguna vez el 1%)
                        ap_periodo = ap_periodo[ap_periodo["AutoPath™ Activo"].notna()].copy()
            
                        if not ap_periodo.empty:
                            if not df_ga_ult_semana.empty:
                                ap_semana = df_ga_ult_semana.groupby(group_keys)["AutoPath™ Activo_clean"].mean().reset_index()
                                ap_semana.rename(columns={"AutoPath™ Activo_clean": "AutoPath_semana"}, inplace=True)
                                df_tabla_ap = pd.merge(ap_periodo, ap_semana, on=group_keys, how="left")
                            else:
                                df_tabla_ap = ap_periodo
                                df_tabla_ap["AutoPath_semana"] = np.nan
            
                            def calc_evolucion(row):
                                v_per = row["AutoPath™ Activo"]
                                v_sem = row["AutoPath_semana"]
                                if pd.notna(v_per) and pd.notna(v_sem):
                                    diff = v_sem - v_per
                                    return f"{diff:+.2f}%"
                                else:
                                    return "-"
            
                            df_tabla_ap["Evolución AutoPath"] = df_tabla_ap.apply(calc_evolucion, axis=1)
            
                            cols_lic_meta = [c for c in [col_licencia, col_fin_licencia, col_estado_licencia] if c and c in df_ga.columns]
                            if cols_lic_meta and col_maq:
                                df_lic_last = df_ga.sort_values("Fecha_fin_dt").groupby(col_maq)[cols_lic_meta].last().reset_index()
                                df_tabla_ap = pd.merge(df_tabla_ap, df_lic_last, on=col_maq, how="left")
            
                            df_tabla_ap["AutoPath™ Activo"] = df_tabla_ap["AutoPath™ Activo"].apply(
                                lambda x: f"{x:.2f}%" if pd.notna(x) else "-"
                            )
            
                            col_order_target = [
                                (col_maq, "Máquina"),
                                (col_tipo, "Tipo"),
                                (col_org, "Organización"),
                                (col_suc, "Sucursal"),
                                ("AutoPath™ Activo", "AutoPath™ Activo"),
                                ("Evolución AutoPath", "Evolución AutoPath"),
                                (col_licencia, "Licencia"),
                                (col_fin_licencia, "Vencimiento Licencia"),
                                (col_estado_licencia, "Estado Licencia"),
                            ]
            
                            cols_existentes_renombrar = {}
                            cols_para_mostrar = []
            
                            for orig, dest in col_order_target:
                                if orig and orig in df_tabla_ap.columns:
                                    cols_para_mostrar.append(orig)
                                    cols_existentes_renombrar[orig] = dest
            
                            df_final_view = df_tabla_ap[cols_para_mostrar].rename(columns=cols_existentes_renombrar)
            
                            st.dataframe(df_final_view, use_container_width=True)
                        else:
                            st.info("ℹ️ No se encontraron máquinas con adopción registrada (> 1%) de AutoPath™ en el período seleccionado.")
            
                    else:
                        st.info("ℹ️ No se encontraron suficientes datos o columnas para armar la tabla de AutoPath™.")
            
                else:
                    st.warning("⚠️ No se encontraron registros de monitores aptos (software ≥ 23.3) en el período seleccionado.")
            
            else:
                st.info("ℹ️ No se encontraron las columnas de Guiado Avanzado requeridas en el archivo cargado.")
                      
    else:
        st.write(
            "No hay máquinas aptas con datos disponibles para mostrar en la tabla."
        )
