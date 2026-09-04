# Pipeline de datos y entrenamiento de MatchPoint

Este documento describe el pipeline reproducible utilizado para el cierre experimental del TFG. El conjunto disponible comprende partidos ATP masculinos de 2006 a 2024.

## Orden oficial

```text
data/raw/*.csv
    ↓  1. ingest_data.py
matches.parquet
    ↓  2. clean_data.py
matches_clean.parquet
    ↓  3. elo.py
elo_history.csv + elo_latest.csv
    ↓  4. build_features.py
features_full.parquet
    ↓  5. train_core_*.py + train_model.py
models/*.pkl
    ↓  6. export_feature_schema.py
feature_schema_*.json
    ↓  7. report_model_metrics.py
docs/model-metrics-baseline-YYYY-MM-DD.md
```

`elo.py` debe ejecutarse antes de `build_features.py`. El constructor de features utiliza el histórico ELO prepartido y comprueba una alineación uno-a-uno mediante `match_row_id`; el proceso aborta si fecha, superficie o jugadores no coinciden.

## 1. Ingesta

```powershell
py -3.12 scripts/ingest_data.py
```

Lee `atp_matches_YYYY.csv` y `atp_matches_qual_chall_YYYY.csv` desde `data/raw` para 2006–2024. Normaliza columnas, fechas y superficies, conserva partidos al mejor de tres o cinco sets y genera:

- `data/processed/matches.parquet`;
- `data/processed/matches_summary.csv`.

## 2. Limpieza

```powershell
py -3.12 scripts/clean_data.py
```

Conserva Hard, Clay y Grass; elimina duplicados exactos y niveles no admitidos; valida jugadores y fechas. El resultado final contiene 198.774 partidos:

- Challenger: 116.610;
- ATP: 45.034;
- Grand Slam: 17.813;
- Masters: 14.243;
- Copa Davis: 4.727;
- ATP Finals: 347.

## 3. ELO

```powershell
py -3.12 scripts/elo.py
```

Calcula ELO global, específico por superficie y blended. Utiliza escala 400, factores K por categoría y ajustes acotados por ausencia y retorno. Cada fila conserva los ratings anteriores y posteriores al partido, además de un identificador estable para enlazarla sin duplicaciones.

## 4. Ingeniería de características

```powershell
py -3.12 scripts/build_features.py
```

Genera exclusivamente información disponible antes de cada partido:

- ELO global, por superficie y blended;
- forma en los cinco partidos anteriores;
- forma reciente con decaimiento temporal;
- H2H global y por superficie;
- descanso efectivo;
- estadísticas de servicio con regularización hacia el promedio histórico;
- edad y diferencias direccionales.

La fila actual se incorpora a los acumuladores solo después de tomar la instantánea prepartido. El resultado tiene 198.774 filas y 80 columnas, sin duplicados exactos.

## 5. Entrenamiento

```powershell
py -3.12 scripts/train_core_model.py
py -3.12 scripts/train_core_elop_model.py
py -3.12 scripts/train_core_calibrated.py
py -3.12 scripts/train_model.py
```

Todos los modelos comparten fronteras temporales:

- entrenamiento: 2006–2021;
- validación o calibración: 2022–2023;
- test final: 2024.

Cada partido se representa en las dos orientaciones A/B dentro de la misma partición. El conjunto de test no participa en entrenamiento, calibración ni selección de candidatos.

## 6. Contratos de inferencia

```powershell
py -3.12 scripts/export_feature_schema.py
```

Los esquemas JSON fijan nombres y orden de las variables. El exportador del ensemble importa directamente el contrato del script de entrenamiento para impedir divergencias entre ambos.

## 7. Métricas

```powershell
py -3.12 scripts/report_model_metrics.py
```

El informe incluye accuracy, AUC, log-loss, Brier y ECE@10, tanto globalmente como por superficie, circuito ATP principal, Challenger y top 10 cuando existe muestra suficiente.

## Reproducibilidad

- Python 3.12 y `scikit-learn==1.8.0`.
- Semillas fijas en los algoritmos estocásticos.
- Ordenación estable y fronteras temporales explícitas.
- Esquemas de features versionados junto a los modelos.
- Tests de regresión para particiones, neutralidad H2H y exclusión del resultado actual en `last5`.

La guía operativa completa se encuentra en [`reentrenar-pipeline.md`](reentrenar-pipeline.md).
