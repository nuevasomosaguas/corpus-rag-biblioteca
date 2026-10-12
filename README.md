# corpus-rag-biblioteca

Los scripts de ingesta, limpieza de texto y estructuración de la biblioteca viva, el núcleo y el área secundaria curada, lista para alimentar los vectores del exoesqueleto cognitivo y los entornos RAG locales.

## El inventario

`inventariar.py CARPETA --bib biblioteca.bib` añade a `CARPETA/inventario.tsv` una fila por cada PDF, EPUB o DjVu nuevo. Rellena solo lo que se puede averiguar:

* la clave más probable de la bibliografía, por el título y el autor;
* la huella (`sha256`), para ver los duplicados;
* las páginas;
* si tiene texto o es un escaneo;
* si el número impreso coincide con el del visor, o con qué desfase (un EPUB no tiene páginas: cuenta sus secciones);
* el idioma;
* y, si el nombre lo dice, la procedencia.

Lo demás se comprueba a mano, y el script nunca lo reescribe: la edición (contra la página de derechos), lo difícil (ecuaciones, tablas) y la procedencia. El inventario, como los PDF, se queda fuera del repositorio: aquí solo van los scripts.

## Requisito: el núcleo primero

`biblioteca.bib` tiene dos capas. Las obras del núcleo llevan `estrato`; las del área secundaria llevan `capa = {secundaria}`, la obra del núcleo de la que cuelgan (`cuelga`), su papel (`papel`: profundización técnica, contraste y crítica, especialización aplicada, fuente original, historia y contexto, divulgación o introducción) y su estado (`estado`: curada o propuesta). La recuperación tiene que leer esos campos y cumplir cuatro reglas:

1. **El núcleo va primero.** Ante una consulta, los pasajes del núcleo se recuperan y se citan antes que los del área secundaria.
2. **Lo secundario va etiquetado.** Un pasaje del área secundaria se presenta con su papel («para profundizar», «contrapeso»…) y con la obra del núcleo de la que cuelga, nunca como el consenso del pensum.
3. **Las obras discutidas traen su contrapeso.** Si se cita una obra del núcleo de la que cuelgan obras con papel «Contraste y crítica», como Plomin o Vanhanen, se recuperan también.
4. **Solo entra lo curado.** Las obras con `estado = {propuesta}` no se indexan hasta que pasan la revisión.

## Tu propio RAG, en casa

Con tus propios PDF, EPUB y DjVu, aunque no sean públicos, y sin que nada salga de tu máquina: los libros, el inventario y el índice viven en una carpeta tuya, fuera del repositorio, y los modelos corren en local con [Ollama](https://ollama.com). Indexa solo ejemplares obtenidos de forma legítima: es la condición de la excepción de minería de textos y datos (artículo 67 del Real Decreto-ley 24/2021), como recuerda la [política de inteligencia artificial](https://nuevasomosaguas.github.io/politica_ia.html).

**Lo que hace falta.** Python 3.11 o posterior y [uv](https://docs.astral.sh/uv/), que instala la única dependencia de `rag.py`, [sqlite-vec](https://github.com/asg017/sqlite-vec), declarada en su cabecera; poppler (`pdftotext`, `pdfinfo`) y djvulibre (`djvutxt`, `djvused`); y Ollama con dos modelos independientes. El de vectores solo busca: tiene que ser multilingüe, para preguntar en castellano a libros en inglés, y cambiarlo obliga a reindexar. El de la respuesta solo redacta, es opcional y puede ser cualquiera que tengas, Gemma, Qwen o Llama, y se elige en cada pregunta:

```sh
ollama pull bge-m3          # los vectores: --embed o RAG_EMBED para usar otro
ollama pull qwen3.8:27b     # la respuesta, por ejemplo: --modelo o RAG_MODELO
```

**Los pasos**, con los libros en `~/biblioteca` y la bibliografía de la web:

```sh
python3 inventariar.py ~/biblioteca --bib ../website/biblioteca.bib    # y revisa inventario.tsv a mano
ollama serve &
uv run rag.py indexar ~/biblioteca --bib ../website/biblioteca.bib
uv run rag.py preguntar ~/biblioteca "¿Qué es la falsificación de preferencias?" --bib ../website/biblioteca.bib
uv run rag.py preguntar ~/biblioteca "¿Qué es la falsificación de preferencias?" --bib ../website/biblioteca.bib --responder --modelo qwen3.8:27b
```

* **`indexar`** guarda en `~/biblioteca/corpus.sqlite` un pasaje por página, con la página impresa si el inventario sabe el desfase, o por fragmento de 400 palabras en un EPUB. Indexa solo las obras con clave del inventario que son del núcleo o están curadas, y borra las que vuelven a propuesta. Es incremental: tras añadir libros o actualizar la bibliografía, se repiten `inventariar.py` e `indexar`. Los vectores van a una tabla de sqlite-vec en el mismo archivo, que busca los vecinos más próximos sin cargar el corpus en memoria. Sin Ollama, el índice es solo léxico, y los vectores se añaden en la siguiente pasada; si cambia el modelo de vectores, se rehacen todos.
* **`preguntar`** combina la búsqueda léxica (BM25) y la de vectores y aplica las cuatro reglas de arriba: los pasajes del núcleo primero, los del área secundaria con su papel y la obra de la que cuelgan, y el contrapeso de cada obra discutida, aunque ningún pasaje suyo case con la pregunta. Sin `--responder`, devuelve los pasajes con su cita; con él, el modelo local que elijas redacta la respuesta a temperatura cero, cita cada afirmación con el número de su pasaje y, ante un ejercicio, responde con preguntas guía.
* **Los escaneos** no tienen texto: `indexar` los señala. Pásalos antes por OCR, por ejemplo con `ocrmypdf -l eng+spa`, y vuelve a inventariarlos.

## La Trituradora

La tercera capa, privada: obras influyentes y débiles para practicar la crítica y preparar argumentos. No está en la web ni en `biblioteca.bib`, y no comparte índice con la biblioteca, de modo que no penetra en el núcleo ni en el área secundaria: `preguntar` no la abre nunca, el índice de la biblioteca rechaza una obra de la Trituradora aunque se cuele en su bibliografía, y el de la Trituradora rechaza lo que no sea suyo.

Entra una obra con alcance público demostrable cuyo argumento central rompe al menos una de las doce reglas del [Manual de bolsillo](https://nuevasomosaguas.github.io/manual_bolsillo.html). Cada cual la llena en su carpeta, a partir de `trituradora.plantilla.bib`, que explica los campos: `tesis`, `reglas`, `contraste`, `motivo` y `estado`, con `capa = {trituradora}`.

```sh
mkdir ~/biblioteca/trituradora                      # sus libros, aquí
cp trituradora.plantilla.bib ~/biblioteca/trituradora/trituradora.bib   # y llénala
python3 inventariar.py ~/biblioteca/trituradora --bib ~/biblioteca/trituradora/trituradora.bib
uv run rag.py indexar ~/biblioteca --bib ../website/biblioteca.bib          # indexa las dos capas
uv run rag.py triturar ~/biblioteca "la ley creó el empleo" --bib ../website/biblioteca.bib --responder --modelo qwen3.8:27b
```

`triturar` recupera los pasajes de la obra, [T1], [T2]…, como el objeto que se examina, con su tesis y las reglas que pone en juego; y de la biblioteca, [1], [2]…, el material para examinarla, con las cuatro reglas de siempre y las obras de su campo `contraste`, aunque la búsqueda no las suba. Con `--responder`, el modelo no escribe la crítica: reconstruye el argumento en su versión más fuerte y formula de tres a cinco preguntas, cada una ligada a una regla del manual y a los pasajes de la biblioteca donde está el material para contestarla. Un pasaje [T] nunca es evidencia de nada.

`python3 test_rag.py` lo comprueba todo con un corpus de juguete y un Ollama falso; necesita además `typst`, `pandoc`, djvulibre y uv. El `.gitignore` impide que un libro, el inventario, el índice o la bibliografía de la Trituradora entren en el repositorio por descuido.

