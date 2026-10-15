"""comprobar.py: si un paso de un desarrollo se sostiene, comprobado por sympy y no por el modelo.

  python3 comprobar.py "log(2)/log(1 + r) ≈ 35" "r = 0.02"
  python3 comprobar.py "n >= 50*log(40)" "2*exp(-2*n*t**2) <= alpha" "t = 0.1" "alpha = 0.05"
  python3 comprobar.py --planteamiento "h2 = 0.84" "h2 = 0.91"

Escribe «sí», «no» o «?», y detrás el motivo. El primer argumento es el paso; los demás, los
planteamientos [P] anteriores, de los que el paso tiene que seguirse: las igualdades se
resuelven y su solución se sustituye en el paso; las desigualdades, si queda una sola
variable, acotan sus valores, y el paso tiene que cumplirse en todos. Con --planteamiento,
el primero es un planteamiento nuevo, que no se deduce de nada, pero no puede contradecir
a los anteriores.

rag.py desarrollar lo llama una vez por paso, en un proceso aparte y con tiempo límite,
porque una expresión como 9**9**9**9 no acaba nunca. La expresión la escribe el modelo, que
lee pasajes que no son de fiar: solo se admiten números, operadores, variables y las
funciones de FUNCIONES, nunca un nombre de Python.

Las relaciones: = es exacta, y se comprueba simplificando la diferencia o, si sympy no llega
a cero, en tres puntos al azar, con valores positivos; ≈ admite hasta un 1% de diferencia;
<, >, <= y >= entre números, o con una sola variable que los planteamientos acotan.
"""
import keyword
import random
import re
import sys

import sympy as sp
from sympy.parsing.sympy_parser import (convert_xor, implicit_multiplication, parse_expr, rationalize,
                                        standard_transformations)

FUNCIONES = {n: getattr(sp, n) for n in """sqrt exp log sin cos tan pi E oo Abs factorial binomial gamma erf
    Sum Integral Derivative Limit integrate diff limit Rational Min Max floor ceiling""".split()}
FUNCIONES["ln"] = sp.log
# Lo que el código que genera parse_expr necesita, y nada más: sin __builtins__ no hay open ni eval.
GLOBALES = {"__builtins__": {}, "Integer": sp.Integer, "Float": sp.Float, "Rational": sp.Rational, "Symbol": sp.Symbol}
# ^ como potencia, 0.2 como 1/5 y 2n como 2*n.
TRANSFORMACIONES = standard_transformations + (convert_xor, rationalize, implicit_multiplication)
# Lo poco de LaTeX que los modelos escriben aunque se les pida Python.
LATEX = {r"\leq": "<=", r"\le": "<=", r"\geq": ">=", r"\ge": ">=", r"\approx": "≈", r"\cdot": "*", r"\times": "*",
         r"\left": "", r"\right": "", "$": "", "{": "(", "}": ")"}
RELACION = r"(<=|>=|≤|≥|≈|=|<|>)"
COMO = {"=": sp.Eq, "≈": sp.Eq, "<": sp.Lt, ">": sp.Gt, "<=": sp.Le, "≤": sp.Le, ">=": sp.Ge, "≥": sp.Ge}


class Duda(Exception):
    """Lo que no se puede decidir: ni sí ni no."""


def limpiar(expresion):
    expresion = expresion.replace("==", "=")
    for latex, python in sorted(LATEX.items(), key=lambda x: -len(x[0])):
        expresion = expresion.replace(latex, python)
    expresion = re.sub(r"\\([a-zA-Z]+)", r" \1 ", expresion)  # \log, \pi, \epsilon: sin la barra, y aparte
    return re.sub(r"(?<![^\W\d])e(?=\s*(\^|\*\*))", "E", expresion).strip()  # e^x es la exponencial


def leer(expresion, local):
    """Los lados y las relaciones de una expresión: a = b ≈ c da [a, b, c] y [=, ≈]."""
    if not re.fullmatch(r"[\w\s+\-*/^().,=<>≈≤≥!]+", expresion) or "__" in expresion or "!=" in expresion \
            or re.search(r"\.\s*[^\W\d]", expresion):
        raise Duda("caracteres que no son de una expresión")
    # Los nombres, quitados antes los números, que en 1e-5 llevan una e y en 2n van pegados a una variable.
    nombres = set(re.findall(r"[^\W\d]\w*", re.sub(r"(?<![\w.])\d+\.?\d*(?:[eE][+-]?\d+)?", " ", expresion)))
    if prohibidos := sorted(n for n in nombres if keyword.iskeyword(n)):
        raise Duda(f"palabras de Python: {', '.join(prohibidos)}")
    local.update({n: FUNCIONES.get(n) or sp.Symbol(n, real=True) for n in nombres if n not in GLOBALES | local})
    partes = re.split(RELACION, expresion)
    if len(partes) < 3:
        raise Duda("no hay igualdad ni desigualdad")
    lados = [parse_expr(p, local_dict=local, global_dict=dict(GLOBALES), transformations=TRANSFORMACIONES).doit()
             for p in partes[::2]]
    return lados, partes[1::2]


def numero(x):
    return complex(sp.N(x, 30))


def par(a, rel, b):
    """Si a rel b se cumple: («sí» o «no», el motivo), o Duda si no se puede saber."""
    if rel == "=":
        if sp.simplify(a - b) == 0:
            return "sí", ""
        # ponytail: tres puntos al azar no son una demostración; bastan para cazar el paso falso
        azar = random.Random(0)
        libres = sorted(a.free_symbols | b.free_symbols, key=str)
        for _ in range(3 if libres else 1):
            v = {s: sp.Rational(azar.randint(5, 30), 10) for s in libres}
            x, y = numero(a.subs(v)), numero(b.subs(v))
            if abs(x - y) > 1e-9 * (1 + abs(x)):
                if not v:
                    return "no", f"{x.real:.6g} no es {y.real:.6g}"
                donde = ", ".join(f"{s} = {float(n):g}" for s, n in v.items())
                return "no", f"{a} no es {b}: con {donde}, {x.real:.6g} frente a {y.real:.6g}"
        return "sí", "" if not libres else "en tres puntos al azar"
    if a.free_symbols | b.free_symbols:
        raise Duda(f"«{rel}» con variables que los planteamientos no fijan")
    x, y = numero(a), numero(b)
    if abs(x.imag) + abs(y.imag) > 1e-12:
        raise Duda("un número complejo")
    x, y = x.real, y.real
    bien = {"≈": abs(x - y) <= 0.01 * max(abs(x), abs(y)), "<": x < y, ">": x > y,
            "<=": x <= y, "≤": x <= y, ">=": x >= y, "≥": x >= y}[rel]
    return ("sí", "") if bien else ("no", f"{x:.6g} {rel} {y:.6g} es falso")


def soluciones(ecuaciones):
    """Las soluciones de los planteamientos, como sustituciones; [{}] si no hay ninguno."""
    if not ecuaciones:
        return [{}]
    incognitas = sorted(set().union(*(e.free_symbols for e in ecuaciones)), key=str)
    try:
        return sp.solve(ecuaciones, incognitas, dict=True)
    except NotImplementedError:
        raise Duda("sympy no sabe resolver los planteamientos")


def dominio(condiciones, extra=()):
    """La variable que queda en unas desigualdades y el conjunto de valores que la cumplen, o
    Duda si quedan varias: sympy solo despeja desigualdades de una variable."""
    libres = set().union(*(c.free_symbols for c in [*condiciones, *extra]))
    if len(libres) != 1:
        raise Duda("desigualdades con varias variables que los planteamientos no fijan")
    x = libres.pop()
    conjunto = sp.S.Reals
    for c in condiciones:
        conjunto = conjunto.intersect(sp.solveset(c, x, sp.S.Reals))
    return x, conjunto


def implica(a, rel, b, condiciones):
    """Si las desigualdades de los planteamientos obligan a que a rel b: («sí» o «no», el motivo)."""
    if rel == "≈":
        raise Duda("«≈» con variables que los planteamientos no fijan")
    x, conjunto = dominio(condiciones, [a - b])
    paso = sp.solveset(COMO[rel](a, b), x, sp.S.Reals)
    dentro = conjunto.is_subset(paso)
    if dentro is None:
        raise Duda("sympy no sabe comparar los conjuntos")
    return ("sí", "") if dentro else ("no", f"con {x} en {sp.N(conjunto, 6)}, {sp.N(a, 6)} {rel} {sp.N(b, 6)} no siempre se cumple")


def comprobar(expresion, premisas=(), planteamiento=False):
    """(«sí», «no» o «?», el motivo) de un paso, o de un planteamiento con --planteamiento."""
    local = {}
    try:
        ecuaciones, condiciones = [], []
        for p in premisas:
            (a, b), (rel,) = leer(limpiar(p), local)
            if a.free_symbols | b.free_symbols:  # sin variables es una cuenta, no un planteamiento
                (ecuaciones if COMO[rel] is sp.Eq else condiciones).append(COMO[rel](a, b))
        lados, relaciones = leer(limpiar(expresion), local)
        casos = soluciones(ecuaciones)
        if not casos:
            raise Duda("los planteamientos anteriores no tienen solución")
        if planteamiento:
            if len(relaciones) != 1:
                raise Duda("un planteamiento es una sola relación")
            nuevo = COMO[relaciones[0]](*lados)
            if not (lados[0].free_symbols | lados[1].free_symbols):  # sin incógnitas, es una cuenta
                return par(lados[0], relaciones[0], lados[1])
            if nuevo is sp.false or (COMO[relaciones[0]] is sp.Eq and ecuaciones and not soluciones(ecuaciones + [nuevo])):
                return "no", "contradice los planteamientos anteriores"
            if COMO[relaciones[0]] is not sp.Eq:
                vacios = []
                for s in casos:
                    try:
                        vacios.append(dominio([c.subs(s) for c in condiciones + [nuevo]])[1] is sp.S.EmptySet)
                    except Duda:
                        vacios.append(False)  # con varias variables no se sabe: se admite
                if all(vacios):
                    return "no", "contradice los planteamientos anteriores"
            return "sí", ""
        motivo = ""
        for a, rel, b in zip(lados, relaciones, lados[1:]):
            for s in casos:  # tiene que cumplirse en todas las soluciones de los planteamientos
                a2, b2 = a.subs(s), b.subs(s)
                if rel != "=" and (a2.free_symbols | b2.free_symbols) and condiciones:
                    veredicto, motivo = implica(a2, rel, b2, [c.subs(s) for c in condiciones])
                else:
                    veredicto, motivo = par(a2, rel, b2)
                if veredicto == "no":
                    return "no", motivo
        return "sí", motivo
    except Duda as e:
        return "?", str(e)
    except Exception as e:  # lo que sympy no entiende o no sabe decidir
        return "?", f"{type(e).__name__}: {e}".splitlines()[0][:200]


if __name__ == "__main__":
    plantea = sys.argv[1] == "--planteamiento"
    paso, *anteriores = sys.argv[2:] if plantea else sys.argv[1:]
    veredicto, motivo = comprobar(paso, anteriores, plantea)
    print(f"{veredicto} {motivo}".strip())
