# Modelos predictivos de MatchPoint

Resultados finales del reentrenamiento del 5 de agosto de 2026. Todos los valores proceden de un test temporal formado exclusivamente por 14.202 partidos de 2024, representados en 28.404 vistas simétricas A/B.

## Comparación final

| ID interno | Nombre público | Accuracy | Log-loss | AUC | Brier | ECE@10 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `baseline_logreg` | Modelo base ELO | 0,6204 | 0,6437 | 0,6746 | 0,2265 | 0,0198 |
| `surface_logreg` | Modelo especializado por superficie | 0,6282 | 0,6394 | 0,6820 | 0,2245 | 0,0133 |
| `calibrated_logreg` | Modelo probabilístico calibrado | 0,6348 | 0,6352 | 0,6882 | 0,2227 | **0,0036** |
| `stacking_ensemble` | Ensemble avanzado | **0,6487** | **0,6191** | **0,7112** | **0,2156** | 0,0162 |

El detalle por superficie y circuito se conserva en [`model-metrics-baseline-2026-08-05.md`](model-metrics-baseline-2026-08-05.md).

## Protocolo común

- Entrenamiento: partidos hasta el 31 de diciembre de 2021.
- Validación y calibración: 2022–2023.
- Test final: 2024.
- Las dos orientaciones de un partido permanecen en la misma partición.
- Las características utilizan únicamente información anterior al partido.
- Los hiperparámetros y candidatos no se seleccionan con el test.

## Modelo base ELO

Regresión logística con una única variable: la probabilidad derivada del ELO global. Actúa como referencia mínima interpretable para cuantificar la mejora de modelos posteriores.

## Modelo especializado por superficie

Regresión logística que combina probabilidades procedentes del ELO global, el ELO específico de Hard/Clay/Grass y un ELO blended 50/50. Mejora todas las métricas globales del baseline y permite medir el valor añadido del contexto de superficie.

## Modelo probabilístico calibrado

Regresión logística con variables históricas de ELO, forma, H2H, descanso, servicio y edad. La base se entrena hasta 2021 y sus probabilidades se calibran de forma isotónica con 2022–2023.

Es el modelo recomendado en la aplicación porque su ECE@10 de 0,0036 indica que las probabilidades globales predichas se corresponden muy bien con las frecuencias observadas. Mantiene además explicabilidad mediante contribuciones de la regresión logística.

## Ensemble avanzado

Stacking de los dos mejores candidatos de validación —CatBoost y LightGBM— con una regresión logística como meta-modelo. Los modelos base se ajustan solo con entrenamiento y el meta-modelo utiliza exclusivamente validación mediante `cv="prefit"`.

Consigue el mejor rendimiento predictivo general y por circuito, pero se mantiene como alternativa avanzada porque es menos interpretable y su calibración es inferior a la del modelo calibrado.

## Auditoría del resultado antiguo

El informe anterior mostraba un AUC de 0,992 para el stacking. El reentrenamiento identificó dos causas que inflaban la evaluación:

1. Los partidos sin H2H tenían valor neutro `0,5` en la vista original y `0` en la invertida, lo que revelaba artificialmente la clase.
2. La forma `last5` incorporaba el resultado actual antes de tomar la instantánea prepartido.

También se corrigió un merge ELO con claves no únicas que añadía 152 filas duplicadas a las features. Tras eliminar estas fugas, la mayor AUC de una variable individual es 0,682 y el ensemble alcanza un AUC final realista de 0,711.

## Interpretación y limitaciones

- El ensemble es el modelo con mayor discriminación, no el recomendado por defecto.
- El modelo calibrado se elige cuando importa la fiabilidad de la probabilidad comunicada.
- El rendimiento es superior en ATP principal que en Challenger; esto debe mencionarse al interpretar predicciones.
- Top 10 contiene solo 128 vistas en el test, por lo que sus métricas tienen mayor incertidumbre.
- Lesiones, estado psicológico y condiciones meteorológicas no están representados explícitamente.
- Las estadísticas históricas de servicio se regularizan para reducir el impacto de muestras pequeñas y datos ausentes.

## Artefactos

| Archivo | Contenido |
| --- | --- |
| `model_baseline_logreg.pkl` | Modelo base ELO |
| `model_surface_logreg.pkl` | Modelo especializado por superficie |
| `model_calibrated_logreg.pkl` | Modelo probabilístico calibrado |
| `model_stacking_ensemble.pkl` | Ensemble avanzado |
| `feature_schema_<modelo>.json` | Contrato ordenado de inferencia |

Los archivos `match_predictor_*.pkl` y ciertos esquemas duplicados se conservan únicamente como alias de compatibilidad.
