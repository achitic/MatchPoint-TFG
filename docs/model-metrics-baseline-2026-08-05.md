# Model Metrics Baseline

- Generated at: `2026-08-05 10:22:33`
- Protocol: train through 2021, validation/calibration in 2022-2023 and final test in 2024.
- The stacking base learners use train only; its prefitted meta-learner uses validation only.

| Model | Protocol | N test | Accuracy | LogLoss | AUC | Brier | ECE@10 |
|---|---|---:|---:|---:|---:|---:|---:|
| `baseline_logreg` | temporal: train<=2021, val=2022-2023, test=2024 | 28404 | 0.620370 | 0.643669 | 0.674558 | 0.226506 | 0.019754 |
| `surface_logreg` | temporal: train<=2021, val=2022-2023, test=2024 | 28404 | 0.628221 | 0.639429 | 0.681980 | 0.224535 | 0.013294 |
| `calibrated_logreg` | temporal: train<=2021, val=2022-2023, test=2024 | 28404 | 0.634805 | 0.635228 | 0.688184 | 0.222689 | 0.003557 |
| `stacking_ensemble` | stack temporal by date (<=2021, 2022-2023, >=2024) | 28404 | 0.648676 | 0.619140 | 0.711211 | 0.215644 | 0.016191 |

## Segment Metrics

| Model | Segment | N | Accuracy | LogLoss | AUC | Brier | ECE@10 |
|---|---|---:|---:|---:|---:|---:|---:|
| `baseline_logreg` | top10_vs_top10 | 128 | 0.640625 | 0.636255 | 0.694092 | 0.221920 | 0.067873 |
| `baseline_logreg` | surface=Hard | 14564 | 0.630047 | 0.636173 | 0.686581 | 0.223125 | 0.017822 |
| `baseline_logreg` | surface=Clay | 12500 | 0.608240 | 0.652819 | 0.658890 | 0.230640 | 0.020693 |
| `baseline_logreg` | surface=Grass | 1340 | 0.628358 | 0.639796 | 0.684903 | 0.224693 | 0.033814 |
| `baseline_logreg` | circuit=ATP_main | 8180 | 0.641320 | 0.621946 | 0.708148 | 0.216897 | 0.028595 |
| `baseline_logreg` | circuit=Challenger | 19704 | 0.610942 | 0.653125 | 0.659252 | 0.230687 | 0.015717 |
| `surface_logreg` | top10_vs_top10 | 128 | 0.656250 | 0.632976 | 0.698242 | 0.220790 | 0.070478 |
| `surface_logreg` | surface=Hard | 14564 | 0.633137 | 0.633846 | 0.690443 | 0.222113 | 0.017333 |
| `surface_logreg` | surface=Clay | 12500 | 0.623120 | 0.646958 | 0.670647 | 0.227799 | 0.010487 |
| `surface_logreg` | surface=Grass | 1340 | 0.622388 | 0.629887 | 0.694210 | 0.220404 | 0.031822 |
| `surface_logreg` | circuit=ATP_main | 8180 | 0.649144 | 0.616536 | 0.715530 | 0.214568 | 0.022816 |
| `surface_logreg` | circuit=Challenger | 19704 | 0.619316 | 0.649204 | 0.667014 | 0.228808 | 0.008815 |
| `calibrated_logreg` | top10_vs_top10 | 128 | 0.664062 | 0.622233 | 0.707886 | 0.217176 | 0.050969 |
| `calibrated_logreg` | surface=Hard | 14564 | 0.640140 | 0.628738 | 0.697138 | 0.219919 | 0.007498 |
| `calibrated_logreg` | surface=Clay | 12500 | 0.629920 | 0.642932 | 0.678201 | 0.225930 | 0.008659 |
| `calibrated_logreg` | surface=Grass | 1340 | 0.622388 | 0.633893 | 0.684005 | 0.222553 | 0.029780 |
| `calibrated_logreg` | circuit=ATP_main | 8180 | 0.652200 | 0.614545 | 0.716335 | 0.213821 | 0.014961 |
| `calibrated_logreg` | circuit=Challenger | 19704 | 0.627182 | 0.644311 | 0.675897 | 0.226560 | 0.006390 |
| `stacking_ensemble` | top10_vs_top10 | 128 | 0.664062 | 0.610162 | 0.732422 | 0.210395 | 0.056644 |
| `stacking_ensemble` | surface=Hard | 14564 | 0.649753 | 0.618788 | 0.712581 | 0.215427 | 0.019126 |
| `stacking_ensemble` | surface=Clay | 12500 | 0.648560 | 0.619478 | 0.709997 | 0.215840 | 0.011943 |
| `stacking_ensemble` | surface=Grass | 1340 | 0.638060 | 0.619820 | 0.708305 | 0.216177 | 0.041669 |
| `stacking_ensemble` | circuit=ATP_main | 8180 | 0.656357 | 0.607845 | 0.725938 | 0.210819 | 0.031767 |
| `stacking_ensemble` | circuit=Challenger | 19704 | 0.644691 | 0.624326 | 0.704363 | 0.217873 | 0.014559 |
