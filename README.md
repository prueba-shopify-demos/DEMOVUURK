# DEMOVUURK

Theme Shopify de la tienda oficial VUURK (gummies energéticas), tienda de producto único sobre **Shopify Basic** con el theme **Savor**.

Dirección del proyecto: eQuantum Consulting.

## Base

- Theme: Savor 4.3.0 (Shopify), código original exportado desde el admin de Shopify.
- Rama de trabajo: `main`.
- Shopify gestiona catálogo, carrito, checkout, pagos y pedidos. Este repositorio contiene solo el theme; no hay storefront externo.

## Estructura

| Carpeta | Contenido |
| --- | --- |
| `assets/` | JavaScript, CSS e iconos SVG del theme |
| `blocks/` | Bloques de theme reutilizables |
| `config/` | `settings_schema.json` y `settings_data.json` |
| `layout/` | `theme.liquid` y `password.liquid` |
| `locales/` | Traducciones del storefront y del editor |
| `sections/` | Secciones y grupos de secciones (header y footer) |
| `snippets/` | Fragmentos Liquid compartidos |
| `templates/` | Plantillas JSON de cada tipo de página |

## Home VUURK (E02-C3)

La Home es una landing de producto único construida con secciones propias en Liquid (`sections/vuurk-*.liquid`), sobre Savor 4.3.0. Header y footer siguen siendo los de Savor.

| Orden | Sección | Función |
| --- | --- | --- |
| 1 | `vuurk-hero` | Portada con el doypack recortado, titular y botón Comprar VUURK |
| 2 | `vuurk-intro` | Presentación del producto y datos visibles en el envase |
| 3 | `vuurk-energy-focus` | Bloque Energía + Enfoque |
| 4 | `vuurk-features` | Características verificadas |
| 5 | `vuurk-pack-viewer` | Vistas frontal, 3/4 y lateral; visor 3D nativo si el producto tiene un GLB |
| 6 | `vuurk-moments` | Situaciones de uso |
| 7 | `vuurk-usage-info` | Información de consumo (solo datos confirmados) |
| 8 | `vuurk-buy` | Compra conectada al producto de Shopify: precio, inventario, cantidad, carrito y checkout |
| 9 | `vuurk-faq` | Preguntas frecuentes |

Estilos y comportamiento compartidos: `assets/vuurk-landing.css` y `assets/vuurk-landing.js`. Los renders del envase (fondo transparente) están en `assets/vuurk-pack-*.webp` y se usan cuando no se elige otra imagen en el editor.

Para activar la compra hay que seleccionar el producto VUURK en las secciones Hero, Compra y Envase 3D. Sin producto seleccionado no se muestra ningún precio.

## Conexión con Shopify

La conexión se hace desde el admin de Shopify (Tienda online → Temas → Agregar tema → Conectar desde GitHub), eligiendo este repositorio y la rama `main`. Shopify la añade como un theme **no publicado** en la biblioteca. No publicar ni sustituir el theme activo sin aprobación.

Los cambios hechos en el editor de temas sobre el theme conectado se guardan como commits en `main`.

## Reglas

- No incluir credenciales, tokens ni datos privados.
- No inventar precios, ingredientes, claims ni información técnica del producto.
- No modificar el logo ni el packaging original de VUURK.
- Cada etapa (E01–E09) requiere aprobación antes de avanzar.
