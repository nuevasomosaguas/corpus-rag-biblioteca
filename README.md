# corpus-rag-biblioteca

Scripts para inventariar, limpiar, indexar y consultar en local la biblioteca viva (el núcleo y el área secundaria curada), pensados para alimentar el exoesqueleto cognitivo y entornos RAG locales.

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

`biblioteca.bib` tiene dos capas. Las obras del núcleo llevan `estrato`. Las del área secundaria llevan `capa = {secundaria}`, la obra del núcleo de la que cuelgan (`cuelga`), su estado (`estado`: curada o propuesta) y su papel (`papel`: profundización técnica, contraste y crítica, especialización aplicada, fuente original, historia y contexto, divulgación o introducción). La recuperación tiene que leer esos campos y cumplir cuatro reglas:

1. **El núcleo va primero.** Ante una consulta, los pasajes del núcleo se recuperan y se citan antes que los del área secundaria.
2. **Lo secundario va etiquetado.** Un pasaje del área secundaria se presenta con su papel («para profundizar», «contrapeso»…) y con la obra del núcleo de la que cuelga, nunca como el consenso del pensum.
3. **Las obras discutidas traen su contrapeso.** Si se cita una obra del núcleo de la que cuelgan obras con papel «Contraste y crítica», como Plomin o Vanhanen, se recuperan también.
4. **Solo entra lo curado.** Las obras con `estado = {propuesta}` no se indexan hasta que pasan la revisión.

## Tu propio RAG, en casa

Funciona con tus propios PDF, EPUB y DjVu, aunque no sean públicos, sin que nada salga de tu máquina. Los libros, el inventario y el índice viven en una carpeta tuya, fuera del repositorio, y los modelos corren en local con [Ollama](https://ollama.com). Indexa solo ejemplares a los que tengas acceso lícito: es la condición de la excepción de minería de textos y datos (artículo 67 del Real Decreto-ley 24/2021), como recuerda la [política de inteligencia artificial](https://nuevasomosaguas.github.io/politica_ia.html).

**Lo que hace falta.** Python 3.11 o posterior y [uv](https://docs.astral.sh/uv/), que instala las dos dependencias declaradas en `rag.py` ([sqlite-vec](https://github.com/asg017/sqlite-vec) y [sympy](https://www.sympy.org)). Además, poppler (`pdftotext`, `pdfinfo`), djvulibre (`djvutxt`, `djvused`) y Ollama con dos modelos independientes. El de vectores solo busca: tiene que ser multilingüe, para preguntar en castellano a libros en inglés, y cambiarlo obliga a reindexar. El de la respuesta solo redacta, es opcional y puede ser cualquiera que tengas, Gemma, Qwen o Llama, y se elige en cada pregunta:

```sh
ollama pull bge-m3          # los vectores: --embed o RAG_EMBED para usar otro
ollama pull gemma4:12b      # la respuesta, por ejemplo: --modelo o RAG_MODELO
```

Qué modelo cabe en tu máquina lo dice la sección siguiente.

## Qué máquina hace falta

**Sin tarjeta gráfica** funciona todo menos la redacción rápida. `indexar` calcula los vectores en la CPU (más despacio, pero una sola vez), y `preguntar` sin `--responder` devuelve los pasajes con su cita al instante. Es además el modo más fiable, porque no genera nada. Redactar en la CPU también se puede, pero despacio: en un procesador de escritorio, unas 7 fichas por segundo, y varios minutos por respuesta entre leer los pasajes, redactar y comprobar frase a frase.

**Para redactar con la tarjeta**, el modelo tiene que caber entero en su memoria, junto al de vectores (`bge-m3`, algo más de 1 GB) y la memoria de la conversación, que a 16.000 fichas ocupa entre 1 y 3 GB según el modelo. Si no cabe, Ollama manda una parte a la CPU y la velocidad cae, mucho en un modelo denso. La cuenta: un modelo cuantizado a 4 bits (Q4_K_M) ocupa unos 0,6 GB por cada mil millones de parámetros.

| Memoria de la tarjeta | Tamaño del modelo que redacta |
|---|---|
| 8 GB | hasta unos 8.000 millones de parámetros |
| 12 GB | hasta unos 12.000 a 14.000 millones |
| 16 GB | unos 14.000 millones, con holgura |
| 24 GB | hasta unos 30.000 millones |

Las cifras son aproximadas. Medido en una RTX 5060 Ti de 16 GB, a 16.000 fichas de contexto: un Gemma 4 de 12.000 millones en Q4_K_M ocupa 8,3 GB, va entero en la tarjeta y redacta a unas 49 fichas por segundo, frente a 7 en la CPU. `gemma4:26b` ocupa 18 GB y no cabe: Ollama reparte el 52% en la tarjeta y el 48% en la CPU. Aun así redacta a 31 fichas por segundo porque es un modelo de mezcla de expertos que activa solo una parte de sus parámetros en cada ficha; uno denso de ese tamaño caería mucho más. Cuenta la memoria libre, no la total: en esa máquina, el escritorio ya ocupaba 3,6 GB de la tarjeta. En un Mac con Apple Silicon la memoria es compartida: cuenta la total menos unos 8 GB para el sistema. En cualquier máquina, 16 GB de RAM como mínimo y 32 para ir holgado. El índice ocupa unos pocos GB por cada mil libros.

**Comprueba que Ollama usa la tarjeta.** `ollama ps`, con el modelo cargado, dice el reparto: tiene que decir 100% GPU. En algunas distribuciones, el paquete `ollama` solo trae la CPU, y la tarjeta pide otro: en Arch, `ollama-cuda` para NVIDIA u `ollama-vulkan`. Si `ollama ps` dice 100% CPU con una tarjeta que debería bastar, es eso.

## Cuánto fiarse

* **Sin `--responder` no hay alucinaciones**, porque no se genera nada: son los pasajes, con su cita. Es el modo de referencia.
* **Con `--responder`, lo que se puede comprobar lo comprueba el código.** Ningún pasaje más allá del umbral entra en la respuesta, tampoco del núcleo, y si no queda ninguno, no se llama al modelo. Cada [n] tiene que existir, cada párrafo debe citar, el contrapeso aparecer solo cuando toca y lo secundario declararse como tal. Si algo falla, se vuelve a pedir la respuesta; lo que sigue mal y el código puede corregir, lo corrige (quita el contrapeso inventado y rotula lo secundario con la cabecera de su pasaje). Cada cifra tiene que aparecer en el pasaje citado (20.000, 20000 y 20,000 cuentan por igual). Cada cita literal entre «» debe ir tal cual y en el idioma del pasaje, con su traducción detrás entre paréntesis y sin comillas si está en otra lengua; así se comprueba la literalidad también en inglés, y la frase que falla se quita. Una segunda llamada revisa, frase a frase, si el pasaje sostiene lo afirmado (convertir una asociación en efecto causal o borrar cautelas cuenta como deformación). La frase sin apoyo se elimina, y la apoyada solo en parte sale con aviso. Un nombre propio que no está en ningún pasaje, también se avisa. Debajo de la respuesta van siempre los pasajes, con un extracto, para contrastarla.
* **Con `desarrollar`, las cuentas las comprueba sympy, no el modelo.** Si un paso [D] no se sigue de los planteamientos, se elimina junto con las conjeturas posteriores. Los datos de un planteamiento [P] tienen que estar en su pasaje o en la pregunta. Pero sympy comprueba la cuenta, no el modelo: si el planteamiento es la fórmula equivocada, la cuenta bien hecha pasa. Un número escrito dentro de un [D], en lugar de en un [P], tampoco se busca en ningún pasaje. Y la igualdad que sympy no consigue simplificar se prueba en tres puntos al azar, que cazan el paso falso pero no son una demostración.
* **El riesgo no llega a cero.** Queda la paráfrasis que desplaza el sentido un grado: la frase se sostiene casi, el comprobador la da por buena, y solo la caza un lector atento con el pasaje delante. Cuanto mayor es el modelo, mejor sintetiza, pero ninguno está libre de errores.

## Los pasos

Con los libros en `~/biblioteca` y la bibliografía de la web:

```sh
python3 inventariar.py ~/biblioteca --bib ../website/biblioteca.bib    # y revisa inventario.tsv a mano
ollama serve &
uv run rag.py indexar ~/biblioteca --bib ../website/biblioteca.bib
uv run rag.py preguntar ~/biblioteca "¿Qué es la falsificación de preferencias?" --bib ../website/biblioteca.bib
uv run rag.py preguntar ~/biblioteca "¿Qué es la falsificación de preferencias?" --bib ../website/biblioteca.bib --responder --modelo gemma4:12b
```

* **`indexar`** guarda en `~/biblioteca/corpus.sqlite` un pasaje por página, con la página impresa si el inventario sabe el desfase, o por fragmento de 400 palabras en un EPUB. El texto respeta el orden de lectura sin mezclar columnas y une las palabras partidas a final de línea. Cada pasaje arranca con las últimas 80 palabras del anterior para no cortar argumentos en el salto de página. Indexa solo las obras con clave del inventario que son del núcleo o están curadas, y borra las que vuelven a propuesta. Es incremental: tras añadir libros o actualizar la bibliografía, se repiten `inventariar.py` e `indexar`. Los vectores van a una tabla de sqlite-vec en el mismo archivo, que busca los vecinos más próximos sin cargar el corpus en memoria. Sin Ollama, el índice es solo léxico, y los vectores se añaden en la siguiente pasada; si cambia el modelo de vectores, se rehacen todos.
* **`preguntar`** combina la búsqueda léxica (BM25, sin palabras vacías) con la de vectores. Aplica las cuatro reglas de arriba: pasajes del núcleo primero, área secundaria con su papel y obra madre, y contrapeso de cada obra discutida. El contrapeso trae su pasaje más próximo solo si queda a menos de `--umbral` (distancia del coseno, 0,46 por defecto); si no, se nombra sin pasaje, en lugar de traer una página que no viene a cuento. Con `--modelo`, la pregunta se traduce además al inglés para la búsqueda léxica, de modo que un pasaje en inglés case por palabras igual que uno en castellano.
* **`--responder`** pide la respuesta al modelo que elijas a temperatura cero, con semilla fija y sin razonamiento previo (que con decodificación voraz entra en bucles). Además ajusta la ventana de contexto para que el prompt quepa entero, porque Ollama recorta sin avisar. Las comprobaciones de la respuesta están en «Cuánto fiarse»; la de apoyo hace una llamada corta por frase, y alarga la espera.
* **Los escaneos** no tienen texto: `indexar` los señala. Pásalos antes por OCR, por ejemplo con `ocrmypdf -l eng+spa`, y vuelve a inventariarlos. Un OCR viejo, con palabras de sobra pero no de verdad, sale en el inventario como «OCR dudoso»: se indexa, pero sus cifras y tablas no son de fiar.

## Medir la recuperación

`test_rag.py` comprueba la mecánica; la calidad se mide con tus libros. `evaluar` lee un TSV con las columnas `pregunta`, `clave` y `pagina`, el número impreso de la página que debería salir, y dice en qué puesto sale cada una, cuántas entran entre las 1, 5 y 10 primeras, el rango recíproco medio y la distancia del coseno del pasaje correcto:

```sh
uv run rag.py evaluar ~/biblioteca preguntas.tsv --bib ../website/biblioteca.bib --modelo gemma4:12b
```

Con unas decenas de preguntas, el umbral, el del contrapeso y el de la abstención, se elige midiendo. Añade preguntas que tu corpus no responde, con la clave y la página vacías, y `evaluar` da para cada umbral a cuántas pertinentes responde y en cuántas de fuera se abstiene. Las dos distribuciones se solapan: en un corpus de 33 libros, las preguntas de fuera tenían su pasaje más próximo entre 0,47 y 0,59, y las pertinentes, su pasaje correcto entre 0,31 y 0,56. A 0,46, el valor por defecto, se abstuvo en las 10 de fuera y respondió a 25 de 30; subirlo responde a más y se abstiene en menos. Igual se comparan dos modelos de vectores, o la búsqueda con y sin la traducción de `--modelo`.

## Desarrollar desde los primeros principios

`preguntar` se queda en lo que dicen los pasajes; `desarrollar` parte de ellos y desarrolla la respuesta paso a paso, desde la definición o el supuesto más básico que den hasta lo que se pregunta. Recupera igual, con las cuatro reglas y la misma abstención, y con `--responder` cada frase de la respuesta es de una de cuatro clases:

* **lo que dicen los pasajes**, con su cita, [2], que pasa por las comprobaciones de siempre;
* **un planteamiento**, el dato o la relación de los que se parte, con su ecuación y su fuente: «al 2% anual [3] [P: r = 0.02]». Sus datos tienen que estar en el pasaje que cita o en la pregunta;
* **un paso deducido**, con su expresión, [D: log(2)/log(1 + r) ≈ 35], que tiene que seguirse de los planteamientos anteriores, y lo comprueba [sympy](https://www.sympy.org), no el modelo;
* **una conjetura**, una idea propia que no se puede comprobar, que empieza por «Conjetura:» y nunca pasa por resultado. Puede llevar su planteamiento, con un dato supuesto: así un problema de Fermi se resuelve con supuestos a la vista y cuentas comprobadas.

```sh
uv run rag.py desarrollar ~/biblioteca "¿En cuántos años se duplica una población que crece al 2%?" --bib ../website/biblioteca.bib --responder --modelo gemma4:12b
```

La diferencia entre planteamiento y paso es la que hay entre premisa y deducción: `2*exp(-2*n*0.01) = 0.05` no es una identidad, es la ecuación que fija n, y lo que viene después tiene que seguirse de ella. `comprobar.py` resuelve los planteamientos, sustituye su solución en el paso y comprueba la relación. La igualdad (=) tiene que ser exacta y ≈ admite un 1% de margen. Las desigualdades (<, >, <= y >=) se comprueban si los dos lados quedan en números o en una sola variable acotada por los planteamientos: de [P: 2*exp(-2*n*t**2) <= alpha], con t = 0.1 y alpha = 0.05, se sigue [D: n >= 184.44], pero no n >= 184.86. Si sympy no llega a cero simplificando, la igualdad se prueba en tres puntos al azar. Las variables son reales: de n ≥ 184,44 no se sigue n ≥ 185, aunque n cuente observaciones. Un planteamiento no se deduce de nada, pero no puede contradecir a los anteriores: h2 = 0.84 después de h2 = 0.91 se quita. El planteamiento o paso que no se sostiene se quita junto con las conjeturas posteriores, que podrían apoyarse en él. Los pasos siguientes se mantienen porque cada uno se comprueba frente a los planteamientos, no frente a otros pasos. Si sympy no sabe decidir un paso, queda con un aviso, y al pie se indica cuántos pasos se comprobaron. Los modelos escriben a menudo en LaTeX aunque se les pida Python: `$`, `\log`, `\leq` y `e^{x}` se traducen. Como la expresión la escribe un modelo sobre pasajes no fiables, se evalúa en un proceso aislado con diez segundos de límite. Solo admite números, operadores, variables y funciones matemáticas básicas: nunca un nombre de Python.

`preguntar` sigue sin resolver ejercicios; `desarrollar`, en cambio, deduce, y no conviene darle el enunciado de un ejercicio que el estudiante tiene que hacer solo.

## Examinar tu afirmación

`examinar` no responde ni corrige: pone a prueba lo que afirmas tú. Le das tu afirmación y, si quieres, tu desarrollo, con planteamientos [P] y pasos [D] como los de `desarrollar`:

```sh
uv run rag.py examinar ~/biblioteca "Una población que crece al 2% anual se duplica en 50 años [P: r = 0.02] [D: log(2)/r ≈ 50]" --bib ../website/biblioteca.bib --responder --modelo gemma4:12b
```

Sin `--responder`, da la comprobación de tu desarrollo y los pasajes con los que ponerla a prueba, sin generar nada. Las reglas, y quién las hace cumplir:

1. **Tu desarrollo lo comprueba sympy, sin modelo.** Los pasos que se siguen de tus planteamientos se dicen. Los que no, vuelven como una pregunta con el contraejemplo de sympy, los valores en los que el paso falla, pero sin lo que valen los dos lados ni el resultado bueno: la cuenta la haces tú. Si sympy no sabe decidir un paso, te pide que lo reescribas para poder comprobarlo. *Código.*
2. **Solo preguntas, de dos a cuatro**, cada una en su línea, numerada y con su cita: «1. ¿…? [3]». La línea que no lo es se quita. *Código.*
3. **Nunca la respuesta**: ni la definición, ni la solución, ni si tu afirmación es correcta. La pregunta que lleva la respuesta dentro, «¿no es cierto que…?», «¿acaso…?», «¿verdad que…?», se quita. *Código, para esas formas; el resto, el modelo.*
4. **Cada pregunta, con su pasaje como contraejemplo o caso límite**: un caso que contradice la afirmación, un límite en el que falla, un supuesto que da por hecho o una palabra que usa sin definir. Y pregunta por tu afirmación, no por el pasaje: cada pregunta cita entre «» tus palabras exactas, las que pone a prueba. *El código comprueba que la pregunta cita tus palabras, que el pasaje existe y que sus cifras y citas literales aparecen en él o en tu afirmación. Decidir si el pasaje funciona como contraejemplo depende del modelo.*
5. **Solo los pasajes, con las cuatro reglas de la recuperación**: lo secundario va rotulado, y si ningún pasaje queda dentro del umbral, no se llama al modelo. *Código, salvo que el modelo no traiga lo que sabe por su cuenta, que es suyo.*
6. **Sin elogios ni reproches**, ni sobre la afirmación ni sobre quien la escribe. *El modelo.*

Si algo falla en las reglas 2 a 4, se pide una vez más, y lo que sigue mal se quita, con su aviso.

## La Trituradora

La tercera capa, privada: obras influyentes y débiles para practicar la crítica y preparar argumentos. No está en la web ni en `biblioteca.bib`, ni comparte índice con la biblioteca, así que no entra en el núcleo ni en el área secundaria. `preguntar` no la abre nunca: el índice de la biblioteca rechaza cualquier obra de la Trituradora aunque se cuele en su bibliografía, y el de la Trituradora rechaza todo lo ajeno.

Entra una obra con alcance público demostrable cuyo argumento central rompe al menos una de las doce reglas del [Manual de bolsillo](https://nuevasomosaguas.github.io/manual_bolsillo.html). Cada cual la llena en su carpeta, a partir de `trituradora.plantilla.bib`, que explica los campos: `tesis`, `reglas`, `contraste`, `motivo` y `estado`, con `capa = {trituradora}`.

```sh
mkdir ~/biblioteca/trituradora                      # sus libros, aquí
cp trituradora.plantilla.bib ~/biblioteca/trituradora/trituradora.bib   # y llénala
python3 inventariar.py ~/biblioteca/trituradora --bib ~/biblioteca/trituradora/trituradora.bib
uv run rag.py indexar ~/biblioteca --bib ../website/biblioteca.bib          # indexa las dos capas
uv run rag.py triturar ~/biblioteca "la ley creó el empleo" --bib ../website/biblioteca.bib --responder --modelo gemma4:12b
```

`triturar` recupera los pasajes de la obra ([T1], [T2]…) como objeto de examen, junto con su tesis y las reglas en juego. De la biblioteca trae el material de contraste ([1], [2]…), aplicando las cuatro reglas de siempre e incluyendo las obras del campo `contraste` aunque la búsqueda no las suba. Con `--responder`, el modelo no redacta la crítica: reconstruye el argumento en su versión más fuerte y plantea de tres a cinco preguntas, cada una ligada a una regla del manual y a los pasajes pertinentes. Un pasaje [T] nunca es evidencia de nada. La respuesta se comprueba igual: que cite, y que estén «El argumento:» y «Para triturarlo:».

## Una prueba con libros de verdad

Con 33 libros, 10.918 pasajes y preguntas en castellano con su página conocida, en una RTX 5060 Ti. De 27 preguntas, la búsqueda léxica sola, en castellano sobre libros en inglés, acertó a la primera en 3 y tuvo la página entre las diez primeras en 6; con la traducción de la pregunta, en 10 y 25. Con traducción y vectores, de 30 preguntas, 16 a la primera, 28 entre las cinco primeras y 29 entre las diez, con un rango recíproco medio de 0,69. Indexar costó 18 segundos sin vectores y 5 minutos con ellos, en un archivo de 103 MB. Un modelo de 12.000 millones afinado para programar redactó con faltas y se saltó dos reglas de formato incluso al pedírselo otra vez, y el código las arregló: conviene un modelo de instrucciones general.

Con `desarrollar`, diez preguntas de cuentas sobre el mismo índice, del tiempo de duplicación a la cota de Hoeffding, la ley de la raíz cúbica o la heredabilidad por gemelos. Con `gemma4:26b`, en la última ronda, sympy comprobó 3 de los 7 pasos [D] que quedaron en las respuestas y quitó 2 que no se seguían de sus planteamientos; en las anteriores había cazado un 184,856 donde la cuenta da 184,44. El modelo de 12.000 millones afinado para programar se equivocó más, con un log(2)/r ≈ 15 donde da 34,66 y una cota de Hoeffding sin su factor 2, y casi todo lo suyo se quitó. El cuello de botella está en que el modelo etiquete sus cuentas como [P] y [D], no en sympy. En la mitad de las respuestas no aparece ninguna etiqueta, y una cuenta suelta se elimina o queda sin comprobar.

`python3 test_rag.py` lo comprueba todo con un corpus de juguete y un Ollama falso; necesita además `typst`, `pandoc`, djvulibre y uv. El `.gitignore` impide que un libro, el inventario, el índice o la bibliografía de la Trituradora entren en el repositorio por descuido.

