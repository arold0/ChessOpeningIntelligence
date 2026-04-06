# Evolución de la Lógica Matemática (OII)

Este documento detalla la transición de la métrica inicial a la versión refinada para asegurar robustez estadística.

---

## Versión 1: Lógica Inicial (Referencia)
*Esta es la lógica básica planteada al inicio del proyecto.*

### 1. Componentes
- **ASR (Adjusted Score Rate):** `Score Rate (Wins + 0.5*Draws / Games) - Expected Score(AVG(Elo Diff))`.
- **TC (Tactical Complexity):** Valor absoluto basado en puzzles sin normalizar por nivel.
- **Sample Size:** Multiplicador logarítmico simple `log10(games_count)`.

### 2. Fórmula OII v1
`OII = ASR / Normalised(TC) * log10(games_count)`

---

## Versión 2: Lógica Refinada (Propuesta Actual)
*Implementación sugerida para corregir sesgos y mejorar la señal/ruido.*

### 1. ASR sin sesgo (Corrección de Jensen)
- **Cálculo:** `expected_per_game = AVG(expected_score(elo_diff))`.
- **Por qué:** Calcula la expectativa partida a partida antes de promediar, respetando la no linealidad de la curva de Elo.

### 2. Suavizado Bayesiano y Fiabilidad
- **Score Bayes:** `(wins + 0.5*draws + prior_strength*0.5) / (games_count + prior_strength)` (con `prior_strength ≈ 20`).
- **Factor de Fiabilidad:** `reliability = games_count / (games_count + k)` (con `k ≈ 400`).

### 3. Normalización de TC por Bracket
- **Cálculo:** `tc_norm = (tc_raw - p5) / (p95 - p5)` calculado individualmente para cada `elo_bracket`.
- **TC Clamped:** `tc_norm_clamped = GREATEST(tc_norm, 0.05)` para evitar divisiones por cero.

### 4. Fórmula OII v2 (Refinada)
`OII = (score_bayes - expected_per_game) * reliability / tc_norm_clamped`

---

## Consideraciones para el Refinamiento Final
*Factores críticos a considerar durante la fase de implementación SQL.*

### 1. El Sesgo del Color (Side-Specific OII)
- **Problema:** El ROI de una apertura es drásticamente diferente para las blancas que para las negras (e.g., Gambito de Rey).
- **Solución:** Calcular el OII tratando cada par `(opening_name, side)` como una entidad única. El dashboard debe permitir filtrar por "Color jugado".

### 2. Segmentación por Ritmo de Juego (Time Class)
- **Problema:** Aperturas complejas (TC alta) tienen ROI positivo en *Classical* pero negativo en *Blitz* debido a la presión de tiempo.
- **Solución:** Incluir `time_class` (Blitz, Rapid, Classical) como una dimensión obligatoria en la partición de los percentiles de TC y en el cálculo del OII.

### 3. Densidad de Datos de Puzzles
- **Problema:** Aperturas raras en ciertos brackets pueden no tener suficientes puzzles para un TC fiable.
- **Solución:** Implementar una jerarquía de "herencia" de TC:
    1. Usar TC del par `(apertura, bracket)`.
    2. Si $N_{puzzles} < 50$, usar el promedio global de la apertura para todos los brackets.
    3. Si persiste el bajo volumen, usar el promedio del bracket.

### 4. Integración de la "Blunder Zone" (Survival ROI)
- **Concepto:** Una apertura no solo es buena por ganar, sino por "mantenerte vivo" más tiempo.
- **Métrica:** `Survival_OII = OII * (Avg_Moves_to_Blunder / Global_Avg_Moves_to_Blunder)`.
- **Uso:** Ayuda a identificar aperturas "sólidas" vs "frágiles" en niveles bajos de Elo.

### 5. Indicadores de Confianza (Z-Score)
- **Z-Score:** `z = (score_bayes - expected_per_game) / sqrt(p*(1-p)/n)`.
- **Tiers:** Gold ($z > 1.96$), Silver ($z > 1.64$), Bronze (Resto).

---

## Comparativa de Decisiones

| Problema | Solución v1 | Solución v2 + Refinamientos | Impacto |
| :--- | :--- | :--- | :--- |
| **Diferencia Elo** | `f(AVG(diff))` | `AVG(f(diff))` | Mayor precisión matemática. |
| **Muestras Pequeñas** | Filtro manual | Suavizado Bayesiano | Menos ruido en el ranking. |
| **TC por Nivel** | Escala Global | Percentiles por Bracket + Time Class | Comparación justa y contextual. |
| **Sesgo Color** | Ignorado | Segmentado por White/Black | ROI real según el bando. |
| **Robustez TC** | Basado en N | Jerarquía de herencia | TC estable incluso en nichos. |

---

## Plan de Implementación
1. Actualizar macros SQL para `expected_score` y `score_bayes`.
2. Modificar la vista `v_opening_intelligence` para incluir percentiles 5/95 por `elo_bracket` y `time_class`.
3. Implementar lógica de herencia de TC para aperturas con pocos datos.
4. Exponer el `z_score`, el `tier_significancia` y la "Blunder Zone" en el Dashboard.
