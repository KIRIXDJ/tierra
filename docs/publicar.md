# Publicar la demo (URL viva)

La app es **estática**: no necesita servidor propio para mostrarse. Solo el bot de
Telegram corre en un portátil. Estas son las opciones para el jurado, de menos a
más trabajo.

## Publicado: GitHub Pages

**https://kirixdj.github.io/tierra/web/** (activado el 2026-11-13; Pages
reconstruye solo con cada push a `main`). Verificado: app, datos, satélite,
texturas, deck y video responden 200 y la app abre sin errores de JS.

## Cómo se activó (por si hay que repetirlo)

### Opción 1 · GitHub Pages (recomendada)

El repo es público (`KIRIXDJ/tierra`) y las rutas son relativas, así que Pages
sirve la app tal cual:

1. En GitHub → **Settings → Pages**.
2. Source: **Deploy from a branch**.
3. Branch: **main** · carpeta: **/ (root)** · Save.
4. Esperar ~1 minuto y abrir:

   **https://kirixdj.github.io/tierra/web/**

Verificado antes de publicar: serví el repo desde una subruta (`/tierra/web/`)
con la red externa bloqueada y la app cargó sin errores (mapa, satélite, fotos y
texturas locales). Si algo falla en Pages, revisar que la rama sea `main` y la
carpeta raíz.

- **Ventaja:** URL fija para el jurado, funciona en el móvil.
- **Límite:** es la demo; los sensores siguen simulados y el bot vive en tu
  portátil (o en un servidor pequeño).

## Opción 2 · Servidor local (feria)

```bash
cd ~/Documentos/Proyectos/tierra
python3 -m http.server 8080
# http://localhost:8080/web/
```

Es la opción sin depender del wifi del lugar. El bot de Telegram va en otra
terminal:

```bash
python3 tools/bot_elio.py
```

## Opción 3 · Otro hosting estático

Netlify, Vercel o Cloudflare Pages aceptan el repo como sitio estático
(directorio raíz). No hay variables de entorno ni claves: todo lo que la app
necesita está en `datos/`.

## Después de publicar (5 minutos)

- [ ] Abrir la URL en el móvil: el monitor entra completo.
- [ ] Verificar el deck: `/docs/deck/index.html`.
- [ ] Verificar el video: `/docs/demo.mp4`.
- [ ] Abrir **Riesgos**, **Satélite NASA** y la rotación (sin errores).
- [ ] Probar el bot desde el móvil (`/estado`, `/riesgos`).
- [ ] Guardar la URL en el pitch y en el README del repo.

## Lo que no se publica

- `.env` (token del bot y clave de IA): está ignorado por git y nunca va al repo.
- `datos/estado_finca.json`: lo escribe el bot en el portátil; en Pages no existe
  y la app simplemente muestra el modo simulación.
