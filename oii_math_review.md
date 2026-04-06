# Revisión de la Lógica Matemática — OII

Análisis detallado de la correctitud matemática del Opening Intelligence Index, contrastando `math_logic_notes.md` con el SQL implementado y el schema completo. Realizado antes de procesar ~20M partidas de Lichess.

---

## 0. Estado Actual: v1 implementado, v2 solo documentado

El SQL actual implementa **fórmula v1**. `math_logic_notes.md` describe v2 como "Propuesta Actual" pero aún no está construida. Todo el análisis que sigue diferencia entre lo que ya existe y lo que falta implementar.

---

## 1. Corrección de Jensen — Matemáticamente Válida, No Implementada

### El problema

La función de puntuación esperada de Elo es sigmoide (no lineal):

```
E(Δ) = 1 / (1 + 10^(-Δ/400))
```

La Desigualdad de Jensen establece que para funciones no lineales `f(E[X]) ≠ E[f(X)]`.

El SQL actual (v1) hace:
```sql
-- INCORRECTO bajo Jensen: aplica f sobre el promedio
adjusted_score_rate(SUM(wins), SUM(draws), COUNT(*), AVG(elo_diff)) AS asr
-- = score_rate - expected_score(AVG(Δ))
```

Lo correcto (v2) es:
```
ASR = score_rate - AVG(expected_score(Δ_por_partida))
```

### Magnitud del sesgo

El bias de Jensen se aproxima como:

```
bias ≈ (1/2) × f''(μ) × Var(Δ)
```

donde `f''(x) = (ln10/400)² × E(x)(1−E(x))(1−2E(x))`

- En μ=0 (Elos iguales): `f''(0) = 0` → sesgo casi nulo
- En μ=100 (blancas más fuertes): sesgo ≈ **−0.011** (1 punto porcentual de ASR)

Para aperturas con ASR típicamente entre 0.02 y 0.08, un sesgo de 0.01 puede cambiar el ranking entre aperturas similares.

### Cambio estructural requerido

Implementar la corrección de Jensen **requiere cambiar `v_opening_results`** — no se puede usar el macro `adjusted_score_rate` tal como está. Hay que calcular `expected_score(elo_diff)` por partida antes del GROUP BY:

```sql
-- En el CTE game_sides, añadir:
expected_score(elo_diff) AS expected_score_per_game,

-- En el SELECT final, reemplazar asr por:
score_rate(SUM(is_win), SUM(is_draw), COUNT(*)) - AVG(expected_score_per_game) AS asr
```

---

## 2. Suavizado Bayesiano + Reliability — Doble Contracción No Justificada

### El Bayes es correcto

La fórmula propuesta:
```
score_bayes = (wins + 0.5×draws + prior×0.5) / (games_count + prior)
```
con `prior ≈ 20` es una **Beta-Binomial conjugada** estándar. Representa 20 "partidas fantasma" con resultado 50%. Matemáticamente sólida.

### El problema: doble contracción hacia cero

La fórmula v2 combina Bayes con un factor de reliability:
```
OII_v2 = (score_bayes − expected_per_game) × reliability / tc_norm_clamped
```
donde `reliability = n / (n + 400)`

Esto crea doble contracción para muestras pequeñas:
1. `score_bayes` encoge el score_rate hacia 0.5 (Bayes)
2. `reliability` multiplica el ASR por un factor pequeño

**Ejemplo con n=50, ASR real = 0.10:**
- Después del Bayes: ASR ajustado ≈ 0.072 (encoge 28.6%)
- reliability = 50/(50+400) = 0.111
- OII ≈ 0.072 × 0.111 / TC ≈ **0.008 / TC**

**Ejemplo con n=5000, mismo ASR real:**
- Después del Bayes: ASR ≈ 0.0996 (casi sin cambio)
- reliability = 5000/(5400) = 0.926
- OII ≈ 0.0996 × 0.926 / TC ≈ **0.092 / TC**

La doble penalización no está justificada en el documento. El suavizado bayesiano ya captura la incertidumbre. **Recomendación: elegir uno de los dos mecanismos**, no ambos simultáneamente.

---

## 3. Eliminación del `log₁₀(n)` — Cambio de Paradigma No Documentado

Esta es la discrepancia más importante entre v1 y v2 que los notes no explican:

| Versión | Escala de muestra | Comportamiento |
|---------|-------------------|----------------|
| v1: `× log₁₀(n)` | Crece sin límite con n | OII(1M juegos) >> OII(1K juegos) para mismo ASR |
| v2: `× n/(n+400)` | Converge a 1 asintóticamente | OII estabiliza una vez hay partidas suficientes |

Con 20M partidas, aperturas populares pueden tener 100K+ juegos en un solo bucket:
- `log₁₀(100K) = 5` → v1 multiplica OII por 5 solo por popularidad
- `100K/(100K+400) ≈ 0.996` → v2 prácticamente sin escala extra

v1 confunde popularidad con calidad. v2 lo corrige, pero los valores son **completamente incomparables** entre versiones. Son métricas conceptualmente distintas:
- v1: "apertura buena Y popular = mejor OII"
- v2: "apertura buena con suficientes muestras = OII estable"

---

## 4. Bug en el SQL Actual: Normalización de TC Global en lugar de por Bracket

### El bug (metrics.sql, líneas 30-37)

```sql
WITH tc_stats AS (
    SELECT
        MIN(median_puzzle_rating) AS min_tc,
        MAX(median_puzzle_rating) AS max_tc
    FROM v_puzzle_difficulty
    WHERE median_puzzle_rating IS NOT NULL
),
...
CROSS JOIN tc_stats   -- ← mismo min/max para TODOS los brackets y time_class
```

### Por qué es un problema

El mismo rango [min, max] global se aplica a todos los brackets y clases de tiempo. Una apertura táctica compleja tendrá el mismo TC_norm en el bracket 800-999 que en el 2000-2199, cuando en realidad su complejidad *relativa* varía según el contexto.

### La corrección propuesta en los notes es correcta

Usar p5/p95 por bracket (y time_class) en lugar de min/max global:
```
tc_norm = (tc_raw - p5_bracket) / (p95_bracket - p5_bracket)
```

**Implicación importante no mencionada en los notes:** Al normalizar TC por bracket, el mismo ECO code obtendrá distintos `tc_norm` en distintos brackets. Esto es correcto conceptualmente (la complejidad relativa importa), pero hace los OII de diferentes brackets **inconmensurables por diseño**. Solo se pueden comparar openings dentro del mismo bracket.

**Asimetría del clamping:** La propuesta de `GREATEST(tc_norm, 0.05)` maneja el límite inferior, pero valores sobre 1.0 (openings por encima del p95) no se clampean. Los outliers superiores de TC producirían OII artificialmente bajo. Considerar también `LEAST(tc_norm, 1.0)` o ajustar el rango a [p5, p95].

---

## 5. Bug en `v_blunder_zone`: Solo Perspectiva de Blancas

### El bug (views.sql, líneas 138-143)

```sql
WITH blunder_data AS (
    SELECT
        eco,
        opening_family,
        white_elo_bracket   AS elo_bracket,   -- ← SOLO bracket de las BLANCAS
        first_blunder_move
    FROM v_games_enriched
    WHERE first_blunder_move IS NOT NULL
)
```

La vista siempre usa el bracket de las blancas, incluso para analizar errores que pueden ser de las negras.

### Problema adicional en el schema

`first_blunder_move INTEGER` en la tabla `games` es un único número por partida, sin distinguir qué color cometió el error. Para implementar `Survival_OII` por color (como proponen los notes), se necesita:

1. Rastrear blunders por color separadamente — `moves_summary` tiene `blunder_count` por color, pero no el número de movimiento del primer blunder por color
2. O bien modificar el schema para capturar `first_white_blunder_move` y `first_black_blunder_move`

La fórmula `Survival_OII = OII × (Avg_Moves_to_Blunder / Global_Avg)` no puede implementarse correctamente hasta resolver esto.

---

## 6. Z-Score de Confianza — Correcto con Ambigüedad

### La fórmula propuesta

```
z = (score_bayes − expected_per_game) / sqrt(p × (1−p) / n)
```

Los tiers Gold (z > 1.96) y Silver (z > 1.64) corresponden a p-valores de 0.025 y 0.05 en pruebas unilaterales — correcto estadísticamente.

### La ambigüedad: ¿qué es `p`?

El documento no lo define. La opción correcta es `p = expected_per_game` (hipótesis nula: el opening no aporta ventaja sobre la expectativa Elo):

```
z = (score_bayes − expected_per_game) / sqrt(expected_per_game × (1−expected_per_game) / n)
```

Usar `p = score_bayes` sería circular y reduciría artificialmente el denominador.

### Advertencia crítica con 20M partidas

Con volúmenes grandes, el z-score es trivialmente alto incluso para ASR mínimos:
```
n=50K, ASR=0.01:
z = 0.01 / sqrt(0.5 × 0.5 / 50000) = 0.01 / 0.00224 ≈ 4.5  → Gold tier
```

Prácticamente todas las aperturas populares serán Gold tier. Con este volumen de datos, la significancia estadística no diferencia aperturas — el **tamaño del efecto (ASR)** es la métrica relevante. Considerar umbrales de tier basados en ASR absoluto además del z-score.

---

## 7. Dirección de la Fórmula OII: ¿Penalizar o Premiar Complejidad?

La fórmula `OII = ASR / TC_norm × [escala]` implica que **menor complejidad → mayor OII** para el mismo ASR.

La intuición: "si ganas lo mismo con una apertura simple que con una táctica compleja, la simple es mejor porque es más fácil de jugar."

**Efectos contraintuitivos a tener en cuenta:**
- El Gambito del Rey (TC alta) obtiene OII penalizado vs. la Apertura Inglesa (TC baja) con mismo ASR
- Openings con TC muy baja → TC_norm cerca de 0 → OII hacia infinito sin el clamping a 0.05

El clamping inferior a 0.05 es necesario y correcto. El valor 0.05 es arbitrario — puede necesitar ajuste empírico tras ver la distribución real.

**Alternativa a considerar:** Fórmula aditiva en lugar de divisiva:
```
OII_alt = ASR − λ × TC_norm
```
donde λ es un peso calibrado. Evita el problema de divisiones por valores pequeños y tiene interpretación más directa.

---

## 8. El Proxy de TC (Puzzles) — Limitaciones Estructurales

### Limitación 1: Densidad heterogénea

Códigos ECO raros pueden tener <10 puzzles (mediana de 5 puzzles ≠ mediana de 2000 puzzles estadísticamente). La jerarquía de herencia propuesta en los notes es la solución correcta:
1. TC del par (ECO, bracket) si N_puzzles ≥ 50
2. Promedio global del ECO para todos los brackets
3. Promedio del bracket si persiste bajo volumen

### Limitación 2: Puzzles miden dificultad de resolución táctica, no complejidad de apertura

Un puzzle de la Siciliana puede surgir en el movimiento 25, lejos de la apertura. El rating del puzzle refleja qué difícil es resolver la táctica concreta, no qué complicada es la apertura en sí.

Alternativas más directas para TC a considerar en futuras versiones:
- Varianza del número de movimientos de las partidas (más varianza = más imprevisible)
- Media de centipawn loss en las primeras N jugadas según el motor
- Proporción de posiciones con múltiples respuestas casi equivalentes según análisis

El proxy de puzzles es razonable como primera aproximación, pero debe documentarse como proxy indirecto.

---

## 9. Consideraciones con 20 Millones de Partidas

### Distribución de buckets

Con granularidad `(ECO × color × bracket × time_class)`:
- ~2200 ECO codes × 2 colores × 9 brackets × 4 time classes = **~158K combinaciones posibles**
- Promedio teórico: ~126 partidas por bucket con 20M partidas totales
- Distribución altamente sesgada: Siciliana/e4-e5/d4 dominan masivamente

### Filtros recomendados antes de calcular OII (no documentados en notes)

```sql
WHERE games_count >= 30          -- mínimo estadístico para Beta
  AND eco IS NOT NULL            -- ya presente en el SQL
  AND time_class != 'ultrabullet' -- demasiado ruido para análisis de aperturas
```

### El prior bayesiano de 20 en contexto de 20M partidas

- Para buckets de 50-200 partidas: prior de 20 da ~20-28% shrinkage → razonable
- Para buckets de 10K+ partidas: prior de 20 da <0.2% shrinkage → irrelevante
- El valor 20 funciona bien para los buckets raros, que son la mayoría

---

## 10. Tabla de Diagnóstico Completo

| Aspecto | Estado | Severidad | Acción requerida |
|---------|--------|-----------|-----------------|
| Corrección de Jensen en ASR | Documentado, NO implementado | **Alta** | Cambio estructural en `v_opening_results` |
| TC normalización global vs por bracket | Bug en `metrics.sql` | **Alta** | Reescribir CTE `tc_stats` con ventanas por bracket |
| `v_blunder_zone` usa solo bracket de White | Bug en `views.sql` | **Media** | Refactorizar para capturar perspectiva de ambos colores |
| `first_blunder_move` sin distinción de color | Limitación del schema | **Media** | Añadir `first_white_blunder_move`, `first_black_blunder_move` |
| Doble contracción (Bayes + reliability) | Redundante, no justificado | **Media** | Elegir un mecanismo o documentar justificación |
| `log₁₀(n)` vs `reliability` — cambio de paradigma | Trade-off no documentado | **Media** | Documentar la decisión explícitamente |
| Z-score: `p` no definido en la fórmula | Ambigüedad en notes | **Baja** | Especificar `p = expected_per_game` |
| Z-score trivialmente alto con 20M partidas | Advertencia de interpretación | **Baja** | Considerar umbrales de effect size además |
| TC clamping solo inferior (0.05), no superior | Asimetría no documentada | **Baja** | Evaluar `LEAST(tc_norm, 1.0)` |
| TC proxy (puzzles) como complejidad directa | Limitación parcialmente documentada | **Baja** | Documentar como proxy indirecto |

---

## 11. Orden de Implementación Sugerido

Basado en severidad e impacto en la calidad del OII:

1. **Corregir normalización de TC por bracket** en `metrics.sql` (bug actual con datos reales)
2. **Implementar Jensen** cambiando la estructura de `v_opening_results`
3. **Revisar doble contracción** — elegir Bayes o reliability, no ambos
4. **Corregir `v_blunder_zone`** para capturar perspectiva de ambos colores
5. **Definir `p` en z-score** y ajustar tiers para datasets grandes
6. **Implementar herencia de TC** para ECOs con pocos puzzles
7. Documentar el trade-off v1 (log-scaling) vs v2 (reliability) en `math_logic_notes.md`
