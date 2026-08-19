import io
import re
import pandas as pd
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
            if diff > 0.05:
                return f"🟢 Genial (+{diff:.2f}%)"
            elif diff < -0.05:
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

        # Función para identificar licencias PUK
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

        # Normalización del tipo para leyenda y agrupaciones
        def normalizar_tipo_puk(lic_val):
            val_str = str(lic_val).lower()
            if "avanzada" in val_str:
                return "Renovable Avanzada"
            return "Renovable Esencial"

        # Filtrar máquinas únicas que posean PUK
        df_puk = df_promedios[
            df_promedios["Licencia"].apply(es_licencia_puk)
        ].copy()

        if not df_puk.empty:
            # Parseo de fecha respetando día/mes/año (dayfirst=True)
            col_fecha_origen = (
                col_fin_licencia
                if col_fin_licencia in df_puk.columns
                else "Vencimiento Licencia"
            )

            df_puk["Fecha_venc_dt"] = pd.to_datetime(
                df_puk[col_fecha_origen], dayfirst=True, errors="coerce"
            )

            df_puk["Tipo_PUK"] = df_puk["Licencia"].apply(normalizar_tipo_puk)

            # Fechas de referencia para cálculos
            hoy = pd.Timestamp.today().normalize()
            proximo_mes = hoy + pd.Timedelta(days=30)

            # --- CÁLCULO DE KPIS PUK ---
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
                st.info(
                    "No hay fechas de vencimiento válidas registradas para"
                    " graficar."
                )

            # --- TABLA DETALLE DE PUKS ---
            st.markdown("##### 📋 Detalle de Equipos con Licencia PUK")

            # Formatear la fecha para mostrar explícitamente en formato DD/MM/YYYY
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
        # (Fuera del else de PUKs para que siempre se evalúe independientemente)
        st.markdown("---")
        st.subheader("📈 Evolución Semanal del Uso de AutoTrac™")
        st.caption(
            "Evolución semanal de la cantidad de máquinas aptas que utilizaron"
            " AutoTrac™ (≥ 1%) y el porcentaje promedio de uso registrado."
        )

        # Preparar base filtrada con fechas válidas
        df_hist_semanal = df_filtrado_aptas.dropna(subset=["Fecha_fin_dt"]).copy()

        if not df_hist_semanal.empty:
            # Agrupación por semana (inicio de semana)
            df_hist_semanal["Semana_Inicio"] = df_hist_semanal[
                "Fecha_fin_dt"
            ].dt.to_period("W").dt.start_time

            # Registros con AutoTrac activo >= 1%
            df_autotrac_semanal = df_hist_semanal[
                pd.notna(df_hist_semanal["AutoTrac™ Activo"])
                & (df_hist_semanal["AutoTrac™ Activo"] >= 1)
            ]

            # Agrupación por semana
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
                # Gráfico con doble eje Y
                fig_semanal = make_subplots(specs=[[{"secondary_y": True}]])

                # Barras: Cantidad de máquinas
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

                # Línea: % Promedio de AutoTrac
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

        # ==========================================
        # PESTAÑA: GUIADO AVANZADO
        # ==========================================
        with tab_guiado:
            st.header("🎯 Análisis de Guiado Avanzado")
            st.caption(
                "Monitoreo de tecnologías avanzadas para monitores con versión de software"
                " 23.3 o superior."
            )
            
            # 1. Lista de tecnologías a evaluar
            cols_guiado = [
                "AutoPath™ Activo",
                "Automatización de maniobras AutoTrac™ Activo",
                "Guiado pasivo de implemento AutoTrac™ Activo",
                "John Deere Machine Sync Vehículo guía activo",
            ]
            
            # Verificar columnas presentes en el DataFrame
            cols_presentes = [c for c in cols_guiado if c in df_filtrado.columns]
            
            if not df_filtrado.empty and cols_presentes:
                df_ga = df_filtrado.copy()
            
                # --- FILTRO POR VERSIÓN DE SOFTWARE (>= 23.3) ---
                col_sw = [c for c in df_ga.columns if "software" in c.lower()]
                if col_sw:
                    # Extrae la versión numérica principal (ej: '23.3.1' -> 23.3)
                    df_ga["sw_num"] = pd.to_numeric(
                        df_ga[col_sw[0]].astype(str).str.extract(r"(\d+\.\d+)")[0],
                        errors="coerce",
                    )
                    df_ga = df_ga[df_ga["sw_num"] >= 23.3]
            
                if not df_ga.empty:
                    # --- DETERMINACIÓN DE FOTO DE HOY Y PERÍODO ANTERIOR ---
                    max_fecha = (
                        df_ga["Fecha_fin_dt"].max() if "Fecha_fin_dt" in df_ga.columns else None
                    )
            
                    if pd.notna(max_fecha):
                        inicio_ult_periodo = max_fecha - pd.Timedelta(days=7)
                        inicio_prev_periodo = max_fecha - pd.Timedelta(days=14)
            
                        df_actual = df_ga[df_ga["Fecha_fin_dt"] > inicio_ult_periodo].copy()
                        df_anterior = df_ga[
                            (df_ga["Fecha_fin_dt"] <= inicio_ult_periodo)
                            & (df_ga["Fecha_fin_dt"] > inicio_prev_periodo)
                        ].copy()
            
                        # --- LIMPIEZA: Convertir < 1% a NaN para NO afectar promedios ---
                        for col in cols_presentes:
                            df_actual[f"{col}_clean"] = df_actual[col].apply(
                                lambda x: x if (pd.notna(x) and x >= 1) else np.nan
                            )
                            df_anterior[f"{col}_clean"] = df_anterior[col].apply(
                                lambda x: x if (pd.notna(x) and x >= 1) else np.nan
                            )
            
                        cols_clean = [f"{col}_clean" for col in cols_presentes]
            
                        # --- CÁLCULO DE KPIS GENERALES ---
                        # 1. Promedio Guiado Avanzado General (ignora NaNs)
                        vals_act = df_actual[cols_clean].values.flatten()
                        vals_act = vals_act[~np.isnan(vals_act)]
                        prom_gen_act = np.mean(vals_act) if len(vals_act) > 0 else 0.0
            
                        vals_ant = df_anterior[cols_clean].values.flatten()
                        vals_ant = vals_ant[~np.isnan(vals_ant)]
                        prom_gen_ant = np.mean(vals_ant) if len(vals_ant) > 0 else 0.0
            
                        diff_prom_gen = prom_gen_act - prom_gen_ant
            
                        # 2. Cantidad de máquinas usando al menos 1 tecnología (>= 1%)
                        maq_act = df_actual[df_actual[cols_clean].notna().any(axis=1)][
                            "Máquina"
                        ].nunique()
                        maq_ant = df_anterior[df_anterior[cols_clean].notna().any(axis=1)][
                            "Máquina"
                        ].nunique()
                        diff_maq = maq_act - maq_ant
            
                        # --- DESPLIEGUE KPIS GENERALES ---
                        st.markdown("### 📌 Resumen General (Foto de Hoy vs. Período Anterior)")
                        col_kpi1, col_kpi2 = st.columns(2)
            
                        with col_kpi1:
                            st.metric(
                                label="📊 Promedio Guiado Avanzado Gral.",
                                value=f"{prom_gen_act:.2f}%" if prom_gen_act > 0 else "0.00%",
                                delta=f"{diff_prom_gen:+.2f}% vs. ant.",
                            )
            
                        with col_kpi2:
                            st.metric(
                                label="🚜 Máquinas Activas en Guiado Avanzado",
                                value=f"{maq_act}",
                                delta=f"{diff_maq:+d} máq. vs. ant.",
                            )
            
                        st.markdown("---")
                        st.markdown("### 🛠️ Uso por Tecnología")
            
                        # --- DESPLIEGUE KPIS INDIVIDUALES (4 COLUMNAS) ---
                        col_t1, col_t2, col_t3, col_t4 = st.columns(4)
                        cols_widgets = [col_t1, col_t2, col_t3, col_t4]
            
                        nombres_cortos = {
                            "AutoPath™ Activo": "AutoPath™",
                            "Automatización de maniobras AutoTrac™ Activo": "Aut. Maniobras (iTEC)",
                            "Guiado pasivo de implemento AutoTrac™ Activo": "Guiado Pasivo Impl.",
                            "John Deere Machine Sync Vehículo guía activo": "Machine Sync",
                        }
            
                        for idx, col in enumerate(cols_guiado):
                            with cols_widgets[idx]:
                                if col in cols_presentes:
                                    val_act = df_actual[f"{col}_clean"].mean()
                                    val_ant = df_anterior[f"{col}_clean"].mean()
            
                                    val_act_num = val_act if pd.notna(val_act) else 0.0
                                    val_ant_num = val_ant if pd.notna(val_ant) else 0.0
                                    diff_tech = val_act_num - val_ant_num
            
                                    label_tech = nombres_cortos.get(col, col)
            
                                    st.metric(
                                        label=f"📡 {label_tech}",
                                        value=f"{val_act:.2f}%"
                                        if pd.notna(val_act)
                                        else "Sin uso (<1%)",
                                        delta=f"{diff_tech:+.2f}% vs. ant."
                                        if (pd.notna(val_act) or pd.notna(val_ant))
                                        else None,
                                    )
                                else:
                                    st.metric(
                                        label=f"📡 {nombres_cortos.get(col, col)}",
                                        value="N/D",
                                    )
                    else:
                        st.info("No hay fechas válidas para construir la foto de hoy.")
                else:
                    st.warning(
                        "⚠️ No se encontraron equipos con versión de software 23.3 o superior."
                    )
            else:
                st.info("No hay datos disponibles para las tecnologías de Guiado Avanzado.")
          
    else:
        st.write(
            "No hay máquinas aptas con datos disponibles para mostrar en la tabla."
        )
