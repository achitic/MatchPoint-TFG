# Comparativa Fatiga v1 - 2026-04-29

## Objetivo
Medir la diferencia entre el comportamiento anterior del motor de simulacion y la nueva capa `fatigue_v1`, usando la misma configuracion y las mismas seeds.

## Metodo
- Script: `scripts/compare_fatigue_effect.py`
- Motor usado: `matchpoint.sim_engine.simulate_match`
- Comparativa:
  - `enable_fatigue=False` como baseline anterior.
  - `enable_fatigue=True` como comportamiento nuevo.
- Configuracion:
  - `p_serve_a = 0.62`
  - `p_serve_b = 0.60`
  - `best_of = 5`
  - `first_server = "A"`
  - `timeline_mode = "points"`
  - seeds `100..129` (`30` partidos)

## Resultado agregado
- Ganador distinto: `8/30` partidos.
- Marcador de sets distinto: `27/30` partidos.
- Delta medio de puntos totales: `-14.43`.
- Delta medio de probabilidad efectiva de saque: `-1.33%`.
- Fatiga maxima media alcanzada: `93.79%`.
- Delta medio de puntos clave: `-1.10`.

## Ejemplo concreto: seed 100

| Metrica | Sin fatiga | Con fatiga |
|---|---:|---:|
| Ganador | A | B |
| Sets | 4-6 6-4 7-6 6-4 | 4-6 4-6 4-6 |
| Puntos totales | 302 | 215 |
| P saque efectiva media | 61.41% | 60.33% |
| P saque efectiva minima | 60.00% | 57.99% |
| Fatiga maxima | 0.00% | 80.60% |
| Puntos clave | 97 | 76 |

## Interpretacion
- La fatiga no es solo un campo decorativo: cambia trayectorias de partido con la misma seed porque reduce `p_server_eff` a medida que avanza el encuentro.
- El efecto medio sobre `p_server_eff` es suave (`-1.33%`), pero acumulado punto a punto puede cambiar marcadores y ganadores.
- En partidos largos la fatiga llega cerca del maximo configurado, por eso aparece una diferencia clara en el tramo final.
- La comparativa es determinista y repetible con el script indicado.

## Validacion automatizada
- `tests/test_sim_engine.py` incluye regresiones para:
  - desactivar fatiga y reproducir baseline sin `fatigue_factor`,
  - comprobar que la fatiga aparece en timeline detallado,
  - verificar que una probabilidad efectiva tardia baja frente al baseline comparable.
