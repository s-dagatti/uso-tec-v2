import streamlit as st
import pandas as pd

# Configuración del Dashboard
st.set_page_config(page_title="Carga de Información - Conci", layout="wide")

st.title("📂 Tablero de Carga de Información")
st.markdown("Sube los archivos Excel para procesar, limpiar y consolidar los datos.")

# --- SIDEBAR: Carga de archivos ---
st.sidebar.header("📁 Carga de Archivos")
uploaded_file = st.sidebar.file_uploader("1. Archivo Analizador de Máquina", type=["xlsx"])
uploaded_file_maquinas = st.sidebar.file_uploader("2. Archivo de Máquinas (Emparejamientos)", type=["xlsx"])

def procesar_datos(df):
    """
    Limpia el dataframe: elimina columnas 'Unidad' y convierte % a numérico.
    """
    # 1. Eliminar columnas 'Unidad'
    cols_to_drop = [c for c in df.columns if 'unidad' in str(c).lower()]
    df = df.drop(columns=cols_to_drop)
    
    # 2. Convertir columnas porcentuales a numéricas
    cols_porcentuales = [c for c in df.columns if 'activo' in str(c).lower() or 'activado' in str(c).lower()]
    
    for col in cols_porcentuales:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', ''), errors='coerce')
        
    return df

# --- LÓGICA PRINCIPAL ---
if uploaded_file is not None:
    try:
        # Leemos el primer archivo
        df_original = pd.read_excel(uploaded_file)
        
        # Procesamos el primer archivo
        df_limpio = procesar_datos(df_original.copy())
        
        # --- NUEVA LÓGICA: CRUCE CON SEGUNDO ARCHIVO (SI ESTÁ CARGADO) ---
        if uploaded_file_maquinas is not None:
            # 1. Leer solo la hoja "Emparejamientos"
            df_maquinas = pd.read_excel(uploaded_file_maquinas, sheet_name='Emparejamientos')
            
            # 2. Filtrar filas donde la columna 'Tipo' sea 'monitor'
            df_monitores = df_maquinas[df_maquinas['Tipo'].astype(str).str.lower() == 'monitor'].copy()
            
            # 3. Seleccionar las columnas necesarias para el cruce
            df_monitores = df_monitores[[
                'Número de serie de emparejamiento', 
                'Número de serie',       # Nro de serie del monitor (Col A)
                'Modelo',                # Modelo (Col B)
                'Versión de software'    # Versión de software (Col E)
            ]]
            
            # Renombramos las columnas del monitor para diferenciarlas claramente en el resultado final
            df_monitores = df_monitores.rename(columns={
                'Número de serie': 'Hardware Monitor',
                'Modelo': 'Modelo Monitor',
                'Versión de software': 'Versión Software Monitor'
            })
            
            # 4. Hacer el merge (cruce) con el df_limpio
            df_final = pd.merge(
                df_limpio, 
                df_monitores, 
                left_on='Número de serie de la máquina', 
                right_on='Número de serie de emparejamiento', 
                how='left'
            )
            
            # Eliminar la columna de cruce duplicada
            if 'Número de serie de emparejamiento' in df_final.columns:
                df_final = df_final.drop(columns=['Número de serie de emparejamiento'])
                
        else:
            # Si no cargó el segundo archivo, usamos el limpio básico
            df_final = df_limpio.copy()
            st.sidebar.warning("⚠️ Falta cargar el archivo de máquinas para completar el cruce de monitores.")

        # --- UI: Resultados ---
        st.success("✅ Archivo procesado con éxito.")
        
        col1, col2 = st.columns(2)
        col1.metric("Columnas originales (Analizador)", len(df_original.columns))
        col2.metric("Columnas resultantes finales", len(df_final.columns))
        
        st.subheader("Vista previa de los datos consolidados")
        st.dataframe(df_final, use_container_width=True)
        
        # Botón para descargar el resultado limpio
        csv = df_final.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar datos consolidados (CSV)",
            data=csv,
            file_name='datos_consolidados_conci.csv',
            mime='text/csv',
        )
        
    except Exception as e:
        st.error(f"❌ Error al procesar los archivos: {e}")
        st.info("Asegúrate de que los archivos sean Excel válidos y contengan las hojas correctas.")
else:
    st.info("Esperando a que subas al menos el primer archivo (Analizador de Máquina) para comenzar...")
