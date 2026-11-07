"""Motor de rotaciones orientativas con la climatología POWER de la finca.

Este módulo es **puro**: no hace red ni lee archivos. Recibe el bloque de una
finca tal como lo publica ``datos/fincas.json`` y devuelve las estrategias
evaluadas.

Las fórmulas son **heurísticas de diseño**, no agronomía:

- ``agua = 10 - 2.5 * |meses_criticos ∩ meses_secos|``, acotado a 0..10.
- ``diversidad = 10 * cultivos_distintos / 3``, acotado a 0..10.
- ``indice = 50 * agua / 10 + 50 * diversidad / 10``, acotado a 0..100.
- Si la temporada reciente está ``por_debajo`` y la demanda es ``alta``, se
  restan 15 puntos. Ese 15 también es un peso de diseño, no una regla
  agronómica.

La tabla de cultivos incluida aquí es **provisional** (sin fuente citable)
mientras no exista ``datos/cultivos.json`` de la tarea 8. No se presentan
rendimientos, dosis ni fechas de siembra.
"""

import math

DEMANDA_AGUA = ("baja", "media", "alta")
_RANGO_DEMANDA = {nombre: indice for indice, nombre in enumerate(DEMANDA_AGUA)}
MESES_SECOS = 3
PESO_DEFICIT = 15

# shortcut: tabla sin fuente citable, se reemplaza por datos/cultivos.json (tarea 8).
CULTIVOS_PROVISIONALES = {
    "maiz": {
        "id": "maiz",
        "nombre": "Maíz",
        "demanda_agua": "alta",
        "meses_criticos": [5, 6, 7, 8],
        "estado": "provisional",
        "fuente": None,
    },
    "frijol": {
        "id": "frijol",
        "nombre": "Frijol",
        "demanda_agua": "media",
        "meses_criticos": [5, 6, 7],
        "estado": "provisional",
        "fuente": None,
    },
    "yuca": {
        "id": "yuca",
        "nombre": "Yuca",
        "demanda_agua": "baja",
        "meses_criticos": [6, 7, 8, 9],
        "estado": "provisional",
        "fuente": None,
    },
    "platano": {
        "id": "platano",
        "nombre": "Plátano",
        "demanda_agua": "alta",
        "meses_criticos": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
        "estado": "provisional",
        "fuente": None,
    },
    "sorgo": {
        "id": "sorgo",
        "nombre": "Sorgo",
        "demanda_agua": "baja",
        "meses_criticos": [5, 6, 7, 8],
        "estado": "provisional",
        "fuente": None,
    },
    "mani": {
        "id": "mani",
        "nombre": "Maní",
        "demanda_agua": "media",
        "meses_criticos": [6, 7, 8],
        "estado": "provisional",
        "fuente": None,
    },
}


def _numero(valor):
    """Convierte a float finito; ``None`` si no es un número utilizable."""
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numero):
        return None
    return numero


def _acotar(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


def _entero(valor):
    """Redondeo mitad hacia arriba, como ``Math.round`` del navegador."""
    return int(math.floor(valor + 0.5))


def _tabla(cultivos):
    """Normaliza la tabla de cultivos a ``{id: entrada}``."""
    if not cultivos:
        return dict(CULTIVOS_PROVISIONALES)
    if isinstance(cultivos, dict):
        return dict(cultivos)
    tabla = {}
    for cultivo in cultivos:
        if isinstance(cultivo, dict) and cultivo.get("id"):
            tabla[cultivo["id"]] = cultivo
    return tabla


def _cultivo(tabla, cultivo_id):
    """Entrada de un cultivo; si no está en la tabla, una provisional vacía."""
    if cultivo_id in tabla:
        return tabla[cultivo_id]
    return {
        "id": cultivo_id,
        "nombre": str(cultivo_id).replace("_", " ").title(),
        "demanda_agua": "media",
        "meses_criticos": [],
        "estado": "provisional",
        "fuente": None,
    }


def meses_secos(climatologia):
    """Tres meses (1..12) con menor media de ``lluvia_mm_dia``.

    Acepta el bloque ``climatologia`` completo (con ``mensual``) o directamente
    el diccionario ``{año: {"lluvia_mm_dia": [...]}}``. Ignora años y meses sin
    dato y devuelve ``[]`` si no hay climatología utilizable.
    """
    if not isinstance(climatologia, dict):
        return []
    mensual = climatologia.get("mensual", climatologia)
    if not isinstance(mensual, dict) or not mensual:
        return []

    sumas = [0.0] * 12
    cuentas = [0] * 12
    for anio in mensual.values():
        if not isinstance(anio, dict):
            continue
        valores = anio.get("lluvia_mm_dia")
        if not isinstance(valores, (list, tuple)):
            continue
        for indice, valor in enumerate(valores[:12]):
            numero = _numero(valor)
            if numero is None:
                continue
            sumas[indice] += numero
            cuentas[indice] += 1

    medias = [
        (sumas[indice] / cuentas[indice], indice + 1)
        for indice in range(12)
        if cuentas[indice]
    ]
    medias.sort()
    return sorted(mes for _, mes in medias[:MESES_SECOS])


def _completar(tabla, preferidos, cantidad):
    """Toma ids preferidos que existan y completa con el resto de la tabla."""
    elegidos = [cultivo_id for cultivo_id in preferidos if cultivo_id in tabla]
    for cultivo_id in tabla:
        if len(elegidos) >= cantidad:
            break
        if cultivo_id not in elegidos:
            elegidos.append(cultivo_id)
    return elegidos[:cantidad]


def _definir_estrategias(finca, tabla):
    """Las tres estrategias: actual y dos alternativas tropicales."""
    actual = finca.get("cultivo_actual")
    cultivos_actual = [actual] if actual and actual not in ("provisional", "") else []
    return [
        ("actual", "Rotación actual", cultivos_actual),
        ("alternativa_1", "Alternativa 1", _completar(tabla, ("maiz", "frijol"), 2)),
        ("alternativa_2", "Alternativa 2", _completar(tabla, ("yuca", "mani", "sorgo"), 3)),
    ]


def _demanda(cultivos):
    """Demanda de agua de la estrategia: la más alta de sus cultivos."""
    if not cultivos:
        return "media"
    mejor = "baja"
    for cultivo in cultivos:
        demanda = cultivo.get("demanda_agua")
        if _RANGO_DEMANDA.get(demanda, -1) > _RANGO_DEMANDA[mejor]:
            mejor = demanda
    return mejor


def _meses_criticos(cultivos):
    """Unión ordenada de los meses en que los cultivos necesitan agua."""
    meses = set()
    for cultivo in cultivos:
        for mes in cultivo.get("meses_criticos") or []:
            numero = _numero(mes)
            if numero is not None and numero == int(numero) and 1 <= numero <= 12:
                meses.add(int(numero))
    return sorted(meses)


def evaluar_rotaciones(finca, contexto_reciente=None, clima=None, cultivos=None):
    """Evalúa la rotación actual y dos alternativas para una finca.

    ``clima`` permite pasar la climatología directamente; si es ``None`` se usa
    ``finca["climatologia"]``. ``contexto_reciente`` es el bloque de esa finca
    en ``datos/reciente.json`` (o ``None``). ``cultivos`` es la tabla de la
    tarea 8; si falta, se usa la tabla provisional interna.

    Devuelve ``{"id", "meses_secos", "estrategias"}`` con el contrato de la
    tarea 4.
    """
    tabla = _tabla(cultivos)
    climatologia = clima if clima is not None else finca.get("climatologia")
    secos = meses_secos(climatologia)

    estado_reciente = None
    if isinstance(contexto_reciente, dict):
        estado_reciente = (contexto_reciente.get("lluvia") or {}).get("estado")

    estrategias = []
    for id_estrategia, titulo, ids in _definir_estrategias(finca, tabla):
        entrada = [_cultivo(tabla, cultivo_id) for cultivo_id in ids]
        demanda = _demanda(entrada)
        criticos = _meses_criticos(entrada)
        comunes = sorted(set(criticos) & set(secos))

        agua = round(_acotar(10.0 - 2.5 * len(comunes), 0.0, 10.0), 1)
        diversidad = round(_acotar(10.0 * len(set(ids)) / 3.0, 0.0, 10.0), 1)
        indice = _entero(5.0 * agua + 5.0 * diversidad)

        motivos = []
        if secos:
            motivos.append(
                "Los meses críticos coinciden con "
                f"{len(comunes)} de los {len(secos)} meses secos de la finca."
            )
        else:
            motivos.append(
                "Sin climatología POWER no se pueden cruzar los meses críticos "
                "con los meses secos."
            )
        motivos.append(
            f"Usa {len(set(ids))} cultivo(s) distinto(s): diversidad "
            f"{diversidad:.1f}/10."
        )
        if not ids:
            motivos.append(
                "El cultivo actual no está identificado; la estrategia queda "
                "sin cultivos."
            )

        if estado_reciente == "por_debajo" and demanda == "alta":
            indice = max(0, min(100, indice - PESO_DEFICIT))
            motivos.append(
                "La temporada reciente está por debajo de lo normal: se restan "
                f"{PESO_DEFICIT} puntos por demanda de agua alta."
            )

        provisional = not entrada or any(
            cultivo.get("estado") == "provisional" or not cultivo.get("fuente")
            for cultivo in entrada
        )

        faltantes = []
        if not secos:
            faltantes.append("sin climatología POWER (meses secos)")
        if not contexto_reciente:
            faltantes.append("sin contexto de la temporada reciente")
        sin_fuente = sorted(
            {
                cultivo.get("id")
                for cultivo in entrada
                if cultivo.get("estado") == "provisional" or not cultivo.get("fuente")
            }
        )
        if sin_fuente:
            faltantes.append("sin fuente citable para: " + ", ".join(sin_fuente))
        if not entrada:
            faltantes.append("cultivo actual sin definir o sin fuente")
        if not faltantes:
            faltantes.append("sin revisión agronómica registrada")

        riesgos = ["El índice es orientativo: no es una recomendación agronómica."]
        if provisional:
            riesgos.append(
                "Los parámetros de cultivo son provisionales y pueden cambiar."
            )
        if demanda == "alta" and secos:
            riesgos.append(
                "La demanda alta puede chocar con los meses secos; el componente "
                "de agua es el más sensible."
            )

        fuentes = []
        for cultivo in entrada:
            fuente = cultivo.get("fuente")
            if fuente and fuente not in fuentes:
                fuentes.append(fuente)

        estrategias.append(
            {
                "id": id_estrategia,
                "titulo": titulo,
                "cultivos": list(ids),
                "demanda_agua": demanda,
                "meses_criticos": criticos,
                "indice": indice,
                "componentes": {"agua": agua, "diversidad": diversidad},
                "motivos": motivos,
                "datos_faltantes": faltantes,
                "riesgos": riesgos,
                "provisional": provisional,
                "fuentes": fuentes,
            }
        )

    return {"id": finca.get("id"), "meses_secos": secos, "estrategias": estrategias}
