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
Esta herramienta procesa el reporte de maquinarias, consolida los registros, 
y cruza los datos con el archivo de **Emparejamientos** para recuperar pantallas faltantes 
y vincular el Número de Serie exacto de cada monitor.
""")

# --- SECCIÓN DE PARÁMETROS Y CARGA ---
st.sidebar.header("📅 Período de Análisis")
fecha_inicio = st.sidebar.date_input("Fecha de Inicio", datetime.date(2025, 1, 1))
fecha_fin = st.sidebar.date_input("Fecha de Fin", datetime.date.today())

st.sidebar.header("📂 Carga de Archivos")
uploaded_file_principal = st.sidebar.file_uploader("1. Machine Report Tech (.xlsx)", type=["xlsx"])
uploaded_file_emparejamientos = st.sidebar.file_uploader("2. Archivo Emparejamientos (.xlsx)", type=["xlsx"])

if uploaded_file_principal is not None:
    # Leer el Excel principal
    df_raw = pd.read_excel(uploaded_file_principal)
    
    if st.button("🚀 Procesar, Limpiar y Emparejar Base de Datos", type="primary"):
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
            
        # PASO 4: EMPAREJAMIENTO DE MONITORES
        if uploaded_file_emparejamientos is not None:
            try:
                # Leer hoja 'Emparejamientos'
                df_emp_raw = pd.read_excel(uploaded_file_emparejamientos, sheet_name='Emparejamientos')
                
                # Filtrar solo Monitores y limpiar strings para el cruce
                df_monitores = df_emp_raw[df_emp_raw['Tipo'] == 'Monitor'].copy()
                df_monitores['Machine_Pin_emp'] = df_monitores['Número de serie de emparejamiento'].astype(str).str.strip()
                df_monitores['Modelo'] = df_monitores['Modelo'].astype(str).str.strip()
                
                # Crear la nueva columna justo después de "Latest Display Software Version"
                if 'Latest Display Software Version' in df_cleaned.columns:
                    idx_software = df_cleaned.columns.get_loc('Latest Display Software Version')
                    df_cleaned.insert(idx_software + 1, 'Número de Serie Monitor', pd.NA)
                else:
                    df_cleaned['Número de Serie Monitor'] = pd.NA
                    
                # Lógica de cruce fila por fila
                def match_monitor(row):
                    pin = str(row['Machine Pin']).strip()
                    hw = str(row['Latest Display Hardware Type']).strip() if pd.notna(row['Latest Display Hardware Type']) else None
                    
                    # Buscar los monitores asociados a este PIN
                    machine_monitors = df_monitores[df_monitores['Machine_Pin_emp'] == pin]
                    
                    if machine_monitors.empty:
                        return row
                        
                    # Si no tiene monitor asignado en la base principal, usamos el del emparejamiento
                    if hw is None or hw == 'nan' or hw == '':
                        first_mon = machine_monitors.iloc[0]
                        row['Latest Display Hardware Type'] = first_mon['Modelo']
                        row['Latest Display Software Version'] = first_mon['Versión de software']
                        row['Número de Serie Monitor'] = first_mon['Número de serie']
                    else:
                        # Si ya tiene un monitor, tratamos de cruzar PIN + Modelo para extraer el número de serie exacto
                        match_hw = machine_monitors[machine_monitors['Modelo'] == hw]
                        if not match_hw.empty:
                            row['Número de Serie Monitor'] = match_hw.iloc[0]['Número de serie']
                        else:
                            # Fallback: asignamos el primer número de serie que aparece para esa máquina
                            row['Número de Serie Monitor'] = machine_monitors.iloc[0]['Número de serie']
                            
                    return row

                df_cleaned = df_cleaned.apply(match_monitor, axis=1)
                st.success("¡Base de datos procesada, fechas asignadas y monitores emparejados exitosamente!")
                
            except Exception as e:
                st.warning(f"Se procesó la base principal, pero hubo un error con el archivo de emparejamientos: {e}")
        else:
            st.info("La base principal se procesó, pero no se cargó archivo de emparejamientos para cruzar monitores.")
        
        # Métricas resultantes
        st.subheader("📈 Resultado Final")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Filas consolidadas", len(df_cleaned))
        if 'Número de Serie Monitor' in df_cleaned.columns:
            monitores_rescatados = df_cleaned['Número de Serie Monitor'].notna().sum()
            r2.metric("N° de Serie de Monitores recuperados", int(monitores_rescatados))
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
            label="📥 Descargar Base Depurada Final (.xlsx)",
            data=excel_data,
            file_name=f"CONCI_Machine_Report_Tech_{fecha_inicio}_{fecha_fin}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
