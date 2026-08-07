import streamlit as st
import pandas as pd
import io
import datetime

# Configuración de la página
st.set_page_config(
    page_title="Depurador de Base de Datos - CONCI",
    page_icon="🚜",
    layout="wide"
)

st.title("🚜 Depurador y Consolidador de Maquinarias & Tecnología")
st.markdown("""
Esta herramienta procesa el reporte de maquinarias (`Machine Report Tech`), elimina registros vacíos, 
**unifica filas duplicadas** para consolidar el PIN de la máquina con su pantalla y asigna el **período de análisis**.
""")

# --- SECCIÓN DE PARÁMETROS (FECHAS DE ANÁLISIS) ---
st.sidebar.header("📅 Período de Análisis")
fecha_inicio = st.sidebar.date_input("Fecha de Inicio", datetime.date(2025, 1, 1))
fecha_fin = st.sidebar.date_input("Fecha de Fin", datetime.date.today())

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
        df_filtered['Model Year_fill'] = df_filtered['Model Year'].fillna(-1)
        df_filtered['Product Family_fill'] = df_filtered['Product Family'].fillna('DESCONOCIDO')
        
        grouped_cols = ['Org Id', 'Product Family_fill', 'Model Year_fill']
        
        def merge_group(group):
            if len(group) == 1:
                return group.iloc[0]
            
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
        
        # PASO 3: Insertar las columnas de Fechas justo después de 'Dealer'
        if 'Dealer' in df_cleaned.columns:
            dealer_idx = df_cleaned.columns.get_loc('Dealer') + 1
            df_cleaned.insert(dealer_idx, 'Fecha Inicio', fecha_inicio.strftime('%Y-%m-%d'))
            df_cleaned.insert(dealer_idx + 1, 'Fecha Fin', fecha_fin.strftime('%Y-%m-%d'))
        else:
            df_cleaned['Fecha Inicio'] = fecha_inicio.strftime('%Y-%m-%d')
            df_cleaned['Fecha Fin'] = fecha_fin.strftime('%Y-%m-%d')
            
        st.success("¡Base de datos procesada, unificada y con fechas asignadas exitosamente!")
        
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
            label="📥 Descargar Base Depurada con Fechas (.xlsx)",
            data=excel_data,
            file_name=f"CONCI_Machine_Report_Tech_{fecha_inicio}_{fecha_fin}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
