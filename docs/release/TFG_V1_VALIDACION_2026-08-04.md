# Acta de validación — MatchPoint TFG v1.0

Fecha: 4 de agosto de 2026

## Resultado ejecutivo

La versión de entrega de MatchPoint queda **apta para comenzar la memoria y preparar la defensa**.

- Código y modelos congelados en Git.
- 106 de 106 tests pasan en el entorno de trabajo.
- Los smokes de inferencia, simulación y torneo pasan.
- El frontend supera ESLint, TypeScript y el build de producción.
- Una instalación aislada creada desde Git reproduce los mismos 106 tests y el build.
- Backend y frontend de la copia aislada responden HTTP 200.

## Historial de cierre

| Commit | Propósito |
| --- | --- |
| `40c7844` | Congelación de la versión candidata, incluyendo frontend, backend, documentación, datos procesados y 11 modelos entrenados. |
| `382cacf` | Portabilidad UTF-8 de los smokes, reutilización de `httpx` y pin de scikit-learn 1.8.0. |
| `fe7184c` | Actualización de React Router de 7.13.1 a 7.18.2. |

La etiqueta final `tfg-v1.0.0` se crea después de incorporar esta acta.

## 1. Congelación de versión

Se revisó el árbol de trabajo y se separaron los archivos de producto de las herramientas locales.

Acciones realizadas:

- Se añadieron al repositorio los 11 ficheros `.pkl` necesarios para ejecutar todos los modelos sin reentrenar.
- Se excluyeron `.agents/`, `.codex/`, `.impeccable/`, `skills-lock.json` y cachés temporales.
- Se actualizó el frontend a versión `1.0.0`.
- Se corrigió el README para usar `requirements.txt`, `npm ci` y los comandos reales de verificación.
- Se normalizaron `README.md` y `README_webapp.md` a UTF-8.

## 2. Pruebas sobre el repositorio de trabajo

### Suite Python

Comando:

```powershell
.venv\Scripts\python.exe -m pytest tests -v
```

Resultado:

```text
106 passed in 103.53s
```

Cobertura funcional incluida:

- Health check y catálogos de API.
- Búsqueda, perfil, historial y estadísticas de jugadores.
- Predicción con los cuatro modelos y alias legacy.
- Guardrails de probabilidades para jugadores élite.
- Simulación por juegos y puntos, semillas y reproducibilidad.
- Fatiga, clutch y motor bayesiano live.
- Estado in-play.
- Torneos y Monte Carlo.

### Smokes

| Comando | Resultado |
| --- | --- |
| `.venv\Scripts\python.exe scripts\smoke_inference.py` | PASS: dataset y predicciones de modelos calibrado/superficie. |
| `.venv\Scripts\python.exe scripts\smoke_simulate_api.py` | PASS: 7 comprobaciones de salud, predicción, simulación, semillas y timelines. |
| `.venv\Scripts\python.exe scripts\smoke_tournament_api.py` | PASS: 7 comprobaciones de catálogos, torneo, reproducibilidad y regresión. |

Durante esta fase se corrigieron dos problemas de portabilidad detectados por los propios smokes:

1. La consola CP-1252 de Windows no podía imprimir símbolos Unicode; los scripts configuran ahora `stdout` como UTF-8.
2. El smoke de torneos usaba `requests` sin declararlo; ahora reutiliza `httpx`, ya incluido en el proyecto.

### Frontend

| Comando | Resultado |
| --- | --- |
| `npm run lint` | PASS |
| `npx tsc -b` | PASS |
| `npm run build` | PASS |

Bundle final medido:

- CSS: 117,63 kB; 21,47 kB gzip.
- JavaScript principal: 395,09 kB; 126,02 kB gzip.
- Funcionalidades avanzadas divididas en chunks independientes.

## 3. Instalación limpia

La prueba se realizó desde un ZIP creado con `git archive`, por lo que no contiene `.venv`, `node_modules`, cachés ni el directorio `.git` del entorno original.

- Archivo: `C:\tmp\mpclean-382cacf.zip`
- Copia aislada: `C:\tmp\mpclean-382cacf`
- Tamaño del archivo Git: 245.859.435 bytes.

### Python limpio

Comandos equivalentes al README:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest tests -q
```

Resultado:

```text
Python 3.12.10
scikit-learn 1.8.0
106 passed in 94.92s
```

El pin `scikit-learn==1.8.0` coincide con la versión usada para serializar los modelos y elimina los avisos de incompatibilidad de versión observados inicialmente.

### Node limpio

```powershell
cd frontend
npm ci
npm run lint
npx tsc -b
npm run build
```

Resultado: instalación de 187 paquetes, lint correcto, TypeScript correcto y build correcto.

### Arranque aislado

Para no interferir con los servidores del usuario, se probaron puertos alternativos:

| Servicio | URL de prueba | Resultado |
| --- | --- | --- |
| FastAPI limpio | `http://127.0.0.1:8001/health` | HTTP 200 |
| Vite limpio | `http://127.0.0.1:5174` | HTTP 200 |

Los dos procesos temporales se cerraron después de la comprobación. Los servidores habituales en 8000/5173 no se modificaron.

## Advertencias no bloqueantes

### Modelos serializados

- XGBoost avisa de que el modelo de stacking fue serializado con una versión anterior. La carga y las predicciones están cubiertas por tests y funcionan correctamente.
- Joblib/NumPy emite un aviso de deprecación al restaurar algunos arrays; no altera los resultados actuales.

Para una futura versión posterior a la entrega sería recomendable reentrenar y exportar el booster XGBoost con su formato nativo.

### Dependencias frontend

Se actualizó `react-router-dom` a la última versión estable comprobada, 7.18.2. La auditoría de producción conserva un aviso alto asociado exclusivamente al modo RSC/Server Actions de React Router. MatchPoint es una SPA de Vite y no utiliza RSC, SSR ni Server Actions, por lo que esa ruta vulnerable no está presente en la aplicación. Se documenta la excepción y se recomienda vigilar una corrección upstream posterior.

## Estado final

| Área | Estado |
| --- | --- |
| Congelación Git | PASS |
| Modelos incluidos | PASS |
| Tests Python | PASS — 106/106 |
| Smokes | PASS |
| Frontend estático | PASS |
| Instalación limpia Python | PASS |
| Instalación limpia Node | PASS |
| Arranque aislado | PASS |
| Bloqueos para comenzar la memoria | Ninguno |
