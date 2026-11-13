"""Enlaces y recursos de la documentación (sin red ni navegador).

Comprueba que cada enlace relativo de README y docs/*.md apunta a un archivo que
existe, y que las imágenes y scripts del deck también. Es barato y evita que la
documentación quede con enlaces muertos después de mover capturas.
"""

import pathlib
import re
import unittest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
PATRON_MD = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
PATRON_HTML = re.compile(r'(?:src|href)="([^"#]+)"')


class TestEnlaces(unittest.TestCase):
    def documentos(self):
        yield RAIZ / "README.md"
        yield from sorted((RAIZ / "docs").glob("*.md"))

    def test_enlaces_markdown(self):
        faltan = []
        for documento in self.documentos():
            texto = documento.read_text(encoding="utf-8")
            for destino in PATRON_MD.findall(texto):
                destino = destino.strip("<>")
                if destino.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                destino = destino.split(" ")[0]
                ruta = (documento.parent / destino).resolve()
                if not ruta.exists():
                    faltan.append(f"{documento.relative_to(RAIZ)} -> {destino}")
        self.assertEqual(faltan, [], "enlaces relativos rotos:\n" + "\n".join(faltan))

    def test_recursos_del_deck(self):
        deck = RAIZ / "docs" / "deck" / "index.html"
        texto = deck.read_text(encoding="utf-8")
        faltan = []
        for destino in PATRON_HTML.findall(texto):
            if destino.startswith(("http://", "https://", "data:")):
                continue
            ruta = (deck.parent / destino).resolve()
            if not ruta.exists():
                faltan.append(destino)
        self.assertEqual(faltan, [], f"recursos del deck que no existen: {faltan}")

    def test_capturas_existen(self):
        capturas = sorted((RAIZ / "docs" / "capturas").glob("*.png"))
        self.assertGreaterEqual(len(capturas), 6)
        for captura in capturas:
            self.assertGreater(captura.stat().st_size, 1000, f"{captura.name} vacía")


if __name__ == "__main__":
    unittest.main()
