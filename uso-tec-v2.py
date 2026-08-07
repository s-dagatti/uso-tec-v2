import streamlit as st
import pandas as pd
import io

st.set_page_config(
    page_title="Depurador de Base de Datos de Maquinarias - CONCI",
    page_icon="🚜",
    layout="wide"
)

st.title("🚜 Depurador y Consolidador de Maquinarias & Tecnología")
st.markdown("""
Esta aplicación permite cargar el reporte de maquinarias (`Machine Report Tech`), eliminar registros incompletos 
y **unificar filas duplicadas** para consolidar el PIN de la máquina con su pantalla y métricas de uso de tecnología.
""")

# Carga de archivo
uploaded_file = st.file_uploader("Cargar archivo Excel (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    # Leer el Excel original
    df_raw = pd.read_excel(uploaded_file)
    
    st.subheader("📊 Datos Originales")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de filas iniciales", len(df_raw))
    col2.metric("Sin Machine Pin inicial", df_raw['Machine Pin'].isna().sum())
    col3.metric("Sin Pantalla asignada", df_raw['Latest Display Hardware Type'].isna().sum())
    
    st.dataframe(df_raw.head(10), use_container_width=True)
    
    if st.button("🚀 Procesar y Limpiar Base de Datos", type="primary"):
        # PASO 1: Eliminar filas donde Machine Pin, Product Family y Display Hardware estén vacíos
        mask_empty = (
            df_raw['Machine Pin'].isna() & 
            df_raw['Product Family'].isna() & 
            df_raw['Latest Display Hardware Type'].isna()
        )
        df_filtered = df_raw[~mask_empty].copy()
        
        # PASO 2: Unificación de filas
        # Definimos las columnas clave para identificar que se trata de la misma máquina
        group_cols = ['Org Id', 'Product Family', 'Model Year']
        
        # Función para combinar filas del mismo grupo
        def merge_group(group):
            if len(group) == 1:
                return group.iloc[0]
            
            # Tomamos la primera fila como base y completamos los nulos con las otras filas del grupo
            combined = group.iloc[0].copy()
            for col in group.columns:
                if pd.isna(combined[col]):
                    valid_vals = group[col].dropna()
                    if not valid_vals.empty:
                        combined[col] = valid_vals.iloc[0]
            return combined

        # Realizamos la agrupación y unificación
        # Tratar NaN en claves de agrupación temporalmente para no perder datos
        df_filtered['Model Year_fill'] = df_filtered['Model Year'].fillna(-1)
        df_filtered['Product Family_fill'] = df_filtered['Product Family'].fillna('DESCONOCIDO')
        
        grouped_cols_temp = ['Org Id', 'Product Family_fill', 'Model Year_fill']
        
        df_cleaned = (
            df_filtered
            .groupby(grouped_cols_temp, as_index=False, group_keys=False)
            .apply(merge_group)
            .drop(columns=['Model Year_fill', 'Product Family_fill'], errors='ignore')
        )
        
        st.success("¡Base de datos procesada exitosamente!")
        
        # Métricas de resultado
        st.subheader("📈 Resultado del Procesamiento")
        res_col1, res_col2, res_col3, res_col4 = st.columns(4)
        res_col1.metric("Filas finales", len(df_cleaned))
        res_col2.metric("Filas eliminadas/consolidadas", len(df_raw) - len(df_cleaned))
        res_col3.metric("Machine Pins recuperados", df_cleaned['Machine Pin'].notna().sum())
        res_col4.metric("% Cobertura de PIN", f"{(df_cleaned['Machine Pin'].notna().mean()*100):.1f}%")
        
        # Visualización de datos depurados
        st.subheader("📋 Vista Previa de la Base de Datos Consolidadas")
        st.dataframe(df_cleaned, use_container_width=True)
        
        # Opción para descargar
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_cleaned.to_excel(writer, index=False, sheet_name='Base_Limpia')
        excel_data = output.getvalue()
        
        st.download_button(
            label="📥 Descargar Base de Datos Depurada (.xlsx)",
            data=excel_data,
            file_name="CONCI_Machine_Report_Tech_Consolidado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
