# OII Development Plan

Master implementation guide for the Opening Intelligence Index (OII). This document replaces `math_logic_notes.md` and `oii_math_review.md` and is the single source of truth for all OII math and SQL development going forward.

---

## Context

The OII metric identifies optimal chess openings per Elo bracket by correcting raw win rates for Elo advantage and positional complexity. Two formula versions exist:

- **v1 (currently implemented in SQL):** `OII = ASR / Normalised(TC) × log₁₀(games_count)`
  - `ASR = score_rate − expected_score(AVG(elo_diff))`
  - TC normalized globally (single min/max across all brackets)
  - `log₁₀(n)` amplifies OII by sample size — conflates popularity with quality

- **v2 (target):** `OII = (score_bayes − expected_per_game) / tc_norm_clamped`
  - ASR corrected for Jensen inequality (per-game expected score before aggregation)
  - TC normalized per `(elo_bracket, time_class)` using p5/p95 percentiles
  - Bayesian smoothing replaces log-scaling — quality-stabilized, not size-amplified

The v1→v2 paradigm shift means **OII scores are not comparable across versions**. All tasks below must land together before the `opening_stats` table is refreshed for the dashboard.

---

## Current SQL State

| File | Status |
|------|--------|
| `sql/macros.sql` | Correct — `expected_score`, `score_rate`, `adjusted_score_rate`, `elo_bracket`, `confidence_flag` all valid |
| `sql/views.sql:v_opening_results` | **Bug** — Jensen incorrect (`AVG(elo_diff)` instead of `AVG(expected_score_per_game)`) |
| `sql/views.sql:v_blunder_zone` | **Bug** — always uses `white_elo_bracket`, ignores Black perspective |
| `sql/views.sql:v_opening_intelligence` | **Bug** — global TC min/max (duplicate of metrics.sql) |
| `sql/metrics.sql` | **Bug** — global TC min/max; v1 OII formula |
| `sql/schema.sql` | `first_blunder_move` has no color distinction (structural limitation) |

---

## Task 1 — Fix TC Normalization Per Bracket

**Severity:** HIGH — Active bug affecting all OII scores with real data  
**Branch:** `feat/fix-tc-normalization-per-bracket`  
**Files:** `sql/metrics.sql`, `sql/views.sql` (both contain `v_opening_intelligence`)

### Problem

The `tc_stats` CTE uses global `MIN/MAX` across all brackets and time classes. A puzzle rated 1800 is hard for a 1000-Elo player but trivial for a 2000-Elo player — using the same normalization range conflates these contexts. Additionally, there is no upper clamping: ECOs above the p95 get `tc_norm > 1`, producing artificially low OII.

```sql
-- CURRENT (broken): single global range
WITH tc_stats AS (
    SELECT MIN(median_puzzle_rating) AS min_tc,
           MAX(median_puzzle_rating) AS max_tc
    FROM v_puzzle_difficulty
    WHERE median_puzzle_rating IS NOT NULL
)
CROSS JOIN tc_stats   -- same min/max for EVERY bracket and time_class
```

### Required Change

Replace the global `CROSS JOIN tc_stats` with p5/p95 percentiles computed per `(elo_bracket, time_class)`, clamp to `[0.05, 1.0]`:

```sql
-- Step 1: compute tc_raw per ECO by joining puzzle data to opening results
oii_raw AS (
    SELECT
        r.*,
        p.median_puzzle_rating AS tc_raw,
        p.puzzle_count
    FROM v_opening_results r
    LEFT JOIN v_puzzle_difficulty p ON r.eco = p.eco
),

-- Step 2: compute p5/p95 per (elo_bracket, time_class)
tc_percentiles AS (
    SELECT
        elo_bracket,
        time_class,
        PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY tc_raw) AS p5_tc,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY tc_raw) AS p95_tc
    FROM oii_raw
    WHERE tc_raw IS NOT NULL
    GROUP BY elo_bracket, time_class
),

-- Step 3: normalize with double clamping
oii_normalised AS (
    SELECT
        r.*,
        tp.p5_tc,
        tp.p95_tc,
        GREATEST(
            LEAST(
                (r.tc_raw - tp.p5_tc)::DOUBLE / NULLIF(tp.p95_tc - tp.p5_tc, 0),
                1.0
            ),
            0.05
        ) AS tc_normalised
    FROM oii_raw r
    LEFT JOIN tc_percentiles tp
        ON r.elo_bracket = tp.elo_bracket
        AND r.time_class = tp.time_class
)
```

### Tests to Add

- `tests/sql/test_metrics.py::test_tc_normalization_is_per_bracket` — same ECO code must yield different `tc_normalised` values in different brackets
- `tests/sql/test_metrics.py::test_tc_norm_clamped_between_005_and_1` — all non-null `tc_normalised` values must be in `[0.05, 1.0]`
- `tests/sql/test_metrics.py::test_tc_norm_no_global_cross_join` — assert no `CROSS JOIN` to a scalar `tc_stats` (code inspection or verify behavior)
- `tests/sql/test_metrics.py::test_tc_norm_upper_clamp` — inject an ECO with puzzle rating far above p95; assert `tc_normalised = 1.0`

### Acceptance Criteria

- [ ] `tc_normalised` computed per `(elo_bracket, time_class)` using p5/p95
- [ ] Values clamped to `[0.05, 1.0]` — both lower and upper bounds
- [ ] No `CROSS JOIN` to a global scalar `tc_stats`
- [ ] Same logic applied in both `views.sql` and `metrics.sql`
- [ ] All existing SQL tests pass; new tests pass

---

## Task 2 — Jensen Correction in ASR

**Severity:** HIGH — Math incorrectness causing ~0.01 ASR bias in unequal-Elo games  
**Branch:** `feat/jensen-correction-asr`  
**Files:** `sql/views.sql:v_opening_results`

### Problem

The Elo expected score function is a sigmoid (non-linear). Jensen's inequality states that `f(E[x]) ≠ E[f(x)]` for non-linear `f`. The current macro applies the sigmoid to the *average* Elo diff:

```sql
-- CURRENT (biased): applies sigmoid once on the group average
adjusted_score_rate(SUM(is_win), SUM(is_draw), COUNT(*), AVG(elo_diff)) AS asr
-- = score_rate - expected_score(AVG(Δ))   ← wrong for non-linear f
```

The bias approximates to `(1/2) × f''(μ) × Var(Δ)`. At μ=100 (common in tournaments), the bias reaches ~0.011 — enough to shift rankings between similar openings.

### Required Change

Compute `expected_score(elo_diff)` **per game row** in the `game_sides` CTE before the `GROUP BY`, then average those per-game expected scores:

```sql
-- In game_sides CTE (both white and black sections), add:
expected_score(elo_diff) AS expected_score_per_game,

-- In the GROUP BY SELECT, replace the asr line:
-- BEFORE:
adjusted_score_rate(SUM(is_win), SUM(is_draw), COUNT(*), AVG(elo_diff)) AS asr,

-- AFTER:
score_rate(SUM(is_win), SUM(is_draw), COUNT(*))
    - AVG(expected_score_per_game)                                        AS asr,
```

The `adjusted_score_rate` macro is kept in `macros.sql` but marked deprecated with a comment. It is no longer called by `v_opening_results`.

### Tests to Add

- `tests/sql/test_macros.py::test_expected_score_nonlinearity` — with a skewed set of Elo diffs (e.g., [-300, +500]), verify `expected_score(AVG) ≠ AVG(expected_score)` numerically
- `tests/sql/test_views.py::test_asr_uses_per_game_expected_score` — insert games with asymmetric Elo distribution into `tmp_duckdb`, verify `v_opening_results.asr` matches the per-game average formula, not the group-average formula
- `tests/sql/test_views.py::test_asr_unbiased_at_zero_variance` — when all games have equal Elo, both formulas agree; verify no regression

### Acceptance Criteria

- [ ] `expected_score_per_game` column computed per row in `game_sides` CTE
- [ ] `asr = score_rate(wins, draws, n) - AVG(expected_score_per_game)` in GROUP BY
- [ ] `adjusted_score_rate` macro kept in `macros.sql` with `-- DEPRECATED` comment
- [ ] `v_opening_results` no longer references `adjusted_score_rate`
- [ ] All SQL tests pass

---

## Task 3 — Bayesian Score: Remove Double Contraction

**Severity:** MEDIUM — Proposed v2 unjustifiably penalizes small samples twice  
**Branch:** `feat/bayesian-score-oii-v2`  
**Files:** `sql/metrics.sql`, `sql/views.sql:v_opening_intelligence`

### Problem

The proposed v2 formula applies **both** Bayesian shrinkage and a reliability multiplier simultaneously:

```
OII_v2 = (score_bayes − expected_per_game) × reliability / tc_norm_clamped
```

This double-penalizes small samples:
- `score_bayes` already shrinks the score toward 0.5 (captures uncertainty)
- `reliability = n/(n+400)` then multiplies by a small factor again

Example with `n=50, ASR_true=0.10`:
- After Bayes: effective ASR ≈ 0.072 (28.6% shrinkage)
- After reliability: `0.072 × 0.111 ≈ 0.008` — 92% total contraction

This is not mathematically justified. Additionally, the v1 `log₁₀(n)` scaling conflates opening quality with popularity.

### Decision

Use **Bayesian score only** — no `reliability` multiplier, no `log₁₀(n)`. This is the v1→v2 paradigm shift: from size-amplified to quality-stabilized OII.

```sql
-- New macro (add to macros.sql):
CREATE OR REPLACE MACRO score_bayes(wins, draws, total_games, prior_strength) AS
    (wins + 0.5 * draws + prior_strength * 0.5)::DOUBLE
    / (total_games + prior_strength)::DOUBLE;

-- In v_opening_intelligence, replace OII formula:
-- BEFORE (v1):
(asr / tc_normalised) * LOG10(games_count::DOUBLE)  AS oii_score,

-- AFTER (v2):
-- score_bayes uses prior_strength = 20 (≈ 20 phantom games at 50%)
(score_bayes(wins, draws, games_count, 20) - avg_expected_per_game)
    / tc_normalised                                  AS oii_score,
```

Note: `avg_expected_per_game` comes from `v_opening_results.asr` reconstituted, or carried forward as a new column from Task 2.

### Tests to Add

- `tests/sql/test_macros.py::test_score_bayes_shrinks_small_samples` — n=10, score_rate=0.9 → `score_bayes` closer to 0.5 than to 0.9
- `tests/sql/test_macros.py::test_score_bayes_stable_large_samples` — n=5000, score_rate=0.6 → `score_bayes` within 0.5% of score_rate
- `tests/sql/test_metrics.py::test_no_log10_in_oii` — OII formula does not scale with `LOG10`
- `tests/sql/test_metrics.py::test_no_reliability_multiplier` — no column named `reliability` in `v_opening_intelligence` output
- `tests/sql/test_metrics.py::test_oii_v2_formula_correct` — known inputs produce expected OII using Bayes formula

### Acceptance Criteria

- [ ] `score_bayes` macro added to `macros.sql` with `prior_strength` parameter
- [ ] `v_opening_intelligence` exposes `score_bayes` column
- [ ] OII formula is `(score_bayes - expected_per_game) / tc_norm_clamped`
- [ ] No `LOG10` scaling in OII
- [ ] No `reliability` column or multiplier
- [ ] Comment in SQL documents v1→v2 paradigm change explicitly

---

## Task 4 — Fix v_blunder_zone: Color-Aware Perspective

**Severity:** MEDIUM — View always uses White's bracket; blocks Survival OII  
**Branch:** `feat/blunder-zone-color-aware`  
**Files:** `sql/schema.sql`, `sql/views.sql:v_blunder_zone`

### Problem 1 — Wrong Bracket

```sql
-- CURRENT (bug): always uses white_elo_bracket for ALL games
WITH blunder_data AS (
    SELECT
        eco,
        opening_family,
        white_elo_bracket AS elo_bracket,   -- ← wrong for Black's blunders
        first_blunder_move
    FROM v_games_enriched
    WHERE first_blunder_move IS NOT NULL
)
```

### Problem 2 — No Color Attribution in Schema

`games.first_blunder_move INTEGER` stores a single move number per game with no information about which color made the error. The `Survival_OII` formula requires color-specific blunder moves.

### Two-Phase Fix

**Phase 4a — Schema change (`sql/schema.sql`):**
Add two new columns to the `games` table; keep `first_blunder_move` for backwards compatibility:

```sql
first_white_blunder_move    INTEGER,   -- move # of White's first blunder (NULL if none)
first_black_blunder_move    INTEGER,   -- move # of Black's first blunder (NULL if none)
```

**Phase 4b — View refactor (`sql/views.sql:v_blunder_zone`):**

```sql
CREATE OR REPLACE VIEW v_blunder_zone AS
WITH white_blunders AS (
    SELECT
        eco, opening_family,
        'white'               AS color,
        white_elo_bracket     AS elo_bracket,
        first_white_blunder_move AS blunder_move
    FROM v_games_enriched
    WHERE first_white_blunder_move IS NOT NULL
),
black_blunders AS (
    SELECT
        eco, opening_family,
        'black'               AS color,
        black_elo_bracket     AS elo_bracket,
        first_black_blunder_move AS blunder_move
    FROM v_games_enriched
    WHERE first_black_blunder_move IS NOT NULL
),
combined AS (
    SELECT * FROM white_blunders
    UNION ALL
    SELECT * FROM black_blunders
)
SELECT
    eco, opening_family, color, elo_bracket,
    COUNT(*)                                                AS games_with_blunder,
    MEDIAN(blunder_move)                                    AS median_blunder_move,
    AVG(blunder_move)                                       AS avg_blunder_move,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY blunder_move) AS p25_blunder_move,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY blunder_move) AS p75_blunder_move,
    confidence_flag(COUNT(*))                               AS confidence
FROM combined
GROUP BY eco, opening_family, color, elo_bracket;
```

### Tests to Add

- `tests/sql/test_schema.py::test_games_has_color_blunder_columns` — assert `first_white_blunder_move` and `first_black_blunder_move` columns exist in `games` table
- `tests/sql/test_views.py::test_blunder_zone_has_color_column` — result set includes a `color` column with values `'white'` and `'black'`
- `tests/sql/test_views.py::test_blunder_zone_white_uses_white_bracket` — inject a game where White and Black have different brackets; verify the white row uses the correct white bracket
- `tests/sql/test_views.py::test_blunder_zone_black_uses_black_bracket` — same game, verify black row uses black bracket

### Acceptance Criteria

- [ ] `games` schema has `first_white_blunder_move` and `first_black_blunder_move` columns
- [ ] `v_blunder_zone` produces separate rows for each color
- [ ] White rows use `white_elo_bracket`; Black rows use `black_elo_bracket`
- [ ] `Survival_OII` computation in Task 7 is unblocked
- [ ] All SQL tests pass

---

## Task 5 — Z-Score Confidence Tiers: Calibrated for Large Datasets

**Severity:** LOW — Z-score formula ambiguous; tiers collapse with 20M+ games  
**Branch:** `feat/zscore-confidence-tiers`  
**Files:** `sql/metrics.sql` or `sql/views.sql:v_opening_intelligence`

### Problems

1. The proposed formula `z = (score_bayes − expected_per_game) / sqrt(p×(1−p)/n)` does not define `p`. It must be `p = expected_per_game` (the null hypothesis: the opening gives no edge over Elo expectation). Using `p = score_bayes` would be circular.

2. With 20M games, z-scores become trivially significant:
   ```
   n=50K, ASR=0.01 → z = 0.01 / sqrt(0.5×0.5/50K) ≈ 4.5 → Gold tier
   ```
   Virtually every popular opening would be Gold, making tiers useless.

3. Solution: require **both** z-score significance AND meaningful effect size (ASR magnitude).

### Formula

```sql
-- Z-score (p = expected_per_game under H0)
z_score = (score_bayes - expected_per_game)
          / NULLIF(SQRT(expected_per_game * (1.0 - expected_per_game) / games_count), 0),

-- Tier requires BOTH statistical significance AND practical effect size
tier = CASE
    WHEN z_score > 1.96  AND ABS(asr) > 0.03  THEN 'gold'
    WHEN z_score > 1.64  AND ABS(asr) > 0.015 THEN 'silver'
    ELSE 'bronze'
END
-- ASR thresholds (0.03, 0.015) are empirical; adjust after seeing real data distribution
```

### Tests to Add

- `tests/sql/test_metrics.py::test_zscore_formula_uses_expected_per_game_as_p` — inject game with known `expected_per_game = E`, verify denominator uses `E*(1-E)/n`
- `tests/sql/test_metrics.py::test_tier_requires_effect_size` — construct case with very high z (large n) but tiny ASR (< 0.015); assert tier = 'bronze'
- `tests/sql/test_metrics.py::test_tier_requires_significance` — large ASR but small n (z < 1.64); assert tier = 'bronze'
- `tests/sql/test_metrics.py::test_gold_tier_requires_both_conditions` — only Gold when z > 1.96 AND ASR > 0.03

### Acceptance Criteria

- [ ] `z_score` column present; denominator uses `p = expected_per_game`
- [ ] `tier` column uses composite condition (z AND ASR thresholds)
- [ ] SQL comment documents the rationale for each threshold
- [ ] All SQL tests pass

---

## Task 6 — TC Inheritance Hierarchy for Sparse ECOs

**Severity:** MEDIUM — Rare openings get statistically unreliable TC from few puzzles  
**Branch:** `feat/tc-inheritance-hierarchy`  
**Files:** `sql/views.sql:v_puzzle_difficulty` (or a new CTE in `v_opening_intelligence`)

### Problem

ECO codes with <10 puzzles produce unreliable medians. A median of 5 puzzle ratings behaves very differently from a median of 2000. Without a fallback, rare openings get noisy TC values that distort OII.

### Three-Tier Fallback Hierarchy

1. **Direct** — use `(ECO, elo_bracket)` TC if `puzzle_count >= 50`
2. **ECO global** — if `puzzle_count < 50`, use the ECO's average TC across all brackets
3. **Bracket global** — if ECO has no puzzle data at all, use the bracket's average TC

```sql
WITH tc_direct AS (
    SELECT eco, elo_bracket, median_puzzle_rating AS tc_value, puzzle_count
    FROM v_puzzle_difficulty
),
tc_eco_global AS (
    SELECT eco, AVG(median_puzzle_rating) AS tc_value
    FROM v_puzzle_difficulty
    GROUP BY eco
),
tc_bracket_global AS (
    -- join puzzles to opening results to get bracket-level average
    SELECT r.elo_bracket, AVG(p.median_puzzle_rating) AS tc_value
    FROM v_opening_results r
    LEFT JOIN v_puzzle_difficulty p ON r.eco = p.eco
    WHERE p.median_puzzle_rating IS NOT NULL
    GROUP BY r.elo_bracket
),
tc_resolved AS (
    SELECT
        r.eco,
        r.elo_bracket,
        COALESCE(
            CASE WHEN td.puzzle_count >= 50 THEN td.tc_value ELSE NULL END,
            teg.tc_value,
            tbg.tc_value
        ) AS tc_effective,
        CASE
            WHEN td.puzzle_count >= 50              THEN 'direct'
            WHEN teg.tc_value IS NOT NULL           THEN 'eco_global'
            ELSE                                         'bracket_global'
        END AS tc_source
    FROM v_opening_results r
    LEFT JOIN tc_direct         td  ON r.eco = td.eco AND r.elo_bracket = td.elo_bracket
    LEFT JOIN tc_eco_global     teg ON r.eco = teg.eco
    LEFT JOIN tc_bracket_global tbg ON r.elo_bracket = tbg.elo_bracket
)
```

### Tests to Add

- `tests/sql/test_views.py::test_tc_uses_direct_when_sufficient` — ECO with 100 puzzles in a bracket → `tc_source = 'direct'`
- `tests/sql/test_views.py::test_tc_inherits_eco_global_when_sparse` — ECO with 20 puzzles → `tc_source = 'eco_global'`
- `tests/sql/test_views.py::test_tc_inherits_bracket_global_when_no_puzzles` — ECO with 0 puzzles → `tc_source = 'bracket_global'`
- `tests/sql/test_views.py::test_no_null_tc_when_any_puzzle_data_exists` — if any puzzle exists in the dataset, no ECO should have `NULL` tc_effective

### Acceptance Criteria

- [ ] Three-tier COALESCE fallback implemented
- [ ] `tc_source` column present indicating which tier was used
- [ ] No `NULL` `tc_effective` for ECOs that have any puzzle data (direct, ECO-global, or bracket-global)
- [ ] All SQL tests pass

---

## Task 7 — Survival OII: Blunder Zone Integration

**Severity:** LOW — Adds "opening solidity" dimension to OII  
**Prerequisite:** Task 4 (color-aware blunder schema + view) must be complete  
**Branch:** `feat/survival-oii`  
**Files:** `sql/metrics.sql`, `sql/views.sql:v_opening_intelligence`

### Concept

A "solid" opening keeps players alive longer before their first serious error. The Survival OII rewards openings where the typical player blunders later than the bracket average.

```
Survival_OII = OII × (avg_moves_to_blunder / global_avg_moves_to_blunder)
```

- `avg_moves_to_blunder`: from `v_blunder_zone` per `(eco, color, elo_bracket)`
- `global_avg_moves_to_blunder`: computed per `(color, elo_bracket)` as the baseline

`Survival_OII` is an **additional column**, not a replacement for `oii_score`.

### Implementation

```sql
-- New CTE in v_opening_intelligence or metrics.sql:
global_blunder_avg AS (
    SELECT
        color,
        elo_bracket,
        AVG(avg_blunder_move) AS global_avg_blunder
    FROM v_blunder_zone
    GROUP BY color, elo_bracket
),

-- In final SELECT, add:
CASE
    WHEN bz.avg_blunder_move IS NULL OR gba.global_avg_blunder IS NULL OR gba.global_avg_blunder = 0 THEN NULL
    ELSE ROUND(oii_score * (bz.avg_blunder_move / gba.global_avg_blunder), 4)
END AS survival_oii,
```

### Tests to Add

- `tests/sql/test_metrics.py::test_survival_oii_rewards_later_blunders` — inject two openings with same OII but one has later avg blunder move; assert its `survival_oii` is higher
- `tests/sql/test_metrics.py::test_survival_oii_null_when_no_blunder_data` — opening with no blunder data → `survival_oii = NULL`
- `tests/sql/test_metrics.py::test_survival_oii_does_not_replace_oii_score` — both `oii_score` and `survival_oii` columns present in output

### Acceptance Criteria

- [ ] `survival_oii` column added to `v_opening_intelligence` and `opening_stats`
- [ ] Uses color-aware `v_blunder_zone` from Task 4
- [ ] `NULL` when blunder data unavailable
- [ ] `oii_score` retained alongside `survival_oii`
- [ ] All SQL tests pass

---

## Formula Summary

| Component | v1 (current) | v2 (target) |
|-----------|-------------|-------------|
| Expected score | `expected_score(AVG(elo_diff))` | `AVG(expected_score(elo_diff_per_game))` |
| Score estimate | `score_rate` | `score_bayes` (Beta-Binomial, prior=20) |
| Sample scaling | `× log₁₀(n)` — grows without bound | None — Bayes handles small-n |
| TC normalization | Global min/max | p5/p95 per `(elo_bracket, time_class)` |
| TC clamping | `GREATEST(tc, 0)` — no upper bound | `GREATEST(LEAST(tc, 1.0), 0.05)` |
| OII formula | `ASR / tc_norm × log₁₀(n)` | `(score_bayes − E_per_game) / tc_norm` |
| Confidence | Not implemented | z-score + effect size composite tier |
| Blunder zone | White bracket only | Color-aware (Task 4) |
| Survival OII | Not implemented | `OII × (avg_blunder / global_avg)` (Task 7) |

---

## Branch Strategy

| Task | Branch | Merges to |
|------|--------|-----------|
| 1 — TC normalization | `feat/fix-tc-normalization-per-bracket` | `dev` |
| 2 — Jensen correction | `feat/jensen-correction-asr` | `dev` |
| 3 — Bayesian score v2 | `feat/bayesian-score-oii-v2` | `dev` |
| 4 — Blunder zone color | `feat/blunder-zone-color-aware` | `dev` |
| 5 — Z-score tiers | `feat/zscore-confidence-tiers` | `dev` |
| 6 — TC inheritance | `feat/tc-inheritance-hierarchy` | `dev` |
| 7 — Survival OII | `feat/survival-oii` | `dev` |

All branches merge to `dev` before `main`. Never push directly to `main`.

---

## Post-Implementation Checklist

After all 7 tasks land on `dev`:

- [ ] Update `CLAUDE.md` — replace v1 OII formula with v2, update "Current Status"
- [ ] Update `sql/README.md` — document new columns in views
- [ ] Validate `opening_stats` materialization with real data (sample run)
- [ ] Review TC threshold `0.05` lower clamp — adjust empirically from real data distribution
- [ ] Review ASR effect-size thresholds for tiers (`0.03`, `0.015`) — calibrate from real data
