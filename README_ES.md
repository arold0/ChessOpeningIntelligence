# ♟️ Chess Opening Intelligence

> 🇬🇧 [Read in English](README.md)

> **¿Qué apertura de ajedrez realmente te da mejores resultados para tu nivel?**

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-green.svg)](LICENSE)
[![DuckDB](https://img.shields.io/badge/DuckDB-motor_analítico-yellow.svg)](https://duckdb.org)

---

## El Problema

Todas las plataformas de ajedrez muestran tasas de victoria por apertura.
El problema es que esos números mienten. Si un jugador de 1500 de Elo gana contra un oponente de 1100 con el Sistema Londres, esa "victoria" infla artificialmente la tasa de éxito del Londres en el rango de 1500. Las tasas brutas no tienen en cuenta *contra quién* ganas ni *qué tan difíciles* son las posiciones resultantes.

Este proyecto corrige eso.

---

## La Métrica: Opening Intelligence Index (OII)

El **OII** es una métrica compuesta que responde: *"Para mi nivel de Elo, ¿qué aperturas me dan el mejor retorno de inversión?"*

Ajusta tres sesgos que las tasas brutas de victoria ignoran:

| Componente | Qué captura |
|------------|-------------|
| **Adjusted Score Rate (ASR)** | Tu rendimiento real menos lo que la fórmula de Elo *espera* que scores. Elimina la ventaja de jugar contra oponentes más débiles. |
| **Tactical Complexity (TC)** | Dificultad mediana de los puzzles que surgen de esa apertura. Una apertura "segura" que evita la táctica se pondera diferente a una Siciliana aguda. |
| **Tamaño de muestra** | Escala logarítmica para que aperturas con 50 partidas no se posicionen por encima de aperturas con 50.000. |

**Fórmula:** `OII = ASR / Normalizado(TC) × log₁₀(cantidad_partidas)`

### Ejemplo

| Apertura | Tasa de Victoria (1200–1400) | ASR | OII |
|----------|------------------------------|-----|-----|
| Sistema Londres | 58% | +0.02 | 0.31 |
| Italiana | 54% | +0.08 | 0.87 |

El Londres *parece* mejor por tasa bruta. Pero al eliminar la ventaja de Elo y considerar la complejidad táctica, la Italiana entrega casi **3 veces más retorno** en el rango 1200–1400.

> **Nota:** Los valores del ejemplo son ilustrativos. Los números reales se publicarán cuando el pipeline de análisis complete el procesamiento de 12 meses de datos de Lichess.

---

## La Zona de Error (Blunder Zone)

Para cada apertura y rango de Elo, calculamos el **número de jugada mediano donde ocurre el primer error grave** (pérdida de centipeones > 200).

Esto te dice *cuándo* pierdes el control de la partida — y si ciertas aperturas te ayudan a mantenerte sólido durante más jugadas que otras.

---

## Arquitectura

Pipeline de extremo a extremo que procesa **más de 1.000 millones de partidas** en una sola máquina.

```
[Lichess .zst Dumps]     [Puzzle CSV]
        │                      │
        ▼                      ▼
   L1 · Ingestión ───────────────────► data/raw/ (parquet)
        │
        ▼
   L2 · Limpieza ───────────────────► data/clean/ (parquet particionado)
        │
        ▼
   L3 · Carga ──────────────────────► DuckDB (tablas analíticas)
        │
        ▼
   L4 · Análisis ───────────────────► Vistas + OII + Zona de Error
        │
        ├──► Dashboard Streamlit (alojado, público)
        └──► Reportes Power BI (local, análisis profundo)
```

---

## Stack Tecnológico

| Herramienta | Rol | Por qué |
|-------------|-----|---------|
| **Python 3.11** | Orquestación del pipeline | Streaming de PGN con `python-chess` y `zstandard` |
| **Polars** | Transformación de datos | API Lazy maneja 1B+ filas con < 4GB RAM |
| **DuckDB** | Motor SQL analítico | Ejecuta analítica compleja localmente sin servidor |
| **SQL** | Lógica de negocio | Todas las métricas calculadas en CTEs y vistas |
| **Streamlit** | Dashboard público | Visualización interactiva alojada |
| **Power BI** | Reportes de análisis profundo | Análisis interactivo multi-página con filtros |

---

## Hallazgos Clave

> 🚧 *Los resultados se publicarán cuando el pipeline de análisis se ejecute sobre el dataset completo de Lichess.*

---

## Inicio Rápido

```bash
# 1. Clonar el repositorio
git clone https://github.com/arold0/ChessOpeningIntelligence.git
cd ChessOpeningIntelligence

# 2. Instalar dependencias
pip install -e ".[dev]"

# 3. Ejecutar el pipeline de puzzles
python pipeline/02_ingest_puzzles.py

# 4. Ejecutar el pipeline de partidas
python pipeline/01_ingest_games.py
```

Para ver todos los comandos de desarrollo disponibles, ejecuta `make help`.

---

## Fuentes de Datos

| Fuente | Formato | Licencia |
|--------|---------|----------|
| [Lichess Game Database](https://database.lichess.org) | PGN `.zst` (12 meses) | CC0 |
| [Lichess Puzzles](https://database.lichess.org/#puzzles) | CSV (5.88M puzzles) | CC0 |

---

## Estructura del Proyecto

```
chess-opening-intelligence/
├── data/
│   ├── source/       ← descargas .zst (git-ignored)
│   ├── raw/          ← Salida L1: parquet crudo
│   ├── clean/        ← Salida L2: parquet particionado
│   └── sample/       ← 10K filas para desarrollo/testing
├── pipeline/         ← Ingestión y transformación en Python
├── sql/              ← DDL, macros, vistas y métricas OII
├── notebooks/        ← EDA y validación del OII
├── dashboard/        ← App Streamlit + reportes Power BI
└── tests/            ← Tests unitarios, integración y SQL
```

---

## Estado del Proyecto

- [x] Diseño y documentación del proyecto
- [x] Infraestructura del pipeline (config, logging, validadores)
- [x] Fundación SQL (schema, macros, vistas, fórmula OII)
- [x] Infraestructura de tests (unitarios, integración, SQL)
- [ ] Pipeline de puzzles (L1–L3)
- [ ] Pipeline de partidas (L1–L3)
- [ ] Notebooks (EDA + validación OII)
- [ ] Dashboard Streamlit
- [ ] Reportes Power BI
- [ ] Análisis completo sobre dataset de 12 meses

---

## Contribuir y Enlaces

- 📖 [Guía de Contribución](CONTRIBUTING.md) — estrategia de ramas, estilo de código, cómo ejecutar tests
- 📄 [Licencia (MIT)](LICENSE)
- 🗂️ [Documentación SQL](sql/README.md) — schema, macros, vistas, orden de ejecución

---

*Construido por [Aroldo](https://github.com/arold0).*
