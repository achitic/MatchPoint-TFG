# Guia para regenerar pipeline y reentrenar modelos

Esta guia asume que estas en la raiz del proyecto:

```powershell
cd "C:\Users\ADRIAN\Desktop\TFG Adri\MatchPoint"
```

## 0. Preparacion

Si no tienes dependencias instaladas en el Python que vas a usar:

```powershell
py -3.12 -m pip install -r requirements.txt
```

Comprobacion rapida:

```powershell
py -3.12 -c "import pandas, sklearn, pyarrow; print('OK deps')"
```

## 1. Anadir CSV nuevos

Los CSV anuales que usa el pipeline deben estar en:

```text
data/raw/
```

Ejemplo esperado:

```text
data/raw/atp_matches_2025.csv
data/raw/atp_matches_qual_chall_2025.csv   # opcional si existe
```

Cuando tengas `atp_matches_2025.csv`, actualiza en `scripts/ingest_data.py`:

```python
YEARS = range(2006, 2026)  # 2006-2025
```

Si solo quieres entrenar hasta 2024, dejalo como esta:

```python
YEARS = range(2006, 2025)  # 2006-2024
```

## 2. Regenerar datos procesados

Orden correcto:

```powershell
py -3.12 scripts/ingest_data.py
py -3.12 scripts/clean_data.py
py -3.12 scripts/elo.py
py -3.12 scripts/build_features.py
```

Por que este orden:

- `ingest_data.py` une los CSV crudos en `data/processed/matches.parquet`.
- `clean_data.py` genera `data/processed/matches_clean.parquet`.
- `elo.py` genera `data/processed/elo_history.csv` y `elo_latest.csv`.
- `build_features.py` necesita `matches_clean.parquet` y `elo_history.csv` para crear `features_full.parquet`.

## 3. Validar outputs del pipeline

Ejecuta:

```powershell
py -3.12 -c "import pandas as pd; df=pd.read_parquet('data/processed/matches_clean.parquet'); print(df['year'].min(), df['year'].max(), len(df)); print(df['surface'].value_counts())"
py -3.12 -c "import pandas as pd; df=pd.read_csv('data/processed/elo_history.csv'); print(df.columns.tolist()); print(len(df))"
py -3.12 -c "import pandas as pd; df=pd.read_parquet('data/processed/features_full.parquet'); print(df.shape); print([c for c in df.columns if 'serve' in c or 'dominance' in c or 'blended' in c])"
```

Debes ver:

- Anos hasta 2025 si metiste el CSV 2025.
- `elo_history.csv` con columnas `elo_w_blended_before` y `elo_l_blended_before`.
- `elo_history.csv` con `match_row_id` único y 198.774 filas.
- `features_full.parquet` con:
  - `elo_diff_blended`
  - `elo_p_blended`
  - `w_serve_pct`, `l_serve_pct`
  - `w_bp_save_pct`, `l_bp_save_pct`
  - `w_dominance`, `l_dominance`
  - `serve_pct_diff`, `bp_save_pct_diff`, `dominance_diff`
- El número de filas de `features_full.parquet` debe coincidir exactamente con `matches_clean.parquet`.

## 4. Reentrenar modelos

Entrena primero los modelos core y despues el ensemble:

```powershell
py -3.12 scripts/train_core_model.py
py -3.12 scripts/train_core_elop_model.py
py -3.12 scripts/train_core_calibrated.py
py -3.12 scripts/train_model.py
```

Outputs principales:

```text
models/model_baseline_logreg.pkl
models/model_surface_logreg.pkl
models/model_calibrated_logreg.pkl
models/model_stacking_ensemble.pkl
```

El modelo recomendado por defecto en la app es:

```text
calibrated_logreg
```

## 5. Exportar schema del ensemble

Los scripts core ya guardan sus schemas. Para el stacking:

```powershell
py -3.12 scripts/export_feature_schema.py
```

Schemas esperados:

```text
models/feature_schema_baseline_logreg.json
models/feature_schema_surface_logreg.json
models/feature_schema_calibrated_logreg.json
models/feature_schema_stacking_ensemble.json
```

## 6. Generar informe de metricas

Cuando los modelos esten entrenados:

```powershell
py -3.12 scripts/report_model_metrics.py
```

Genera un Markdown en:

```text
docs/model-metrics-baseline-YYYY-MM-DD.md
```

Ese informe debe incluir:

- Accuracy
- LogLoss
- AUC
- Brier
- ECE@10
- metricas por superficie si hay suficientes datos

## 7. Smoke tests de inferencia

Prueba que el modelo puede construir features y predecir:

```powershell
py -3.12 scripts/smoke_inference.py
```

Tambien puedes probar un partido manual:

```powershell
py -3.12 scripts/predict_match.py --player_a "Carlos Alcaraz" --player_b "Jannik Sinner" --surface Hard --model calibrated_logreg
```

Si falla por nombres, usa nombres exactos del dataset. Para buscarlos:

```powershell
py -3.12 -c "import pandas as pd; df=pd.read_parquet('data/processed/matches_clean.parquet'); names=sorted(set(df['winner_name']).union(df['loser_name'])); print([n for n in names if 'Alcaraz' in n or 'Sinner' in n])"
```

## 8. Comprobaciones de backend

Validacion rapida de imports y app:

```powershell
py -3.12 -m py_compile backend/main.py matchpoint/feature_builder.py matchpoint/predictor.py
```

Si quieres levantar backend:

```powershell
py -3.12 -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

En otra terminal:

```powershell
curl.exe http://127.0.0.1:8000/healthz
```

## 9. Frontend

Desde `frontend/`:

```powershell
cd frontend
npm install
npm run build
npm run dev
```

Vuelve a la raiz si vas a seguir con scripts Python:

```powershell
cd ..
```

## 10. Checklist final

Antes de dar el reentrenamiento por bueno:

```powershell
py -3.12 -m py_compile scripts/ingest_data.py scripts/clean_data.py scripts/elo.py scripts/build_features.py scripts/train_core_model.py scripts/train_core_elop_model.py scripts/train_core_calibrated.py scripts/train_model.py scripts/report_model_metrics.py matchpoint/feature_builder.py
py -3.12 scripts/smoke_inference.py
```

Revisa manualmente:

- `data/processed/matches_summary.csv` llega al ano esperado.
- `data/processed/features_full.parquet` contiene las nuevas features.
- `models/feature_schema_calibrated_logreg.json` tiene `elo_scale: 400.0`.
- `models/feature_schema_calibrated_logreg.json` incluye las features de servicio.
- `models/feature_schema_stacking_ensemble.json` contiene el mismo contrato que `STACKING_FEATURES`.
- `scripts/report_model_metrics.py` genera informe sin errores.
- La app predice con `calibrated_logreg`.

## 11. Orden compacto para reentrenar todo

Usa este bloque cuando ya tengas los CSV colocados y `YEARS` actualizado:

```powershell
py -3.12 scripts/ingest_data.py
py -3.12 scripts/clean_data.py
py -3.12 scripts/elo.py
py -3.12 scripts/build_features.py
py -3.12 scripts/train_core_model.py
py -3.12 scripts/train_core_elop_model.py
py -3.12 scripts/train_core_calibrated.py
py -3.12 scripts/train_model.py
py -3.12 scripts/export_feature_schema.py
py -3.12 scripts/report_model_metrics.py
py -3.12 scripts/smoke_inference.py
```
