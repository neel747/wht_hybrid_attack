# Project Status Log: Two-Stage Cascade WHT Correlation Attack

This file tracks all modifications, improvements, and experimental results for the WHT Hybrid Attack project. It serves as a living document — update this whenever changes are made to the codebase.

> **Reference**: See `project_review.md` for the full review with weakness IDs (W1–W13).

---

## 📅 Last Updated: 2026-04-22

---

## ✅ Completed Tasks

### Documentation & Theory

| Date | Task | Files Modified | Details |
|------|------|----------------|---------|
| 2026-04-07 | **W4**: Statistical rigor (100 trials, 95% CI) | `cascade_wht_attack.py` | t-distribution for timing, Wilson score for success rates |
| 2026-04-07 | **W5**: Meier-Staffelbach FCA implementation | `cascade_wht_attack.py` | Full 3-way comparison: Standard vs FCA vs Cascade WHT |
| 2026-04-07 | **W2**: Pruning Survival Theorem | `pruning_theorem.md`, `pruning_survival_analysis.py` | CLT + order stats derivation; 500-trial Monte Carlo validation matches theory within 95% CI |
| 2026-04-07 | **W6 v1**: N₁/N ratio sweep | `n1_ratio_sweep.py` | Original ratio-based sweep (30 trials, majority only) |

### Code Fixes (2026-04-22)

| Date | Task | Files Modified | Details |
|------|------|----------------|---------|
| 2026-04-22 | **W12**: Vectorized spectral accumulator | `cascade_wht_attack.py` | Replaced Python `for` loop with `np.add.at(f, indices, ks_signed)` — single numpy call for honest timing |
| 2026-04-22 | **W10**: Per-LFSR success tracking | `cascade_wht_attack.py` | Added `per_lfsr_success` and `per_lfsr_ranks` to diagnostics dict; `secret_seeds` now passed through for tracking |
| 2026-04-22 | **Fix 1: Theory-driven N₁** | `cascade_wht_attack.py` | **MAJOR**: Replaced hardcoded `N1 = N // 4` with `compute_optimal_n1()` — computes minimum N₁ from Corollary 1 of pruning theorem: `N₁ ≥ [Φ⁻¹(1−δ)·√(1−ε²) + √(2·ln(2^L/M))]² / ε²`. Attack is now self-tuning for any (L, M, p). |
| 2026-04-22 | **Fix 2: Absolute N₁ framing** | `n1_ratio_sweep.py` | Reframed sweep around absolute N₁ values (not N₁/N ratios) — consistent with Corollary 1 which proves N₁_min depends on (L, M, p), NOT on N |
| 2026-04-22 | **Fix 3: Multi-p sweep** | `n1_ratio_sweep.py` | Now sweeps 3 correlation strengths: p=0.75 (majority), p=0.625 (hybrid), p=0.56 (near-corr-immune) |
| 2026-04-22 | **Fix 4: 100 trials** | `n1_ratio_sweep.py` | Increased from 30 to 100 trials per configuration |
| 2026-04-22 | **Fix 5: Joint (N₁, M) heatmap** | `n1_ratio_sweep.py` | Added theoretical heatmap showing P_survive as function of both N₁ and M |
| 2026-04-22 | **W3: Multiple combining functions** | `cascade_wht_attack.py` | **MAJOR**: Implemented combining function registry with 3 modes: (1) **Majority** p=0.75, (2) **Geffe generator** p={0.5, 0.75, 0.75} — real published cipher with asymmetric correlations, (3) **BSC-degraded** p_eff=0.56 — standard Siegenthaler/Meier-Staffelbach technique. Added `COMBINING_FUNCTIONS` dict, `_apply_combiner()`, `apply_bsc_noise()`, `p_corr_per_lfsr` property. Main engine now loops over all 3 modes automatically. |

---

## 📊 Verified Theory-Driven N₁ Values

Output from `compute_optimal_n1()` (target: P_survive ≥ 99%):

| L | M = √(2^L) | p=0.75 (ε=0.50) | p=0.625 (ε=0.25) | p=0.56 (ε=0.12) |
|---|---|---|---|---|
| 13 | 90 | N₁=101 | N₁=443 | N₁=1961 |
| 14 | 128 | N₁=106 | N₁=461 | N₁=2044 |
| 20 | 1024 | N₁=132 | N₁=572 | N₁=2528 |

**Key insight**: N₁_min scales as `Ω(L/ε²)` — linearly in LFSR length, inversely quadratic in bias.

---

## 🛠️ Remaining Tasks

### Priority 1 — BLOCKING for publication

- [ ] **W1: Scale LFSR sizes** to L ∈ {16, 18, 20, 22} — eliminates "toy-scale" criticism
- [x] **W3: Multiple combining functions** — ✅ Implemented: Majority (p=0.75), Geffe (p={0.5, 0.75, 0.75}), BSC-degraded (p=0.56). `main()` now runs all 3 modes.

### Priority 2 — Strongly recommended

- [ ] **W7: M parameter sweep** — justify M = √(2^L) empirically or replace with theory-optimal M
- [ ] **W8: Memory complexity analysis** — document O(2^L) memory requirements for WHT
- [ ] **W9: Short keystream failure analysis** — analyze why success drops at N=200
- [x] **W10: Per-LFSR analysis** — ✅ Tracking added to diagnostics

### Priority 3 — Nice to have

- [ ] **W11: Parallelism/GPU discussion** — note embarrassingly parallel WHT
- [x] **W12: Vectorized accumulator** — ✅ Replaced with `np.add.at`
- [ ] **W13: Connection vector optimization** — note O(N×L) dominance for large N

### Paper Polish

- [ ] Formal algorithm pseudocode (LaTeX Algorithm2e)
- [ ] Complexity comparison table with all known attacks
- [ ] Scaling plot: speedup vs L and vs N
- [ ] Failure analysis: when/why Stage 1 pruning fails
- [ ] Real cipher applicability discussion (E0, A5/1, Grain)

---

## 📝 Architecture Notes

### Theory-Driven N₁ Flow (NEW)
```
cascade_wht_attack()
  → compute_optimal_n1(L_max, M, p_corr, target=0.99)
    → Corollary 1: N₁ ≥ [z_δ·√(1−ε²) + √(2·ln(2^L/M))]² / ε²
    → Returns integer ≥ 30 (CLT validity floor)
  → N1 = min(N1_theory, N)  # cap at available keystream
  → wht_spectral_pruning(L, taps, keystream, N1, M)
```

### Key Function Signatures Changed
- `cascade_wht_attack()` — added `p_corr: float = 0.75` parameter
- `cascade_wht_attack()` — N₁ now computed from `compute_optimal_n1()` instead of `N // 4`
- `wht_spectral_pruning()` — accumulator uses `np.add.at` (vectorized)
- `run_comparison()` — added `combiner_mode` and `bsc_p_target` params; uses per-LFSR p_corr
- `StreamCipher` — added `mode` param, `p_corr_per_lfsr` property, uses `_apply_combiner()`
- `main()` — loops over 3 combining function modes (majority, geffe, BSC-degraded)

### Combining Function Architecture (NEW — W3)
```
COMBINING_FUNCTIONS = {
    'majority': p_corr=[0.75, 0.75, 0.75],
    'geffe':    p_corr=[0.50, 0.75, 0.75],  # x1=selector
}

StreamCipher(configs, mode='geffe') → _apply_combiner(outputs, 'geffe')
apply_bsc_noise(keystream, p_orig=0.75, p_target=0.56) → simulates lower p

main() → for mode in [majority, geffe, bsc_degraded]:
           run_comparison(..., combiner_mode=mode, bsc_p_target=...)
```

---

## 🔗 File Reference

| File | Purpose |
|------|---------|
| `cascade_wht_attack.py` | Main attack implementation + 3-way comparison engine |
| `n1_ratio_sweep.py` | N₁ parameter analysis (v2: theory-driven, multi-p, heatmap) |
| `pruning_theorem.md` | Theoretical derivation of pruning survival probability |
| `pruning_survival_analysis.py` | Monte Carlo validation of Theorem 1 |
| `novelty_analysis.md` | Positioning against prior art |
| `project_review.md` | Full review with weakness IDs (W1–W13) |
| `theorem_references.md` | Reference citations |
