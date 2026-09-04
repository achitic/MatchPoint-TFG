# MatchPoint

Trabajo de Fin de Grado para predecir partidos de tenis ATP y simular partidos
y torneos a partir de datos históricos. La API está desarrollada con FastAPI y
la interfaz con React, TypeScript y Vite.

La aplicación utiliza cuatro modelos:

- `baseline_logreg`
- `surface_logreg`
- `calibrated_logreg`
- `stacking_ensemble`

Los modelos serializados y los datos necesarios para la demostración se
incluyen en `models/` y `data/processed/`.

## Requisitos

- Python 3.13
- Node.js 20 o superior
- npm

Los modelos fueron serializados con **scikit-learn 1.8.0**. Debe utilizarse esa
versión exacta: cargar los `.pkl` con scikit-learn 1.9.0 u otra versión puede
producir incompatibilidades. El lock de Python ya fija la versión correcta.

## Instalación

Desde PowerShell, en la raíz del proyecto:

```powershell
.\bootstrap.ps1
```

El script crea `.venv` con Python 3.13 e instala `requirements-dev.lock`
verificando sus hashes.

Para instalar el frontend:

```powershell
cd frontend
npm ci
```

## Ejecución

Backend, desde la raíz:

```powershell
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Frontend, en otra terminal:

```powershell
cd frontend
npm run dev
```

- Interfaz: <http://localhost:5173>
- API: <http://localhost:8000>
- Documentación de la API: <http://localhost:8000/docs>

También puede iniciarse la aplicación con Docker:

```powershell
docker compose up --build --wait
```

En ese caso, la interfaz queda disponible en <http://localhost>.

## Pruebas

Backend:

```powershell
.venv\Scripts\python.exe -m pytest tests -q
```

Frontend:

```powershell
cd frontend
npm run lint
npm run test:unit
npm run build
```

Pruebas de navegador:

```powershell
$env:MATCHPOINT_PYTHON = (Resolve-Path ..\.venv\Scripts\python.exe).Path
npm run test:e2e
```

## Datos y entrenamiento

El pipeline utiliza partidos ATP masculinos de 2006 a 2024. El orden de
ingesta, limpieza, cálculo Elo, construcción de variables y entrenamiento está
documentado en [`docs/pipeline.md`](docs/pipeline.md).

No deben modificarse manualmente los ficheros de `data/processed/` ni los
artefactos de `models/`. Para regenerarlos se utilizan los scripts de `scripts/`
y las versiones fijadas en los locks.

La validación de la entrega y el protocolo temporal de entrenamiento se recogen
en:

- [`docs/release/TFG_V1_VALIDACION_2026-08-04.md`](docs/release/TFG_V1_VALIDACION_2026-08-04.md)
- [`docs/release/TFG_MODELOS_REENTRENAMIENTO_2026-08-05.md`](docs/release/TFG_MODELOS_REENTRENAMIENTO_2026-08-05.md)

## Licencias y atribución

El código original se distribuye según [`LICENSE`](LICENSE). Los datos ATP
proceden de Jeff Sackmann / Tennis Abstract y están sujetos a CC BY-NC-SA 4.0.
La atribución completa se encuentra en
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
