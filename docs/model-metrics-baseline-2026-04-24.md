# Model Metrics Baseline

> **Informe histórico sustituido.** Estas métricas contienen fugas detectadas durante la auditoría final. No deben utilizarse en la memoria. Consulte `model-metrics-baseline-2026-08-05.md`.

- Generated at: `2026-04-24 12:37:28`
- Note: `stacking_ensemble` uses a different temporal split protocol than core models.

| Model | Protocol | N test | LogLoss | AUC | Brier | ECE@10 |
|---|---|---:|---:|---:|---:|---:|
| `baseline_logreg` | core temporal 80/10/10 | 39786 | 0.471194 | 0.885247 | 0.150946 | 0.096367 |
| `surface_logreg` | core temporal 80/10/10 | 39786 | 0.371667 | 0.914232 | 0.117763 | 0.008273 |
| `calibrated_logreg` | core temporal 80/10/10 | 39786 | 0.371974 | 0.913880 | 0.117880 | 0.006531 |
| `stacking_ensemble` | stack temporal by date (<=2021, 2022-2023, >=2024) | 28448 | 0.130178 | 0.992434 | 0.037474 | 0.010315 |

## Segment Metrics

| Model | Segment | N | LogLoss | AUC | Brier | ECE@10 |
|---|---|---:|---:|---:|---:|---:|
| `baseline_logreg` | top10_vs_top10 | 198 | 0.519023 | 0.857055 | 0.162944 | 0.104804 |
| `baseline_logreg` | surface=Hard | 22087 | 0.468983 | 0.885992 | 0.150023 | 0.095551 |
| `baseline_logreg` | surface=Clay | 16349 | 0.472317 | 0.885795 | 0.151388 | 0.099089 |
| `baseline_logreg` | surface=Grass | 1350 | 0.493757 | 0.866427 | 0.160675 | 0.088346 |
| `surface_logreg` | top10_vs_top10 | 198 | 0.316146 | 0.936537 | 0.093954 | 0.077064 |
| `surface_logreg` | surface=Hard | 22087 | 0.368545 | 0.915653 | 0.116896 | 0.008883 |
| `surface_logreg` | surface=Clay | 16349 | 0.373655 | 0.913446 | 0.118071 | 0.010012 |
| `surface_logreg` | surface=Grass | 1350 | 0.398680 | 0.899628 | 0.128224 | 0.023894 |
| `calibrated_logreg` | top10_vs_top10 | 198 | 0.317810 | 0.934905 | 0.095192 | 0.071817 |
| `calibrated_logreg` | surface=Hard | 22087 | 0.368297 | 0.915305 | 0.116920 | 0.006729 |
| `calibrated_logreg` | surface=Clay | 16349 | 0.374687 | 0.913082 | 0.118326 | 0.006939 |
| `calibrated_logreg` | surface=Grass | 1350 | 0.399277 | 0.899472 | 0.128189 | 0.026701 |
| `stacking_ensemble` | top10_vs_top10 | 132 | 0.243306 | 0.968779 | 0.071101 | 0.046291 |
| `stacking_ensemble` | surface=Hard | 14584 | 0.130073 | 0.992536 | 0.037311 | 0.009261 |
| `stacking_ensemble` | surface=Clay | 12524 | 0.125051 | 0.992982 | 0.035918 | 0.012153 |
| `stacking_ensemble` | surface=Grass | 1340 | 0.179235 | 0.984879 | 0.053785 | 0.024815 |
