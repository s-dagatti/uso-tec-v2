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
    
    # 1. PREPROCESAMIENTO DE FECHAS DE PERÍODO (Para filtros)
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
        
        ultimo_fin = max_date_global
        ultimo_inicio = df[df['Fecha_Fin_DT'] == pd.to_datetime(ultimo_fin)]['Fecha_Inicio_DT'].min()
        default_inicio = ultimo_inicio.date() if pd.notna(ultimo_inicio) else min_date_global
    else:
        import datetime
        min_date_global = datetime.date(2025, 1, 1)
        max_date_global = datetime.date.today()
        default_inicio = min_date_global
        ultimo_fin = max_date_global

    # --- COLUMNAS V (Índice 21) y W (Índice 22) ---
    col_v_lic_inicio = df.columns[21] if len(df.columns) > 21 else None
    col_w_lic_fin = df.columns[22] if len(df.columns) > 22 else None

    # --- DETECCIÓN DE COLUMNA DE FAMILIA ---
    col_familia = 'Product Family' if 'Product Family' in df.columns else ('Familia de Producto' if 'Familia de Producto' in df.columns else None)

    # --- SIDEBAR: FILTROS ---
    st.sidebar.header("🔍 Filtros de Análisis")
    
    # Filtro 1: Sucursal
    sucursales = ["Todas"] + sorted([str(s) for s in df['Sucursal'].dropna().unique()]) if 'Sucursal' in df.columns else ["Todas"]
    sel_sucursal = st.sidebar.selectbox("1. Sucursal", sucursales)
    
    # Filtro 2: Org Name
    df_pre = df.copy()
    if sel_sucursal != "Todas":
        df_pre = df_pre[df_pre['Sucursal'].astype(str) == sel_sucursal]
        
    orgs = ["Todas"] + sorted([str(o) for o in df_pre['Org Name'].dropna().unique()]) if 'Org Name' in df_pre.columns else ["Todas"]
    sel_org = st.sidebar.selectbox("2. Organización (Org Name)", orgs)
    
    # Filtro 3: Familia de Máquina
    if col_familia and col_familia in df.columns:
        familias = ["Todas"] + sorted([str(f) for f in df[col_familia].dropna().unique()])
    else:
        familias = ["Todas"]
    sel_familia = st.sidebar.selectbox("3. Familia de Máquina", familias)

    # Filtro 4: Slider de Período Analizado
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 Período Analizado")
    
    if min_date_global < max_date_global:
        rango_fechas = st.sidebar.slider("Selecciona el rango:", min_value=min_date_global, max_value=max_date_global, value=(default_inicio, ultimo_fin))
    else:
        rango_fechas = (min_date_global, max_date_global)

    # --- APLICACIÓN DE FILTROS ---
    df_filtered = df.copy()
    if sel_sucursal != "Todas": df_filtered = df_filtered[df_filtered['Sucursal'].astype(str) == sel_sucursal]
    if sel_org != "Todas": df_filtered = df_filtered[df_filtered['Org Name'].astype(str) == sel_org]
    if col_familia and sel_familia != "Todas": df_filtered = df_filtered[df_filtered[col_familia].astype(str) == sel_familia]
    
    if 'Fecha_Fin_DT' in df_filtered.columns and not df_filtered['Fecha_Fin_DT'].dropna().empty:
        inicio_sel, fin_sel = rango_fechas
        df_filtered = df_filtered[(df_filtered['Fecha_Fin_DT'].dt.date >= inicio_sel) & (df_filtered['Fecha_Fin_DT'].dt.date <= fin_sel)]

    # ==========================================
    # PESTAÑA AUTOTRAC
    # ==========================================
    st.subheader("Análisis de Adopción: AutoTrac")
    
    busqueda = st.text_input("🔎 Buscar por Machine Pin u Org Name:", "")
    df_display = df_filtered[df_filtered['Machine Pin'].astype(str).str.contains(busqueda, case=False, na=False) | 
                             df_filtered['Org Name'].astype(str).str.contains(busqueda, case=False, na=False)] if busqueda else df_filtered.copy()

    col_hardware = next((c for c in df_display.columns if 'hardware' in c.lower()), None)
    col_lic_nombre = next((c for c in df_display.columns if 'licencia' in c.lower() or 'license' in c.lower()), None)

    if not df_display.empty and 'Machine Pin' in df_display.columns:
        
        def evaluar_fila(row):
            hw = str(row[col_hardware]).strip() if col_hardware and pd.notna(row[col_hardware]) else ""
            lic_nombre = str(row[col_lic_nombre]).strip() if col_lic_nombre and pd.notna(row[col_lic_nombre]) else ""
            
            f_ini = row[col_v_lic_inicio] if col_v_lic_inicio in row else "-"
            f_fin = row[col_w_lic_fin] if col_w_lic_fin in row else "-"
            
            is_g5 = hw.upper().startswith("G5")
            is_autotrac = lic_nombre.lower().startswith("autotrac")
            
            return pd.Series([hw, is_g5, lic_nombre, is_autotrac, f_ini, f_fin])

        res_eval = df_display.apply(evaluar_fila, axis=1)
        res_eval.columns = ['HW', 'Es_G5', 'Lic_Name', 'Is_Auto', 'F_Ini', 'F_Fin']
        df_proc = pd.concat([df_display.reset_index(drop=True), res_eval], axis=1)
        df_proc['AutoTrac_Num'] = pd.to_numeric(df_proc['AutoTrac'].astype(str).str.replace('%', '').str.replace(',', '.'), errors='coerce') * 100

        lista_final = []
        for pin, group in df_proc.groupby('Machine Pin', dropna=False):
            if group['Es_G5'].iloc[0]:
                g_auto = group[group['Is_Auto']]
                row = g_auto.iloc[0].copy() if not g_auto.empty else group.iloc[0].copy()
                row['Licencia AutoTrac'] = row['Lic_Name'] if not g_auto.empty else "Sin Licencia AutoTrac"
                row['Fecha Inicio'] = row['F_Ini'] if not g_auto.empty else "-"
                row['Fecha Fin'] = row['F_Fin'] if not g_auto.empty else "-"
            else:
                row = group.iloc[0].copy()
                row['Licencia AutoTrac'] = "De base"
                row['Fecha Inicio'] = "-"
                row['Fecha Fin'] = "-"
            
            row['% Uso'] = group['AutoTrac_Num'].mean()
            lista_final.append(row)

        df_final = pd.DataFrame(lista_final)
        df_final['% Uso AutoTrac'] = df_final['% Uso'].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "N/A")
        
        # Estilo
        def resaltar(val_num):
            if pd.notna(val_num) and val_num < 60.0: return 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold;'
            return ''

        df_show = df_final[['Sucursal', 'Org Name', 'Product Family', 'Machine Pin', 'Hardware Monitor', 'Licencia AutoTrac', 'Fecha Inicio', 'Fecha Fin', '% Uso AutoTrac']]
        
        st.dataframe(df_show.style.apply(lambda s: [resaltar(v) for v in df_final['% Uso']], subset=['% Uso AutoTrac']), use_container_width=True)
