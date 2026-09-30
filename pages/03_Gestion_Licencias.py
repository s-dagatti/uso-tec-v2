import base64
import io
import re
import uuid

import numpy as np
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Gestión de Licencias", page_icon="🔑", layout="wide")
st.title("🔑 Constructor de la Base Histórica de Licencias")
st.caption("Consolida equipos, emparejamientos, licencias Operations Center y control administrativo en una foto por fecha de actualización.")

HISTORICO_PATH = "datos_licencias_clientes.csv"

COMPONENTES_VALIDOS = [
    "Monitor",
    "Receptores de posición"
]

ADMIN_VALIDOS = [
    "Monitor Gen 4",
    "Antena 6000"
]


def limpiar_texto(serie):
    return (
        serie
        .astype("string")
        .str.strip()
        .replace(
            {
                "---": pd.NA,
                "": pd.NA,
                "nan": pd.NA
            }
        )
    )


def normalizar_serie(serie):

    return (
        limpiar_texto(serie)
        .str.upper()
        .str.replace(
            r"[^A-Z0-9]",
            "",
            regex=True
        )
        .replace("", pd.NA)
    )


def normalizar_orgid(serie):

    return (
        pd.to_numeric(
            serie,
            errors="coerce"
        )
        .astype("Int64")
        .astype("string")
        .replace("<NA>", pd.NA)
    )


def leer_csv_robusto(archivo):

    if hasattr(archivo, "getvalue"):
        datos = archivo.getvalue()
    else:
        datos = archivo.read()

    configuraciones = [
        ("utf-8-sig", ","),
        ("utf-8", ","),
        ("cp1252", ","),
        ("latin1", ","),
        ("utf-8-sig", ";"),
        ("cp1252", ";"),
        ("latin1", ";"),
        ("utf-8-sig", "\t"),
        ("cp1252", "\t"),
    ]

    for encoding, separador in configuraciones:

        try:

            df = pd.read_csv(
                io.BytesIO(datos),
                encoding=encoding,
                sep=separador,
                engine="python"
            )

            # Evita aceptar una lectura mala
            # donde todo quedó en una sola columna
            if len(df.columns) > 1:

                df.columns = (
                    df.columns
                    .astype(str)
                    .str.strip()
                )

                return df

        except Exception:
            continue

    raise ValueError(
        "No se pudo leer el CSV."
    )


def exigir_columnas(df, requeridas, nombre):

    faltantes = [
        c
        for c in requeridas
        if c not in df.columns
    ]

    if faltantes:

        raise ValueError(
            f"{nombre}: faltan columnas: {', '.join(faltantes)}"
        )


def fecha_mixta(serie):

    try:

        return pd.to_datetime(
            serie,
            format="mixed",
            dayfirst=True,
            errors="coerce"
        )

    except TypeError:

        return pd.to_datetime(
            serie,
            dayfirst=True,
            errors="coerce"
        )


def cargar_config_github():

    try:

        return (
            st.secrets["github"]["repo"],
            st.secrets["github"]["token"]
        )

    except Exception:

        return (
            None,
            None
        )


@st.cache_data(
    ttl=60,
    show_spinner=False
)
def cargar_historico(repo, path, token):

    if not repo or not token:
        return pd.DataFrame()

    url = (
        f"https://api.github.com/repos/"
        f"{repo}/contents/{path}"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.raw+json"
    }

    respuesta = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    if respuesta.status_code == 404:
        return pd.DataFrame()

    respuesta.raise_for_status()

    return pd.read_csv(
        io.StringIO(respuesta.text),
        low_memory=False
    )



def guardar_github(df, repo, path, token, mensaje):
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    consulta = requests.get(url, headers=headers, timeout=30)
    sha = consulta.json().get("sha") if consulta.status_code == 200 else None
    contenido = base64.b64encode(df.to_csv(index=False).encode("utf-8-sig")).decode("ascii")
    payload = {"message": mensaje, "content": contenido}
    if sha:
        payload["sha"] = sha
    respuesta = requests.put(url, headers=headers, json=payload, timeout=60)
    if respuesta.status_code not in (200, 201):
        raise RuntimeError(respuesta.json().get("message", respuesta.text))


def detectar_columna(df, candidatos, etiqueta):
    mapa = {str(c).strip().lower(): c for c in df.columns}
    for candidato in candidatos:
        if candidato.lower() in mapa:
            return mapa[candidato.lower()]
    raise ValueError(f"No se encontró la columna {etiqueta} en la base de organizaciones.")


def estado_unificado(estado_original, vencimiento, fecha_corte):
    estado = "" if pd.isna(estado_original) else str(estado_original).strip().upper()
    if "CANCEL" in estado:
        return "Cancelada"
    if "NO ACTIV" in estado:
        return "No activada"
    if pd.isna(vencimiento):
        if "VENC" in estado:
            return "Vencida"
        if "VIG" in estado or "ACTIV" in estado:
            return "Vigente"
        return "Sin fecha"
    dias = (vencimiento.normalize() - pd.Timestamp(fecha_corte)).days
    if dias < 0:
        return "Vencida"
    if dias <= 30:
        return "Vence en 30 días"
    if dias <= 60:
        return "Vence en 60 días"
    if dias <= 90:
        return "Vence en 90 días"
    return "Vigente"


def familia_licencia(nombre, componente, modelo):
    texto = f"{nombre} {componente} {modelo}".upper()
    if "G5" in texto or "ULTIMATE" in texto:
        return "G5"
    if "7000" in texto:
        return "SF7000"
    if "7500" in texto:
        return "SF7500"
    if "6000" in texto or "SF2" in texto or "SF3" in texto:
        return "SF6000"
    if "GEN 4" in texto or "4240" in texto or "4640" in texto or "COMMANDCENTER" in texto:
        return "Gen4"
    return "Otra"


def movimiento_admin(producto):
    texto = "" if pd.isna(producto) else str(producto).strip()
    prefijo = texto.split("-")[0].strip().lower()
    if prefijo.startswith("renov"):
        return "Renovación"
    if prefijo.startswith("actual"):
        return "Actualización"
    if prefijo.startswith("nuevo"):
        return "Nuevo"
    return "No informado"


def preparar_maestros(archivo_equipos):
    maquinas = pd.read_excel(archivo_equipos, sheet_name="Máquinas", engine="openpyxl")
    emp = pd.read_excel(archivo_equipos, sheet_name="Emparejamientos", engine="openpyxl")
    exigir_columnas(maquinas, ["Alías", "Número de serie", "Modelo", "Tipo", "Identificador de organización", "Nombre de organización"], "Hoja Máquinas")
    exigir_columnas(emp, ["Número de serie", "Modelo", "Tipo", "Versión de software", "Identificador de organización", "Nombre de organización", "Número de serie de emparejamiento"], "Hoja Emparejamientos")

    maquinas["Serie Máquina"] = limpiar_texto(maquinas["Número de serie"])
    maquinas["_maq"] = normalizar_serie(maquinas["Número de serie"])
    maquinas["Org ID Máquina"] = normalizar_orgid(maquinas["Identificador de organización"])
    maquinas = maquinas[maquinas["_maq"].notna()].copy()
    if "Visto por última vez" in maquinas:
        maquinas["_orden"] = fecha_mixta(maquinas["Visto por última vez"])
        maquinas = maquinas.sort_values("_orden")
    maquinas = maquinas.drop_duplicates("_maq", keep="last")
    maquinas = maquinas.rename(columns={"Alías": "Alias Máquina", "Modelo": "Modelo Máquina", "Tipo": "Tipo Máquina", "Nombre de organización": "Organización Máquina"})

    emp = emp[emp["Tipo"].isin(COMPONENTES_VALIDOS)].copy()
    emp["Serie Componente"] = limpiar_texto(emp["Número de serie"])
    emp["_comp"] = normalizar_serie(emp["Número de serie"])
    emp["_maq"] = normalizar_serie(emp["Número de serie de emparejamiento"])
    emp["Org ID Componente"] = normalizar_orgid(emp["Identificador de organización"])
    emp = emp[emp["_comp"].notna()].copy()
    if "Visto por última vez" in emp:
        emp["_orden"] = fecha_mixta(emp["Visto por última vez"])
        emp = emp.sort_values("_orden")
    emp = emp.drop_duplicates("_comp", keep="last")
    emp = emp.rename(columns={"Tipo": "Tipo Componente", "Modelo": "Modelo Componente", "Versión de software": "Versión Software", "Nombre de organización": "Organización Componente"})

    cols_maq = ["_maq", "Serie Máquina", "Alias Máquina", "Modelo Máquina", "Tipo Máquina", "Org ID Máquina", "Organización Máquina"]
    comp = emp.merge(maquinas[cols_maq], on="_maq", how="left")
    return maquinas, comp


def consolidar(fecha_actualizacion, archivo_equipos, archivo_orgs, archivo_licencias, archivo_admin):
    maquinas, comp = preparar_maestros(archivo_equipos)

    orgs = leer_csv_robusto(archivo_orgs)
    col_org = detectar_columna(orgs, ["Org ID", "OrgId", "ID de organización", "ID de cliente/organización"], "Org ID")
    col_suc = detectar_columna(orgs, ["Sucursal", "SUC?", "SUCURSAL"], "Sucursal")
    mapa_org = orgs[[col_org, col_suc]].copy()
    mapa_org["Org ID"] = normalizar_orgid(mapa_org[col_org])
    mapa_org["Sucursal"] = limpiar_texto(mapa_org[col_suc])
    mapa_org = mapa_org.dropna(subset=["Org ID"]).drop_duplicates("Org ID", keep="last")[["Org ID", "Sucursal"]]

    lic = pd.read_excel(archivo_licencias, sheet_name="Licencias", engine="openpyxl")
    exigir_columnas(lic, ["Nombre de licencia", "Número de licencia", "Nombre del cliente", "OrgId", "Estado", "Fecha de inicio", "Fecha de terminación", "N.° de serie", "Modelo", "Tipo"], "Licencias Operations Center")
    lic["Serie Asignada Licencia"] = limpiar_texto(lic["N.° de serie"])
    lic["_asignada"] = normalizar_serie(lic["N.° de serie"])
    lic["Org ID Licencia"] = normalizar_orgid(lic["OrgId"])

    comp_idx = comp.set_index("_comp", drop=False)
    maq_idx = maquinas.set_index("_maq", drop=False)
    mon_por_maq = (comp[comp["Tipo Componente"].eq("Monitor")].drop_duplicates("_maq", keep="last").set_index("_maq", drop=False))

    filas = []
    for _, r in lic.iterrows():
        asignada = r["_asignada"]
        tipo = "" if pd.isna(r["Tipo"]) else str(r["Tipo"]).strip()
        c = None
        m = None
        metodo = "No encontrado"
        if pd.isna(asignada):
            metodo = "Sin serie asignada"
        elif tipo in ("Monitor", "Receptor de posición") and asignada in comp_idx.index:
            c = comp_idx.loc[asignada]
            if isinstance(c, pd.DataFrame): c = c.iloc[-1]
            metodo = "Serie de monitor" if tipo == "Monitor" else "Serie de receptor"
        elif tipo == "Machine" and asignada in maq_idx.index:
            m = maq_idx.loc[asignada]
            if isinstance(m, pd.DataFrame): m = m.iloc[-1]
            if asignada in mon_por_maq.index:
                c = mon_por_maq.loc[asignada]
                if isinstance(c, pd.DataFrame): c = c.iloc[-1]
            metodo = "Serie de máquina"
        elif asignada in comp_idx.index:
            c = comp_idx.loc[asignada]
            if isinstance(c, pd.DataFrame): c = c.iloc[-1]
            metodo = "Serie de componente inferida"
        elif asignada in maq_idx.index:
            m = maq_idx.loc[asignada]
            if isinstance(m, pd.DataFrame): m = m.iloc[-1]
            metodo = "Serie de máquina inferida"

        def valor(obj, campo):
            return obj.get(campo, pd.NA) if obj is not None else pd.NA
        orgid = r["Org ID Licencia"]
        if pd.isna(orgid): orgid = valor(c, "Org ID Componente")
        if pd.isna(orgid): orgid = valor(m, "Org ID Máquina")
        organizacion = r["Nombre del cliente"]
        if pd.isna(organizacion): organizacion = valor(c, "Organización Componente")
        venc = fecha_mixta(pd.Series([r["Fecha de terminación"]])).iloc[0]
        nombre = r["Nombre de licencia"]
        modelo_comp = valor(c, "Modelo Componente")
        tipo_comp = valor(c, "Tipo Componente")
        filas.append({
            "Org ID": orgid, "Organización": organizacion,
            "Alias Máquina": valor(c, "Alias Máquina") if c is not None else valor(m, "Alias Máquina"),
            "Serie Máquina": valor(c, "Serie Máquina") if c is not None else valor(m, "Serie Máquina"),
            "Modelo Máquina": valor(c, "Modelo Máquina") if c is not None else valor(m, "Modelo Máquina"),
            "Tipo Máquina": valor(c, "Tipo Máquina") if c is not None else valor(m, "Tipo Máquina"),
            "Tipo Componente": tipo_comp if c is not None else ("Máquina" if tipo == "Machine" else tipo),
            "Modelo Componente": modelo_comp if c is not None else r["Modelo"],
            "Serie Componente": valor(c, "Serie Componente"), "Versión Software": valor(c, "Versión Software"),
            "Serie Asignada Licencia": r["Serie Asignada Licencia"], "Tipo Asignación Original": tipo,
            "Nombre Licencia": nombre, "Número Licencia": r["Número de licencia"],
            "Tipo Movimiento": "No informado", "Fecha Inicio Licencia": fecha_mixta(pd.Series([r["Fecha de inicio"]])).iloc[0],
            "Fecha Vencimiento": venc, "Estado Original": r["Estado"],
            "Estado Licencia": estado_unificado(r["Estado"], venc, fecha_actualizacion),
            "Familia Licencia": familia_licencia(nombre, tipo_comp, modelo_comp),
            "Fuente": "Operations Center", "Método Vinculación": metodo
        })

    admin = leer_csv_robusto(archivo_admin)
    exigir_columnas(admin, ["COMPONENTE", "Tornillería", "Producto", "Fecha de inicio", "Fecha final", "ID de cliente/organización", "Nombre del cliente", "ESTADO"], "Control administrativo")
    admin = admin[limpiar_texto(admin["COMPONENTE"]).isin(ADMIN_VALIDOS)].copy()
    admin["_comp"] = normalizar_serie(admin["Tornillería"])
    admin["Org ID Admin"] = normalizar_orgid(admin["ID de cliente/organización"])
    for _, r in admin.iterrows():
        clave = r["_comp"]
        c = None
        if pd.notna(clave) and clave in comp_idx.index:
            c = comp_idx.loc[clave]
            if isinstance(c, pd.DataFrame): c = c.iloc[-1]
        venc = fecha_mixta(pd.Series([r["Fecha final"]])).iloc[0]
        nombre = r["Producto"]
        componente = r["COMPONENTE"]
        orgid = r["Org ID Admin"] if pd.notna(r["Org ID Admin"]) else (c.get("Org ID Componente", pd.NA) if c is not None else pd.NA)
        filas.append({
            "Org ID": orgid, "Organización": r["Nombre del cliente"],
            "Alias Máquina": c.get("Alias Máquina", pd.NA) if c is not None else pd.NA,
            "Serie Máquina": c.get("Serie Máquina", pd.NA) if c is not None else pd.NA,
            "Modelo Máquina": c.get("Modelo Máquina", pd.NA) if c is not None else pd.NA,
            "Tipo Máquina": c.get("Tipo Máquina", pd.NA) if c is not None else pd.NA,
            "Tipo Componente": "Monitor" if componente == "Monitor Gen 4" else "Receptor de posición",
            "Modelo Componente": componente,
            "Serie Componente": r["Tornillería"],
            "Versión Software": c.get("Versión Software", pd.NA) if c is not None else pd.NA,
            "Serie Asignada Licencia": r["Tornillería"], "Tipo Asignación Original": componente,
            "Nombre Licencia": nombre, "Número Licencia": r.get("ID", pd.NA),
            "Tipo Movimiento": movimiento_admin(nombre),
            "Fecha Inicio Licencia": fecha_mixta(pd.Series([r["Fecha de inicio"]])).iloc[0],
            "Fecha Vencimiento": venc, "Estado Original": r["ESTADO"],
            "Estado Licencia": estado_unificado(r["ESTADO"], venc, fecha_actualizacion),
            "Familia Licencia": familia_licencia(nombre, componente, componente),
            "Fuente": "Control administrativo",
            "Método Vinculación": "Serie de componente" if c is not None else "No encontrado"
        })

    salida = pd.DataFrame(filas)
    salida["Org ID"] = normalizar_orgid(salida["Org ID"])
    salida = salida.merge(mapa_org, on="Org ID", how="left")
    salida["Fecha de Actualización"] = pd.Timestamp(fecha_actualizacion)
    salida["Fecha de Carga"] = pd.Timestamp.now()
    salida["Lote de Actualización"] = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    salida["Días para Vencer"] = (pd.to_datetime(salida["Fecha Vencimiento"], errors="coerce") - pd.Timestamp(fecha_actualizacion)).dt.days
    salida["Clave Componente"] = normalizar_serie(salida["Serie Componente"]).fillna(normalizar_serie(salida["Serie Asignada Licencia"]))
    salida["Clave Licencia"] = limpiar_texto(salida["Número Licencia"]).fillna(limpiar_texto(salida["Nombre Licencia"]))

    orden = ["Fecha de Actualización", "Fecha de Carga", "Lote de Actualización", "Sucursal", "Org ID", "Organización",
             "Alias Máquina", "Serie Máquina", "Modelo Máquina", "Tipo Máquina", "Tipo Componente", "Modelo Componente",
             "Serie Componente", "Versión Software", "Serie Asignada Licencia", "Tipo Asignación Original", "Nombre Licencia",
             "Número Licencia", "Familia Licencia", "Tipo Movimiento", "Fecha Inicio Licencia", "Fecha Vencimiento", "Días para Vencer",
             "Estado Original", "Estado Licencia", "Fuente", "Método Vinculación", "Clave Componente", "Clave Licencia"]
    return salida[orden]


repo, token = cargar_config_github()
try:
    historico = cargar_historico(repo, HISTORICO_PATH, token)
except Exception as e:
    historico = pd.DataFrame()
    st.warning(f"No se pudo leer el histórico de GitHub: {e}")

st.subheader("📦 Estado del histórico")
a, b, c = st.columns(3)
a.metric("Registros históricos", f"{len(historico):,}")
if not historico.empty and "Fecha de Actualización" in historico:
    ultima = pd.to_datetime(historico["Fecha de Actualización"], format="mixed", errors="coerce").max()
    b.metric("Última actualización", ultima.strftime("%d/%m/%Y") if pd.notna(ultima) else "Sin datos")
    c.metric("Componentes", historico.get("Clave Componente", pd.Series(dtype=str)).nunique())
else:
    b.metric("Última actualización", "Sin datos")
    c.metric("Componentes", 0)

st.subheader("📁 Archivos de entrada")
col1, col2 = st.columns(2)
with col1:
    archivo_equipos = st.file_uploader("1. Excel de Máquinas y Emparejamientos", type=["xlsx"], key="lic_equipos")
    archivo_licencias = st.file_uploader("3. Excel de licencias G5 / SF7000 / SF7500", type=["xlsx"], key="lic_oc")
with col2:
    archivo_orgs = st.file_uploader("2. CSV de Org ID y Sucursal", type=["csv"], key="lic_orgs")
    archivo_admin = st.file_uploader("4. CSV de control administrativo Gen4 / SF6000", type=["csv"], key="lic_admin")

fecha_actualizacion = st.date_input("📅 Fecha de actualización", value=pd.Timestamp.today().date(), key="fecha_actualizacion_licencias")

if all([archivo_equipos, archivo_orgs, archivo_licencias, archivo_admin]):
    try:
        with st.spinner("Consolidando componentes y licencias..."):
            foto = consolidar(fecha_actualizacion, archivo_equipos, archivo_orgs, archivo_licencias, archivo_admin)

        st.success("Archivos procesados correctamente.")
        x1, x2, x3, x4 = st.columns(4)
        x1.metric("Licencias en la foto", f"{len(foto):,}")
        x2.metric("Componentes identificados", foto["Clave Componente"].nunique())
        x3.metric("Vigentes", foto["Estado Licencia"].eq("Vigente").sum())
        x4.metric("Vencidas", foto["Estado Licencia"].eq("Vencida").sum())

        st.subheader("🔎 Control del cruce")
        control = foto.groupby(["Fuente", "Método Vinculación"], dropna=False).size().reset_index(name="Registros")
        st.dataframe(control, use_container_width=True, hide_index=True)

        if not historico.empty:
            final = pd.concat([historico, foto], ignore_index=True, sort=False)
        else:
            final = foto.copy()
        claves_dedup = [c for c in ["Fecha de Actualización", "Fuente", "Clave Componente", "Clave Licencia", "Fecha Inicio Licencia", "Fecha Vencimiento"] if c in final.columns]
        final = final.drop_duplicates(subset=claves_dedup, keep="last")

        st.subheader("👁️ Vista previa de la nueva foto")

        tab_todas, tab_operations, tab_admin = st.tabs([
            "📋 Todas",
            "🛰️ Operations Center",
            "🗂️ Control Administrativo"
        ])
        
        with tab_todas:
        
            st.caption(
                f"{len(foto):,} registros"
            )
        
            st.dataframe(
                foto,
                use_container_width=True,
                hide_index=True
            )
        
        with tab_operations:
        
            df_operations = (
                foto[
                    foto["Fuente"]
                    == "Operations Center"
                ]
            )
        
            st.caption(
                f"{len(df_operations):,} registros"
            )
        
            st.dataframe(
                df_operations,
                use_container_width=True,
                hide_index=True
            )
        
        with tab_admin:
        
            df_admin_preview = (
                foto[
                    foto["Fuente"]
                    == "Control administrativo"
                ]
            )
        
            st.caption(
                f"{len(df_admin_preview):,} registros"
            )
        
            st.dataframe(
                df_admin_preview,
                use_container_width=True,
                hide_index=True
            )
        h=True, hide_index=True)

        csv_final = final.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 Descargar histórico consolidado", data=csv_final, file_name=HISTORICO_PATH, mime="text/csv")

        if not repo or not token:
            st.info("Configurá st.secrets['github']['repo'] y st.secrets['github']['token'] para habilitar la actualización en GitHub.")
        elif st.button("🚀 Actualizar serie histórica en GitHub", type="primary"):
            guardar_github(final, repo, HISTORICO_PATH, token, f"Actualización licencias {pd.Timestamp(fecha_actualizacion):%Y-%m-%d}")
            st.cache_data.clear()
            st.success("Base histórica actualizada correctamente.")
            st.rerun()

    except Exception as e:
        st.exception(e)
else:
    st.info("Cargá los cuatro archivos para construir la foto de licencias.")
