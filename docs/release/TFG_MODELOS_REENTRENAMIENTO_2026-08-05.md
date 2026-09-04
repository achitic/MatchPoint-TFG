# Acta de reentrenamiento y validación final de modelos

Fecha: 5 de agosto de 2026  
Versión de datos: ATP masculino 2006–2024  
Entorno: Python 3.12.10, scikit-learn 1.8.0

## Resultado ejecutivo

El pipeline completo se regeneró y los cuatro modelos se reentrenaron con un test temporal exclusivo de 2024. La auditoría detectó y corrigió tres defectos metodológicos previos: duplicación de filas al unir ELO, inclusión del partido actual en `last5` y codificación asimétrica del H2H sin historial en el stacking.

El AUC antiguo de 0,992 no era válido como resultado final. Tras eliminar las fugas, el ensemble obtiene AUC 0,7112 y el modelo calibrado ECE@10 0,0036. Se mantiene `calibrated_logreg` como opción recomendada por la fiabilidad de sus probabilidades y su explicabilidad; `stacking_ensemble` queda como alternativa de mayor rendimiento predictivo.

## Datos finales

| Comprobación | Resultado |
| --- | ---: |
| Periodo | 2006-01-02 → 2024-12-18 |
| Partidos ingeridos | 201.522 |
| Partidos limpios | 198.774 |
| Filas de features | 198.774 |
| Columnas de features | 80 |
| Jugadores con ELO | 6.502 |
| Duplicados exactos en features | 0 |
| ELO prepartido sin correspondencia | 0 % |
| Features principales con NaN | 0 % |

Distribución del conjunto limpio:

- Hard: 103.948 partidos.
- Clay: 83.456.
- Grass: 11.370.
- Challenger: 116.610.
- ATP/Grand Slam/Masters/Finals: 77.437.
- Copa Davis: 4.727.

## Incidencias detectadas y resolución

### 1. Merge ELO no único

La unión por fecha, superficie, ganador y perdedor no era única en 152 registros. El merge multiplicaba filas y generaba 198.926 ejemplos desde 198.774 partidos.

Solución: `elo.py` genera `match_row_id`; `build_features.py` exige alineación uno-a-uno y valida además fecha, superficie y jugadores. El pipeline aborta ante cualquier discrepancia.

### 2. Fuga en la forma de cinco partidos

`compute_last5` añadía el resultado actual antes de calcular la instantánea, permitiendo que la feature conociera parte de la etiqueta.

Solución: calcular primero la forma prepartido y actualizar el historial después. Se añadió un test de regresión específico.

### 3. H2H asimétrico en el stacking

Los partidos sin enfrentamientos previos tenían `h2h_ratio=0,5` en la vista original, pero terminaban como `0` en la invertida. El modelo podía distinguir la clase por esta codificación.

Solución: utilizar `0,5` como valor neutro en ambas orientaciones. La AUC individual sospechosa del H2H descendió de aproximadamente 0,83 a 0,529. La mayor AUC de una feature aislada pasó a ser 0,682, correspondiente al ELO blended.

### 4. Contrato desactualizado del ensemble

El ensemble se entrenaba con 34 variables y el exportador conservaba 31.

Solución: el exportador importa directamente `STACKING_FEATURES` desde el entrenamiento. El esquema final contiene 34 variables y la inferencia se verificó manualmente.

### 5. Rendimiento de inferencia

Las nuevas estadísticas de servicio provocaban un recorrido Python completo por casi 199.000 partidos en cada predicción, haciendo que la suite superase diez minutos.

Solución: vectorizar los acumulados de servicio. Se comprobó su equivalencia con las features de entrenamiento, con diferencias máximas del orden de `1e-14`. La suite completa volvió a 109,66 segundos.

### 6. Portabilidad de scripts

- `clean_data.py` no podía imprimir símbolos Unicode en CP-1252.
- `predict_match.py` no encontraba el paquete `matchpoint` al ejecutarse directamente.

Ambos problemas se corrigieron y los comandos documentados funcionan en Windows.

## Protocolo experimental

- Train: 2006–2021, 316.282 vistas.
- Validación/calibración: 2022–2023, 52.862 vistas.
- Test: 2024, 28.404 vistas correspondientes a 14.202 partidos.
- Las vistas A/B de un partido comparten partición.
- El test no interviene en ajuste, calibración ni selección.
- En el stacking, CatBoost y LightGBM se ajustan con train; el meta-modelo usa validación con bases prefiteadas.

## Métricas finales

| Modelo | Accuracy | Log-loss | AUC | Brier | ECE@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Modelo base ELO | 0,6204 | 0,6437 | 0,6746 | 0,2265 | 0,0198 |
| Modelo especializado por superficie | 0,6282 | 0,6394 | 0,6820 | 0,2245 | 0,0133 |
| Modelo probabilístico calibrado | 0,6348 | 0,6352 | 0,6882 | 0,2227 | **0,0036** |
| Ensemble avanzado | **0,6487** | **0,6191** | **0,7112** | **0,2156** | 0,0162 |

En ATP principal, el ensemble alcanza AUC 0,7259; en Challenger, 0,7044. El detalle completo está en [`../model-metrics-baseline-2026-08-05.md`](../model-metrics-baseline-2026-08-05.md).

## Selección final

### Recomendado: modelo probabilístico calibrado

Se usa por defecto porque:

- mejora el baseline en todas las métricas;
- presenta la mejor calibración global;
- sus probabilidades son el resultado principal mostrado al usuario;
- conserva una explicación basada en coeficientes;
- es más sencillo de defender académicamente.

### Alternativa: ensemble avanzado

Se conserva para comparación y escenarios donde se prioriza discriminación. Obtiene el mejor accuracy, AUC, log-loss y Brier, pero su ECE es peor y su interpretación es menos directa.

## Validación funcional

| Verificación | Resultado |
| --- | --- |
| Compilación de scripts Python | PASS |
| Tests de protocolo nuevos | PASS — 4/4 |
| Suite pytest completa | PASS — 110/110 en 109,66 s |
| Smoke de inferencia | PASS |
| Smoke de simulación | PASS — 7 comprobaciones |
| Smoke de torneos | PASS — 7 comprobaciones |
| Predicción manual calibrada | PASS |
| Predicción manual ensemble | PASS |
| Frontend ESLint | PASS |
| Frontend TypeScript | PASS |
| Frontend build | PASS — 5,89 s |

Bundle frontend: CSS 117,63 kB, 21,47 kB gzip; JavaScript principal 395,19 kB, 126,07 kB gzip.

## Advertencias no bloqueantes

- Joblib/NumPy emite avisos de deprecación al restaurar algunos arrays; no afecta a los resultados verificados.
- FastAPI TestClient conserva un aviso de deprecación upstream.
- La muestra top 10 del test contiene 128 vistas y debe interpretarse con cautela.
- Los datos terminan en 2024; incorporar 2025 queda como trabajo futuro cuando exista una fuente homogénea.

## Material para la memoria

Este cierre permite documentar una evolución experimental verificable:

1. baseline ELO;
2. incorporación del contexto de superficie;
3. variables históricas y calibración;
4. ensemble avanzado;
5. detección de resultados anómalos;
6. auditoría de fugas;
7. reentrenamiento limpio;
8. selección final basada en rendimiento, calibración e interpretabilidad.
