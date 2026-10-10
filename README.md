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

## Requisito: el núcleo primero

`biblioteca.bib` tiene dos capas. Las obras del núcleo llevan `estrato`; las del área secundaria llevan `capa = {secundaria}`, la obra del núcleo de la que cuelgan (`cuelga`), su papel (`papel`: profundización técnica, contraste y crítica, especialización aplicada, fuente original, historia y contexto, divulgación o introducción) y su estado (`estado`: curada o propuesta). La recuperación tiene que leer esos campos y cumplir cuatro reglas:

1. **El núcleo va primero.** Ante una consulta, los pasajes del núcleo se recuperan y se citan antes que los del área secundaria.
2. **Lo secundario va etiquetado.** Un pasaje del área secundaria se presenta con su papel («para profundizar», «contrapeso»…) y con la obra del núcleo de la que cuelga, nunca como el consenso del pensum.
3. **Las obras discutidas traen su contrapeso.** Si se cita una obra del núcleo de la que cuelgan obras con papel «Contraste y crítica», como Plomin o Vanhanen, se recuperan también.
4. **Solo entra lo curado.** Las obras con `estado = {propuesta}` no se indexan hasta que pasan la revisión.
