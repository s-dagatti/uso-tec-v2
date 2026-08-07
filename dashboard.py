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

    # --- DETECCIÓN DE NOMBRES DE COLUMNAS PARA FILTROS ---
    col_familia = 'Product Family' if 'Product Family' in df.columns else ('Familia de Producto' if 'Familia de Producto' in df.columns else None)
    col_licencia = 'Estado Licencia' if 'Estado Licencia' in df.columns else ('Tipo Licencia' if 'Tipo Licencia' in df.columns else None)

    # --- SIDEBAR: FILTROS CASCADA ---
    st.sidebar.header("🔍 Filtros de Análisis")
    
    # Filtro 1: Sucursal
    sucursales = ["Todas"] + sorted([str(s) for s in df['Sucursal'].dropna().unique()]) if 'Sucursal' in df.columns else ["Todas"]
    sel_sucursal = st.sidebar.selectbox("1. Sucursal", sucursales)
    
    # Filtrado dinámico 1
    df_pre = df.copy()
    if sel_sucursal != "Todas":
        df_pre = df_pre[df_pre['Sucursal'].astype(str) == sel_sucursal]
        
    # Filtro 2: Org Name
    orgs = ["Todas"] + sorted([str(o) for o in df_pre['Org Name'].dropna().unique()]) if 'Org Name' in df_pre.columns else ["Todas"]
    sel_org = st.sidebar.selectbox("2. Organización (Org Name)", orgs)
    
    # Filtrado dinámico 2
    if sel_org != "Todas":
        df_pre = df_pre[df_pre['Org Name'].astype(str) == sel_org]

    # Filtro 3: Familia de Máquina
    if col_familia and col_familia in df_pre.columns:
        familias = ["Todas"] + sorted([str(f) for f in df_pre[col_familia].dropna().unique()])
    else:
        familias = ["Todas"]
    sel_familia = st.sidebar.selectbox("3. Familia de Máquina", familias)

    # Filtrado dinámico 3
    if col_familia and sel_familia != "Todas":
        df_pre = df_pre[df_pre[col_familia].astype(str) == sel_familia]

    # Filtro 4: Tipo / Estado de Licencia
    if col_licencia and col_licencia in df_pre.columns:
        licencias = ["Todas"] + sorted([str(l) for l in df_pre[col_licencia].dropna().unique()])
    else:
        licencias = ["Todas"]
    sel_licencia = st.sidebar.selectbox("4. Tipo/Estado de Licencia", licencias)

    # Filtro 5: Slider de Período Analizado
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

    # --- APLICACIÓN DE TODOS LOS FILTROS A LA BASE ---
    df_filtered = df.copy()
    
    if sel_sucursal != "Todas":
        df_filtered = df_filtered[df_filtered['Sucursal'].astype(str) == sel_sucursal]
        
    if sel_org != "Todas":
        df_filtered = df_filtered[df_filtered['Org Name'].astype(str) == sel_org]

    if col_familia and sel_familia != "Todas":
        df_filtered = df_filtered[df_filtered[col_familia].astype(str) == sel_familia]

    if col_licencia and sel_licencia != "Todas":
        df_filtered = df_filtered[df_filtered[col_licencia].astype(str) == sel_licencia]
        
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
            # Excluir nulos para AutoTrac
            df_autotrac_valid = df_filtered[df_filtered['AutoTrac'].notna()].copy()
            
            # Convertir a número flotante
            df_autotrac_valid['AutoTrac_Num'] = pd.to_numeric(
                df_autotrac_valid['AutoTrac'].astype(str).str.replace('%', '').str.replace(',', '.'), 
                errors='coerce'
            )
            df_autotrac_valid = df_autotrac_valid[df_autotrac_valid['AutoTrac_Num'].notna()]
            
            # Cantidad de máquinas únicas (por Machine Pin)
            if 'Machine Pin' in df_autotrac_valid.columns:
                cant_maquinas_autotrac = df_autotrac_valid['Machine Pin'].dropna().nunique()
            else:
                cant_maquinas_autotrac = len(df_autotrac_valid)
                
            # Promedio % de uso (* 100 porque viene en decimales)
            promedio_autotrac = df_autotrac_valid['AutoTrac_Num'].mean() * 100
            
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
            help="Promedio de uso calculado únicamente sobre los registros con datos válidos (excluyendo campos nulos) multiplicado x100."
        )
        
        kpi_col3.metric(
            label="📋 Total Registros Filtrados",
            value=len(df_filtered)
        )

        st.markdown("---")

        # --- TABLA DEL FINAL CON BUSCADOR, LICENCIAS G5 Y AGRUPACIÓN ---
        st.subheader("🔍 Tabla Resumen por Equipo y Estado de Licencia AutoTrac")
        
        busqueda = st.text_input("🔎 Buscar por Machine Pin u Org Name:", "")
        
        if busqueda:
            mask_search = (
                df_filtered['Machine Pin'].astype(str).str.contains(busqueda, case=False, na=False) |
                df_filtered['Org Name'].astype(str).str.contains(busqueda, case=False, na=False)
            )
            df_display = df_filtered[mask_search].copy()
        else:
            df_display = df_filtered.copy()

        # --- IDENTIFICAR COLUMNAS CLAVE DE HARDWARE Y LICENCIAS ---
        col_hardware = next((c for c in df_display.columns if 'hardware' in c.lower()), None)
        col_lic_nombre = next((c for c in df_display.columns if 'nombre' in c.lower() and 'licencia' in c.lower()), 
                              next((c for c in df_display.columns if 'licencia' in c.lower() or 'license' in c.lower()), None))
        col_f_inicio = next((c for c in df_display.columns if 'inicio' in c.lower() and c not in ['Fecha_Inicio_DT']), 'Fecha Inicio')
        col_f_term = next((c for c in df_display.columns if 'termin' in c.lower() or 'fin' in c.lower() or 'vencim' in c.lower()), 'Fecha de Terminación')

        # --- EVALUACIÓN DE LICENCIA G5 REGISTRO POR REGISTRO ---
        def evaluar_licencia_autotrac(row):
            hw = str(row[col_hardware]).strip() if col_hardware and pd.notna(row[col_hardware]) else ""
            if hw.upper().startswith("G5"):
                lic_nombre = str(row[col_lic_nombre]).strip() if col_lic_nombre and pd.notna(row[col_lic_nombre]) else ""
                
                if lic_nombre.lower().startswith("autotrac"):
                    lic_info = lic_nombre
                elif lic_nombre:
                    lic_info = f"Otra: {lic_nombre}"
                else:
                    lic_info = "Sin Licencia AutoTrac"
                
                f_ini = str(row[col_f_inicio]).split('T')[0].split(' ')[0] if col_f_inicio in row and pd.notna(row[col_f_inicio]) else "-"
                f_fin = str(row[col_f_term]).split('T')[0].split(' ')[0] if col_f_term in row and pd.notna(row[col_f_term]) else "-"
                
                return pd.Series([hw, lic_info, f_ini, f_fin])
            else:
                hw_val = hw if hw else "Desconocido"
                return pd.Series([hw_val, "De base", "-", "-"])

        # Aplicar la lógica si la base no está vacía
        if not df_display.empty:
            res_lic = df_display.apply(evaluar_licencia_autotrac, axis=1)
            res_lic.columns = ['Hardware Monitor', 'Licencia AutoTrac', 'Fecha Inicio Licencia', 'Fecha Terminación Licencia']
            
            df_display['Hardware Monitor'] = res_lic['Hardware Monitor']
            df_display['Licencia AutoTrac'] = res_lic['Licencia AutoTrac']
            df_display['Fecha Inicio Licencia'] = res_lic['Fecha Inicio Licencia']
            df_display['Fecha Terminación Licencia'] = res_lic['Fecha Terminación Licencia']

            # Convertir AutoTrac a flotante * 100
            df_display['AutoTrac_Num'] = pd.to_numeric(
                df_display['AutoTrac'].astype(str).str.replace('%', '').str.replace(',', '.'), 
                errors='coerce'
            ) * 100

            # --- AGRUPACIÓN POR NÚMERO DE SERIE DE MÁQUINA (Machine Pin) ---
            cols_grupo = ['Sucursal', 'Org Name', 'Product Family', 'Machine Pin', 'Hardware Monitor', 'Licencia AutoTrac', 'Fecha Inicio Licencia', 'Fecha Terminación Licencia']
            cols_grupo_existentes = [c for c in cols_grupo if c in df_display.columns]

            # Agrupar por Machine Pin y metadatos, calculando el promedio del % de AutoTrac
            df_grouped = df_display.groupby(cols_grupo_existentes, as_index=False, dropna=False).agg({
                'AutoTrac_Num': 'mean'
            })

            # Formatear la columna de porcentaje
            df_grouped['% Uso AutoTrac'] = df_grouped['AutoTrac_Num'].apply(
                lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A"
            )
            df_grouped = df_grouped.drop(columns=['AutoTrac_Num'], errors='ignore')

            st.dataframe(df_grouped, use_container_width=True)
            st.caption(f"Mostrando {len(df_grouped)} equipos únicos agrupados por N° de Serie (Machine Pin).")
        else:
            st.info("No hay datos que coincidan con los filtros seleccionados.")

    # ==========================================
    # PESTAÑA 2: PRÓXIMAS TECNOLOGÍAS
    # ==========================================
    with tab_proximas:
        st.info("🚧 Próximamente habilitaremos aquí los análisis para RowSense, AutoPath, Machine Sync, etc.")
