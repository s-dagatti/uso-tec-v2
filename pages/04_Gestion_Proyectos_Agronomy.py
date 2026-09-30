import base64
import io
import re
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

# =========================================================
# CONFIGURACIÓN
# =========================================================

st.set_page_config(
    page_title="Gestión de Agronomys",
    page_icon="🌱",
    layout="wide"
)

DATA_PATH = "datos_proyectos_agronomy_analyzer.csv"

QUARTERS = [
    "Q1",
    "Q2",
    "Q3",
    "Q4"
]

COLUMNAS_BASE = [
    "FECHA Y HORA",
    "ID CLIENTE",
    "CLIENTE",
    "SUCURSAL",
    "CATEGORÍA DE EVALUACIÓN",
    "Tipo de Proyecto",
    "NOMBRE",
    "Ubicación",
    "Planificación - Estado",
    "Planificación - Horas",
    "Recopilación de Datos - Estado",
    "Recopilación de Datos - Horas",
    "Generación de informe - Estado",
    "Generación de informe - Horas",
    "Q PLANTEADO",
    "ID PRUEBA",
    "LINK ACCESO",
    "FY"
]

# =========================================================
# FUNCIONES DE GITHUB
# =========================================================

def configurar_github():

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
def cargar_base(
    repo,
    token,
    path
):

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

        return pd.DataFrame(
            columns=COLUMNAS_BASE
        )

    respuesta.raise_for_status()

    return pd.read_csv(
        io.StringIO(respuesta.text),
        low_memory=False
    )


def guardar_base(
    df,
    repo,
    token,
    path,
    mensaje
):

    url = (
        f"https://api.github.com/repos/"
        f"{repo}/contents/{path}"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    consulta = requests.get(
        url,
        headers=headers,
        timeout=30
    )

    sha = (
        consulta.json().get("sha")
        if consulta.status_code == 200
        else None
    )

    contenido_csv = (
        df
        .to_csv(index=False)
        .encode("utf-8-sig")
    )

    contenido = base64.b64encode(
        contenido_csv
    ).decode("ascii")

    payload = {
        "message": mensaje,
        "content": contenido
    }

    if sha:
        payload["sha"] = sha

    respuesta = requests.put(
        url,
        headers=headers,
        json=payload,
        timeout=60
    )

    if respuesta.status_code not in (
        200,
        201
    ):

        try:

            detalle = respuesta.json().get(
                "message",
                respuesta.text
            )

        except Exception:

            detalle = respuesta.text

        raise RuntimeError(
            f"GitHub no pudo guardar la base: {detalle}"
        )

# =========================================================
# FUNCIONES AUXILIARES
# =========================================================

def texto_limpio(valor):

    if pd.isna(valor):
        return ""

    return str(valor).strip()


def clave_texto(valor):

    texto = (
        texto_limpio(valor)
        .upper()
    )

    return re.sub(
        r"[^A-Z0-9]+",
        "",
        texto
    )


def normalizar_numero(valor):

    if (
        pd.isna(valor)
        or texto_limpio(valor) == ""
    ):
        return ""

    numero = pd.to_numeric(
        pd.Series([valor]),
        errors="coerce"
    ).iloc[0]

    if pd.notna(numero):
        return str(int(numero))

    return texto_limpio(valor)


def crear_clave_proyecto(df):

    id_prueba = df.get(
        "ID PRUEBA",
        pd.Series(
            index=df.index,
            dtype="object"
        )
    )

    id_prueba = id_prueba.apply(
        normalizar_numero
    )

    clave_fallback = (

        df["ID CLIENTE"]
        .apply(normalizar_numero)

        + "|"

        + df["Tipo de Proyecto"]
        .apply(clave_texto)

        + "|"

        + df["NOMBRE"]
        .apply(clave_texto)

        + "|"

        + df["FY"]
        .apply(normalizar_numero)

        + "|"

        + df["Q PLANTEADO"]
        .apply(clave_texto)

    )

    claves = []

    for prueba, fallback in zip(
        id_prueba,
        clave_fallback
    ):

        if prueba:

            claves.append(
                f"PRUEBA|{prueba}"
            )

        else:

            claves.append(
                f"PROYECTO|{fallback}"
            )

    return pd.Series(
        claves,
        index=df.index,
        dtype="string"
    )


def preparar_base(df):

    base = df.copy()

    for columna in COLUMNAS_BASE:

        if columna not in base.columns:
            base[columna] = pd.NA

    columnas_horas = [
        "Planificación - Horas",
        "Recopilación de Datos - Horas",
        "Generación de informe - Horas"
    ]

    for columna in columnas_horas:

        base[columna] = pd.to_numeric(
            base[columna],
            errors="coerce"
        ).fillna(0.0)

    columnas_estado = [
        "Planificación - Estado",
        "Recopilación de Datos - Estado",
        "Generación de informe - Estado"
    ]

    for columna in columnas_estado:

        base[columna] = (
            base[columna]
            .fillna("No Iniciado")
            .astype(str)
            .str.strip()
        )

    base["Clave Proyecto"] = (
        crear_clave_proyecto(base)
    )

    return base


def es_sin_avance(df):

    estados_sin_avance = (

        df["Planificación - Estado"]
        .eq("No Iniciado")

        &

        df["Recopilación de Datos - Estado"]
        .eq("No Iniciado")

        &

        df["Generación de informe - Estado"]
        .eq("No Iniciado")

    )

    horas_cero = (

        df["Planificación - Horas"]
        .fillna(0)
        .eq(0)

        &

        df["Recopilación de Datos - Horas"]
        .fillna(0)
        .eq(0)

        &

        df["Generación de informe - Horas"]
        .fillna(0)
        .eq(0)

    )

    return (
        estados_sin_avance
        & horas_cero
    )


def opciones(serie):

    return sorted(

        serie
        .dropna()
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .unique()

    )


def guardar_y_refrescar(
    df_actualizado,
    mensaje
):

    columnas_guardar = [

        columna

        for columna in df_actualizado.columns

        if columna != "Clave Proyecto"

    ]

    guardar_base(

        df_actualizado[columnas_guardar],

        repo,

        token,

        DATA_PATH,

        mensaje

    )

    st.cache_data.clear()

    st.success(
        "✅ La base se actualizó correctamente."
    )

    st.rerun()

# =========================================================
# CARGA DE DATOS
# =========================================================

repo, token = configurar_github()

if not repo or not token:

    st.error(
        "Falta configurar "
        "st.secrets['github']['repo'] "
        "y st.secrets['github']['token']."
    )

    st.stop()

try:

    df = preparar_base(
        cargar_base(
            repo,
            token,
            DATA_PATH
        )
    )

except Exception as error:

    st.error(
        f"No se pudo cargar la base: {error}"
    )

    st.stop()

# =========================================================
# ENCABEZADO
# =========================================================

st.title(
    "🌱 Gestión de Proyectos Agronomy Analyzer"
)

st.caption(
    "Consulta y administración de proyectos "
    "Agronomy Analyzer."
)

# =========================================================
# TABS
# =========================================================

tab_consulta, tab_nuevo, tab_eliminar = st.tabs(
    [
        "📋 Agronomys existentes",
        "➕ Nuevo Agronomy",
        "🗑️ Eliminar Agronomys"
    ]
)

# =========================================================
# TAB 1 — AGRONOMYS EXISTENTES
# =========================================================

with tab_consulta:

    st.subheader(
        "Agronomys existentes"
    )

    f1, f2, f3, f4 = st.columns(4)

    with f1:

        solo_sin_avance = st.checkbox(
            "Mostrar solo proyectos sin avance",
            value=False
        )

    with f2:

        filtro_sucursal = st.multiselect(
            "Sucursal",
            opciones(
                df["SUCURSAL"]
            )
        )

    with f3:

        filtro_cliente = st.multiselect(
            "Cliente",
            opciones(
                df["CLIENTE"]
            )
        )

    with f4:

        filtro_tipo = st.multiselect(
            "Tipo de proyecto",
            opciones(
                df["Tipo de Proyecto"]
            )
        )

    f5, f6, f7 = st.columns(3)

    with f5:

        filtro_fy = st.multiselect(
            "FY",
            opciones(
                df["FY"]
            )
        )

    with f6:

        filtro_q = st.multiselect(
            "Quarter",
            opciones(
                df["Q PLANTEADO"]
            )
        )

    with f7:

        filtro_categoria = st.multiselect(
            "Categoría de evaluación",
            opciones(
                df[
                    "CATEGORÍA DE EVALUACIÓN"
                ]
            )
        )

    vista = df.copy()

    if solo_sin_avance:

        vista = vista[
            es_sin_avance(vista)
        ].copy()

    if filtro_sucursal:

        vista = vista[
            vista["SUCURSAL"]
            .isin(filtro_sucursal)
        ].copy()

    if filtro_cliente:

        vista = vista[
            vista["CLIENTE"]
            .isin(filtro_cliente)
        ].copy()

    if filtro_tipo:

        vista = vista[
            vista["Tipo de Proyecto"]
            .isin(filtro_tipo)
        ].copy()

    if filtro_fy:

        vista = vista[
            vista["FY"]
            .astype(str)
            .isin(filtro_fy)
        ].copy()

    if filtro_q:

        vista = vista[
            vista["Q PLANTEADO"]
            .astype(str)
            .isin(filtro_q)
        ].copy()

    if filtro_categoria:

        vista = vista[
            vista["CATEGORÍA DE EVALUACIÓN"]
            .isin(filtro_categoria)
        ].copy()

    sin_avance_total = (
        int(
            es_sin_avance(vista).sum()
        )
        if not vista.empty
        else 0
    )

    completados = int(
        vista[
            "Generación de informe - Estado"
        ]
        .eq("Completado")
        .sum()
    )

    horas = (
        vista[
            [
                "Planificación - Horas",
                "Recopilación de Datos - Horas",
                "Generación de informe - Horas"
            ]
        ]
        .sum()
        .sum()
    )

    k1, k2, k3, k4 = st.columns(4)

    k1.metric(
        "📋 Proyectos",
        f"{len(vista):,}"
    )

    k2.metric(
        "⚪ Sin avance",
        f"{sin_avance_total:,}"
    )

    k3.metric(
        "✅ Completados",
        f"{completados:,}"
    )

    k4.metric(
        "⏱ Horas cargadas",
        f"{horas:,.1f}"
    )

    columnas_vista = [
        "CLIENTE",
        "SUCURSAL",
        "CATEGORÍA DE EVALUACIÓN",
        "Tipo de Proyecto",
        "NOMBRE",
        "Ubicación",
        "Planificación - Estado",
        "Planificación - Horas",
        "Recopilación de Datos - Estado",
        "Recopilación de Datos - Horas",
        "Generación de informe - Estado",
        "Generación de informe - Horas",
        "Q PLANTEADO",
        "FY",
        "ID PRUEBA",
        "LINK ACCESO"
    ]

    st.dataframe(
        vista[
            columnas_vista
        ]
        .sort_values(
            [
                "SUCURSAL",
                "CLIENTE",
                "NOMBRE"
            ]
        ),
        use_container_width=True,
        hide_index=True,
        column_config={
            "LINK ACCESO":
                st.column_config.LinkColumn(
                    "Acceso",
                    display_text="Abrir"
                )
        }
    )

# =========================================================
# TAB 2 — NUEVO AGRONOMY
# =========================================================

with tab_nuevo:

    st.subheader(
        "➕ Crear un nuevo Agronomy"
    )

    st.info(
        "El proyecto se crea sin avance. "
        "Luego cada agrónomo podrá actualizar las etapas "
        "desde el dashboard principal."
    )

    clientes = (
        df[
            [
                "ID CLIENTE",
                "CLIENTE",
                "SUCURSAL"
            ]
        ]
        .dropna(subset=["CLIENTE"])
        .drop_duplicates()
        .sort_values(
            [
                "CLIENTE",
                "SUCURSAL"
            ]
        )
    )

    clientes["Etiqueta"] = clientes.apply(

        lambda fila:
        f"{texto_limpio(fila['CLIENTE'])} · "
        f"{texto_limpio(fila['SUCURSAL'])} · "
        f"ID {normalizar_numero(fila['ID CLIENTE'])}",

        axis=1

    )

    with st.form(
        "form_nuevo_agronomy",
        clear_on_submit=False
    ):

        usar_cliente_existente = st.checkbox(
            "Asignar a un cliente existente",
            value=True
        )

        if (
            usar_cliente_existente
            and
            not clientes.empty
        ):

            etiqueta_cliente = st.selectbox(
                "Cliente",
                clientes["Etiqueta"].tolist()
            )

            fila_cliente = clientes[
                clientes["Etiqueta"]
                .eq(etiqueta_cliente)
            ].iloc[0]

            id_cliente = normalizar_numero(
                fila_cliente["ID CLIENTE"]
            )

            cliente = texto_limpio(
                fila_cliente["CLIENTE"]
            )

            sucursal = texto_limpio(
                fila_cliente["SUCURSAL"]
            )

            st.caption(
                f"Sucursal asignada: {sucursal}"
            )

        else:

            c1, c2, c3 = st.columns(3)

            with c1:
                id_cliente = st.text_input(
                    "ID Cliente"
                )

            with c2:
                cliente = st.text_input(
                    "Cliente"
                )

            with c3:
                sucursal = st.text_input(
                    "Sucursal"
                )

        c1, c2 = st.columns(2)

        with c1:

            categoria = st.text_input(
                "Categoría de Evaluación"
            )

            tipo_proyecto = st.text_input(
                "Tipo de Proyecto"
            )

            nombre = st.text_input(
                "Nombre del Proyecto"
            )

        with c2:

            ubicacion = st.text_input(
                "Ubicación"
            )

            quarter = st.selectbox(
                "Quarter",
                QUARTERS
            )

            fy = st.number_input(
                "FY",
                min_value=20,
                max_value=99,
                value=datetime.now().year % 100,
                step=1
            )

        guardar = st.form_submit_button(
            "🚀 Crear Agronomy",
            type="primary"
        )

    if guardar:

        errores = []

        if not texto_limpio(id_cliente):
            errores.append("ID Cliente")

        if not texto_limpio(cliente):
            errores.append("Cliente")

        if not texto_limpio(sucursal):
            errores.append("Sucursal")

        if not texto_limpio(tipo_proyecto):
            errores.append("Tipo de Proyecto")

        if not texto_limpio(nombre):
            errores.append("Nombre")

        if errores:

            st.error(
                "Completá los siguientes campos: "
                + ", ".join(errores)
            )

        else:

            nueva_fila = {

                "FECHA Y HORA":
                    pd.Timestamp.now().strftime(
                        "%d/%m/%Y %H:%M:%S"
                    ),

                "ID CLIENTE":
                    id_cliente,

                "CLIENTE":
                    cliente,

                "SUCURSAL":
                    sucursal,

                "CATEGORÍA DE EVALUACIÓN":
                    categoria,

                "Tipo de Proyecto":
                    tipo_proyecto,

                "NOMBRE":
                    nombre,

                "Ubicación":
                    ubicacion,

                "Planificación - Estado":
                    "No Iniciado",

                "Planificación - Horas":
                    0.0,

                "Recopilación de Datos - Estado":
                    "No Iniciado",

                "Recopilación de Datos - Horas":
                    0.0,

                "Generación de informe - Estado":
                    "No Iniciado",

                "Generación de informe - Horas":
                    0.0,

                "Q PLANTEADO":
                    quarter,

                "ID PRUEBA":
                    pd.NA,

                "LINK ACCESO":
                    pd.NA,

                "FY":
                    int(fy)

            }

            nuevo_df = pd.DataFrame(
                [nueva_fila]
            )

            nuevo_df["Clave Proyecto"] = (
                crear_clave_proyecto(
                    nuevo_df
                )
            )

            nueva_clave = (
                nuevo_df.iloc[0][
                    "Clave Proyecto"
                ]
            )

            if (
                nueva_clave
                in
                set(
                    df["Clave Proyecto"]
                    .astype(str)
                )
            ):

                st.error(
                    "Ese proyecto ya existe."
                )

            else:

                actualizado = pd.concat(
                    [
                        df,
                        nuevo_df
                    ],
                    ignore_index=True,
                    sort=False
                )

                guardar_y_refrescar(
                    actualizado,
                    f"Alta Agronomy: {cliente} - {nombre}"
                )
# =========================================================
# TAB 3 — ELIMINAR AGRONOMYS
# =========================================================

with tab_eliminar:

    st.subheader(
        "🗑️ Eliminar Agronomys"
    )

    st.warning(
        "La eliminación modifica la base del repositorio. "
        "Verificá cuidadosamente la selección antes de confirmar."
    )

    solo_sin_avance_eliminar = st.checkbox(
        "Mostrar solamente proyectos sin avance",
        value=True,
        key="solo_sin_avance_eliminar"
    )

    candidatos = df.copy()

    if solo_sin_avance_eliminar:

        candidatos = candidatos[
            es_sin_avance(candidatos)
        ].copy()

    candidatos = (
        candidatos
        .sort_values(
            [
                "SUCURSAL",
                "CLIENTE",
                "NOMBRE"
            ]
        )
        .copy()
    )

    candidatos.insert(
        0,
        "Eliminar",
        False
    )

    columnas_editor = [
        "Eliminar",
        "CLIENTE",
        "SUCURSAL",
        "Tipo de Proyecto",
        "NOMBRE",
        "Q PLANTEADO",
        "FY",
        "Clave Proyecto"
    ]

    editado = st.data_editor(

        candidatos[
            columnas_editor
        ],

        use_container_width=True,

        hide_index=True,

        disabled=[
            c
            for c in columnas_editor
            if c != "Eliminar"
        ],

        column_config={
            "Eliminar":
                st.column_config.CheckboxColumn(
                    "Eliminar",
                    help=(
                        "Marcá los proyectos "
                        "que querés eliminar."
                    )
                ),

            "Clave Proyecto":
                None
        },

        key="editor_eliminar_agronomy"

    )

    claves_eliminar = (

        editado.loc[
            editado["Eliminar"]
            .fillna(False),

            "Clave Proyecto"
        ]

        .astype(str)

        .tolist()

    )

    st.caption(
        f"Proyectos seleccionados: "
        f"{len(claves_eliminar)}"
    )

    confirmar = st.checkbox(
        "Confirmo que deseo eliminar definitivamente "
        "los proyectos seleccionados",
        value=False
    )

    if st.button(
        "🗑️ Eliminar seleccionados",
        type="primary",
        disabled=(
            not claves_eliminar
            or not confirmar
        )
    ):

        actualizado = (

            df[
                ~df["Clave Proyecto"]
                .astype(str)
                .isin(claves_eliminar)
            ]

            .copy()

        )

        guardar_y_refrescar(

            actualizado,

            (
                f"Eliminación de "
                f"{len(claves_eliminar)} Agronomys"
            )

        )
