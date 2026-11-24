# SEIS ESTRELLAS · Canal de GTA 6

Diez vídeos listos para subir el día de lanzamiento de GTA 6 (**jueves 19 de noviembre de 2026**), con guion, voz en off, gráficos animados, música original, miniatura, subtítulos y metadatos de YouTube.

## Los 10 vídeos

| # | Carpeta | Qué busca la gente | Publicar (hora peninsular) |
|---|---------|--------------------|-------------------|
| 1 | `videos/01-no-me-deja-jugar` | "gta 6 se cierra", "gta 6 no me deja jugar", "gta 6 online" | **Jue 19 · 00:05** (lo antes posible) |
| 2 | `videos/02-cuanto-pesa` | "cuánto pesa gta 6", "gta 6 gb" | Jue 19 · 09:00 |
| 3 | `videos/03-estandar-vs-ultimate` | "gta 6 precio", "ultimate edition vale la pena" | Jue 19 · 11:00 |
| 4 | `videos/04-gta6-pc` | "gta 6 pc", "cuándo sale gta 6 en pc" | Jue 19 · 13:00 |
| 5 | `videos/05-consolas-compatibles` | "gta 6 ps4", "gta 6 series s" | Jue 19 · 15:00 |
| 6 | `videos/06-lucia-y-jason` | "personajes gta 6", "lucía gta 6" | Jue 19 · 17:00 |
| 7 | `videos/07-mapa-leonida` | "mapa gta 6", "leonida" | Vie 20 · 12:00 |
| 8 | `videos/08-ajustes-tv-consola` | "gta 6 mejores ajustes", "hdr ps5" | Vie 20 · 18:00 |
| 9 | `videos/09-cronologia-retrasos` | "gta 6 retraso", "historia de gta 6" | Sáb 21 · 12:00 |
| 10 | `videos/10-historia-de-gta` | "historia de gta", "todos los gta" | Dom 22 · 12:00 |

Sube los 10 el jueves y deja programados del 7 al 10: así el canal publica algo nuevo cada día del primer fin de semana, que es cuando más se busca. Si prefieres publicarlos todos el jueves, también vale.

### Qué hay en cada carpeta

- `video.mp4`: el vídeo final en 1080p a 30 fps, con el audio normalizado a −14 LUFS.
- `miniatura.png`: miniatura de 1280×720.
- `subtitulos.srt`: subtítulos en español para subir a YouTube.
- `metadatos.md`: título, descripción con capítulos, etiquetas, comentario fijado y ajustes de subida, listos para copiar.
- `guion.md`: el guion completo con marcas de tiempo.
- `script.yaml`: la fuente desde la que se genera todo.

En `channel/` están el banner (2560×1440) y el avatar (800×800).

## Checklist de subida (cada vídeo)

1. Sube `video.mp4`, pega el título y la descripción de `metadatos.md`.
2. Pon la miniatura `miniatura.png`.
3. Pega las etiquetas, categoría **Videojuegos**, juego **Grand Theft Auto VI**.
4. Sube `subtitulos.srt` como subtítulos en español.
5. Añade la pantalla final (suscripción + siguiente vídeo) y mételo en la lista "GTA 6 · Guías de lanzamiento".
6. Publica o programa a la hora de la tabla y fija el comentario.

## Cómo se eligieron los temas

Los temas salen de las preguntas que más se repiten en los análisis de búsquedas publicados y en la cobertura de lanzamiento de noviembre de 2026. Por ejemplo, el estudio de Uswitch sobre datos de Google contó 2,17 millones de búsquedas solo de la fecha de salida. También se usaron las listas de "preguntas más frecuentes" de medios de videojuegos. No tuve acceso directo a Google Trends: antes de grabar los siguientes vídeos, revisa allí las consultas en auge del día.

## Datos y fuentes

Cada `metadatos.md` lista sus fuentes, y las cifras clave también aparecen en pantalla con su fuente. Los datos sin confirmación oficial se presentan como reportados o estimados: la hora de la costa oeste de EE. UU., la fecha de PC y los precios de México. **Si Rockstar publica algún cambio antes de subir, edita `script.yaml` y vuelve a renderizar.**

## Notas legales y de monetización

- Todos los gráficos y la música son originales y se generan por código. No se usa material de Rockstar: ni logotipos, ni capturas, ni tráileres, ni el mapa oficial. El mapa del vídeo 7 es una ilustración aproximada y lo indica en pantalla.
- El nombre "GTA 6" se usa solo para describir el contenido. No uses el logotipo oficial en miniaturas ni en el banner.
- La voz es sintética (Kokoro, licencia Apache 2.0). YouTube no exige marcarla como "contenido alterado" porque no imita a una persona real, pero si algún día quieres grabar con tu voz, los guiones están en `guion.md`.

## Volver a generar

```bash
pip install kokoro-onnx soundfile scipy pyyaml pillow numpy
mkdir -p .models && cd .models
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
cd ..
python3 tools/render.py videos/01-hora-de-salida            # un vídeo
python3 tools/render.py videos/01-hora-de-salida --preview  # solo fotogramas de muestra en build/
python3 tools/channel_art.py                                # banner y avatar
```

Puedes cambiar el nombre del canal, la voz y las pronunciaciones en `tools/config.py`.
