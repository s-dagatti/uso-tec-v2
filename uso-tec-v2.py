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
cruza los datos con los archivos de **Emparejamientos** y **Licencias**, y requiere **completar manualmente** 
los equipos que registraron uso de tecnología pero no tienen identificador.
""")

# --- INICIALIZAR VARIABLES EN SESIÓN ---
if 'df_procesado' not in st.session_state:
    st.session_state['df_procesado'] = None

# --- SECCIÓN DE PARÁMETROS Y CARGA ---
st.sidebar.header("📅 Período de Análisis")
fecha_inicio = st.sidebar.date_input("Fecha de Inicio", datetime.date(2025, 1, 1))
fecha_fin = st.sidebar.date_input("Fecha de Fin", datetime.date.today())

st.sidebar.header("📂 Carga de Archivos")
uploaded_file_principal = st.sidebar.file_uploader("1. Machine Report Tech (.xlsx)", type=["xlsx"])
uploaded_file_emparejamientos = st.sidebar.file_uploader("2. Archivo Emparejamientos (.xlsx)", type=["xlsx"])
uploaded_file_licencias = st.sidebar.file_uploader("3. Archivo Licencias (.xlsx)", type=["xlsx"])

if uploaded_file_principal is not None:
    if st.sidebar.button("🚀 Procesar, Limpiar y Emparejar", type="primary"):
        # Leer el Excel principal
        df_raw = pd.read_excel(uploaded_file_principal)
        
        # PASO 1: Eliminar filas vacías
        mask_empty = (
            df_raw['Machine Pin'].isna() & 
            df_raw['Product Family'].isna() & 
            df_raw['Latest Display Hardware Type'].isna()
        )
        df_filtered = df_raw[~mask_empty].copy()
        
        # PASO 2: Unificación de filas
        df_filtered['Model Year_fill'] = df_filtered['Model Year'].fillna(-1)
        df_filtered['Product Family_fill'] = df_filtered['Product Family'].fillna('DESCONOCIDO')
        
        grouped_cols = ['Org Id', 'Product Family_fill', 'Model Year_fill']
        
        def merge_group(group):
            if len(group) == 1:
                return group.iloc[0]
            combined = group.iloc[0].copy()
            for col in group.columns:
                if pd.isna(combined[col]):
                    valid_vals = group.dropna(subset=[col])
                    if not valid_vals.empty:
                        combined[col] = valid_vals.iloc[0][col]
            return combined

        df_cleaned = (
            df_filtered
            .groupby(grouped_cols, as_index=False, group_keys=False)
            .apply(merge_group)
            .drop(columns=['Model Year_fill', 'Product Family_fill'], errors='ignore')
        )
        
        # PASO 3: Insertar Fechas
        if 'Dealer' in df_cleaned.columns:
            dealer_idx = df_cleaned.columns.get_loc('Dealer') + 1
            df_cleaned.insert(dealer_idx, 'Fecha Inicio', fecha_inicio.strftime('%Y-%m-%d'))
            df_cleaned.insert(dealer_idx + 1, 'Fecha Fin', fecha_fin.strftime('%Y-%m-%d'))
        else:
            df_cleaned['Fecha Inicio'] = fecha_inicio.strftime('%Y-%m-%d')
            df_cleaned['Fecha Fin'] = fecha_fin.strftime('%Y-%m-%d')
            
        # PASO 4: EMPAREJAMIENTO DE MONITORES
        if 'Latest Display Software Version' in df_cleaned.columns:
            idx_software = df_cleaned.columns.get_loc('Latest Display Software Version')
            df_cleaned.insert(idx_software + 1, 'Número de Serie Monitor', pd.NA)
        else:
            df_cleaned['Número de Serie Monitor'] = pd.NA

        if uploaded_file_emparejamientos is not None:
            try:
                df_emp_raw = pd.read_excel(uploaded_file_emparejamientos, sheet_name='Emparejamientos')
                df_monitores = df_emp_raw[df_emp_raw['Tipo'].astype(str).str.strip() == 'Monitor'].copy()
                df_monitores['Machine_Pin_emp'] = df_monitores['Número de serie de emparejamiento'].astype(str).str.strip()
                df_monitores['Modelo'] = df_monitores['Modelo'].astype(str).str.strip()
                
                def match_monitor(row):
                    pin = str(row['Machine Pin']).strip()
                    hw = str(row['Latest Display Hardware Type']).strip() if pd.notna(row['Latest Display Hardware Type']) else None
                    
                    machine_monitors = df_monitores[df_monitores['Machine_Pin_emp'] == pin]
                    if machine_monitors.empty:
                        return row
                        
                    if hw is None or hw == 'nan' or hw == '':
                        first_mon = machine_monitors.iloc[0]
                        row['Latest Display Hardware Type'] = first_mon['Modelo']
                        row['Latest Display Software Version'] = first_mon['Versión de software']
                        row['Número de Serie Monitor'] = first_mon['Número de serie']
                    else:
                        match_hw = machine_monitors[machine_monitors['Modelo'] == hw]
                        if not match_hw.empty:
                            row['Número de Serie Monitor'] = match_hw.iloc[0]['Número de serie']
                        else:
                            row['Número de Serie Monitor'] = machine_monitors.iloc[0]['Número de serie']
                    return row

                df_cleaned = df_cleaned.apply(match_monitor, axis=1)
            except Exception as e:
                st.sidebar.warning(f"Error procesando emparejamientos: {e}")
        
        # Guardar en sesión
        st.session_state['df_procesado'] = df_cleaned


# --- INTERFAZ POST-PROCESAMIENTO ---
if st.session_state['df_procesado'] is not None:
    df_base = st.session_state['df_procesado'].copy()
    
    # Identificar columnas de tecnología
    tecnologias = ['AutoTrac', 'RowSense', 'AIG', 'ATIG', 'ATTA', 'AutoPath', 'Machine Sync Leader']
    tech_cols = [col for col in tecnologias if col in df_base.columns]
    
    # PASO 5: FILTRAR FILAS PARA EDICIÓN MANUAL
    has_tech_data = df_base[tech_cols].notna().any(axis=1)
    mask_manual = df_base['Machine Pin'].isna() & df_base['Número de Serie Monitor'].isna() & has_tech_data
    
    if mask_manual.any():
        st.warning("⚠️ **Atención:** Completa los `Machine Pin` o `Número de Serie Monitor` de las siguientes máquinas. Es obligatorio para cruzar luego las licencias.")
        
        df_ok = df_base[~mask_manual]
        df_manual = df_base[mask_manual]
        
        column_config = {
            col: st.column_config.Column(disabled=True) for col in df_manual.columns if col not in ['Machine Pin', 'Número de Serie Monitor']
        }
        
        edited_manual = st.data_editor(
            df_manual,
            column_config=column_config,
            use_container_width=True,
            key="editor_manual"
        )
        
        df_final = pd.concat([df_ok, edited_manual], ignore_index=True)
    else:
        st.success("✅ Base de datos procesada exitosamente. No hay registros pendientes de revisión manual.")
        df_final = df_base
        
    # PASO 6: CRUCE DE LICENCIAS
    if uploaded_file_licencias is not None:
        try:
            df_lic = pd.read_excel(uploaded_file_licencias)
            
            # Desestimar "Receptor de Posición"
            df_lic = df_lic[df_lic['Tipo'].astype(str).str.strip().str.lower() != 'receptor de posición'].copy()
            
            # Preparar columnas para cruce (minúsculas y sin espacios para evitar errores de tipeo)
            df_final['temp_org'] = df_final['Org Name'].astype(str).str.strip().str.lower()
            df_final['temp_pin'] = df_final['Machine Pin'].astype(str).str.strip().str.lower()
            df_final['temp_mon'] = df_final['Número de Serie Monitor'].astype(str).str.strip().str.lower()
            
            df_lic['temp_org'] = df_lic['Nombre del cliente'].astype(str).str.strip().str.lower()
            df_lic['temp_serie'] = df_lic['N.° de serie'].astype(str).str.strip().str.lower()
            
            records = []
            
            for idx, row in df_final.iterrows():
                # Condición 1: Match de Nombre de Cliente (Org Name)
                m_org = df_lic['temp_org'] == row['temp_org']
                # Condición 2: Match de Serie (con Machine Pin O con Display Pin)
                m_serie = (df_lic['temp_serie'] == row['temp_pin']) | (df_lic['temp_serie'] == row['temp_mon'])
                
                matches = df_lic[m_org & m_serie]
                row_dict = row.to_dict()
                
                if matches.empty:
                    # Si no hay licencias, completamos con nulos
                    row_dict['Nombre de licencia'] = pd.NA
                    row_dict['Número de licencia'] = pd.NA
                    row_dict['Estado Licencia'] = pd.NA
                    row_dict['Fecha de inicio'] = pd.NA
                    row_dict['Fecha de terminación'] = pd.NA
                    row_dict['Fecha de vencimiento de pedido'] = pd.NA
                    records.append(row_dict)
                else:
                    # Si hay 1 o más licencias, creamos una fila por cada licencia
                    for _, m_row in matches.iterrows():
                        new_row = row_dict.copy()
                        new_row['Nombre de licencia'] = m_row['Nombre de licencia']
                        new_row['Número de licencia'] = m_row['Número de licencia']
                        new_row['Estado Licencia'] = m_row['Estado']
                        new_row['Fecha de inicio'] = m_row['Fecha de inicio']
                        new_row['Fecha de terminación'] = m_row['Fecha de terminación']
                        new_row['Fecha de vencimiento de pedido'] = m_row['Fecha de vencimiento de pedido']
                        records.append(new_row)
                        
            df_final = pd.DataFrame(records)
            # Limpiamos las columnas temporales
            df_final.drop(columns=['temp_org', 'temp_pin', 'temp_mon'], inplace=True, errors='ignore')
            
            st.success("✅ Archivo de Licencias cruzado correctamente.")
        except Exception as e:
            st.error(f"Error procesando las licencias: {e}")

    # --- MÉTRICAS Y DESCARGA ---
    st.subheader("📈 Resultado Final")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Filas Totales (incluye licencias)", len(df_final))
    
    if 'Número de Serie Monitor' in df_final.columns:
        monitores = df_final['Número de Serie Monitor'].notna().sum()
        r2.metric("Monitores Emparejados", int(monitores))
        
    r3.metric("Machine Pins Activos", int(df_final['Machine Pin'].notna().sum()))
    
    if 'Número de licencia' in df_final.columns:
        licencias_match = df_final['Número de licencia'].notna().sum()
        r4.metric("Licencias Cruzadas", int(licencias_match))
    
    st.subheader("📋 Base de Datos Resultante")
    st.dataframe(df_final, use_container_width=True)
    
    # Preparar el archivo de descarga
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_final.to_excel(writer, index=False, sheet_name='Base_Consolidada')
    excel_data = output.getvalue()
    
    st.download_button(
        label="📥 Descargar Base Consolidada Final (.xlsx)",
        data=excel_data,
        file_name=f"CONCI_Machine_Report_Tech_Final_{fecha_inicio}_{fecha_fin}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
