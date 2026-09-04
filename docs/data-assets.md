# Datos y artefactos externos

## Alcance del repositorio

MatchPoint usa exclusivamente partidos **ATP masculinos de 2006 a 2024**. El
runtime necesita `data/processed/` y `models/`; el pipeline parte de los CSV
seleccionados en `data/raw/`. Las copias completas de repositorios de terceros
en `data/ATP/` y `data/WTA/` no forman parte de la distribución del código.

Esta separación evita duplicar más de 1 GB de fuentes históricas y deja claro
que WTA, Match Charting y Slam Point-by-Point no intervienen en los modelos de
esta versión.

## Procedencia y licencia

Los datos operativos proceden de
[Jeff Sackmann / Tennis Abstract](https://github.com/JeffSackmann/tennis_atp)
y están sujetos a CC BY-NC-SA 4.0: atribución obligatoria, uso no comercial y
compartición de derivados bajo la misma licencia. Consulta
[`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) antes de redistribuirlos.

## Regenerar la entrada

En una carpeta de trabajo fuera del repositorio:

```powershell
git clone --depth 1 https://github.com/JeffSackmann/tennis_atp.git
Copy-Item tennis_atp\atp_matches_*.csv <ruta-matchpoint>\data\raw\
```

Para reproducir exactamente esta entrega deben conservarse los años 2006–2024
y los nombres esperados por `scripts/ingest_data.py`. Después se ejecuta el
pipeline descrito en [`pipeline.md`](pipeline.md). La descarga más reciente
puede cambiar respecto a la instantánea usada en el TFG; registre fecha y commit
de origen si vuelve a entrenar los modelos.

## Política de Git

- `data/ATP/` y `data/WTA/`: fuentes completas ignoradas; descargar bajo demanda.
- `data/raw/`: instantánea de entrada seleccionada para reproducibilidad.
- `data/processed/`: derivados necesarios para evaluación y runtime.
- `models/`: modelos serializados; deben cargarse con la versión fijada de
  scikit-learn (`1.8.0`).
