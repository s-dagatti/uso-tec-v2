import streamlit as st
import pandas as pd
import requests
import base64
import io
import plotly.express as px
import plotly.graph_objects as go

# Configuración de la página
st.set_page_config(
    page_title="Dashboard de Adopción Tecnológica - CONCI",
    page_icon="📊",
    layout="wide"
)

# --- CONFIGURACIÓN DE ARCHIVO EN GITHUB ---
NOMBRE_ARCHIVO_GITHUB = "data/base_datos_consolidada.xlsx"

# --- FUNCIÓN DE LECTURA DESDE GITHUB (CON CACHÉ) ---
@st.cache_data(ttl=300)  # Se actualiza cada 5 minutos automáticamente
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

# --- ENCABEZADO ---
st.title("📊 Tablero de Análisis de Uso de Tecnología y Licencias")
st.markdown("Monitoreo en tiempo real de la adopción tecnológica, monitores emparejados y estado de licencias por sucursal.")

# Botón para forzar actualización de datos
col_title, col_btn = st.columns([4, 1])
with col_btn:
    if st.button("🔄 Refrescar Datos"):
        st.cache_data.clear()
        st.rerun()

# --- CARGA DE DATOS ---
with st.spinner("Cargando la base de datos consolidada desde GitHub..."):
    df = cargar_datos_github()

if df is not None and not df.empty:
    
    # Preprocesamiento de fechas para filtros
    if 'Fecha Fin' in df.columns:
        df['Fecha Fin DT'] = pd.to_datetime(df['Fecha Fin'], errors='coerce')
    else:
        df['Fecha Fin DT'] = pd.NaT

    # --- FILTROS EN BARRA LATERAL ---
    st.sidebar.header("🔍 Filtros de Análisis")
    
    # 1. Filtro Sucursal
    sucursales = ["Todas"] + sorted([str(s) for s in df['Sucursal'].dropna().unique()]) if 'Sucursal' in df.columns else ["Todas"]
    sel_sucursal = st.sidebar.selectbox("Sucursal", sucursales)
    
    # 2. Filtro Familia de Producto
    familias = ["Todas"] + sorted([str(f) for f in df['Product Family'].dropna().unique()]) if 'Product Family' in df.columns else ["Todas"]
    sel_familia = st.sidebar.selectbox("Familia de Producto", familias)
    
    # 3. Filtro Estado de Licencia
    estados_lic = ["Todos"] + sorted([str(e) for e in df['Estado Licencia'].dropna().unique()]) if 'Estado Licencia' in df.columns else ["Todos"]
    sel_licencia = st.sidebar.selectbox("Estado de Licencia", estados_lic)

    # Aplicar Filtros
    df_filtered = df.copy()
    if sel_sucursal != "Todas":
        df_filtered = df_filtered[df_filtered['Sucursal'].astype(str) == sel_sucursal]
    if sel_familia != "Todas":
        df_filtered = df_filtered[df_filtered['Product Family'].astype(str) == sel_familia]
    if sel_licencia != "Todos":
        df_filtered = df_filtered[df_filtered['Estado Licencia'].astype(str) == sel_licencia]

    # --- KPI METRICS ---
    st.markdown("---")
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    
    total_maquinas = len(df_filtered)
    kpi1.metric("🚜 Equipos Analizados", total_maquinas)
    
    if 'Machine Pin' in df_filtered.columns:
        pins_validos = df_filtered['Machine Pin'].notna().sum()
        kpi2.metric("🆔 PINs Identificados", pins_validos, f"{round(pins_validos/total_maquinas*100, 1) if total_maquinas>0 else 0}%")
        
    if 'Número de Serie Monitor' in df_filtered.columns:
        monitores_val = df_filtered['Número de Serie Monitor'].notna().sum()
        kpi3.metric("🖥️ Monitores Emparejados", monitores_val, f"{round(monitores_val/total_maquinas*100, 1) if total_maquinas>0 else 0}%")
        
    if 'AutoTrac' in df_filtered.columns:
        autotrac_act = df_filtered['AutoTrac'].notna().sum()
        kpi4.metric("🛰️ Uso AutoTrac", autotrac_act, f"{round(autotrac_act/total_maquinas*100, 1) if total_maquinas>0 else 0}%")
        
    if 'Estado Licencia' in df_filtered.columns:
        lic_activas = (df_filtered['Estado Licencia'].astype(str).str.lower() == 'activa').sum()
        kpi5.metric("📜 Licencias Activas", lic_activas)

    st.markdown("---")

    # --- SECCIÓN DE GRÁFICOS INTERACTIVOS ---
    g1, g2 = st.columns(2)
    
    # Gráfico 1: Adopción de Tecnologías Key (AutoTrac, RowSense, AutoPath, etc.)
    with g1:
        st.subheader("🛰️ Adopción por Paquete Tecnológico")
        tecnologias = ['AutoTrac', 'RowSense', 'AIG', 'ATIG', 'ATTA', 'AutoPath', 'Machine Sync Leader']
        tech_counts = {}
        for tech in tecnologias:
            if tech in df_filtered.columns:
                # Se excluyen nulos segun la lógica establecida
                tech_counts[tech] = df_filtered[tech].notna().sum()
                
        df_tech = pd.DataFrame(list(tech_counts.items()), columns=['Tecnología', 'Equipos'])
        df_tech['% Adopción'] = (df_tech['Equipos'] / total_maquinas * 100).round(1) if total_maquinas > 0 else 0
        
        fig_tech = px.bar(
            df_tech, 
            x='Tecnología', 
            y='Equipos',
            text='% Adopción',
            color='Equipos',
            color_continuous_scale='Greens',
            title="Cantidad de Equipos por Tecnología Detectada"
        )
        fig_tech.update_traces(texttemplate='%{text}%', textposition='outside')
        fig_tech.update_layout(showlegend=False, yaxis_title="N° de Equipos")
        st.plotly_chart(fig_tech, use_container_width=True)

    # Gráfico 2: Distribución por Sucursal
    with g2:
        st.subheader("🏢 Distribución de Equipos por Sucursal")
        if 'Sucursal' in df_filtered.columns and df_filtered['Sucursal'].notna().any():
            df_suc = df_filtered['Sucursal'].value_counts().reset_index()
            df_suc.columns = ['Sucursal', 'Cantidad']
            
            fig_suc = px.pie(
                df_suc, 
                names='Sucursal', 
                values='Cantidad',
                hole=0.4,
                title="Proporción de Equipos Monitoreados por Sucursal"
            )
            fig_suc.update_traces(textinfo='percent+label')
            st.plotly_chart(fig_suc, use_container_width=True)
        else:
            st.info("No hay datos de Sucursal disponibles para graficar.")

    g3, g4 = st.columns(2)
    
    # Gráfico 3: Estado de Licencias
    with g3:
        st.subheader("📜 Estado de Licencias por Tipo")
        if 'Estado Licencia' in df_filtered.columns and df_filtered['Estado Licencia'].notna().any():
            df_lic_summary = df_filtered['Estado Licencia'].value_counts().reset_index()
            df_lic_summary.columns = ['Estado', 'Cantidad']
            
            fig_lic = px.bar(
                df_lic_summary,
                x='Estado',
                y='Cantidad',
                color='Estado',
                color_discrete_map={'Activa': '#2ca02c', 'Inactiva': '#d62728', 'Vencida': '#ff7f0e'},
                title="Estado General de las Licencias"
            )
            st.plotly_chart(fig_lic, use_container_width=True)
        else:
            st.info("No hay información de licencias vinculadas.")

    # Gráfico 4: Evolución por Familia de Producto
    with g4:
        st.subheader("🚜 Equipos por Familia de Producto")
        if 'Product Family' in df_filtered.columns:
            df_fam = df_filtered['Product Family'].value_counts().reset_index()
            df_fam.columns = ['Familia de Producto', 'Cantidad']
            
            fig_fam = px.bar(
                df_fam,
                x='Cantidad',
                y='Familia de Producto',
                orientation='h',
                color='Cantidad',
                color_continuous_scale='Viridis',
                title="Top Familias de Maquinarias"
            )
            fig_fam.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig_fam, use_container_width=True)

    # --- TABLA EXPLORADORA DETALLADA ---
    st.markdown("---")
    st.subheader("🔍 Explorador Detallado de la Base")
    
    # Buscador de texto libre
    busqueda = st.text_input("🔎 Buscar por PIN, Cliente (Org Name) o Monitor:", "")
    if busqueda:
        mask = (
            df_filtered['Machine Pin'].astype(str).str.contains(busqueda, case=False, na=False) |
            df_filtered['Org Name'].astype(str).str.contains(busqueda, case=False, na=False) |
            df_filtered['Número de Serie Monitor'].astype(str).str.contains(busqueda, case=False, na=False)
        )
        df_display = df_filtered[mask]
    else:
        df_display = df_filtered

    st.dataframe(df_display, use_container_width=True)

    # Exportación rápida
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_display.to_excel(writer, index=False, sheet_name='Base_Filtrada')
    
    st.download_button(
        label="📥 Descargar Vista Actual en Excel",
        data=output.getvalue(),
        file_name="CONCI_Reporte_Filtrado_Dashboard.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
