# Krafsti Studio

**Herramienta de diseño para cortadoras láser e impresoras UV, en un solo archivo, gratis y sin internet.**

### ▶ [Abrir Krafsti Studio en el navegador](https://krafsti.github.io/krafsti-studio/)

*Funciona en el navegador, sin instalar nada. Para usarla sin internet, descarga `index.html` (más abajo).*

Hecha en casa por Aaron (Krafsti) con ayuda de Claude, al principio para su papá y su cortadora láser. Ahora la usan los dos para diseñar llaveros, letreros, plantillas, grabados y piezas para la impresora UV eufyMake.

> *English:* Krafsti Studio is a free, offline, single-file design tool for laser cutters (LightBurn, LaserGRBL, xTool) and UV printers. It traces images to SVG, removes backgrounds, and has a small layer editor with text, shapes, a pen tool, boolean operations and text on a path. The interface is in Spanish. Free for non-commercial use; anything you make with it is yours to sell (see [LICENSE.md](LICENSE.md)).

## Cómo se usa

1. **En línea:** ábrela en **[krafsti.github.io/krafsti-studio](https://krafsti.github.io/krafsti-studio/)**.
   **Sin internet:** descarga **[`index.html`](index.html)** (botón «Download raw file») y ábrelo con doble clic.
2. Mejor en **Chrome** o **Edge**: con ellos se puede guardar el proyecto en una carpeta.
3. Pulsa **Guía**, arriba, y elige lo que quieres hacer: la guía te lleva paso a paso y señala cada botón.

No hay que instalar nada. El archivo descargado funciona sin internet: las fuentes y todo lo demás van dentro.

## Qué hace

- **Vectorizar**: pasa un dibujo, logo o foto a SVG para la láser, con medidas reales en milímetros. Tiene modos de grabado, corte, silueta, líneas, capas de madera, ilustración (hasta 24 tonos), plantillas de estarcido y mapa de relieve para la eufyMake.
- **Retocar**: quita el fondo de una foto o borra manchas, con varita, pincel y retoque del borde.
- **Componer**: un pequeño editor de capas.
  - Textos con 21 fuentes, en arco, alrededor de un círculo o siguiendo una línea.
  - Formas, pluma con curvas y trazados guardados.
  - Selecciones y varita.
  - **Unir y restar formas**, para contornos limpios.
  - Sombras, desenfoque, ajustes de color y niveles, paleta del proyecto.
  - Lienzo circular para llaveros, reglas, guías e imanes.
  - Guarda el proyecto y exporta PNG, JPG o SVG, este último «como se ve» o «solo contornos» para cortar.
- **Convertir formato**: de SVG a PNG o JPG.

## Licencia

**Gratis para usar, copiar, cambiar y compartir sin fines comerciales.** No se puede vender la herramienta ni cobrar por ella. **Lo que hagas con ella es tuyo**: las piezas y diseños que hagas los puedes vender. Los detalles están en [LICENSE.md](LICENSE.md): PolyForm Noncommercial 1.0.0 con un permiso adicional para lo que fabriques.

Las fuentes y las librerías que lleva dentro tienen sus propias licencias: [AVISOS-TERCEROS.md](AVISOS-TERCEROS.md).

## Novedades

Las versiones y sus cambios están en [NOVEDADES.md](NOVEDADES.md).

## Para quien quiera tocar el código

- Todo está en `index.html`: un solo archivo con los estilos, la página y el código. Al principio del archivo hay un comentario que explica sus partes.
- **Pruebas automáticas**: `pruebas/pruebas_krafsti.py` comprueba en Chrome lo importante de la herramienta (unas 40 cosas), sin internet.

  ```
  pip install playwright
  playwright install chromium
  python3 pruebas/pruebas_krafsti.py index.html
  ```

  Tiene que terminar con «… bien, 0 mal».
