# Pruning Survival Probability: Theoretical Analysis

> **Result**: We derive a closed-form expression for the probability that the correct
> LFSR seed survives WHT spectral pruning in Stage 1 of the Cascade WHT attack.

---

## 1. Notation & Setup

| Symbol | Definition |
|--------|-----------|
| L | LFSR register length (bits) |
| N₁ | Number of keystream bits used in Stage 1 (WHT pruning) |
| M | Number of top candidates retained after pruning |
| p | Correlation probability: P(keystream_t = LFSR_output_t) |
| ε | Correlation bias: ε = 2p − 1 (e.g., ε = 0.5 for majority) |
| s* | The correct (secret) LFSR seed |
| W(s) | WHT spectral coefficient for seed s |
| Φ(·) | Standard normal CDF |
| Φ⁻¹(·) | Standard normal quantile (inverse CDF) |

The WHT computes, for each seed s ∈ {1, ..., 2^L − 1}:

```
W(s) = Σ_{t=0}^{N₁-1} (-1)^{z_t ⊕ x_t(s)}
```

where z_t is the observed keystream bit and x_t(s) is the LFSR output for seed s at time t.

Stage 1 retains the M seeds with the largest |W(s)| values.

---

## 2. Distributional Model

### Lemma 1 (Distribution of W(s*) — Correct Seed)

**Statement.** Let s* be the correct seed. Then:

```
W(s*) ~ N(N₁ε, N₁(1 − ε²))     where ε = 2p − 1
```

equivalently: W(s*) ~ N(N₁(2p−1), 4N₁p(1−p))

**Proof.** Each term in the sum is Y_t = (−1)^{z_t ⊕ x_t(s*)}. Since z_t = x_t(s*) with
probability p (by Siegenthaler's correlation [1]):

- P(Y_t = +1) = P(z_t = x_t(s*)) = p
- P(Y_t = −1) = 1 − p

Therefore:
- E[Y_t] = p · (+1) + (1−p) · (−1) = 2p − 1 = ε
- Var[Y_t] = E[Y_t²] − (E[Y_t])² = 1 − ε² = 4p(1−p)

Since {Y_t} are i.i.d. (conditional on s*), by the Central Limit Theorem [5]:

```
W(s*) = Σ Y_t ~ N(N₁ε, N₁(1 − ε²))     ∎
```

**Numerical examples:**

| Combining function | p | ε = 2p−1 | E[W(s*)] for N₁=200 | StdDev |
|---|---|---|---|---|
| Majority (3-input) | 0.75 | 0.50 | 100.0 | 12.25 |
| XOR-majority hybrid | 0.625 | 0.25 | 50.0 | 13.23 |
| Near-corr-immune | 0.56 | 0.12 | 24.0 | 13.86 |

---

### Lemma 2 (Distribution of W(s) — Wrong Seeds)

**Statement.** For any s ≠ s*, let W(s) denote the WHT coefficient. Then:

```
W(s) ~ N(0, N₁)
```

and |W(s)| follows the half-normal distribution with scale √N₁.

**Proof.** For s ≠ s*, the LFSR sequence x_t(s) is a pseudo-random binary sequence whose
statistical correlation with the keystream z_t is negligible (the keystream is generated
from s*, not s). Each term Y_t = (−1)^{z_t ⊕ x_t(s)} is ±1 with approximately equal
probability:

- E[Y_t] ≈ 0
- Var[Y_t] ≈ 1

By CLT: W(s) = Σ Y_t ~ N(0, N₁).     ∎

**Note.** This assumes independence of wrong-seed outputs from the keystream, which holds
exactly for truly random sequences and approximately for LFSR sequences of maximal period
when N₁ ≪ 2^L (which is always the case in practice).

---

## 3. Pruning Threshold

### Lemma 3 (Order Statistic Threshold)

**Statement.** Let W₁, ..., W_{2^L−1} be the |W(s)| values for all wrong seeds s ≠ s*.
The pruning keeps the top-M values. The correct seed survives iff |W(s*)| exceeds the
(2^L − 1 − M + 1)-th order statistic of {|W_i|}, which is approximately:

```
τ(N₁, L, M) = √N₁ · Φ⁻¹(1 − M / (2 · 2^L))
```

**Proof.** The wrong-seed values |W(s)| follow the half-normal distribution with CDF:

```
F(x) = 2Φ(x/√N₁) − 1     for x ≥ 0
```

The M-th largest of (2^L − 1) i.i.d. samples exceeds value x with probability approximately
M/(2^L − 1) ≈ M/2^L. So the threshold τ satisfies:

```
P(|W(s)| > τ) = M / 2^L
```

Using the half-normal survival function:

```
1 − F(τ) = 2(1 − Φ(τ/√N₁)) = M / 2^L

⟹ 1 − Φ(τ/√N₁) = M / (2 · 2^L)

⟹ τ = √N₁ · Φ⁻¹(1 − M / (2 · 2^L))     ∎
```

**Numerical examples (N₁ = 200):**

| L | 2^L | M = √(2^L) | M/2^L | τ |
|---|---|---|---|---|
| 10 | 1,024 | 32 | 0.031 | 26.6 |
| 12 | 4,096 | 64 | 0.016 | 30.7 |
| 14 | 16,384 | 128 | 0.0078 | 33.7 |
| 16 | 65,536 | 256 | 0.0039 | 36.3 |
| 20 | 1,048,576 | 1,024 | 0.00098 | 41.6 |

---

## 4. Main Theorem

### Theorem 1 (Pruning Survival Probability)

**Statement.** The probability that the correct seed s* is among the top-M candidates
after WHT spectral pruning is:

```
P_survive(N₁, L, M, p) = Φ( (N₁ε − τ) / √(N₁(1 − ε²)) )
```

where:
- ε = 2p − 1 (correlation bias)
- τ = √N₁ · Φ⁻¹(1 − M/(2 · 2^L)) (pruning threshold from Lemma 3)

**Proof.** The correct seed survives iff |W(s*)| > τ. Since W(s*) ~ N(N₁ε, N₁(1−ε²))
by Lemma 1, and N₁ε > 0, we have |W(s*)| ≈ W(s*) with high probability (the coefficient
is positive with overwhelming probability when N₁ε ≫ √(N₁(1−ε²))).

Therefore:

```
P(|W(s*)| > τ) ≈ P(W(s*) > τ)
                = P( (W(s*) − N₁ε) / √(N₁(1−ε²)) > (τ − N₁ε) / √(N₁(1−ε²)) )
                = 1 − Φ( (τ − N₁ε) / √(N₁(1−ε²)) )
                = Φ( (N₁ε − τ) / √(N₁(1−ε²)) )     ∎
```

**Interpretation:** The survival probability depends on the ratio of the "signal"
(N₁ε = expected WHT coefficient of correct seed) to the "noise floor" (τ = threshold
set by wrong seeds). When the signal greatly exceeds the threshold, P_survive → 1.

---

## 5. Corollaries

### Corollary 1 (Sufficient condition on N₁)

**Statement.** For P_survive ≥ 1 − δ, it suffices to have:

```
N₁ ≥ [ Φ⁻¹(1−δ) · √(1−ε²) + √(2 ln(2^L / M)) ]² / ε²
```

When M = 2^{L/2} (our default choice M = √(2^L)), this simplifies to:

```
N₁ = Ω( L / ε² ) = Ω( L / (2p−1)² )
```

**Proof sketch.** Setting P_survive = 1 − δ in Theorem 1:

```
Φ⁻¹(1−δ) = (N₁ε − τ) / √(N₁(1−ε²))
```

Substituting τ ≈ √(2N₁ · ln(2^L/M)) (using the Gaussian tail approximation
Φ⁻¹(1−x) ≈ √(2 ln(1/x)) for small x):

```
Φ⁻¹(1−δ) · √(N₁(1−ε²)) = N₁ε − √(2N₁ ln(2^L/M))
```

Dividing by √N₁:

```
Φ⁻¹(1−δ) · √(1−ε²) = √N₁ · ε − √(2 ln(2^L/M))
```

Solving for √N₁ and squaring gives the result. With M = 2^{L/2}:

```
ln(2^L / M) = ln(2^{L/2}) = (L/2) ln 2
```

So the critical term is √(L ln 2), giving N₁ = Ω(L/ε²).     ∎

**Key insight:** The required partial keystream length scales:
- **Linearly** in LFSR length L
- **Inversely quadratically** in the correlation bias ε = 2p−1

This means stronger correlation (larger p) requires drastically less keystream.

**Numerical predictions for P_survive = 0.99 (δ = 0.01):**

| L | p | ε | M = √(2^L) | N₁ (required) | N₁/L ratio |
|---|---|---|---|---|---|
| 14 | 0.75 | 0.50 | 128 | ~68 | 4.9 |
| 14 | 0.625 | 0.25 | 128 | ~237 | 16.9 |
| 14 | 0.56 | 0.12 | 128 | ~989 | 70.6 |
| 20 | 0.75 | 0.50 | 1024 | ~100 | 5.0 |
| 20 | 0.625 | 0.25 | 1024 | ~350 | 17.5 |
| 20 | 0.56 | 0.12 | 1024 | ~1444 | 72.2 |

---

### Corollary 2 (Optimal M for fixed N₁)

**Statement.** For a given N₁ and target P_survive = 1 − δ, the minimum required M is:

```
M_min = 2^L · 2 · (1 − Φ(τ_max / √N₁))
```

where τ_max = N₁ε − Φ⁻¹(1−δ) · √(N₁(1−ε²)).

This can be rewritten as:

```
M_min = 2^{L+1} · Φ̄( √N₁ · ε − Φ⁻¹(1−δ) · √(1−ε²) )
```

where Φ̄ = 1 − Φ is the Gaussian survival function.

**Implication:** Larger M (more survivors) makes pruning easier (higher P_survive)
but increases Stage 2 cost. There is an optimal trade-off that minimizes total
attack time — this is analyzed empirically in `pruning_survival_analysis.py`.

---

## 6. Assumptions & Limitations

1. **CLT validity**: The Gaussian approximation requires N₁ ≳ 30. For very small N₁,
   the exact binomial distribution should be used instead.

2. **Independence of wrong seeds**: We assume W(s) for different wrong seeds s are
   approximately independent. In reality, LFSR sequences from different seeds have
   weak correlations, but these vanish for maximal-period polynomials when L is moderate.

3. **Positive W(s*)**: We approximate |W(s*)| ≈ W(s*) (drop the absolute value).
   This is valid when N₁ε ≫ √(N₁(1−ε²)), i.e., √N₁ · ε ≫ √(1−ε²), which holds
   for N₁ ≥ (1−ε²)/ε² ≈ 4p(1−p)/(2p−1)² (typically < 20 for p ≥ 0.56).

4. **Quantile approximation for τ**: For very large M/2^L ratios (M ≈ 2^L), the
   threshold τ approaches 0 and the pruning becomes trivial. The formula is most
   useful for M ≪ 2^L (e.g., M = 2^{L/2}).

---

## 7. References

[1] Siegenthaler, T. (1985). "Decrypting a Class of Stream Ciphers Using Ciphertext Only."
    *IEEE Trans. Computers*, C-34(1), 81–85.

[2] Meier, W. & Staffelbach, O. (1989). "Fast Correlation Attacks on Certain Stream Ciphers."
    *J. Cryptology*, 1(3), 159–176.

[3] Chose, P., Joux, A. & Mitton, M. (2002). "Fast Correlation Attacks: An Algorithmic
    Point of View." *EUROCRYPT 2002*, LNCS 2332, 209–221.

[4] Canteaut, A. & Trabbia, M. (2000). "Improved Fast Correlation Attacks Using Parity-Check
    Equations of Weight 4 and 5." *EUROCRYPT 2000*, LNCS 1807, 573–588.

[5] Feller, W. (1968). *An Introduction to Probability Theory and Its Applications*,
    Vol. 1, 3rd ed. Wiley.

[6] David, H.A. & Nagaraja, H.N. (2003). *Order Statistics*, 3rd ed. Wiley.

[7] Leadbetter, M.R., Lindgren, G. & Rootzén, H. (1983). *Extremes and Related Properties
    of Random Sequences and Processes*. Springer.
