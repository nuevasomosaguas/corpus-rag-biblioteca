#!/usr/bin/env python3
"""test_rag.py: la comprobación de inventariar.py y rag.py, sin libros reales ni Ollama.

Crea en una carpeta temporal un PDF (con portada, para el desfase), un EPUB y un DjVu, y
una bibliografía con una obra del núcleo, su contrapeso curado, una ampliación curada y
una propuesta; y una Trituradora con una obra curada y una propuesta, más una obra de la
Trituradora colada en la bibliografía de la biblioteca, para ver que no entra. Un servidor
falso hace de Ollama. Necesita typst, pandoc, djvulibre y uv.
"""
import hashlib
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RELLENO = " ".join(f"palabra{i}" for i in range(120))

BIB = """@book{alfa2000libro,
  author     = {Alfa, Ana},
  title      = {Libro sobre preferencias ocultas},
  year       = {2000},
  estrato    = {accion}
}

@book{beta2010critica,
  author     = {Beta, Bruno},
  title      = {Crítica de las preferencias ocultas},
  year       = {2010},
  capa       = {secundaria},
  cuelga     = {alfa2000libro},
  papel      = {Contraste y crítica},
  motivo     = {Discute a Alfa.},
  estado     = {curada}
}

@book{delta2015extension,
  author     = {Delta, Dora and Epsilon, Eva and Zeta, Zoe},
  title      = {Extensiones formales del modelo},
  year       = {2015},
  capa       = {secundaria},
  cuelga     = {alfa2000libro},
  papel      = {Profundización técnica},
  motivo     = {Formaliza a Alfa.},
  estado     = {curada}
}

@book{gamma2020borrador,
  author     = {Gamma, Gina},
  title      = {Borrador sin revisar},
  year       = {2020},
  capa       = {secundaria},
  cuelga     = {alfa2000libro},
  papel      = {Introducción},
  motivo     = {Pendiente.},
  estado     = {propuesta}
}

@book{sigma2001colada,
  author     = {Sigma, Saul},
  title      = {Ensayo colado en la biblioteca},
  year       = {2001},
  capa       = {trituradora},
  estado     = {curada}
}
"""

TRITURADORA = """@book{omega2012ensayo,
  author     = {Omega, Olga},
  title      = {Ensayo sobre preferencias reveladas},
  year       = {2012},
  capa       = {trituradora},
  tesis      = {El ketman demuestra que nadie miente en público},
  reglas     = {8, 9},
  contraste  = {beta2010critica},
  motivo     = {Superventas; confunde la secuencia con el efecto.},
  estado     = {curada}
}

@book{psi2019panfleto,
  author     = {Psi, Pablo},
  title      = {Panfleto pendiente de revisar},
  year       = {2019},
  capa       = {trituradora},
  estado     = {propuesta}
}
"""


class FalsoOllama(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # /api/tags: los modelos instalados
        self.responder({"models": [{"name": "gemma4:26b"}, {"name": "qwen3.8:27b"}]})

    def do_POST(self):
        datos = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/api/embed":
            vec = lambda t: [sum(int(hashlib.md5(w.encode()).hexdigest(), 16) % 16 == d for w in t.lower().split()) + 0.01
                             for d in range(16)]
            r = {"embeddings": [vec(t) for t in datos["input"]]}
        else:
            r = {"message": {"content": f"Respuesta de {datos['model']} [1]."}}
            assert datos["options"]["temperature"] == 0
            sistema, usuario = datos["messages"][0]["content"], datos["messages"][1]["content"]
            assert datos["messages"][0]["role"] == "system" and "Solo los pasajes" in sistema
            assert re.search(r"^\[1\] Alfa \(2000\)", usuario, re.M)
            # La Trituradora, con su propia instrucción, y sus pasajes solo con ella.
            assert ("[T1] Omega" in usuario) == ("Los [T] nunca son evidencia" in sistema), (sistema, usuario)
            assert "12. Desconfía del indicador que se premia" in sistema or "[T1]" not in usuario
        self.responder(r)

    def responder(self, r):
        cuerpo = json.dumps(r).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, *a):
        pass


def correr(script, *orden, env=None):
    # rag.py declara su dependencia, sqlite-vec, y uv la instala; inventariar.py no tiene.
    inicio = ["uv", "run", "--quiet", "--script"] if script == "rag.py" else [sys.executable]
    r = subprocess.run([*inicio, script, *orden], capture_output=True, text=True, cwd=AQUI, env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout + r.stderr


def main():
    d = Path(tempfile.mkdtemp())
    (d / "biblioteca.bib").write_text(BIB, encoding="utf-8")

    # El PDF: una portada sin número y tres páginas numeradas desde el 1.
    paginas = [f"El ketman es la falsificación de preferencias. {RELLENO}",
               f"La zarzaparrilla solo aparece aquí. {RELLENO}",
               f"Tercera página del libro. {RELLENO}"]
    typ = '#set page(numbering: none)\nPortada\n#pagebreak()\n#set page(numbering: "1")\n#counter(page).update(1)\n' + \
          "\n#pagebreak()\n".join(paginas)
    (d / "alfa.typ").write_text(typ, encoding="utf-8")
    subprocess.run(["typst", "compile", str(d / "alfa.typ"), str(d / "Alfa - Libro sobre preferencias ocultas.pdf")], check=True)
    (d / "alfa.typ").unlink()

    (d / "beta.md").write_text(f"# Uno\n\nEl ketman no explica todo. {RELLENO}\n\n# Dos\n\nOtra sección. {RELLENO}\n",
                               encoding="utf-8")
    subprocess.run(["pandoc", str(d / "beta.md"), "-o", str(d / "Beta - Critica de las preferencias ocultas.epub"),
                    "--metadata", "title=Crítica de las preferencias ocultas"], check=True)
    (d / "beta.md").unlink()

    (d / "extension.typ").write_text(f"Una extensión formal del ketman. {RELLENO}", encoding="utf-8")
    subprocess.run(["typst", "compile", str(d / "extension.typ"), str(d / "Delta - Extensiones formales del modelo.pdf")], check=True)
    (d / "extension.typ").unlink()

    # El DjVu: una página en blanco con una capa de texto.
    (d / "g.pbm").write_text("P1\n8 8\n" + "0 " * 64)
    djvu = d / "Gamma - Borrador sin revisar.djvu"
    subprocess.run(["cjb2", str(d / "g.pbm"), str(djvu)], check=True)
    (d / "g.txt").write_text(f'(page 0 0 8 8 "El ketman del borrador. {RELLENO}")')
    subprocess.run(["djvused", str(djvu), "-e", f"select 1; set-txt {d / 'g.txt'}", "-s"], check=True)
    (d / "g.pbm").unlink(), (d / "g.txt").unlink()

    def pdf(carpeta, nombre, texto):
        (carpeta / "x.typ").write_text(texto, encoding="utf-8")
        subprocess.run(["typst", "compile", str(carpeta / "x.typ"), str(carpeta / nombre)], check=True)
        (carpeta / "x.typ").unlink()

    # Una obra de la Trituradora colada en la carpeta y la bibliografía de la biblioteca.
    pdf(d, "Sigma - Ensayo colado en la biblioteca.pdf", f"El ketman colado. {RELLENO}")
    t = d / "trituradora"
    t.mkdir()
    (t / "trituradora.bib").write_text(TRITURADORA, encoding="utf-8")
    pdf(t, "Omega - Ensayo sobre preferencias reveladas.pdf", f"Como prueba el ketman, nadie miente nunca en público. {RELLENO}")
    pdf(t, "Psi - Panfleto pendiente de revisar.pdf", f"El ketman del panfleto. {RELLENO}")

    bib = ["--bib", str(d / "biblioteca.bib")]
    correr("inventariar.py", str(d), *bib)
    filas = {f.split("\t")[1]: f.split("\t") for f in (d / "inventario.tsv").read_text().splitlines()[1:]}
    alfa = filas["Alfa - Libro sobre preferencias ocultas.pdf"]
    assert alfa[0] == "alfa2000libro" and alfa[4] == "digital" and alfa[5] == "desfase +1", alfa
    beta = filas["Beta - Critica de las preferencias ocultas.epub"]
    assert beta[0] == "beta2010critica" and beta[5].startswith("no (EPUB"), beta
    assert filas["Gamma - Borrador sin revisar.djvu"][0] == "gamma2020borrador"
    assert filas["Gamma - Borrador sin revisar.djvu"][3] == "1"

    correr("inventariar.py", str(t), "--bib", str(t / "trituradora.bib"))

    # Sin Ollama: índice léxico, y avisa.
    sin = dict(os.environ, OLLAMA_HOST="127.0.0.1:9")
    salida = correr("rag.py", "indexar", str(d), *bib, env=sin)
    assert "Propuesta, no se indexa: gamma2020borrador" in salida and "sin vector" in salida, salida
    assert "alfa2000libro: 3 pasajes" in salida, salida  # la portada, sin texto, no cuenta
    assert "De la Trituradora, no entra en la biblioteca: sigma2001colada" in salida, salida
    assert "La Trituradora:" in salida and "omega2012ensayo: 1 pasajes" in salida, salida
    assert "Propuesta, no se indexa: psi2019panfleto" in salida, salida

    servidor = http.server.HTTPServer(("127.0.0.1", 0), FalsoOllama)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    con = dict(os.environ, OLLAMA_HOST=f"127.0.0.1:{servidor.server_port}")
    salida = correr("rag.py", "indexar", str(d), *bib, env=con)
    assert "pasajes, 0 sin vector" in salida, salida  # los vectores llegan en la segunda pasada
    salida = correr("rag.py", "indexar", str(d), "--embed", "otro-modelo", *bib, env=con)
    assert "se rehacen todos" in salida and "pasajes, 0 sin vector" in salida, salida
    salida = correr("rag.py", "preguntar", str(d), "ketman", *bib, env=con)
    assert "son de otro-modelo, no de bge-m3: solo búsqueda léxica" in salida, salida
    salida = correr("rag.py", "indexar", str(d), *bib, env=con)
    assert "se rehacen todos" in salida and "pasajes, 0 sin vector" in salida, salida

    salida = correr("rag.py", "preguntar", str(d), "ketman", *bib, env=con)
    for ajena in ("Omega", "Sigma", "Psi", "Trituradora"):
        assert ajena not in salida, salida  # preguntar no abre nunca La Trituradora
    citas = re.findall(r"^\[\d+\] (.*)$", salida, re.M)
    assert citas[0].startswith("Alfa (2000), Libro sobre preferencias ocultas, p. 1"), citas  # el núcleo primero, con la página impresa
    assert any("Área secundaria, contraste y crítica de Alfa (2000)" in c for c in citas), citas
    assert any(c.startswith("Delta et al. (2015)") for c in citas), citas
    assert not any("Gamma" in c for c in citas), citas
    assert "xhtml" not in salida, salida  # el EPUB, sin su cabecera

    # El contrapeso llega aunque la búsqueda no lo suba: con vectores, con su mejor pasaje;
    # solo con la búsqueda léxica, que no lo encuentra, nombrado.
    salida = correr("rag.py", "preguntar", str(d), "zarzaparrilla", "--k", "1", *bib, env=con)
    assert re.search(r"^\[\d\] Beta \(2010\).*contraste y crítica de Alfa", salida, re.M), salida
    assert "sin pasaje" not in salida and "solo búsqueda léxica" not in salida, salida
    salida = correr("rag.py", "preguntar", str(d), "zarzaparrilla", "--k", "1", *bib, env=sin)
    assert re.search(r"^\[1\] Alfa \(2000\).*p\. 2$", salida, re.M), salida
    assert "Contrapeso sin pasaje que case con la pregunta: Beta (2010)" in salida, salida
    assert "Delta" not in salida, salida

    # El modelo de la respuesta es cualquiera de Ollama, y no hay uno por defecto.
    r = subprocess.run(["uv", "run", "--quiet", "--script", "rag.py", "preguntar", str(d), "ketman", "--responder", *bib],
                       capture_output=True, text=True, cwd=AQUI, env=con)
    assert r.returncode != 0 and "gemma4:26b, qwen3.8:27b" in r.stderr, r.stderr
    for modelo in ("gemma4:26b", "qwen3.8:27b"):
        salida = correr("rag.py", "preguntar", str(d), "ketman", "--responder", "--modelo", modelo, *bib, env=con)
        assert salida.startswith(f"Respuesta de {modelo} [1]."), salida
    salida = correr("rag.py", "preguntar", str(d), "ketman", "--responder", *bib, env=dict(con, RAG_MODELO="qwen3.8:27b"))
    assert salida.startswith("Respuesta de qwen3.8:27b [1]."), salida

    # triturar: el objeto, [T1], con su tesis y sus reglas; luego la biblioteca, con lo que
    # señala el campo contraste, aunque la búsqueda no lo subiera.
    salida = correr("rag.py", "triturar", str(d), "nadie miente en público", "--k", "1", *bib, env=sin)
    assert re.search(r"^\[T1\] Omega \(2012\), Ensayo sobre preferencias reveladas, p\. 1 del visor\. La Trituradora: "
                     r"tesis «El ketman demuestra que nadie miente en público»; reglas del manual en juego: 8, 9$", salida, re.M), salida
    assert "Beta (2010)" in salida and "Psi" not in salida and "Sigma" not in salida, salida
    salida = correr("rag.py", "triturar", str(d), "ketman", "--responder", "--modelo", "qwen3.8:27b", *bib, env=con)
    assert salida.startswith("Respuesta de qwen3.8:27b"), salida

    # Lo que vuelve a propuesta sale del índice.
    (d / "biblioteca.bib").write_text(BIB.replace("Formaliza a Alfa.},\n  estado     = {curada}",
                                                  "Formaliza a Alfa.},\n  estado     = {propuesta}"), encoding="utf-8")
    salida = correr("rag.py", "indexar", str(d), *bib, env=con)
    assert "Sale del índice: delta2015extension" in salida, salida
    salida = correr("rag.py", "preguntar", str(d), "ketman", *bib, env=con)
    assert "Delta" not in salida, salida
    servidor.shutdown()
    shutil.rmtree(d)
    print("test_rag.py: todo en orden.")


if __name__ == "__main__":
    main()
