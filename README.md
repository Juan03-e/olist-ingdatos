# Ingeniería de Datos 2026 · Casos de estudio 1 y 2 · Equipo 6

Bruno Fidalgo y Juan Pablo Esteva. Dataset: [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (CC BY-NC-SA 4.0).

## Cómo reproducir

1. `pip install -r requirements.txt`
2. Descargar el ZIP de Kaggle y descomprimir los 9 CSV en `data/raw/` (no se suben al repositorio).
3. Ejecutar en orden, desde `notebooks/`:
   - `01_avance_olist.ipynb`: exploración y diagnóstico (entrega de avance).
   - `02_curacion_controles.ipynb`: Caso 1 final. Curación, contrato Pandera, perfil antes/después, desafío.
   - `03_enriquecimiento.ipynb`: Caso 2. Parte de `data/curated/` y descarga sola las capas externas en `data/external/`.

En Google Colab:

```
!git clone https://github.com/Juan03-e/olist-ingdatos.git olist-ingdatos
%cd olist-ingdatos/notebooks
!pip install -q -r ../requirements.txt
```

y subir los 9 CSV a `data/raw/`.

## Estructura

| Carpeta | Contenido |
|---|---|
| `data/raw/` | CSV originales de Kaggle, nunca se modifican (ignorados por git) |
| `data/curated/` | `pedidos.parquet` (una fila por pedido) e `items.parquet` (una fila por ítem), salida del Caso 1 |
| `data/external/` | capas del IBGE descargadas por el notebook 03 (ignoradas por git) |
| `data/enriched/` | `pedidos_enriquecidos.gpkg` (capas `pedidos` y `uf`) y `.parquet`, salida del Caso 2 |
| `src/contratos.py` | contratos Pandera y controles de ambos casos |
| `reports/` | informes, perfil antes/después, log de curación, filas afectadas, desafíos, importancia de features y figuras |

## Capas externas

- Límites municipales: https://github.com/tbrugz/geodata-br (`geojson/geojs-100-mun.json`), fuente IBGE.
- Sedes municipales, capitales y regiones: https://github.com/kelvins/municipios-brasileiros (MIT), fuente IBGE.
