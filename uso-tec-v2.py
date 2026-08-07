import streamlit as st
import pandas as pd
import io

# Configuración de la página
st.set_page_config(
    page_title="Depurador de Base de Datos - CONCI",
    page_icon="🚜",
    layout="wide"
)

st.title("🚜 Depurador y Consolidador de Maquinarias & Tecnología")
st.markdown("""
Esta herramienta procesa el reporte de maquinarias (`Machine Report Tech`), elimina registros vacíos 
y **unifica filas duplicadas** para consolidar el PIN de la máquina con su pantalla y métricas de tecnología.
""")

# Cargar archivo Excel
uploaded_file = st.file_uploader("Cargar archivo Excel (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    # Leer el Excel original
    df_raw = pd.read_excel(uploaded_file)
    
    st.subheader("📊 Diagnóstico de Datos Originales")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total de filas cargadas", len(df_raw))
    c2.metric("Sin Machine Pin", int(df_raw['Machine Pin'].isna().sum()))
    c3.metric("Sin Monitor/Pantalla", int(df_raw['Latest Display Hardware Type'].isna().sum()))
    
    with st.expander("Ver muestra de datos originales"):
        st.dataframe(df_raw.head(10), use_container_width=True)
    
    if st.button("🚀 Procesar y Limpiar Base de Datos", type="primary"):
        # PASO 1: Eliminar filas completamente vacías en las 3 variables clave
        mask_empty = (
            df_raw['Machine Pin'].isna() & 
            df_raw['Product Family'].isna() & 
            df_raw['Latest Display Hardware Type'].isna()
        )
        df_filtered = df_raw[~mask_empty].copy()
        
        # PASO 2: Unificación de filas que corresponden a la misma máquina
        # Agrupamos por Cliente (Org Id / Org Name), Familia de producto y Año
        df_filtered['Model Year_fill'] = df_filtered['Model Year'].fillna(-1)
        df_filtered['Product Family_fill'] = df_filtered['Product Family'].fillna('DESCONOCIDO')
        
        grouped_cols = ['Org Id', 'Product Family_fill', 'Model Year_fill']
        
        def merge_group(group):
            if len(group) == 1:
                return group.iloc[0]
            
            # Tomamos la primera fila como plantilla y completamos vacíos con las otras filas
            combined = group.iloc[0].copy()
            for col in group.columns:
                if pd.isna(combined[col]):
                    valid_vals = group[col].dropna()
                    if not valid_vals.empty:
                        combined[col] = valid_vals.iloc[0]
            return combined

        df_cleaned = (
            df_filtered
            .groupby(grouped_cols, as_index=False, group_keys=False)
            .apply(merge_group)
            .drop(columns=['Model Year_fill', 'Product Family_fill'], errors='ignore')
        )
        
        st.success("¡Base de datos procesada y unificada con éxito!")
        
        # Métricas resultantes
        st.subheader("📈 Resultado de la Consolidación")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Filas consolidadas", len(df_cleaned))
        r2.metric("Filas reducidas/depuradas", len(df_raw) - len(df_cleaned))
        r3.metric("Machine Pins finales", int(df_cleaned['Machine Pin'].notna().sum()))
        r4.metric("% Cobertura PIN", f"{(df_cleaned['Machine Pin'].notna().mean()*100):.1f}%")
        
        # Vista de resultados
        st.subheader("📋 Base de Datos Resultante")
        st.dataframe(df_cleaned, use_container_width=True)
        
        # Generar descarga Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_cleaned.to_excel(writer, index=False, sheet_name='Base_Limpia')
        excel_data = output.getvalue()
        
        st.download_button(
            label="📥 Descargar Base Depurada (.xlsx)",
            data=excel_data,
            file_name="CONCI_Machine_Report_Tech_Limpio.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
