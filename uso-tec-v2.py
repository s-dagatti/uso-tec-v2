import streamlit as st
import pandas as pd
import datetime

# Configuración del Dashboard
st.set_page_config(page_title="Carga de Información - Conci", layout="wide")

st.title("📂 Tablero de Carga de Información")
st.markdown("Sube los archivos para procesar, limpiar y consolidar los datos de máquinas, monitores y licencias.")

# --- SIDEBAR: Carga de archivos ---
st.sidebar.header("📁 Carga de Archivos")
uploaded_file_analizador = st.sidebar.file_uploader("1. Archivo Analizador de Máquina", type=["xlsx"])
uploaded_file_maquinas = st.sidebar.file_uploader("2. Archivo de Máquinas (Emparejamientos)", type=["xlsx"])
uploaded_file_activaciones = st.sidebar.file_uploader("3. Control de Activaciones (CSV)", type=["csv"])

def procesar_analizador(df):
    """
    Limpia el dataframe de Analizador: elimina columnas 'Unidad' y convierte % a numérico.
    """
    # 1. Eliminar columnas 'Unidad'
    cols_to_drop = [c for c in df.columns if 'unidad' in str(c).lower()]
    df = df.drop(columns=cols_to_drop)
    
    # 2. Convertir columnas porcentuales a numéricas
    cols_porcentuales = [c for c in df.columns if 'activo' in str(c).lower() or 'activado' in str(c).lower()]
    
    for col in cols_porcentuales:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', ''), errors='coerce')
        
    return df

def calcular_estado_licencia(row):
    """
    Determina el estado de la licencia: 'No tiene', 'Vencida' o 'Vigente'.
    """
    licencia = row.get('Licencia Gen4')
    if pd.isna(licencia) or str(licencia).strip() in ['', '-']:
        return "No tiene"
    
    fin_dt = row.get('Fin_Licencia_DT')
    if pd.isna(fin_dt):
        # Si tiene licencia nombrada pero sin fecha de expiración explícita
        return "Vigente"
    
    today = pd.Timestamp.now().normalize()
    if fin_dt < today:
        return "Vencida"
    else:
        return "Vigente"

# --- LÓGICA PRINCIPAL ---
if uploaded_file_analizador is not None:
    try:
        # 1. LEER Y PROCESAR ARCHIVO ANALIZADOR
        df_original = pd.read_excel(uploaded_file_analizador)
        df_final = procesar_analizador(df_original.copy())
        
        # 2. CRUCE CON SEGUNDO ARCHIVO (EMPAREJAMIENTOS)
        if uploaded_file_maquinas is not None:
            df_maquinas = pd.read_excel(uploaded_file_maquinas, sheet_name='Emparejamientos')
            
            # Filtrar solo 'monitor' en columna Tipo
            df_monitores = df_maquinas[df_maquinas['Tipo'].astype(str).str.lower() == 'monitor'].copy()
            
            # Seleccionar y renombrar columnas
            df_monitores = df_monitores[[
                'Número de serie de emparejamiento', 
                'Número de serie',       # Nro de serie del monitor (Col A)
                'Modelo',                # Modelo Monitor (Col B)
                'Versión de software'    # Versión Software Monitor (Col E)
            ]].rename(columns={
                'Número de serie': 'Hardware Monitor',
                'Modelo': 'Modelo Monitor',
                'Versión de software': 'Versión Software Monitor'
            })
            
            # Cruce 1: Serie de máquina vs Serie de emparejamiento
            df_final = pd.merge(
                df_final, 
                df_monitores, 
                left_on='Número de serie de la máquina', 
                right_on='Número de serie de emparejamiento', 
                how='left'
            )
            
            if 'Número de serie de emparejamiento' in df_final.columns:
                df_final = df_final.drop(columns=['Número de serie de emparejamiento'])
        else:
            st.sidebar.warning("⚠️ Falta cargar el archivo de máquinas (Emparejamientos).")

        # 3. CRUCE CON TERCER ARCHIVO (LICENCIAS / ACTIVACIONES GEN 4)
        if uploaded_file_activaciones is not None and 'Hardware Monitor' in df_final.columns:
            df_activaciones = pd.read_csv(uploaded_file_activaciones)
            
            # Filtrar solo "Monitor Gen 4" en la columna COMPONENTE
            df_gen4 = df_activaciones[
                df_activaciones['COMPONENTE'].astype(str).str.strip().str.lower() == 'monitor gen 4'
            ].copy()
            
            # Ordenar por fecha de inicio para tomar la última activación registrada por monitor
            df_gen4['Fecha_Inicio_DT'] = pd.to_datetime(df_gen4['Fecha de inicio'], format='%d/%m/%Y', errors='coerce')
            df_gen4 = df_gen4.sort_values('Fecha_Inicio_DT', ascending=True)
            df_gen4_unique = df_gen4.drop_duplicates(subset=['Tornillería'], keep='last')
            
            # Seleccionar y renombrar columnas requeridas
            df_licencias_gen4 = df_gen4_unique[[
                'Tornillería',
                'Producto',
                'Duración',
                'Fecha de inicio',
                'Fecha final'
            ]].rename(columns={
                'Producto': 'Licencia Gen4',
                'Duración': 'Duración Licencia Gen4',
                'Fecha de inicio': 'Comienzo Licencia Gen4',
                'Fecha final': 'Fin Licencia Gen4'
            })
            
            # Cruce 2: Hardware Monitor vs Tornillería
            df_final = pd.merge(
                df_final,
                df_licencias_gen4,
                left_on='Hardware Monitor',
                right_on='Tornillería',
                how='left'
            )
            
            if 'Tornillería' in df_final.columns:
                df_final = df_final.drop(columns=['Tornillería'])

            # 4. CÁLCULO DEL ESTADO DE LA LICENCIA
            df_final['Fin_Licencia_DT'] = pd.to_datetime(df_final['Fin Licencia Gen4'], format='%d/%m/%Y', errors='coerce')
            df_final['Estado Licencia Gen4'] = df_final.apply(calcular_estado_licencia, axis=1)
            
            # Eliminamos la columna auxiliar de fecha datetime
            df_final = df_final.drop(columns=['Fin_Licencia_DT'])

        elif uploaded_file_activaciones is None:
            st.sidebar.warning("⚠️ Falta cargar el archivo CSV de activaciones.")

        # --- UI: RESULTADOS ---
        st.success("✅ Datos consolidados con éxito.")
        
        # Métricas resumidas
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Máquinas Totales", len(df_final))
        col2.metric("Columnas Resultantes", len(df_final.columns))
        
        if 'Estado Licencia Gen4' in df_final.columns:
            cant_vigentes = (df_final['Estado Licencia Gen4'] == 'Vigente').sum()
            cant_vencidas = (df_final['Estado Licencia Gen4'] == 'Vencida').sum()
            cant_no_tiene = (df_final['Estado Licencia Gen4'] == 'No tiene').sum()
            
            col3.metric("🟢 Vigentes", cant_vigentes)
            col4.metric("🔴 Vencidas", cant_vencidas)
            col5.metric("⚪ No tiene", cant_no_tiene)

        st.subheader("Vista previa de los datos consolidados")
        st.dataframe(df_final, use_container_width=True)
        
        # Botón para descargar el resultado consolidado
        csv = df_final.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar datos consolidados (CSV)",
            data=csv,
            file_name='datos_consolidados_conci.csv',
            mime='text/csv',
        )
        
    except Exception as e:
        st.error(f"❌ Error al procesar los archivos: {e}")
        st.info("Asegúrate de que los archivos cargados sean válidos y tengan el formato correcto.")
else:
    st.info("Esperando a que subas al menos el primer archivo (Analizador de Máquina) para comenzar...")
