#!/usr/bin/env python
# coding: utf-8

# # Two-Stage Cascade WHT Correlation Attack
# ### vs Standard Correlation Attack on 40-bit LFSR Stream Cipher
# 
# Novel attack using Walsh-Hadamard Transform on partial keystream for
# spectral pruning (Stage 1), followed by precise correlation on survivors
# (Stage 2), achieving **O(L×2^L + √(2^L)×N)** vs standard **O(N×2^L)**.

# In[1]:


import numpy as np
import time
import csv
import os
import matplotlib.pyplot as plt
from scipy import stats
from scipy.sparse import csr_matrix
from typing import List, Tuple, Optional


# ## 1. LFSR & Stream Cipher

# In[2]:


class LFSR:
    """Linear Feedback Shift Register."""

    def __init__(self, length: int, taps: List[int], seed: int):
        self.length = length
        self.taps = taps
        self.state = seed if seed != 0 else 1
        self.mask = (1 << length) - 1

    def clock(self) -> int:
        out = self.state & 1
        fb = 0
        for t in self.taps:
            if t < self.length:
                fb ^= (self.state >> t) & 1
        self.state = ((self.state >> 1) | (fb << (self.length - 1))) & self.mask
        return out

    def generate(self, n: int) -> np.ndarray:
        return np.array([self.clock() for _ in range(n)], dtype=np.uint8)


# In[3]:


class StreamCipher:
    """Stream cipher combining 3 LFSRs with majority function."""

    def __init__(self, configs: List[Tuple[int, List[int]]],
                 seeds: Tuple[int, ...] = None):
        self.configs = configs
        if seeds is None:
            seeds = tuple(np.random.randint(1, (1 << c[0])) for c in configs)
        self.seeds = seeds
        self.lfsrs = [LFSR(c[0], c[1], s)
                      for c, s in zip(configs, seeds)]

    def generate_keystream(self, n: int) -> np.ndarray:
        outputs = np.stack([lfsr.generate(n) for lfsr in self.lfsrs])
        return (np.sum(outputs, axis=0) >= 2).astype(np.uint8)


# ## 2. Connection Vector Generator

# In[4]:


def compute_connection_vectors(length: int, taps: List[int],
                               n_bits: int) -> np.ndarray:
    """
    Compute connection vectors g_0, g_1, ..., g_{n_bits-1}.

    Each g_t is an L-bit vector such that:
        output_t(seed) = <g_t, seed> mod 2

    The first L vectors are identity rows (output = state bit).
    For t >= L, g_t is derived from g_{t-1} using the companion
    matrix transpose (LFSR recurrence).

    Returns: (n_bits, length) array of uint8
    """
    vectors = np.zeros((n_bits, length), dtype=np.uint8)

    # First L vectors: identity (output_t = seed_bit_t)
    for t in range(min(length, n_bits)):
        vectors[t, t] = 1

    # Remaining: g_t = A^T · g_{t-1}
    for t in range(length, n_bits):
        vectors[t, 1:] = vectors[t - 1, :-1]
        if vectors[t - 1, length - 1]:
            for tap in taps:
                vectors[t, tap] ^= 1

    return vectors


# In[5]:


def vectors_to_indices(vectors: np.ndarray) -> np.ndarray:
    """Convert binary vectors to integer indices for the WHT array."""
    length = vectors.shape[1]
    powers = 1 << np.arange(length, dtype=np.int64)
    return vectors.astype(np.int64) @ powers


# ## 3. Fast Walsh-Hadamard Transform (Vectorized)

# In[6]:


def fwht(a: np.ndarray) -> np.ndarray:
    """
    Fast Walsh-Hadamard Transform (numpy-vectorized).

    Input:  array of length 2^L (spectral accumulator f)
    Output: array where result[s] = Σ_x f(x) · (-1)^{<x,s>}
            = correlation of seed s with keystream

    Complexity: O(L × 2^L) — computed via butterfly operations.
    """
    a = a.copy().astype(np.float64)
    n = len(a)
    h = 1
    while h < n:
        a_reshaped = a.reshape(-1, 2 * h)
        left = a_reshaped[:, :h].copy()
        right = a_reshaped[:, h:].copy()
        a_reshaped[:, :h] = left + right
        a_reshaped[:, h:] = left - right
        h *= 2
    return a


# ## 4. Stage 1: WHT Spectral Pruning

# In[7]:


def wht_spectral_pruning(length: int, taps: List[int],
                         keystream: np.ndarray,
                         n1: int, M: int) -> np.ndarray:
    """
    Stage 1: Use WHT on partial keystream (first n1 bits) to find
    top-M candidate seeds.

    Complexity: O(n1 × L + L × 2^L)
    """
    g_vectors = compute_connection_vectors(length, taps, n1)
    indices = vectors_to_indices(g_vectors)

    f = np.zeros(1 << length, dtype=np.float64)
    ks_signed = 1.0 - 2.0 * keystream[:n1].astype(np.float64)

    for t in range(n1):
        f[indices[t]] += ks_signed[t]

    f = fwht(f)

    f[0] = 0  # seed 0 is invalid
    top_m = np.argsort(np.abs(f))[-M:]

    return top_m


# ## 5. Stage 2: Precise Correlation on Survivors

# In[8]:


def precise_correlation_on_survivors(
    length: int, taps: List[int],
    keystream: np.ndarray,
    survivors: np.ndarray,
    K: int
) -> List[int]:
    """
    Stage 2: Compute full N-bit correlation only on M surviving seeds.
    Complexity: O(M × N)
    """
    N = len(keystream)
    scores = []

    for seed in survivors:
        seed_int = int(seed)
        if seed_int == 0:
            continue
        lfsr = LFSR(length, taps, seed_int)
        output = lfsr.generate(N)
        corr = int(np.sum(output == keystream))
        scores.append((seed_int, corr))

    scores.sort(key=lambda x: -x[1])
    return [s for s, _ in scores[:K]]


# ## 6. Standard Correlation Attack (Baseline)

# In[9]:


def correlation_attack_single_lfsr(
    length: int, taps: List[int],
    keystream: np.ndarray
) -> Tuple[int, int]:
    """
    Standard correlation: try ALL 2^L seeds, return best.
    Complexity: O(N × 2^L)
    """
    N = len(keystream)
    best_seed = 1
    best_corr = 0

    for seed in range(1, 1 << length):
        lfsr = LFSR(length, taps, seed)
        output = lfsr.generate(N)
        corr = int(np.sum(output == keystream))
        if corr > best_corr:
            best_corr = corr
            best_seed = seed

    return best_seed, best_corr


# In[10]:


def correlation_attack(
    keystream: np.ndarray,
    configs: List[Tuple[int, List[int]]]
) -> Tuple[bool, Optional[Tuple[int, ...]], float]:
    """Full standard correlation attack on the stream cipher."""
    start = time.perf_counter()

    seeds = []
    for length, taps in configs:
        seed, _ = correlation_attack_single_lfsr(length, taps, keystream)
        seeds.append(seed)

    seeds = tuple(seeds)
    cipher = StreamCipher(configs, seeds=seeds)
    success = np.array_equal(
        cipher.generate_keystream(len(keystream)), keystream
    )

    elapsed = time.perf_counter() - start
    return success, seeds if success else None, elapsed


# ## 7. Fast Correlation Attack (Meier-Staffelbach)

# In[10b]:


def _poly_multiply_gf2(poly1: set, poly2: set) -> set:
    """Multiply two polynomials over GF(2), represented as sets of exponents."""
    result = set()
    for a in poly1:
        for b in poly2:
            term = a + b
            if term in result:
                result.remove(term)  # XOR cancellation
            else:
                result.add(term)
    return result


def find_parity_checks(length: int, taps: List[int], N: int,
                       max_weight: int = 5) -> List[List[int]]:
    """
    Find low-weight parity-check equations from the LFSR feedback polynomial.

    The LFSR recurrence gives: z_{t+L} = z_{t+tap0} XOR z_{t+tap1} XOR ...
    => parity check: z_{t+tap0} XOR z_{t+tap1} XOR ... XOR z_{t+L} = 0

    We also multiply the feedback polynomial by (1 + x^d) for various d
    to find additional low-weight parity checks (polynomial multiples).

    Returns: list of offset lists [[d0, d1, ..., dk], ...]
             Each means z_{t+d0} XOR z_{t+d1} XOR ... XOR z_{t+dk} = 0
    """
    # Feedback polynomial: x^L + x^{tap0} + x^{tap1} + ...
    poly = set(taps) | {length}

    all_checks = []
    seen = set()

    # Fundamental check
    fund = sorted(poly)
    all_checks.append(fund)
    seen.add(tuple(fund))

    # Low-weight multiples via (1 + x^d)
    for d in range(1, N):
        multiplier = {0, d}
        product = _poly_multiply_gf2(poly, multiplier)
        if len(product) <= max_weight and len(product) > 0:
            offsets = sorted(product)
            min_o = offsets[0]
            offsets = [o - min_o for o in offsets]
            if max(offsets) < N:
                key = tuple(offsets)
                if key not in seen:
                    seen.add(key)
                    all_checks.append(offsets)

    # Low-weight multiples via (1 + x^a + x^b)
    for a in range(1, min(N // 2, 40)):
        for b in range(a + 1, min(N // 2, 40)):
            multiplier = {0, a, b}
            product = _poly_multiply_gf2(poly, multiplier)
            if len(product) <= max_weight and len(product) > 0:
                offsets = sorted(product)
                min_o = offsets[0]
                offsets = [o - min_o for o in offsets]
                if max(offsets) < N:
                    key = tuple(offsets)
                    if key not in seen:
                        seen.add(key)
                        all_checks.append(offsets)

    return all_checks


def _build_check_structures(checks: List[List[int]], N: int):
    """
    Build vectorized check structures for the iterative decoder.

    Returns:
        checks_2d:  (n_instances, max_weight) int32 array of bit positions
        indicator:  (N, n_instances) sparse matrix — indicator[bit, check]=1
        n_checks_per_bit: (N,) array — number of checks each bit participates in
    """
    # Generate all check instances
    instances = []
    for offsets in checks:
        max_off = max(offsets)
        for t in range(N - max_off):
            instances.append([t + d for d in offsets])

    n_inst = len(instances)
    if n_inst == 0:
        return None, None, None

    max_w = max(len(inst) for inst in instances)
    checks_2d = np.full((n_inst, max_w), -1, dtype=np.int32)
    for i, inst in enumerate(instances):
        for j, p in enumerate(inst):
            checks_2d[i, j] = p

    # Build sparse indicator matrix: indicator[bit, check_instance] = 1
    rows, cols = [], []
    for ci, inst in enumerate(instances):
        for p in inst:
            rows.append(p)
            cols.append(ci)
    indicator = csr_matrix(
        (np.ones(len(rows), dtype=np.float64), (rows, cols)),
        shape=(N, n_inst)
    )
    n_checks_per_bit = np.array(
        indicator.sum(axis=1), dtype=np.float64
    ).flatten()

    return checks_2d, indicator, n_checks_per_bit


def fca_single_lfsr(
    length: int, taps: List[int],
    keystream: np.ndarray,
    p_corr: float = 0.75,
    max_iterations: int = 30,
    n_restarts: int = 20
) -> Tuple[int, int]:
    """
    Meier-Staffelbach Fast Correlation Attack on a single LFSR.

    Uses low-weight parity-check equations derived from the feedback
    polynomial and iterative bit-flipping decoding to recover the
    initial state.

    Key property: Does NOT enumerate 2^L states.
    Complexity: O(N × checks × iterations × restarts)

    Based on:
        Meier & Staffelbach, "Fast Correlation Attacks on Certain
        Stream Ciphers", Journal of Cryptology, 1(3), 1989.

    Args:
        length: LFSR register length
        taps: feedback tap positions
        keystream: observed (noisy) keystream bits
        p_corr: correlation probability P(ks_t = lfsr_t)
        max_iterations: max decoder iterations per restart
        n_restarts: number of random restarts

    Returns: (best_seed, best_correlation_count)
    """
    N = len(keystream)

    # Step 1: Find parity-check equations from polynomial multiples
    checks = find_parity_checks(length, taps, N, max_weight=5)

    # Step 2: Build vectorized structures
    checks_2d, indicator, n_checks_per_bit = _build_check_structures(
        checks, N
    )
    if checks_2d is None:
        # Fallback: no usable checks, return trivial result
        return 1, 0

    n_inst = checks_2d.shape[0]
    max_w = checks_2d.shape[1]

    # Precompute safe denominator for threshold
    safe_denom = n_checks_per_bit.copy()
    safe_denom[safe_denom == 0] = 1.0

    best_seed = 1
    best_corr = 0

    for restart in range(n_restarts):
        # Initialize estimate
        estimate = keystream.copy().astype(np.uint8)
        if restart > 0:
            # Random perturbation: flip bits with probability (1 - p)
            flip_mask = np.random.random(N) < (1.0 - p_corr)
            estimate[flip_mask] ^= 1

        for iteration in range(max_iterations):
            # Vectorized parity computation across all check instances
            parities = np.zeros(n_inst, dtype=np.uint8)
            for w in range(max_w):
                valid = checks_2d[:, w] >= 0
                parities[valid] ^= estimate[checks_2d[valid, w]]

            # Count unsatisfied checks per bit via sparse matrix multiply
            unsatisfied = np.asarray(
                indicator @ parities.astype(np.float64)
            ).flatten()

            # Flip bits where majority of checks are unsatisfied
            flip_mask = unsatisfied > (n_checks_per_bit / 2)
            n_flipped = int(np.sum(flip_mask))

            if n_flipped == 0:
                break

            estimate[flip_mask] ^= 1

        # Recover initial state from first L output bits
        seed = 0
        for i in range(min(length, N)):
            if estimate[i]:
                seed |= (1 << i)

        if seed == 0:
            continue

        # Validate by computing actual correlation
        lfsr = LFSR(length, taps, seed)
        output = lfsr.generate(N)
        corr = int(np.sum(output == keystream))

        if corr > best_corr:
            best_corr = corr
            best_seed = seed

    return best_seed, best_corr


def fast_correlation_attack(
    keystream: np.ndarray,
    configs: List[Tuple[int, List[int]]],
    p_corr: float = 0.75
) -> Tuple[bool, Optional[Tuple[int, ...]], float]:
    """
    Full Meier-Staffelbach Fast Correlation Attack on the stream cipher.

    Recovers each LFSR initial state independently via iterative
    bit-flipping decoding on parity-check equations, then verifies
    the combined result.

    Complexity: O(N × checks × iters × restarts) per LFSR — no 2^L term.
    """
    start = time.perf_counter()

    seeds = []
    for length, taps in configs:
        seed, _ = fca_single_lfsr(length, taps, keystream, p_corr=p_corr)
        seeds.append(seed)

    seeds = tuple(seeds)
    cipher = StreamCipher(configs, seeds=seeds)
    success = np.array_equal(
        cipher.generate_keystream(len(keystream)), keystream
    )

    elapsed = time.perf_counter() - start
    return success, seeds if success else None, elapsed


# ## 8. Full Cascade WHT Attack

# In[11]:


def cascade_wht_attack(
    keystream: np.ndarray,
    configs: List[Tuple[int, List[int]]],
    K: int = 5
) -> Tuple[bool, Optional[Tuple[int, ...]], float, dict]:
    """
    Two-Stage Cascade WHT Correlation Attack.

    Stage 1: WHT on partial keystream (N/4 bits) → spectral pruning
             → keep top-M candidates where M = √(2^L)
    Stage 2: Full N-bit correlation on M survivors → top-K seeds
    Stage 3: Verify K³ combinations against full keystream

    Complexity: O(L×2^L + √(2^L)×N + K³×N) per LFSR
    vs Standard: O(N×2^L) per LFSR
    """
    start = time.perf_counter()
    N = len(keystream)
    N1 = max(N // 4, 50)

    diagnostics = {
        'N': N, 'N1': N1,
        'stage1_time': 0, 'stage2_time': 0, 'stage3_time': 0,
        'M_values': []
    }

    top_candidates = []

    for length, taps in configs:
        M = max(int(np.sqrt(1 << length)), K + 1)
        diagnostics['M_values'].append(M)

        t1 = time.perf_counter()
        survivors = wht_spectral_pruning(length, taps, keystream, N1, M)
        diagnostics['stage1_time'] += time.perf_counter() - t1

        t2 = time.perf_counter()
        top_k = precise_correlation_on_survivors(
            length, taps, keystream, survivors, K
        )
        diagnostics['stage2_time'] += time.perf_counter() - t2

        top_candidates.append(top_k)

    t3 = time.perf_counter()
    for s1 in top_candidates[0]:
        for s2 in top_candidates[1]:
            for s3 in top_candidates[2]:
                cipher = StreamCipher(
                    configs, seeds=(s1, s2, s3)
                )
                if np.array_equal(
                    cipher.generate_keystream(N), keystream
                ):
                    diagnostics['stage3_time'] = time.perf_counter() - t3
                    elapsed = time.perf_counter() - start
                    return True, (s1, s2, s3), elapsed, diagnostics

    diagnostics['stage3_time'] = time.perf_counter() - t3
    elapsed = time.perf_counter() - start
    return False, None, elapsed, diagnostics


# ## 8. Correctness Verification (7-bit LFSR)

# In[12]:


def verify_wht_correctness():
    """
    Verify WHT-computed correlations match exhaustive correlation
    on a small 7-bit LFSR.
    """
    print("=" * 70)
    print("CORRECTNESS VERIFICATION: WHT vs Exhaustive (7-bit LFSR)")
    print("=" * 70)

    length = 7
    taps = [0, 3]
    N = 50

    seed = np.random.randint(1, 1 << length)
    lfsr = LFSR(length, taps, seed)
    keystream = lfsr.generate(N)

    print(f"  LFSR: {length}-bit, taps={taps}, secret seed={seed}")
    print(f"  Keystream length: {N}")

    # Method 1: WHT (all correlations at once)
    g_vectors = compute_connection_vectors(length, taps, N)
    indices = vectors_to_indices(g_vectors)
    f = np.zeros(1 << length, dtype=np.float64)
    ks_signed = 1.0 - 2.0 * keystream.astype(np.float64)
    for t in range(N):
        f[indices[t]] += ks_signed[t]
    wht_corr = fwht(f)

    # Method 2: Exhaustive (one seed at a time)
    exhaustive_corr = np.zeros(1 << length, dtype=np.float64)
    for s in range(1, 1 << length):
        test_lfsr = LFSR(length, taps, s)
        output = test_lfsr.generate(N)
        exhaustive_corr[s] = np.sum(
            (1.0 - 2.0 * output) * (1.0 - 2.0 * keystream)
        )

    # Compare
    match = True
    for s in range(1, 1 << length):
        if abs(wht_corr[s] - exhaustive_corr[s]) > 1e-6:
            print(f"  ✗ MISMATCH at seed {s}: WHT={wht_corr[s]:.2f}, "
                  f"Exhaustive={exhaustive_corr[s]:.2f}")
            match = False

    if match:
        print(f"  ✓ All {(1 << length) - 1} seed correlations match!")

    wht_best = np.argmax(np.abs(wht_corr[1:])) + 1
    exh_best = np.argmax(np.abs(exhaustive_corr[1:])) + 1
    print(f"  WHT best seed:        {wht_best} (corr={wht_corr[wht_best]:.1f})")
    print(f"  Exhaustive best seed: {exh_best} (corr={exhaustive_corr[exh_best]:.1f})")
    print(f"  True secret seed:     {seed}")
    print(f"  WHT found correct:    {'✓' if wht_best == seed else '✗'}")
    print()
    return match


# In[13]:


print("STEP 1: CORRECTNESS VERIFICATION\n")
ok = verify_wht_correctness()
if not ok:
    raise RuntimeError("WHT verification failed!")


# ## 9. Comparison Engine

# In[14]:


def compute_95ci(data: np.ndarray) -> Tuple[float, float, float]:
    """
    Compute mean and 95% confidence interval for a data array.
    Returns: (mean, ci_lower, ci_upper)
    Uses t-distribution for small samples, normal for large.
    """
    n = len(data)
    mean = np.mean(data)
    if n < 2:
        return mean, mean, mean
    se = stats.sem(data)  # standard error of the mean
    # 95% CI using t-distribution
    ci = stats.t.interval(0.95, df=n - 1, loc=mean, scale=se)
    return mean, ci[0], ci[1]


def run_comparison(
    configs: List[Tuple[int, List[int]]],
    keystream_lengths: List[int],
    n_trials: int = 100,
    K: int = 5,
    verbose: bool = True
) -> Tuple[list, list]:
    """3-way comparison: Standard Correlation vs FCA vs Cascade WHT.

    Reports mean ± 95% confidence interval (CI) for all timing metrics.
    """
    total_bits = sum(c[0] for c in configs)

    print("=" * 100)
    print("ATTACK COMPARISON: STANDARD CORRELATION vs FCA (MEIER-STAFFELBACH) vs CASCADE WHT")
    print("=" * 100)
    print("LFSR Configuration:")
    for i, (length, taps) in enumerate(configs):
        print(f"  LFSR{i+1}: {length}-bit, taps={taps}")
    print(f"Total key space: {total_bits} bits")
    search_sizes = [f"{(1 << c[0]) - 1}" for c in configs]
    print(f"Search space per LFSR: {' + '.join(search_sizes)} = "
          f"{sum((1 << c[0]) - 1 for c in configs)} seeds")
    print(f"Keystream lengths: {keystream_lengths}")
    print(f"Trials per length: {n_trials}")
    print(f"Statistical reporting: mean ± 95% CI (t-distribution)")
    print(f"Top-K candidates: {K} → {K**3} verification combos")
    for length, _ in configs:
        M = max(int(np.sqrt(1 << length)), K + 1)
        print(f"  Pruning threshold for {length}-bit LFSR: M={M} "
              f"(from 2^{length}={1 << length})")
    print(f"\nAttacks:")
    print(f"  1. Standard Correlation — exhaustive O(N×2^L)")
    print(f"  2. FCA (Meier-Staffelbach) — iterative bit-flipping, no 2^L enumeration")
    print(f"  3. Cascade WHT — spectral pruning O(L×2^L + √(2^L)×N)")
    print()

    all_trials = []
    summary_rows = []
    total_experiments = len(keystream_lengths) * n_trials
    experiment_count = 0

    for ks_len in keystream_lengths:
        print("─" * 70)
        print(f"  Keystream length: {ks_len} bits")
        print("─" * 70)

        corr_results = []
        fca_results = []
        wht_results = []

        for trial in range(n_trials):
            cipher = StreamCipher(configs)
            secret_seeds = cipher.seeds
            keystream = cipher.generate_keystream(ks_len)

            # Attack 1: Standard exhaustive correlation
            corr_ok, corr_seeds, corr_time = correlation_attack(
                keystream, configs
            )

            # Attack 2: FCA (Meier-Staffelbach)
            fca_ok, fca_seeds, fca_time = fast_correlation_attack(
                keystream, configs
            )

            # Attack 3: Cascade WHT
            wht_ok, wht_seeds, wht_time, wht_diag = cascade_wht_attack(
                keystream, configs, K=K
            )

            corr_results.append((corr_ok, corr_time))
            fca_results.append((fca_ok, fca_time))
            wht_results.append((wht_ok, wht_time, wht_diag))

            trial_data = {
                'ks_len': ks_len,
                'trial': trial + 1,
                'secret_seeds': str(secret_seeds),
                'corr_success': corr_ok,
                'corr_time_ms': round(corr_time * 1000, 1),
                'fca_success': fca_ok,
                'fca_time_ms': round(fca_time * 1000, 1),
                'wht_success': wht_ok,
                'wht_time_ms': round(wht_time * 1000, 1),
                'wht_stage1_ms': round(wht_diag['stage1_time'] * 1000, 1),
                'wht_stage2_ms': round(wht_diag['stage2_time'] * 1000, 1),
                'wht_stage3_ms': round(wht_diag['stage3_time'] * 1000, 1),
                'speedup_vs_corr': round(corr_time / wht_time, 2)
                    if wht_time > 0 else float('inf'),
                'speedup_vs_fca': round(fca_time / wht_time, 2)
                    if wht_time > 0 else float('inf'),
            }
            all_trials.append(trial_data)

            experiment_count += 1
            if verbose and ((trial + 1) % 10 == 0 or trial == n_trials - 1):
                corr_succ = sum(1 for ok, _ in corr_results if ok)
                fca_succ = sum(1 for ok, _ in fca_results if ok)
                wht_succ = sum(1 for ok, _, _ in wht_results if ok)
                pct = experiment_count / total_experiments * 100
                print(f"  [{pct:5.1f}%] Trial {trial+1:3d}/{n_trials}  "
                      f"Corr: {corr_succ}/{trial+1}  "
                      f"FCA: {fca_succ}/{trial+1}  "
                      f"WHT: {wht_succ}/{trial+1}  "
                      f"spd: {trial_data['speedup_vs_corr']:.1f}×")

        # --- Compute statistics with 95% CI ---
        corr_times_ms = np.array([t for _, t in corr_results]) * 1000
        fca_times_ms = np.array([t for _, t in fca_results]) * 1000
        wht_times_ms = np.array([t for _, t, _ in wht_results]) * 1000

        spd_corr_arr = np.array([
            ct / wt if wt > 0 else float('inf')
            for (_, ct), (_, wt, _) in zip(corr_results, wht_results)
        ])
        spd_fca_arr = np.array([
            ft / wt if wt > 0 else float('inf')
            for (_, ft), (_, wt, _) in zip(fca_results, wht_results)
        ])

        corr_rate = sum(1 for ok, _ in corr_results if ok) / n_trials * 100
        fca_rate = sum(1 for ok, _ in fca_results if ok) / n_trials * 100
        wht_rate = sum(1 for ok, _, _ in wht_results if ok) / n_trials * 100

        corr_mean, corr_ci_lo, corr_ci_hi = compute_95ci(corr_times_ms)
        fca_mean, fca_ci_lo, fca_ci_hi = compute_95ci(fca_times_ms)
        wht_mean, wht_ci_lo, wht_ci_hi = compute_95ci(wht_times_ms)
        spd_corr_mean, spd_corr_ci_lo, spd_corr_ci_hi = compute_95ci(spd_corr_arr)
        spd_fca_mean, spd_fca_ci_lo, spd_fca_ci_hi = compute_95ci(spd_fca_arr)

        corr_ci_half = (corr_ci_hi - corr_ci_lo) / 2
        fca_ci_half = (fca_ci_hi - fca_ci_lo) / 2
        wht_ci_half = (wht_ci_hi - wht_ci_lo) / 2

        # Wilson CI for success rates
        corr_succ_n = sum(1 for ok, _ in corr_results if ok)
        fca_succ_n = sum(1 for ok, _ in fca_results if ok)
        wht_succ_n = sum(1 for ok, _, _ in wht_results if ok)
        corr_rate_ci_lo, corr_rate_ci_hi = _wilson_ci(corr_succ_n, n_trials)
        fca_rate_ci_lo, fca_rate_ci_hi = _wilson_ci(fca_succ_n, n_trials)
        wht_rate_ci_lo, wht_rate_ci_hi = _wilson_ci(wht_succ_n, n_trials)

        summary = {
            'ks_len': ks_len,
            'n_trials': n_trials,
            # Standard correlation
            'corr_success_pct': round(corr_rate, 1),
            'corr_success_ci_lo': round(corr_rate_ci_lo, 1),
            'corr_success_ci_hi': round(corr_rate_ci_hi, 1),
            'corr_avg_ms': round(corr_mean, 1),
            'corr_ci_lo_ms': round(corr_ci_lo, 1),
            'corr_ci_hi_ms': round(corr_ci_hi, 1),
            'corr_ci_half_ms': round(corr_ci_half, 1),
            # FCA (Meier-Staffelbach)
            'fca_success_pct': round(fca_rate, 1),
            'fca_success_ci_lo': round(fca_rate_ci_lo, 1),
            'fca_success_ci_hi': round(fca_rate_ci_hi, 1),
            'fca_avg_ms': round(fca_mean, 1),
            'fca_ci_lo_ms': round(fca_ci_lo, 1),
            'fca_ci_hi_ms': round(fca_ci_hi, 1),
            'fca_ci_half_ms': round(fca_ci_half, 1),
            # Cascade WHT
            'wht_success_pct': round(wht_rate, 1),
            'wht_success_ci_lo': round(wht_rate_ci_lo, 1),
            'wht_success_ci_hi': round(wht_rate_ci_hi, 1),
            'wht_avg_ms': round(wht_mean, 1),
            'wht_ci_lo_ms': round(wht_ci_lo, 1),
            'wht_ci_hi_ms': round(wht_ci_hi, 1),
            'wht_ci_half_ms': round(wht_ci_half, 1),
            # Speedups
            'speedup_vs_corr_mean': round(spd_corr_mean, 2),
            'speedup_vs_corr_ci_lo': round(spd_corr_ci_lo, 2),
            'speedup_vs_corr_ci_hi': round(spd_corr_ci_hi, 2),
            'speedup_vs_fca_mean': round(spd_fca_mean, 2),
            'speedup_vs_fca_ci_lo': round(spd_fca_ci_lo, 2),
            'speedup_vs_fca_ci_hi': round(spd_fca_ci_hi, 2),
        }
        summary_rows.append(summary)

        print()
        print(f"  ► Correlation:  {corr_rate:.0f}% "
              f"[{corr_rate_ci_lo:.1f}%, {corr_rate_ci_hi:.1f}%]  "
              f"avg {corr_mean:.1f} ms  "
              f"95% CI [{corr_ci_lo:.1f}, {corr_ci_hi:.1f}]")
        print(f"  ► FCA (M-S):    {fca_rate:.0f}% "
              f"[{fca_rate_ci_lo:.1f}%, {fca_rate_ci_hi:.1f}%]  "
              f"avg {fca_mean:.1f} ms  "
              f"95% CI [{fca_ci_lo:.1f}, {fca_ci_hi:.1f}]")
        print(f"  ► Cascade WHT:  {wht_rate:.0f}% "
              f"[{wht_rate_ci_lo:.1f}%, {wht_rate_ci_hi:.1f}%]  "
              f"avg {wht_mean:.1f} ms  "
              f"95% CI [{wht_ci_lo:.1f}, {wht_ci_hi:.1f}]")
        print(f"  ► WHT speedup:  vs Corr {spd_corr_mean:.2f}×  "
              f"[{spd_corr_ci_lo:.2f}, {spd_corr_ci_hi:.2f}]  |  "
              f"vs FCA {spd_fca_mean:.2f}×  "
              f"[{spd_fca_ci_lo:.2f}, {spd_fca_ci_hi:.2f}]")
        print()

    # Final summary table
    print("\n" + "=" * 110)
    print(f"RESULTS SUMMARY  ({n_trials} trials per config, 95% CI)")
    print("=" * 110)
    print(f"{'KS':<6}│ {'Corr %':>6} {'Corr ms':>10} │ "
          f"{'FCA %':>6} {'FCA ms':>10} │ "
          f"{'WHT %':>6} {'WHT ms':>10} │ "
          f"{'vs Corr':>8} {'vs FCA':>8}")
    print("─" * 110)
    for s in summary_rows:
        print(
            f"{s['ks_len']:<6}│ "
            f"{s['corr_success_pct']:>5.0f}% {s['corr_avg_ms']:>9.1f} │ "
            f"{s['fca_success_pct']:>5.0f}% {s['fca_avg_ms']:>9.1f} │ "
            f"{s['wht_success_pct']:>5.0f}% {s['wht_avg_ms']:>9.1f} │ "
            f"{s['speedup_vs_corr_mean']:>7.1f}× "
            f"{s['speedup_vs_fca_mean']:>7.1f}×"
        )

    return all_trials, summary_rows


def _wilson_ci(successes: int, total: int,
               z: float = 1.96) -> Tuple[float, float]:
    """
    Wilson score confidence interval for a proportion (%).
    More accurate than normal approximation, especially near 0% or 100%.
    """
    if total == 0:
        return 0.0, 100.0
    p = successes / total
    denom = 1 + z**2 / total
    centre = (p + z**2 / (2 * total)) / denom
    margin = z * np.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denom
    lo = max(0.0, centre - margin) * 100
    hi = min(1.0, centre + margin) * 100
    return lo, hi


# ## 10. Run Comparison

# In[15]:


LFSR_40BIT = [
    (14, [0, 2, 5]),
    (13, [0, 3]),
    (13, [0, 1, 4]),
]

KEYSTREAM_LENGTHS = [200, 500, 800, 1500]
N_TRIALS = 100
K = 5

print("STEP 2: ATTACK COMPARISON\n")
all_trials, summary_rows = run_comparison(
    LFSR_40BIT, KEYSTREAM_LENGTHS,
    n_trials=N_TRIALS, K=K
)


# ## 11. Save Results

# In[16]:


def save_results_csv(all_trials, summary_rows):
    """Save per-trial and summary results to CSV with 95% CI (3-way)."""
    base_dir = os.getcwd()

    trial_path = os.path.join(base_dir, 'cascade_wht_trials.csv')
    with open(trial_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'ks_len', 'trial', 'secret_seeds',
            'corr_success', 'corr_time_ms',
            'fca_success', 'fca_time_ms',
            'wht_success', 'wht_time_ms',
            'wht_stage1_ms', 'wht_stage2_ms', 'wht_stage3_ms',
            'speedup_vs_corr', 'speedup_vs_fca'
        ])
        writer.writeheader()
        writer.writerows(all_trials)
    print(f"Per-trial results saved to '{trial_path}'")

    summary_path = os.path.join(base_dir, 'cascade_wht_summary.csv')
    with open(summary_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'ks_len', 'n_trials',
            'corr_success_pct', 'corr_success_ci_lo', 'corr_success_ci_hi',
            'corr_avg_ms', 'corr_ci_lo_ms', 'corr_ci_hi_ms', 'corr_ci_half_ms',
            'fca_success_pct', 'fca_success_ci_lo', 'fca_success_ci_hi',
            'fca_avg_ms', 'fca_ci_lo_ms', 'fca_ci_hi_ms', 'fca_ci_half_ms',
            'wht_success_pct', 'wht_success_ci_lo', 'wht_success_ci_hi',
            'wht_avg_ms', 'wht_ci_lo_ms', 'wht_ci_hi_ms', 'wht_ci_half_ms',
            'speedup_vs_corr_mean', 'speedup_vs_corr_ci_lo', 'speedup_vs_corr_ci_hi',
            'speedup_vs_fca_mean', 'speedup_vs_fca_ci_lo', 'speedup_vs_fca_ci_hi'
        ])
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"Summary results saved to '{summary_path}'")

print("\nSTEP 3: SAVING RESULTS\n")
save_results_csv(all_trials, summary_rows)


# ## 12. Visualization

# In[17]:


def plot_results(summary_rows):
    """Generate 4-panel comparison plot: 3 attacks with 95% CI."""
    ks_lens = [s['ks_len'] for s in summary_rows]
    n_trials = summary_rows[0]['n_trials']

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle(
        f'3-Way Attack Comparison ({n_trials} trials/config, 95% CI)\n'
        f'Standard Correlation vs FCA (Meier-Staffelbach) vs Cascade WHT',
        fontsize=13, fontweight='bold'
    )

    colors = {'corr': '#e74c3c', 'fca': '#f39c12', 'wht': '#2ecc71'}

    # --- Panel 1: Success Rate ---
    ax = axes[0, 0]
    for key, label, marker, ls in [
        ('corr', 'Correlation', 'o', '-'),
        ('fca', 'FCA (M-S)', 'D', '-.'),
        ('wht', 'Cascade WHT', 's', '--'),
    ]:
        rates = [s[f'{key}_success_pct'] for s in summary_rows]
        err_lo = [s[f'{key}_success_pct'] - s[f'{key}_success_ci_lo']
                  for s in summary_rows]
        err_hi = [s[f'{key}_success_ci_hi'] - s[f'{key}_success_pct']
                  for s in summary_rows]
        ax.errorbar(ks_lens, rates, yerr=[err_lo, err_hi],
                    fmt=f'{marker}{ls}', label=label, color=colors[key],
                    linewidth=2, capsize=4)
    ax.set_xlabel('Keystream Length (bits)')
    ax.set_ylabel('Success Rate (%)')
    ax.set_title('Success Rate (95% CI)')
    ax.legend()
    ax.set_ylim(-5, 105)
    ax.grid(True, alpha=0.3)

    # --- Panel 2: Execution Time ---
    ax = axes[0, 1]
    for key, label, marker, ls in [
        ('corr', 'Correlation', 'o', '-'),
        ('fca', 'FCA (M-S)', 'D', '-.'),
        ('wht', 'Cascade WHT', 's', '--'),
    ]:
        avgs = [s[f'{key}_avg_ms'] for s in summary_rows]
        ci_half = [s[f'{key}_ci_half_ms'] for s in summary_rows]
        ax.errorbar(ks_lens, avgs, yerr=ci_half,
                    fmt=f'{marker}{ls}', label=label, color=colors[key],
                    linewidth=2, capsize=4)
    ax.set_xlabel('Keystream Length (bits)')
    ax.set_ylabel('Average Time (ms)')
    ax.set_title('Execution Time (mean ± 95% CI)')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # --- Panel 3: Speedup vs Standard Correlation ---
    ax = axes[1, 0]
    speedups = [s['speedup_vs_corr_mean'] for s in summary_rows]
    spd_err_lo = [s['speedup_vs_corr_mean'] - s['speedup_vs_corr_ci_lo']
                  for s in summary_rows]
    spd_err_hi = [s['speedup_vs_corr_ci_hi'] - s['speedup_vs_corr_mean']
                  for s in summary_rows]
    bars = ax.bar(range(len(ks_lens)), speedups, color=colors['wht'],
                  alpha=0.8, yerr=[spd_err_lo, spd_err_hi],
                  capsize=5, ecolor='#2c3e50')
    for i, (bar, sp) in enumerate(zip(bars, speedups)):
        ax.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + spd_err_hi[i] + 1.0,
                f'{sp:.1f}×', ha='center', va='bottom',
                fontweight='bold', fontsize=9)
    ax.set_xticks(range(len(ks_lens)))
    ax.set_xticklabels([str(k) for k in ks_lens])
    ax.set_xlabel('Keystream Length (bits)')
    ax.set_ylabel('Speedup Factor')
    ax.set_title('WHT Speedup vs Standard Correlation')
    ax.axhline(y=1.0, color='red', linestyle='--', alpha=0.5)
    ax.grid(True, alpha=0.3, axis='y')

    # --- Panel 4: Speedup vs FCA ---
    ax = axes[1, 1]
    speedups_fca = [s['speedup_vs_fca_mean'] for s in summary_rows]
    spd_fca_err_lo = [s['speedup_vs_fca_mean'] - s['speedup_vs_fca_ci_lo']
                      for s in summary_rows]
    spd_fca_err_hi = [s['speedup_vs_fca_ci_hi'] - s['speedup_vs_fca_mean']
                      for s in summary_rows]
    bars = ax.bar(range(len(ks_lens)), speedups_fca, color='#3498db',
                  alpha=0.8, yerr=[spd_fca_err_lo, spd_fca_err_hi],
                  capsize=5, ecolor='#2c3e50')
    for i, (bar, sp) in enumerate(zip(bars, speedups_fca)):
        ax.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + spd_fca_err_hi[i] + 0.3,
                f'{sp:.1f}×', ha='center', va='bottom',
                fontweight='bold', fontsize=9)
    ax.set_xticks(range(len(ks_lens)))
    ax.set_xticklabels([str(k) for k in ks_lens])
    ax.set_xlabel('Keystream Length (bits)')
    ax.set_ylabel('Speedup Factor')
    ax.set_title('WHT Speedup vs FCA (Meier-Staffelbach)')
    ax.axhline(y=1.0, color='red', linestyle='--', alpha=0.5,
               label='1.0× (no speedup)')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plot_path = os.path.join(os.getcwd(), 'cascade_wht_comparison.png')
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"\nPlot saved to '{plot_path}'")
    plt.show()

print("\nSTEP 4: VISUALIZATION\n")
plot_results(summary_rows)

print("\n✓ Done!")

