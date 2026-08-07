import streamlit as st
import pandas as pd
import requests
import base64
import io

# Configuración de la página
st.set_page_config(
    page_title="Dashboard de Adopción Tecnológica - CONCI",
    page_icon="📊",
    layout="wide"
)

# --- CONFIGURACIÓN DE ARCHIVO EN GITHUB ---
NOMBRE_ARCHIVO_GITHUB = "data/base_datos_consolidada.xlsx"

# --- FUNCIÓN DE LECTURA DESDE GITHUB (CON CACHÉ) ---
@st.cache_data(ttl=300)
def cargar_datos_github():
    try:
        gh_config = st.secrets["github"]
        token = gh_config["token"]
        repo = gh_config["repo"]
        branch = gh_config.get("branch", "main")
        
        url = f"https://api.github.com/repos/{repo}/contents/{NOMBRE_ARCHIVO_GITHUB}?ref={branch}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            content_b64 = res.json()["content"]
            file_bytes = base64.b64decode(content_b64)
            df = pd.read_excel(io.BytesIO(file_bytes))
            return df
        else:
            st.error(f"⚠️ No se encontró la base de datos en GitHub (`{NOMBRE_ARCHIVO_GITHUB}`). Carga primero datos con la app de depuración.")
            return None
    except Exception as e:
        st.error(f"❌ Error al conectar con GitHub para leer la base de datos: {e}")
        return None

# --- ENCABEZADO Y REFRESCAR ---
col_head, col_btn = st.columns([4, 1])
with col_head:
    st.title("📊 Dashboard de Adopción Tecnológica")
with col_btn:
    if st.button("🔄 Refrescar Base"):
        st.cache_data.clear()
        st.rerun()

# --- CARGA DE DATOS ---
with st.spinner("Cargando la base de datos desde GitHub..."):
    df = cargar_datos_github()

if df is not None and not df.empty:
    
    # 1. PREPROCESAMIENTO DE FECHAS
    if 'Fecha Fin' in df.columns:
        df['Fecha_Fin_DT'] = pd.to_datetime(df['Fecha Fin'], errors='coerce')
    else:
        df['Fecha_Fin_DT'] = pd.NaT

    if 'Fecha Inicio' in df.columns:
        df['Fecha_Inicio_DT'] = pd.to_datetime(df['Fecha Inicio'], errors='coerce')
    else:
        df['Fecha_Inicio_DT'] = pd.NaT

    # Determinar el rango global de fechas
    fechas_validas = df['Fecha_Fin_DT'].dropna()
    if not fechas_validas.empty:
        min_date_global = df['Fecha_Inicio_DT'].dropna().min().date() if not df['Fecha_Inicio_DT'].dropna().empty else fechas_validas.min().date()
        max_date_global = fechas_validas.max().date()
        
        # Último período registrado para poner de default
        ultimo_fin = max_date_global
        ultimo_inicio = df[df['Fecha_Fin_DT'] == pd.to_datetime(ultimo_fin)]['Fecha_Inicio_DT'].min()
        default_inicio = ultimo_inicio.date() if pd.notna(ultimo_inicio) else min_date_global
    else:
        import datetime
        min_date_global = datetime.date(2025, 1, 1)
        max_date_global = datetime.date.today()
        default_inicio = min_date_global
        ultimo_fin = max_date_global

    # --- SIDEBAR: FILTROS ---
    st.sidebar.header("🔍 Filtros de Análisis")
    
    # Filtro 1: Sucursal
    sucursales = ["Todas"] + sorted([str(s) for s in df['Sucursal'].dropna().unique()]) if 'Sucursal' in df.columns else ["Todas"]
    sel_sucursal = st.sidebar.selectbox("1. Sucursal", sucursales)
    
    # Filtrar DF preliminar por sucursal para adaptar las Orgs disponibles
    df_pre = df.copy()
    if sel_sucursal != "Todas":
        df_pre = df_pre[df_pre['Sucursal'].astype(str) == sel_sucursal]
        
    # Filtro 2: Org Name
    orgs = ["Todas"] + sorted([str(o) for o in df_pre['Org Name'].dropna().unique()]) if 'Org Name' in df_pre.columns else ["Todas"]
    sel_org = st.sidebar.selectbox("2. Organización (Org Name)", orgs)
    
    # Filtro 3: Slider de Período Analizado (Por defecto en el último período)
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 Período Analizado")
    
    if min_date_global < max_date_global:
        rango_fechas = st.sidebar.slider(
            "Selecciona el rango de fechas:",
            min_value=min_date_global,
            max_value=max_date_global,
            value=(default_inicio, ultimo_fin)
        )
    else:
        rango_fechas = (min_date_global, max_date_global)
        st.sidebar.info(f"Fecha analizada: `{max_date_global}`")

    # --- APLICACIÓN DE FILTROS A LA BASE ---
    df_filtered = df.copy()
    
    if sel_sucursal != "Todas":
        df_filtered = df_filtered[df_filtered['Sucursal'].astype(str) == sel_sucursal]
        
    if sel_org != "Todas":
        df_filtered = df_filtered[df_filtered['Org Name'].astype(str) == sel_org]
        
    if 'Fecha_Fin_DT' in df_filtered.columns and not df_filtered['Fecha_Fin_DT'].dropna().empty:
        inicio_sel, fin_sel = rango_fechas
        mask_fecha = (df_filtered['Fecha_Fin_DT'].dt.date >= inicio_sel) & (df_filtered['Fecha_Fin_DT'].dt.date <= fin_sel)
        df_filtered = df_filtered[mask_fecha]

    # --- ESTRUCTURA DE PESTAÑAS (TABS POR TECNOLOGÍA) ---
    tab_autotrac, tab_proximas = st.tabs(["🛰️ AutoTrac", "🚧 Próximas Tecnologías"])

    # ==========================================
    # PESTAÑA 1: AUTOTRAC
    # ==========================================
    with tab_autotrac:
        st.subheader("Análisis de Adopción: AutoTrac")
        st.caption(f"Mostrando datos desde **{rango_fechas[0]}** hasta **{rango_fechas[1]}**")
        
        # --- CÁLCULO DE KPIS PARA AUTOTRAC ---
        if 'AutoTrac' in df_filtered.columns:
            # Excluir nulos para AutoTrac (Lógica de negocio: los nulos no se consideran 0)
            df_autotrac_valid = df_filtered[df_filtered['AutoTrac'].notna()].copy()
            
            # Convierte a numérico por seguridad si viene como texto/porcentaje
            df_autotrac_valid['AutoTrac_Num'] = pd.to_numeric(
                df_autotrac_valid['AutoTrac'].astype(str).str.replace('%', '').str.replace(',', '.'), 
                errors='coerce'
            )
            
            # Solo máquinas donde AutoTrac tiene un registro de uso/presencia
            # 1. Cantidad de máquinas únicas (por Machine Pin)
            if 'Machine Pin' in df_autotrac_valid.columns:
                cant_maquinas_autotrac = df_autotrac_valid['Machine Pin'].dropna().nunique()
            else:
                cant_maquinas_autotrac = len(df_autotrac_valid)
                
            # 2. Promedio % de uso de AutoTrac (ignora completamente los nulos)
            promedio_autotrac = df_autotrac_valid['AutoTrac_Num'].mean()
            
        else:
            cant_maquinas_autotrac = 0
            promedio_autotrac = 0.0

        # --- DESPLIEGUE DE KPIS ---
        kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
        
        kpi_col1.metric(
            label="🚜 Máquinas Usando AutoTrac",
            value=f"{cant_maquinas_autotrac} equipos",
            help="Cantidad de equipos únicos (sin repetir Machine Pin) con registro de uso de AutoTrac."
        )
        
        val_promedio_str = f"{promedio_autotrac:.1f}%" if pd.notna(promedio_autotrac) else "N/A"
        kpi_col2.metric(
            label="📈 % de Uso Promedio AutoTrac",
            value=val_promedio_str,
            help="Promedio de uso calculado únicamente sobre los registros con datos válidos (excluyendo campos nulos)."
        )
        
        kpi_col3.metric(
            label="📋 Total Registros Filtrados",
            value=len(df_filtered)
        )

        st.markdown("---")

        # --- TABLA DEL FINAL CON BUSCADOR ---
        st.subheader("🔍 Tabla Detallada de Equipos")
        
        busqueda = st.text_input("🔎 Buscar por Machine Pin, Org Name o Número de Serie Monitor:", "")
        
        if busqueda:
            mask_search = (
                df_filtered['Machine Pin'].astype(str).str.contains(busqueda, case=False, na=False) |
                df_filtered['Org Name'].astype(str).str.contains(busqueda, case=False, na=False) |
                df_filtered['Número de Serie Monitor'].astype(str).str.contains(busqueda, case=False, na=False)
            )
            df_display = df_filtered[mask_search]
        else:
            df_display = df_filtered

        st.dataframe(df_display, use_container_width=True)
        st.caption(f"Mostrando {len(df_display)} registros de un total de {len(df_filtered)}.")

    # ==========================================
    # PESTAÑA 2: PRÓXIMAS TECNOLOGÍAS
    # ==========================================
    with tab_proximas:
        st.info("🚧 En los siguientes pasos iremos agregando los análisis para RowSense, AutoPath, Machine Sync, etc.")
