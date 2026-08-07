import streamlit as st
import pandas as pd
import io
import datetime
import requests
import base64

# Configuración de la página
st.set_page_config(
    page_title="Depurador de Base de Datos - CONCI",
    page_icon="🚜",
    layout="wide"
)

# Nombre fijo del archivo consolidado en el repositorio de GitHub
NOMBRE_ARCHIVO_GITHUB = "data/base_datos_consolidada.xlsx"

st.title("🚜 Depurador y Consolidador de Maquinarias & Tecnología")
st.markdown("""
Esta herramienta procesa el reporte semanal de maquinarias, consolida los registros, 
cruza los datos con **Emparejamientos**, **Licencias** y **Organizaciones/Sucursales**, 
y los **acumula semana a semana** en la base de datos de GitHub.
""")

# --- FUNCIÓN PARA OBTENER LA BASE EXISTENTE DE GITHUB ---
@st.cache_data(ttl=60) # Guarda en caché por 1 min para no saturar la API
def consultar_base_github():
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
            df_existente = pd.read_excel(io.BytesIO(file_bytes))
            
            # Obtener último período registrado
            if 'Fecha Fin' in df_existente.columns and 'Fecha Inicio' in df_existente.columns:
                df_existente['Fecha Fin Temp'] = pd.to_datetime(df_existente['Fecha Fin'], errors='coerce')
                df_existente['Fecha Inicio Temp'] = pd.to_datetime(df_existente['Fecha Inicio'], errors='coerce')
                
                ultimo_fin = df_existente['Fecha Fin Temp'].max()
                ultimo_inicio = df_existente[df_existente['Fecha Fin Temp'] == ultimo_fin]['Fecha Inicio Temp'].min()
                
                # Limpiar columnas temporales
                df_existente.drop(columns=['Fecha Fin Temp', 'Fecha Inicio Temp'], inplace=True)
                
                str_inicio = ultimo_inicio.strftime('%Y-%m-%d') if pd.notna(ultimo_inicio) else "N/A"
                str_fin = ultimo_fin.strftime('%Y-%m-%d') if pd.notna(ultimo_fin) else "N/A"
                
                return df_existente, str_inicio, str_fin
            return df_existente, "Desconocido", "Desconocido"
        else:
            return None, None, None
    except Exception:
        return None, None, None


# --- FUNCIÓN PARA SUBIR/SOBREESCRIBIR EN GITHUB VIA API ---
def subir_a_github(file_bytes, mensaje_commit):
    try:
        gh_config = st.secrets["github"]
        token = gh_config["token"]
        repo = gh_config["repo"]
        branch = gh_config.get("branch", "main")
        
        url = f"https://api.github.com/repos/{repo}/contents/{NOMBRE_ARCHIVO_GITHUB}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Verificar si el archivo ya existe para obtener su SHA
        res_get = requests.get(f"{url}?ref={branch}", headers=headers)
        sha = res_get.json().get("sha") if res_get.status_code == 200 else None
        
        content_b64 = base64.b64encode(file_bytes).decode('utf-8')
        
        payload = {
            "message": mensaje_commit,
            "content": content_b64,
            "branch": branch
        }
        if sha:
            payload["sha"] = sha
            
        res_put = requests.put(url, headers=headers, json=payload)
        
        if res_put.status_code in [200, 201]:
            st.cache_data.clear() # Limpiar caché para refrescar la lectura
            return True, f"✅ Base de datos actualizada en GitHub (`{repo}/{NOMBRE_ARCHIVO_GITHUB}`)"
        else:
            return False, f"❌ Error de GitHub ({res_put.status_code}): {res_put.json().get('message')}"
            
    except KeyError:
        return False, "⚠️ Falta la configuración de GitHub en `st.secrets`."
    except Exception as e:
        return False, f"❌ Error al conectar con GitHub: {e}"


# --- ESTADO DE LA BASE DE DATOS EN GITHUB (PANEL SUPERIOR) ---
df_historico, ult_inicio, ult_fin = consultar_base_github()

st.sidebar.markdown("---")
st.sidebar.header("📌 Estado en GitHub")

if df_historico is not None:
    st.info(f"""
    📅 **Último período en GitHub:**  
    **Desde:** `{ult_inicio}`  
    **Hasta:** `{ult_fin}`  
    
    📊 **Total registros acumulados:** {len(df_historico)} filas
    """)
else:
    st.warning("⚠️ No se encontró una base acumulada en GitHub. La primera subida creará el archivo inicial.")


# --- INICIALIZAR VARIABLES EN SESIÓN ---
if 'df_procesado' not in st.session_state:
    st.session_state['df_procesado'] = None

# --- SECCIÓN DE PARÁMETROS Y CARGA NUEVA SEMANA ---
st.sidebar.header("📅 Período de la Nueva Semana")
fecha_inicio = st.sidebar.date_input("Fecha de Inicio", datetime.date.today() - datetime.timedelta(days=7))
fecha_fin = st.sidebar.date_input("Fecha de Fin", datetime.date.today())

st.sidebar.header("📂 Carga de Archivos de la Semana")
uploaded_file_principal = st.sidebar.file_uploader("1. Machine Report Tech (.xlsx)", type=["xlsx"])
uploaded_file_emparejamientos = st.sidebar.file_uploader("2. Archivo Emparejamientos (.xlsx)", type=["xlsx"])
uploaded_file_licencias = st.sidebar.file_uploader("3. Archivo Licencias (.xlsx)", type=["xlsx"])
uploaded_file_orgs = st.sidebar.file_uploader("4. Base Orgs & Sucursales (.csv)", type=["csv"])

if uploaded_file_principal is not None:
    if st.sidebar.button("🚀 Procesar Semana Actual", type="primary"):
        df_raw = pd.read_excel(uploaded_file_principal)
        
        # PASO 1: Eliminar filas vacías
        mask_empty = (
            df_raw['Machine Pin'].isna() & 
            df_raw['Product Family'].isna() & 
            df_raw['Latest Display Hardware Type'].isna()
        )
        df_filtered = df_raw[~mask_empty].copy()
        
        # PASO 2: Unificación de filas dentro del reporte semanal
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
        
        # PASO 3: Insertar Fechas de la semana procesada
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
        st.warning("⚠️ **Atención:** Completa los `Machine Pin` o `Número de Serie Monitor` pendientes de esta semana:")
        
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
        
        df_final_semana = pd.concat([df_ok, edited_manual], ignore_index=True)
    else:
        st.success("✅ Semana procesada exitosamente sin inconsistencias pendientes.")
        df_final_semana = df_base
        
    # PASO 6: CRUCE DE LICENCIAS
    if uploaded_file_licencias is not None:
        try:
            df_lic = pd.read_excel(uploaded_file_licencias)
            df_lic = df_lic[df_lic['Tipo'].astype(str).str.strip().str.lower() != 'receptor de posición'].copy()
            
            df_final_semana['temp_org'] = df_final_semana['Org Name'].astype(str).str.strip().str.lower()
            df_final_semana['temp_pin'] = df_final_semana['Machine Pin'].astype(str).str.strip().str.lower()
            df_final_semana['temp_mon'] = df_final_semana['Número de Serie Monitor'].astype(str).str.strip().str.lower()
            
            df_lic['temp_org'] = df_lic['Nombre del cliente'].astype(str).str.strip().str.lower()
            df_lic['temp_serie'] = df_lic['N.° de serie'].astype(str).str.strip().str.lower()
            
            records = []
            for idx, row in df_final_semana.iterrows():
                m_org = df_lic['temp_org'] == row['temp_org']
                m_serie = (df_lic['temp_serie'] == row['temp_pin']) | (df_lic['temp_serie'] == row['temp_mon'])
                
                matches = df_lic[m_org & m_serie]
                row_dict = row.to_dict()
                
                if matches.empty:
                    row_dict['Nombre de licencia'] = pd.NA
                    row_dict['Número de licencia'] = pd.NA
                    row_dict['Estado Licencia'] = pd.NA
                    row_dict['Fecha de inicio'] = pd.NA
                    row_dict['Fecha de terminación'] = pd.NA
                    row_dict['Fecha de vencimiento de pedido'] = pd.NA
                    records.append(row_dict)
                else:
                    for _, m_row in matches.iterrows():
                        new_row = row_dict.copy()
                        new_row['Nombre de licencia'] = m_row['Nombre de licencia']
                        new_row['Número de licencia'] = m_row['Número de licencia']
                        new_row['Estado Licencia'] = m_row['Estado']
                        new_row['Fecha de inicio'] = m_row['Fecha de inicio']
                        new_row['Fecha de terminación'] = m_row['Fecha de terminación']
                        new_row['Fecha de vencimiento de pedido'] = m_row['Fecha de vencimiento de pedido']
                        records.append(new_row)
                        
            df_final_semana = pd.DataFrame(records)
            df_final_semana.drop(columns=['temp_org', 'temp_pin', 'temp_mon'], inplace=True, errors='ignore')
        except Exception as e:
            st.error(f"Error procesando las licencias: {e}")

    # PASO 7: CRUCE DE SUCURSAL
    if uploaded_file_orgs is not None:
        try:
            df_orgs_raw = pd.read_csv(uploaded_file_orgs)
            
            def clean_org_id(val):
                if pd.isna(val):
                    return None
                try:
                    return str(int(float(val))).strip()
                except (ValueError, TypeError):
                    return str(val).strip()

            mapping_sucursal = {}
            if 'Org ID' in df_orgs_raw.columns and 'SUC?' in df_orgs_raw.columns:
                for _, r in df_orgs_raw.iterrows():
                    if pd.notna(r['Org ID']) and pd.notna(r['SUC?']):
                        k = clean_org_id(r['Org ID'])
                        if k:
                            mapping_sucursal[k] = str(r['SUC?']).strip()
            
            col_org_id = None
            for candidate in ['Org Id', 'Org ID', 'ORG ID', 'Org id']:
                if candidate in df_final_semana.columns:
                    col_org_id = candidate
                    break
                    
            if col_org_id:
                df_final_semana['temp_org_key'] = df_final_semana[col_org_id].apply(clean_org_id)
                df_final_semana['Sucursal'] = df_final_semana['temp_org_key'].map(mapping_sucursal)
                df_final_semana.drop(columns=['temp_org_key'], inplace=True, errors='ignore')
        except Exception as e:
            st.error(f"Error procesando sucursales: {e}")

    # --- UNIFICACIÓN / CONCATENACIÓN CON LA BASE HISTÓRICA ---
    if df_historico is not None:
        # Unir base histórica + semana actual y eliminar duplicados exactos si los hay
        df_acumulado = pd.concat([df_historico, df_final_semana], ignore_index=True)
        df_acumulado.drop_duplicates(inplace=True)
    else:
        df_acumulado = df_final_semana.copy()

    # --- MÉTRICAS Y RESUMEN ---
    st.subheader("📈 Resumen de la Consolidación")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Filas Nuevas (Semana)", len(df_final_semana))
    m2.metric("Total Acumulado Historico", len(df_acumulado))
    m3.metric("Período Procesado", f"{fecha_inicio} a {fecha_fin}")
    m4.metric("Máquinas Nuevas con PIN", int(df_final_semana['Machine Pin'].notna().sum()))
    
    st.subheader("📋 Vista Previa de la Base Acumulada")
    st.dataframe(df_acumulado.tail(20), use_container_width=True)
    st.caption("Mostrando los últimos 20 registros acumulados.")
    
    # --- PREPARACIÓN DEL EXCEL PARALELO ---
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_acumulado.to_excel(writer, index=False, sheet_name='Base_Consolidada')
    excel_bytes_acumulado = output.getvalue()

    # --- BOTONES DE ACCIÓN ---
    st.subheader("🚀 Exportación e Integración")
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.download_button(
            label="📥 Descargar Copia Local Acumulada (.xlsx)",
            data=excel_bytes_acumulado,
            file_name=f"CONCI_Base_Acumulada_{fecha_fin}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
    with c2:
        msg_commit = f"🤖 Carga semanal: {fecha_inicio} al {fecha_fin} ({len(df_final_semana)} filas)"
        if st.button("📤 Anexar y Guardar en GitHub", type="primary", use_container_width=True):
            with st.spinner("Actualizando base histórica en GitHub..."):
                exito, mensaje = subir_a_github(excel_bytes_acumulado, msg_commit)
                if exito:
                    st.success(mensaje)
                    st.rerun() # Recargar la app para actualizar las métricas
                else:
                    st.error(mensaje)
