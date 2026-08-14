import streamlit as st
import pandas as pd

# Configuración del Dashboard
st.set_page_config(page_title="Carga de Información - Conci", layout="wide")

st.title("📂 Tablero de Carga de Información")
st.markdown("Sube el archivo Excel para procesar y limpiar automáticamente los datos.")

# --- SIDEBAR: Carga de archivo ---
uploaded_file = st.sidebar.file_uploader("Selecciona el archivo Excel", type=["xlsx"])

def procesar_datos(df):
    """
    Limpia el dataframe: elimina columnas 'Unidad' y convierte % a numérico.
    """
    # 1. Eliminar columnas 'Unidad'
    cols_to_drop = [c for c in df.columns if 'unidad' in str(c).lower()]
    df = df.drop(columns=cols_to_drop)
    
    # 2. Convertir columnas porcentuales a numéricas
    # Buscamos columnas que contengan 'activo' o 'activado'
    cols_porcentuales = [c for c in df.columns if 'activo' in str(c).lower() or 'activado' in str(c).lower()]
    
    for col in cols_porcentuales:
        # Convertimos a string, eliminamos '%', y forzamos a numérico
        df[col] = pd.to_numeric(df[col].astype(str).str.replace('%', ''), errors='coerce')
        
    return df

# --- LÓGICA PRINCIPAL ---
if uploaded_file is not None:
    try:
        # Leemos el archivo
        df_original = pd.read_excel(uploaded_file)
        
        # Procesamos
        df_limpio = procesar_datos(df_original.copy())
        
        # UI: Resultados
        st.success("✅ Archivo cargado y procesado con éxito.")
        
        col1, col2 = st.columns(2)
        col1.metric("Columnas originales", len(df_original.columns))
        col2.metric("Columnas resultantes", len(df_limpio.columns))
        
        st.subheader("Vista previa de los datos limpios")
        st.dataframe(df_limpio, use_container_width=True)
        
        # Botón para descargar el resultado limpio
        csv = df_limpio.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar datos limpios (CSV)",
            data=csv,
            file_name='datos_limpios_conci.csv',
            mime='text/csv',
        )
        
    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")
        st.info("Asegúrate de que el archivo sea un Excel válido.")
else:
    st.info("Esperando a que subas un archivo para comenzar...")
