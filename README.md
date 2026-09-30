# corpus-rag-biblioteca

Los scripts de ingesta, limpieza de texto y estructuración de la biblioteca viva de 141+ fuentes, lista para alimentar los vectores del exoesqueleto cognitivo y los entornos RAG locales.

## El inventario

`inventariar.py CARPETA --bib biblioteca.bib` añade a `CARPETA/inventario.tsv` una fila por cada PDF nuevo. Rellena solo lo que se puede averiguar:

* la clave más probable de la bibliografía, por el título y el autor;
* la huella (`sha256`), para ver los duplicados;
* las páginas;
* si tiene texto o es un escaneo;
* si el número impreso coincide con el del visor, o con qué desfase;
* el idioma;
* y, si el nombre lo dice, la procedencia.

Lo demás se comprueba a mano, y el script nunca lo reescribe: la edición (contra la página de derechos), lo difícil (ecuaciones, tablas) y la procedencia. El inventario, como los PDF, se queda fuera del repositorio: aquí solo van los scripts.
