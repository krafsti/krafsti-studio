# Novedades de Krafsti Studio

## 1.34 — 2026-11-25
- **«Guardar»** en lugar de «Descargar»: en la aplicación, y en Chrome y Edge, sale la ventana «Guardar como» para elegir dónde. «Guardar todos» (Convertir formato) pide una carpeta una sola vez.
- **Carpetas sin avisos en la aplicación**: guardar en una carpeta, abrir carpeta, guardar y abrir usan las ventanas del sistema y ya no preguntan «Allow this site…». Recuerda la última carpeta. En Linux, las carpetas ahora también funcionan.
- **Arreglo**: «Abrir archivo…» con un proyecto guardado en carpeta ya no lo abre con las imágenes vacías: en la aplicación las lee de `imagenes/` (y la carpeta queda vinculada); en el navegador avisa de que se abre con «Abrir carpeta…».
- **Vectorizar guarda el trabajo**: «Guardar el trabajo…» y «Abrir un trabajo…» (Ctrl+S / Ctrl+O) guardan la imagen con sus ajustes, colores protegidos, grupos, tonos incluidos, láminas y alturas.
- **Conectar con asistentes (MCP)**, en la aplicación: botón «Asistentes» para que Claude Desktop o ChatGPT de escritorio manejen Componer (textos, formas, imágenes, unir y restar, texto alrededor del círculo, exportar, guardar, captura). Apagado de inicio y solo en el propio ordenador.

## 1.33 — 2026-11-25
- **Aplicación de escritorio para Windows y Linux**, que avisa sola cuando hay una versión nueva. Dentro de la aplicación, guardar abre la ventana «Guardar como» del sistema.
- Icono nuevo: la K hecha de tres piezas. Ahora también sale en la pestaña del navegador.

## 1.32 — 2026-11-25
- Limpieza por dentro, sin cambios al usarla. Se suman pruebas automáticas (`pruebas/pruebas_krafsti.py`).

## 1.31 — 2026-11-25
- Funciona **sin internet**: las fuentes y el motor de Vectorizar van dentro del archivo.
- El SVG saca las letras **tal como se ven**, también las escritas a mano.
- **Guía** dentro de la aplicación: 9 recetas paso a paso que señalan los botones.
- Duplicar varias capas a la vez.

## 1.30 — 2026-11-24
- Guardar cualquier capa como **trazado**.
- **Color tomado** a la vista y **paleta de colores** del proyecto.
- Al tirar de una esquina, las formas crecen **sin deformarse** (con Mayúsculas, sí se deforman).
- **Desenfoque**: normal, de movimiento y radial.

## 1.29 — 2026-11-24
- **Iconos** en las herramientas.
- **Texto que sigue una línea**: sobre un trazado, una forma o un círculo, con «Darle la vuelta» para la parte de abajo.

## 1.28 — 2026-11-24
- **Unir y restar formas**: unir, restar, solo lo que se cruza, quitar lo que se cruza. Sirve para hacer el agujero de un llavero o unir un texto a su marco.
- «Convertir en forma» para textos (letras unidas) e imágenes (su silueta).

## Antes (V8 a V27, noviembre de 2026)
- **V8–V13**: Vectorizador Láser: modos de grabado, corte, silueta, líneas, capas, ilustración, plantillas de estarcido, mapa de relieve para la eufyMake, «Quitar fondo» y el primer editor de capas.
- **V14–V18**: nombre Krafsti Studio. Formas, pluma, selecciones, SVG directo desde Componer, unidades, reglas, guías e imanes.
- **V19–V22**: guardar proyectos y copia automática; aspecto de aplicación; lienzo circular y textos alrededor del círculo.
- **V23–V27**: varias capas, varita, borde y color de la capa, tomar color, pluma como «pad», ajustes de imagen, trazados, sombras y botón Nuevo.
