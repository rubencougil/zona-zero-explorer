# Zona Zero — Archivo Musical

Archivo personal de reseñas de discos, crónicas de conciertos y entrevistas publicadas por **Rubén Cougil Grande** en la webzine [Zona Zero](https://zona-zero.net) (2006–2016) y en [RockZone Magazine](https://www.rockzonemag.com).

---

## Características

- **109+ artículos** — reseñas, crónicas de conciertos y entrevistas
- Búsqueda en tiempo real por artista, disco o contenido
- Filtrado por tipo de contenido
- Portadas de discos y fotos de artistas vía iTunes / Deezer
- Estética de revista musical rock (tema oscuro)
- Web estática, desplegable en GitHub Pages

---

## Desarrollo local

```bash
# 1. Generar datos (portadas incluidas, se cachean en cover_cache.json)
python3 build.py

# 2. Servir localmente
cd public && python3 -m http.server 8000
# → http://localhost:8000
```

---

## Importar artículos desde RockZone Magazine

El script `import_rockzone.py` busca artículos firmados por Rubén Cougil en rockzonemag.com y los convierte a Markdown en `data/`.

```bash
# Ver qué se importaría (sin escribir nada)
python3 import_rockzone.py

# Importar artículos nuevos
python3 import_rockzone.py --save

# Reimportar y sobreescribir los ya existentes
python3 import_rockzone.py --save --force

# Después de importar, regenerar el sitio
python3 build.py
```

El script:
1. Busca en `https://www.rockzonemag.com/?s=ruben+cougil` (paginando si hay más de una página)
2. Solo importa artículos que contengan la firma **RUBÉN COUGIL** en el cuerpo del texto
3. Convierte el HTML a Markdown y guarda en `data/rz_[titulo].md`
4. No sobreescribe archivos existentes a menos que uses `--force`

---

## Estructura

```
zona-zero-explorer/
├── data/                   # Artículos en Markdown (fuente)
│   ├── *.md                # Zona Zero (2006–2016)
│   └── rz_*.md             # RockZone Magazine (importados)
├── public/                 # Web estática generada
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   ├── robots.txt          # Bloquea indexación por buscadores
│   └── data.json           # Generado por build.py
├── build.py                # Genera data.json (con portadas)
├── import_rockzone.py      # Importa artículos de rockzonemag.com
└── cover_cache.json        # Caché de URLs de portadas (iTunes/Deezer)
```

---

## Deploy en GitHub Pages

Cualquier push a `main` lanza automáticamente el deploy vía GitHub Actions.

Para activar GitHub Pages en el repositorio:
1. Ve a **Settings → Pages**
2. En *Source*, selecciona **GitHub Actions**

---

*Por Rubén Cougil Grande · 2006–2026*
