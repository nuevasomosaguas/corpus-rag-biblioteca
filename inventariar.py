#!/usr/bin/env python3
"""inventariar.py CARPETA [--bib biblioteca.bib]: el inventario de los PDF del corpus.

Añade a CARPETA/inventario.tsv una fila por cada PDF que aún no esté, con lo que se
puede averiguar solo: la clave más probable de la bibliografía (por el título y el
autor), la huella (sha256), las páginas, si tiene texto o es un escaneo, si los números
impresos coinciden con los del visor (o con qué desfase), el idioma y, si el nombre lo
dice, la procedencia. Lo demás (la edición, lo difícil, la procedencia) se rellena a
mano, y el script nunca lo toca: las filas que ya están no se reescriben.

Un archivo renombrado se reconoce por su huella: su fila cambia de nombre y conserva lo
demás. Avisa además de los duplicados (la misma huella), de los archivos de la lista que
ya no están en la carpeta y de las claves que no existen en la bibliografía.
Necesita pdfinfo y pdftotext (poppler-utils).
"""
import argparse
import collections
import csv
import hashlib
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

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
    """clave → (título, apellidos de los autores), de un .bib de un campo por línea."""
    entradas, clave = {}, None
    for linea in Path(ruta).read_text(encoding="utf-8").splitlines():
        if m := re.match(r"\s*@\w+\s*\{\s*([^,\s]+)\s*,", linea):
            clave = m.group(1)
            entradas[clave] = ["", ""]
        elif clave and (m := re.match(r"\s*(title|author)\s*=\s*[{\"](.*?)[}\"]?,?\s*$", linea, re.I)):
            campo = 0 if m.group(1).lower() == "title" else 1
            entradas[clave][campo] = m.group(2).replace("{", "").replace("}", "")
    return entradas


def adivinar(texto, entradas):
    """La entrada cuyo título (palabras de más de tres letras) y primer apellido mejor
    casan con el nombre del archivo y sus metadatos; None si ninguna pasa del 60 %."""
    palabras = set(normal(texto).split())
    mejor, puntos = None, 0.6
    for clave, (titulo, autores) in entradas.items():
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


def pdfinfo(ruta):
    salida = subprocess.run(["pdfinfo", str(ruta)], capture_output=True, text=True).stdout
    return dict(l.split(":", 1) for l in salida.splitlines() if ":" in l)


def pagina(ruta, n):
    return subprocess.run(["pdftotext", "-layout", "-f", str(n), "-l", str(n), str(ruta), "-"],
                          capture_output=True, text=True).stdout


def examinar(ruta, total):
    """texto, páginas reales, idioma y caracteres ilegibles por cada mil palabras, con
    diez páginas repartidas por el libro."""
    muestra = sorted({max(1, round(total * i / 11)) for i in range(1, 11)}) if total else []
    textos = {n: pagina(ruta, n) for n in muestra}
    palabras = sorted(len(t.split()) for t in textos.values())
    mediana = palabras[len(palabras) // 2] if palabras else 0
    texto = "digital" if mediana >= 80 else "escaneado" if mediana <= 10 else "mixto (revisar)"

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
    reales = "?" if veces < len(textos) / 2 else "sí" if desfase == 0 else f"desfase {desfase:+d}"

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
    en_carpeta = {p.name for p in args.carpeta.glob("*.pdf")}
    for pdf in sorted(args.carpeta.glob("*.pdf")):
        if pdf.name in conocidos:
            continue
        huella = hashlib.sha256(pdf.read_bytes()).hexdigest()
        antigua = next((f for f in filas if f["sha256"] == huella and f["archivo"] not in en_carpeta), None)
        if antigua:
            print(f"  Renombrado: {antigua['archivo']} → {pdf.name}")
            antigua["archivo"] = pdf.name
            renombrados += 1
            continue
        info = pdfinfo(pdf)
        total = int(info.get("Pages", "0").strip() or 0)
        texto, reales, idioma, ilegibles = examinar(pdf, total)
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
