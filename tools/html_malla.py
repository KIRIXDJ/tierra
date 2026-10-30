"""Lee y reescribe el bloque JSON de la malla dentro del HTML del demo."""

import json
import re

PATRON = re.compile(
    r'(<script id="malla" type="application/json">)(.*?)(</script>)',
    re.S,
)


def leer_malla(html):
    """Devuelve el diccionario del bloque ``#malla``."""
    coincidencia = PATRON.search(html)
    if not coincidencia:
        raise ValueError("El HTML no tiene el bloque de la malla.")
    return json.loads(coincidencia.group(2) or "null")


def reemplazar_malla(html, malla):
    """Sustituye el contenido del bloque y devuelve el HTML nuevo."""
    coincidencia = PATRON.search(html)
    if not coincidencia:
        raise ValueError("El HTML no tiene el bloque de la malla.")
    texto = json.dumps(malla, ensure_ascii=False, separators=(",", ":"))
    return html[:coincidencia.start(2)] + texto + html[coincidencia.end(2):]
