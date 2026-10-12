#!/usr/bin/env python3
"""inventariar.py CARPETA [--bib biblioteca.bib]: el inventario de los libros del corpus.

Añade a CARPETA/inventario.tsv una fila por cada PDF, EPUB o DjVu que aún no esté, con lo que se
puede averiguar solo: la clave más probable de la bibliografía (por el título y el
autor), la huella (sha256), las páginas, si tiene texto o es un escaneo, si los números
impresos coinciden con los del visor (o con qué desfase), el idioma y, si el nombre lo
dice, la procedencia. Lo demás (la edición, lo difícil, la procedencia) se rellena a
mano, y el script nunca lo toca: las filas que ya están no se reescriben.

Un archivo renombrado se reconoce por su huella: su fila cambia de nombre y conserva lo
demás. Avisa además de los duplicados (la misma huella), de los archivos de la lista que
ya no están en la carpeta y de las claves que no existen en la bibliografía.
Necesita pdfinfo y pdftotext (poppler-utils), y djvused y djvutxt (djvulibre) para los DjVu.
Un EPUB no tiene páginas: cuenta sus secciones, en el orden de lectura.
"""
import argparse
import collections
import csv
import hashlib
import html.parser
import posixpath
import re
import subprocess
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from urllib.parse import unquote

FORMATOS = (".pdf", ".epub", ".djvu")
COLUMNAS = ["clave", "archivo", "sha256", "paginas", "texto", "paginas_reales", "idioma",
            "edicion_ok", "dificil", "procedencia", "notas"]
PALABRAS = {
    "en": {"the", "and", "of", "to", "is", "that", "in", "it", "for", "with"},
    "es": {"el", "la", "de", "que", "y", "los", "las", "en", "por", "con"},
}


def normal(s):
    s = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", " ", s)  # JaynesProbability2003
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s)


def bibliografia(ruta):
    """clave → {campo: valor}, sin llaves, de un .bib de un campo por línea."""
    entradas, clave = {}, None
    for linea in Path(ruta).read_text(encoding="utf-8").splitlines():
        if m := re.match(r"\s*@\w+\s*\{\s*([^,\s]+)\s*,", linea):
            clave = m.group(1)
            entradas[clave] = {}
        elif clave and (m := re.match(r"\s*(\w+)\s*=\s*[{\"](.*?)[}\"]?,?\s*$", linea)):
            entradas[clave][m.group(1).lower()] = m.group(2).replace("{", "").replace("}", "")
    return entradas


def adivinar(texto, entradas):
    """La entrada cuyo título (palabras de más de tres letras) y primer apellido mejor
    casan con el nombre del archivo y sus metadatos; None si ninguna pasa del 60 %."""
    palabras = set(normal(texto).split())
    mejor, puntos = None, 0.6
    for clave, e in entradas.items():
        titulo, autores = e.get("title", ""), e.get("author") or e.get("editor", "")
        apellido = normal(autores.split(",")[0].split(" and ")[0]).split()
        if not apellido or apellido[-1] not in palabras:
            continue
        # El título entero o solo el principal, sin el subtítulo (tras los dos puntos),
        # que los nombres de archivo suelen dejar fuera.
        for t in {titulo, titulo.split(":")[0]}:
            del_titulo = [p for p in normal(t).split() if len(p) > 3]
            p = sum(w in palabras for w in del_titulo) / len(del_titulo) if del_titulo else 0
            if p > puntos:
                mejor, puntos = clave, p
    return mejor


def salida(*orden):
    return subprocess.run(orden, capture_output=True, text=True).stdout


class _Texto(html.parser.HTMLParser):
    """El texto de un XHTML, sin la cabecera, los scripts ni los estilos, con un salto por bloque."""
    def __init__(self):
        super().__init__()
        self.partes, self.fuera = [], 0

    def handle_starttag(self, tag, attrs):
        self.fuera += tag in ("head", "script", "style")
        if tag in ("p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self.partes.append("\n")

    def handle_endtag(self, tag):
        self.fuera -= tag in ("head", "script", "style") and self.fuera > 0

    def handle_data(self, data):
        if not self.fuera:
            self.partes.append(data)


def epub(ruta):
    """Los metadatos (Title, Author) y el texto de cada sección del EPUB, en el orden del spine."""
    with zipfile.ZipFile(ruta) as z:
        opf = ET.fromstring(z.read("META-INF/container.xml")).find(".//{*}rootfile").get("full-path")
        raiz, base = ET.fromstring(z.read(opf)), posixpath.dirname(opf)
        items = {i.get("id"): i.get("href") for i in raiz.iterfind(".//{*}item")}
        secciones = []
        for ref in raiz.iterfind(".//{*}itemref"):
            href = posixpath.normpath(posixpath.join(base, unquote(items[ref.get("idref")])))
            p = _Texto()
            p.feed(z.read(href).decode("utf-8", "ignore"))
            secciones.append("".join(p.partes))
        dato = lambda tag: next((e.text or "" for e in raiz.iterfind(f".//{{*}}{tag}")), "")
        return {"Title": dato("title"), "Author": dato("creator")}, secciones


def paginas(ruta, maqueta=True):
    """Los metadatos y el texto de cada página (o de cada sección, en un EPUB).

    maqueta=True conserva la disposición de la página, que deja el número impreso en su
    línea; es la que necesita el inventario. Con maqueta=False, el texto sigue el orden de
    lectura, que no mezcla las dos columnas de un artículo en la misma línea, y las
    palabras partidas con guion a final de línea se vuelven a unir: es la de los pasajes."""
    tipo = ruta.suffix.lower()
    if tipo == ".epub":
        return epub(ruta)
    if tipo == ".djvu":
        texto = salida("djvutxt", str(ruta))
    else:
        texto = salida("pdftotext", *(["-layout"] if maqueta else []), str(ruta), "-")
    if not maqueta:
        texto = re.sub(r"(\w)-\n\s*([a-záéíóúüñ])", r"\1\2", texto)
    info = dict(l.split(":", 1) for l in salida("pdfinfo", str(ruta)).splitlines() if ":" in l) if tipo == ".pdf" else {}
    total = int(salida("djvused", "-e", "n", str(ruta)) or 0) if tipo == ".djvu" else int(info.get("Pages", "0").strip() or 0)
    # pdftotext y djvutxt cierran cada página con un salto de página.
    return info, (texto.split("\f") + [""] * total)[:total]


def ocr_dudoso(texto):
    """Si un texto parece un OCR malo: menos del 80% de sus fichas (sin contar las cifras)
    parecen palabras, letras con alguna vocal, o más del 8% son letras sueltas que no son
    palabras de una letra. ponytail: umbrales a ojo; afinarlos con libros de verdad."""
    fichas = [f.strip(".,;:!?¿¡()[]«»\"'’“”-–—") for f in texto.split()]
    fichas = [f for f in fichas if f and not re.fullmatch(r"[\d.,%/:+-]+", f)]
    if len(fichas) < 50:
        return False
    palabras = sum(f.isalpha() and len(f) > 1 and bool(re.search(r"[aeiouyáéíóúü]", f, re.I)) for f in fichas)
    sueltas = sum(len(f) == 1 and f.lower() not in "aeiouy" for f in fichas)
    return palabras / len(fichas) < 0.8 or sueltas / len(fichas) > 0.08


def examinar(todas, total):
    """texto, páginas reales, idioma y caracteres ilegibles por cada mil palabras, con
    diez páginas repartidas por el libro. Un texto con palabras de sobra puede ser un OCR
    viejo: «OCR dudoso» si pocas fichas parecen palabras o abundan las letras sueltas."""
    muestra = sorted({max(1, round(total * i / 11)) for i in range(1, 11)}) if total else []
    textos = {n: todas[n - 1] for n in muestra}
    palabras = sorted(len(t.split()) for t in textos.values())
    mediana = palabras[len(palabras) // 2] if palabras else 0
    texto = "digital" if mediana >= 80 else "escaneado" if mediana <= 10 else "mixto (revisar)"
    if texto == "digital" and ocr_dudoso(" ".join(textos.values())):
        texto = "OCR dudoso"

    # El número impreso: una línea que es solo un número, o que empieza o acaba en uno
    # (la cabecera «12  Capítulo»), entre las dos primeras y las dos últimas.
    desfases = []
    for n, t in textos.items():
        lineas = [l.strip() for l in t.splitlines() if l.strip()]
        for l in lineas[:2] + lineas[-2:]:
            m = re.fullmatch(r"(\d{1,4})", l) or re.match(r"(\d{1,4})\s{2,}\S", l) or re.search(r"\S\s{2,}(\d{1,4})$", l)
            if m and 0 < int(m.group(1)) <= total:
                desfases.append(n - int(m.group(1)))
                break
    desfase, veces = collections.Counter(desfases).most_common(1)[0] if desfases else (None, 0)
    reales = "?" if not veces or veces < len(textos) / 2 else "sí" if desfase == 0 else f"desfase {desfase:+d}"

    todas = normal(" ".join(textos.values())).split()
    cuenta = {idioma: sum(w in lista for w in todas) for idioma, lista in PALABRAS.items()}
    idioma = max(cuenta, key=cuenta.get) if max(cuenta.values(), default=0) > 20 else "?"
    # Ilegibles: los que la fuente no traduce a Unicode (símbolos de fórmulas, sobre todo).
    unido = "".join(textos.values())
    ilegibles = sum(c == "\ufffd" or ord(c) < 9 or 0x0e <= ord(c) < 0x20 for c in unido)
    return texto, reales, idioma, 1000 * ilegibles / max(1, len(unido.split()))


def main():
    a = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    a.add_argument("carpeta", type=Path)
    a.add_argument("--bib", type=Path, default=Path.home() / "Documents/nuevasomosaguas.bib")
    args = a.parse_args()
    if not args.bib.exists():
        sys.exit(f"No encuentro la bibliografía: {args.bib} (--bib biblioteca.bib)")
    entradas = bibliografia(args.bib)
    tsv = args.carpeta / "inventario.tsv"

    filas = []
    if tsv.exists():
        with open(tsv, newline="", encoding="utf-8") as f:
            filas = list(csv.DictReader(f, delimiter="\t"))
    conocidos = {f["archivo"] for f in filas}
    huellas = {f["sha256"]: f["archivo"] for f in filas}

    nuevos = renombrados = 0
    libros = sorted(p for p in args.carpeta.iterdir() if p.suffix.lower() in FORMATOS)
    en_carpeta = {p.name for p in libros}
    for pdf in libros:
        if pdf.name in conocidos:
            continue
        with open(pdf, "rb") as f:
            huella = hashlib.file_digest(f, "sha256").hexdigest()
        antigua = next((f for f in filas if f["sha256"] == huella and f["archivo"] not in en_carpeta), None)
        if antigua:
            print(f"  Renombrado: {antigua['archivo']} → {pdf.name}")
            antigua["archivo"] = pdf.name
            renombrados += 1
            continue
        info, todas = paginas(pdf)
        total = len(todas)
        texto, reales, idioma, ilegibles = examinar(todas, total)
        if pdf.suffix.lower() == ".epub":
            reales = "no (EPUB: secciones)"
        notas = []
        if ilegibles >= 1:
            notas.append(f"{ilegibles:.0f} caracteres ilegibles por cada mil palabras (símbolos sin Unicode): mirar las fórmulas")
        productor = (info.get("Creator", "") + " " + info.get("Producer", "")).strip()
        if "calibre" in productor.lower():
            reales = "no"
            notas.append("convertido por Calibre: sus páginas no son las del libro")
        if huella in huellas:
            notas.append(f"duplicado de {huellas[huella]}")
        clave = adivinar(f"{pdf.stem} {info.get('Title', '')} {info.get('Author', '')}", entradas) or ""
        if clave:
            notas.append("clave por el título: comprobar")
        procedencia = "Anna's Archive (por el nombre)" if re.search(r"\bannas? ?s? archive\b", normal(pdf.name)) else ""
        filas.append({"clave": clave, "archivo": pdf.name, "sha256": huella, "paginas": total,
                      "texto": texto, "paginas_reales": reales, "idioma": idioma, "edicion_ok": "",
                      "dificil": "", "procedencia": procedencia, "notas": "; ".join(notas)})
        huellas.setdefault(huella, pdf.name)
        nuevos += 1

    with open(tsv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, COLUMNAS, delimiter="\t", extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(filas)

    print(f"{tsv}: {nuevos} nuevos, {renombrados} renombrados, {len(filas)} en total.")
    for f in filas:
        if f["archivo"] not in en_carpeta:
            print(f"  Ya no está en la carpeta: {f['archivo']}")
        if f["clave"] and f["clave"] not in entradas:
            print(f"  Clave que no está en la bibliografía: {f['clave']} ({f['archivo']})")
        if not f["clave"]:
            print(f"  Sin clave: {f['archivo']}")
    faltan = len(entradas) - len({f["clave"] for f in filas if f["clave"] in entradas})
    print(f"  De la bibliografía faltan {faltan} de {len(entradas)} obras.")


if __name__ == "__main__":
    main()
