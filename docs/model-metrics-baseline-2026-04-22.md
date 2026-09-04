# Model Metrics Baseline

> **Informe histórico sustituido.** Estas métricas contienen fugas detectadas durante la auditoría final. No deben utilizarse en la memoria. Consulte `model-metrics-baseline-2026-08-05.md`.

- Generated at: `2026-04-22 13:27:40`
- Note: `stacking_ensemble` uses a different temporal split protocol than core models.

| Model | Protocol | N test | LogLoss | AUC | Brier | ECE@10 |
|---|---|---:|---:|---:|---:|---:|
| `baseline_logreg` | core temporal 80/10/10 | 39786 | 0.471194 | 0.885247 | 0.150946 | 0.096367 |
| `surface_logreg` | core temporal 80/10/10 | 39786 | 0.391295 | 0.903438 | 0.125239 | 0.012340 |
| `calibrated_logreg` | core temporal 80/10/10 | 39786 | 0.390734 | 0.903292 | 0.125229 | 0.004557 |
| `stacking_ensemble` | stack temporal by date (<=2021, 2022-2023, >=2024) | 28448 | 0.130178 | 0.992434 | 0.037474 | 0.010315 |
