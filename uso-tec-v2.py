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
cruza los datos con el archivo de **Emparejamientos** y requiere **completar manualmente** 
los equipos que registraron uso de tecnología pero no tienen identificador.
""")

# --- INICIALIZAR VARIABLES EN SESIÓN ---
# Esto es vital para que al editar la tabla manualmente, Streamlit no reinicie el proceso
if 'df_procesado' not in st.session_state:
    st.session_state['df_procesado'] = None

# --- SECCIÓN DE PARÁMETROS Y CARGA ---
st.sidebar.header("📅 Período de Análisis")
fecha_inicio = st.sidebar.date_input("Fecha de Inicio", datetime.date(2025, 1, 1))
fecha_fin = st.sidebar.date_input("Fecha de Fin", datetime.date.today())

st.sidebar.header("📂 Carga de Archivos")
uploaded_file_principal = st.sidebar.file_uploader("1. Machine Report Tech (.xlsx)", type=["xlsx"])
uploaded_file_emparejamientos = st.sidebar.file_uploader("2. Archivo Emparejamientos (.xlsx)", type=["xlsx"])

if uploaded_file_principal is not None:
    # Botón para iniciar el procesamiento en la barra lateral
    if st.sidebar.button("🚀 Procesar, Limpiar y Emparejar", type="primary"):
        # Leer el Excel principal
        df_raw = pd.read_excel(uploaded_file_principal)
        
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
        if 'Latest Display Software Version' in df_cleaned.columns:
            idx_software = df_cleaned.columns.get_loc('Latest Display Software Version')
            df_cleaned.insert(idx_software + 1, 'Número de Serie Monitor', pd.NA)
        else:
            df_cleaned['Número de Serie Monitor'] = pd.NA

        if uploaded_file_emparejamientos is not None:
            try:
                df_emp_raw = pd.read_excel(uploaded_file_emparejamientos, sheet_name='Emparejamientos')
                df_monitores = df_emp_raw[df_emp_raw['Tipo'] == 'Monitor'].copy()
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
        
        # Guardar en memoria de sesión
        st.session_state['df_procesado'] = df_cleaned


# --- INTERFAZ POST-PROCESAMIENTO ---
if st.session_state['df_procesado'] is not None:
    df_base = st.session_state['df_procesado'].copy()
    
    # Identificar columnas de tecnología 
    tecnologias = ['AutoTrac', 'RowSense', 'AIG', 'ATIG', 'ATTA', 'AutoPath', 'Machine Sync Leader']
    tech_cols = [col for col in tecnologias if col in df_base.columns]
    
    # PASO 5: FILTRAR FILAS PARA EDICIÓN MANUAL
    # Chequeamos si alguna tecnología tiene datos (excluyendo campos nulos de la fórmula)
    has_tech_data = df_base[tech_cols].notna().any(axis=1)
    # Condición: Falta PIN y Falta Serie del Monitor y Tiene datos de tecnología
    mask_manual = df_base['Machine Pin'].isna() & df_base['Número de Serie Monitor'].isna() & has_tech_data
    
    if mask_manual.any():
        st.warning("⚠️ **Atención:** Se encontraron registros que reportan uso de tecnología pero no tienen asignado ni **Machine Pin** ni **Número de Serie Monitor**. Es obligatorio completarlos.")
        
        # Separar las bases
        df_ok = df_base[~mask_manual]
        df_manual = df_base[mask_manual]
        
        st.markdown("### ✏️ Edición Manual Obligatoria")
        st.markdown("Por favor, haz **doble clic en las celdas vacías** de la tabla para completar `Machine Pin` y/o `Número de Serie Monitor`. Al terminar de escribir, la base final se actualizará abajo automáticamente.")
        
        # Bloquear edición en el resto de las columnas para evitar errores
        column_config = {
            col: st.column_config.Column(disabled=True) for col in df_manual.columns if col not in ['Machine Pin', 'Número de Serie Monitor']
        }
        
        # Mostrar el editor interactivo
        edited_manual = st.data_editor(
            df_manual,
            column_config=column_config,
            use_container_width=True,
            key="editor_manual"
        )
        
        # Unir las bases de nuevo con los datos editados
        df_final = pd.concat([df_ok, edited_manual], ignore_index=True)
        
        # Validación: Chequear si todavía quedan filas de estas sin completar
        aún_vacios = edited_manual['Machine Pin'].isna() & edited_manual['Número de Serie Monitor'].isna()
        if aún_vacios.any():
            st.error("❌ Aún hay registros de la tabla superior sin identificar. Sigue editando las celdas.")
        else:
            st.success("✅ Todos los campos obligatorios detectados fueron completados.")
            
    else:
        st.success("¡Base de datos procesada exitosamente! No se detectaron registros con tecnología sin identificar.")
        df_final = df_base
        
    # --- MÉTRICAS Y DESCARGA ---
    st.subheader("📈 Resultado Final")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Filas consolidadas", len(df_final))
    if 'Número de Serie Monitor' in df_final.columns:
        monitores_rescatados = df_final['Número de Serie Monitor'].notna().sum()
        r2.metric("Monitores con N° de Serie", int(monitores_rescatados))
    r3.metric("Machine Pins Finales", int(df_final['Machine Pin'].notna().sum()))
    r4.metric("% Cobertura PIN", f"{(df_final['Machine Pin'].notna().mean()*100):.1f}%")
    
    st.subheader("📋 Base de Datos Resultante")
    st.dataframe(df_final, use_container_width=True)
    
    # Preparar el archivo de descarga
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_final.to_excel(writer, index=False, sheet_name='Base_Limpia')
    excel_data = output.getvalue()
    
    st.download_button(
        label="📥 Descargar Base Depurada Final (.xlsx)",
        data=excel_data,
        file_name=f"CONCI_Machine_Report_Tech_{fecha_inicio}_{fecha_fin}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
