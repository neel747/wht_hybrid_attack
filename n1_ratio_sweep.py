#!/usr/bin/env python3
"""
W6 Fix (v2): N₁ Parameter Sweep — Theory-Driven Analysis
==========================================================
Replaces the original ratio-based sweep with:
  1. Absolute N₁ sweep (not N₁/N ratios) — consistent with Corollary 1
  2. Multiple correlation strengths p = {0.75, 0.625, 0.56}
  3. 100 trials per configuration (was 30)
  4. Joint (N₁, M) heatmap for optimal operating point
  5. Overlay of theoretical P_survive curve on empirical data

The key insight from Corollary 1 is that N₁_min depends on L, M, and p,
NOT on N. This script validates that claim empirically.

Usage:
    python n1_ratio_sweep.py
"""

import numpy as np
import time
import csv
import os
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from scipy import stats
from typing import List, Tuple, Optional

from cascade_wht_attack import (
    LFSR, StreamCipher,
    wht_spectral_pruning, precise_correlation_on_survivors,
    compute_95ci, _wilson_ci, compute_optimal_n1
)


# ─────────────────────────────────────────────────────────────
# Modified cascade attack with configurable N₁ and M
# ─────────────────────────────────────────────────────────────

def cascade_wht_attack_custom(
    keystream: np.ndarray,
    configs: List[Tuple[int, List[int]]],
    n1_absolute: int = 100,
    M_override: int = None,
    K: int = 5
) -> Tuple[bool, Optional[Tuple[int, ...]], float, dict]:
    """
    Cascade WHT attack with configurable absolute N₁ and optional M override.

    Args:
        keystream: observed keystream bits
        configs: list of (length, taps) for each LFSR
        n1_absolute: absolute number of keystream bits for Stage 1
        M_override: if set, use this M instead of √(2^L)
        K: number of top candidates per LFSR
    """
    start = time.perf_counter()
    N = len(keystream)
    N1 = min(n1_absolute, N)  # Can't exceed available keystream

    diagnostics = {
        'N': N, 'N1': N1,
        'stage1_time': 0, 'stage2_time': 0, 'stage3_time': 0,
        'M_values': []
    }

    top_candidates = []

    for length, taps in configs:
        M = M_override if M_override else max(int(np.sqrt(1 << length)), K + 1)
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


# ─────────────────────────────────────────────────────────────
# Theoretical P_survive calculator
# ─────────────────────────────────────────────────────────────

def theoretical_survival(N1: int, L: int, M: int, p: float) -> float:
    """Compute P_survive from Theorem 1 of pruning_theorem.md."""
    epsilon = 2 * p - 1
    if epsilon <= 0 or N1 <= 0:
        return 0.0

    tail_prob = M / (2.0 * (1 << L))
    tau = np.sqrt(N1) * stats.norm.isf(tail_prob)

    mean_correct = N1 * epsilon
    std_correct = np.sqrt(N1 * (1 - epsilon**2))

    if std_correct == 0:
        return 1.0 if mean_correct > tau else 0.0

    z_score = (mean_correct - tau) / std_correct
    return stats.norm.cdf(z_score)


# ─────────────────────────────────────────────────────────────
# Sweep Configuration
# ─────────────────────────────────────────────────────────────

LFSR_40BIT = [
    (14, [0, 2, 5]),
    (13, [0, 3]),
    (13, [0, 1, 4]),
]

# Fix 2: Absolute N₁ values (not ratios) — maps directly to Corollary 1
N1_VALUES = [30, 40, 50, 60, 70, 80, 100, 125, 150, 200, 250, 300]

# Fix 3: Multiple correlation probabilities
P_CORR_VALUES = [0.75, 0.625, 0.56]
P_CORR_LABELS = {
    0.75: 'Majority (p=0.75, ε=0.50)',
    0.625: 'XOR-Majority Hybrid (p=0.625, ε=0.25)',
    0.56: 'Near-Corr-Immune (p=0.56, ε=0.12)',
}

# Fixed keystream length (long enough that N₁ is never bottlenecked by N)
KEYSTREAM_LENGTH = 1500

# Fix 4: 100 trials per configuration
N_TRIALS = 100
K = 5

# Fix 5: M values for joint heatmap
M_VALUES = [32, 64, 128, 256, 512]


# ─────────────────────────────────────────────────────────────
# Sweep 1: Absolute N₁ vs P_survive at multiple p
# ─────────────────────────────────────────────────────────────

def run_n1_absolute_sweep():
    """
    Sweep absolute N₁ values across multiple correlation strengths.
    This validates that the minimum N₁ is an absolute threshold
    (depends on L, M, p) and NOT a ratio of N.
    """
    L_max = max(c[0] for c in LFSR_40BIT)
    M_default = max(int(np.sqrt(1 << L_max)), K + 1)

    print("=" * 90)
    print("W6 FIX v2: ABSOLUTE N₁ PARAMETER SWEEP (THEORY-DRIVEN)")
    print("=" * 90)
    print(f"LFSR Configuration: {LFSR_40BIT}")
    print(f"Keystream length: N={KEYSTREAM_LENGTH} (fixed, long enough)")
    print(f"N₁ values (absolute): {N1_VALUES}")
    print(f"Correlation probabilities: {P_CORR_VALUES}")
    print(f"M = {M_default} (= √(2^{L_max}))")
    print(f"Trials per config: {N_TRIALS}")
    print(f"Total experiments: {len(N1_VALUES) * len(P_CORR_VALUES) * N_TRIALS}")
    print()

    # Print theory predictions first
    print("─" * 70)
    print("THEORETICAL PREDICTIONS (Corollary 1)")
    print("─" * 70)
    for p in P_CORR_VALUES:
        n1_min = compute_optimal_n1(L_max, M_default, p_corr=p, target_survival=0.99)
        eps = 2 * p - 1
        print(f"  p={p:.3f} (ε={eps:.3f}): N₁_min = {n1_min} bits for 99% survival")
    print()

    all_results = []

    for p_corr in P_CORR_VALUES:
        eps = 2 * p_corr - 1
        n1_theory = compute_optimal_n1(L_max, M_default, p_corr=p_corr,
                                        target_survival=0.99)
        print(f"\n{'─' * 70}")
        print(f"  p = {p_corr} (ε = {eps:.3f})  |  N₁_theory = {n1_theory}")
        print(f"{'─' * 70}")

        for n1 in N1_VALUES:
            successes = 0
            times = []

            # Compute theoretical P_survive for this point
            p_theory = theoretical_survival(n1, L_max, M_default, p_corr)

            for trial in range(N_TRIALS):
                # Generate cipher with majority function (p=0.75)
                # For p < 0.75, we simulate by adding noise to keystream
                cipher = StreamCipher(LFSR_40BIT)
                keystream = cipher.generate_keystream(KEYSTREAM_LENGTH)

                # If testing lower correlation, add noise to simulate
                if p_corr < 0.75:
                    # Current correlation is 0.75. We need to reduce it.
                    # Apply BSC with crossover prob to get effective p_corr
                    # p_eff = p_orig * p_bsc + (1-p_orig) * (1-p_bsc)
                    # Solving: p_bsc = (p_corr - 0.25) / 0.5  (for p_orig=0.75)
                    p_bsc = (p_corr - 0.25) / 0.5
                    noise = np.random.choice([0, 1], size=KEYSTREAM_LENGTH,
                                              p=[p_bsc, 1-p_bsc])
                    keystream = keystream ^ noise.astype(np.uint8)

                ok, seeds, elapsed, diag = cascade_wht_attack_custom(
                    keystream, LFSR_40BIT, n1_absolute=n1, K=K
                )

                if ok:
                    successes += 1
                times.append(elapsed * 1000)

            times_arr = np.array(times)
            mean_t, ci_lo_t, ci_hi_t = compute_95ci(times_arr)
            rate = successes / N_TRIALS * 100
            rate_ci_lo, rate_ci_hi = _wilson_ci(successes, N_TRIALS)

            result = {
                'p_corr': p_corr,
                'epsilon': round(eps, 3),
                'n1_absolute': n1,
                'n1_theory_min': n1_theory,
                'p_theory': round(p_theory, 4),
                'success_pct': round(rate, 1),
                'success_ci_lo': round(rate_ci_lo, 1),
                'success_ci_hi': round(rate_ci_hi, 1),
                'avg_time_ms': round(mean_t, 1),
                'time_ci_lo_ms': round(ci_lo_t, 1),
                'time_ci_hi_ms': round(ci_hi_t, 1),
            }
            all_results.append(result)

            marker = "✓" if rate >= 99.0 else "○" if rate >= 90.0 else "✗"
            print(f"  {marker} N₁={n1:4d}  "
                  f"Success: {rate:5.1f}% [{rate_ci_lo:.1f}, {rate_ci_hi:.1f}]  "
                  f"Theory: {p_theory*100:5.1f}%  "
                  f"Time: {mean_t:7.1f}ms")

    return all_results


# ─────────────────────────────────────────────────────────────
# Sweep 2: Joint (N₁, M) Heatmap
# ─────────────────────────────────────────────────────────────

def run_joint_n1_m_sweep():
    """
    Fix 5: Joint sweep of N₁ and M to find the optimal operating point.
    Uses theoretical P_survive (validated by pruning_survival_analysis.py)
    to produce a heatmap without requiring exhaustive empirical runs.
    """
    L = max(c[0] for c in LFSR_40BIT)
    N = KEYSTREAM_LENGTH

    print("\n" + "=" * 70)
    print("JOINT (N₁, M) HEATMAP — Theoretical P_survive")
    print("=" * 70)

    n1_range = np.arange(30, 351, 10)
    m_range = M_VALUES

    results = {}
    for p_corr in [0.75, 0.625]:
        eps = 2 * p_corr - 1
        heatmap = np.zeros((len(m_range), len(n1_range)))

        for i, M in enumerate(m_range):
            for j, n1 in enumerate(n1_range):
                heatmap[i, j] = theoretical_survival(int(n1), L, M, p_corr)

        results[p_corr] = {
            'n1_range': n1_range,
            'm_range': m_range,
            'heatmap': heatmap,
        }

        print(f"\n  p={p_corr} (ε={eps:.2f}):")
        for i, M in enumerate(m_range):
            # Find minimum N₁ for 99% survival
            idx_99 = np.where(heatmap[i, :] >= 0.99)[0]
            if len(idx_99) > 0:
                n1_99 = n1_range[idx_99[0]]
                print(f"    M={M:4d}: N₁_min(99%) = {n1_99:4d}")
            else:
                print(f"    M={M:4d}: N₁_min(99%) > {n1_range[-1]}")

    return results


# ─────────────────────────────────────────────────────────────
# Save CSV
# ─────────────────────────────────────────────────────────────

def save_sweep_csv(results):
    path = os.path.join(os.getcwd(), 'n1_ratio_sweep.csv')
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'p_corr', 'epsilon', 'n1_absolute', 'n1_theory_min',
            'p_theory',
            'success_pct', 'success_ci_lo', 'success_ci_hi',
            'avg_time_ms', 'time_ci_lo_ms', 'time_ci_hi_ms',
        ])
        writer.writeheader()
        writer.writerows(results)
    print(f"\nResults saved to '{path}'")


# ─────────────────────────────────────────────────────────────
# Visualization: 3-panel + heatmap
# ─────────────────────────────────────────────────────────────

def plot_sweep(results, heatmap_data):
    """
    Generate publication-quality plots:
      Panel 1: Empirical success rate vs absolute N₁ (all p values)
      Panel 2: Theory vs Empirical overlay
      Panel 3: Execution time vs N₁
      Panel 4: Joint (N₁, M) heatmap
    """
    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    fig.suptitle(
        f'N₁ Parameter Analysis ({N_TRIALS} trials/config, 95% CI)\n'
        f'Absolute N₁ Threshold — Theory-Driven Selection',
        fontsize=14, fontweight='bold'
    )

    colors = {0.75: '#1f77b4', 0.625: '#ff7f0e', 0.56: '#2ca02c'}
    L_max = max(c[0] for c in LFSR_40BIT)
    M_default = max(int(np.sqrt(1 << L_max)), K + 1)

    # --- Panel 1: Success Rate vs Absolute N₁ ---
    ax = axes[0, 0]
    for p_corr in P_CORR_VALUES:
        subset = [r for r in results if r['p_corr'] == p_corr]
        n1s = [r['n1_absolute'] for r in subset]
        rates = [r['success_pct'] for r in subset]
        err_lo = [r['success_pct'] - r['success_ci_lo'] for r in subset]
        err_hi = [r['success_ci_hi'] - r['success_pct'] for r in subset]

        ax.errorbar(n1s, rates, yerr=[err_lo, err_hi],
                    fmt='o-', label=P_CORR_LABELS[p_corr], color=colors[p_corr],
                    linewidth=2, capsize=4, markersize=5)

        # Mark theory-predicted N₁_min
        n1_min = compute_optimal_n1(L_max, M_default, p_corr=p_corr,
                                     target_survival=0.99)
        ax.axvline(x=n1_min, color=colors[p_corr], linestyle=':', alpha=0.6)

    ax.set_xlabel('Absolute N₁ (bits used for WHT Stage 1)', fontsize=11)
    ax.set_ylabel('Success Rate (%)', fontsize=11)
    ax.set_title('Empirical Success Rate vs Absolute N₁')
    ax.set_ylim(-5, 105)
    ax.legend(fontsize=8, loc='lower right')
    ax.grid(True, alpha=0.3)

    # --- Panel 2: Theory vs Empirical Overlay ---
    ax = axes[0, 1]
    n1_smooth = np.linspace(20, 350, 200)
    for p_corr in P_CORR_VALUES:
        subset = [r for r in results if r['p_corr'] == p_corr]
        n1s = [r['n1_absolute'] for r in subset]
        rates_emp = [r['success_pct'] / 100 for r in subset]

        # Smooth theoretical curve
        p_theory_curve = [theoretical_survival(int(n), L_max, M_default, p_corr)
                          for n in n1_smooth]

        ax.plot(n1_smooth, [p * 100 for p in p_theory_curve], '--',
                color=colors[p_corr], label=f'Theory (p={p_corr})', linewidth=2)
        ax.scatter(n1s, [r * 100 for r in rates_emp],
                   color=colors[p_corr], marker='o', s=40, zorder=5,
                   label=f'Empirical (p={p_corr})')

    ax.axhline(99, color='k', linestyle=':', alpha=0.5, label='99% target')
    ax.set_xlabel('Absolute N₁ (bits)', fontsize=11)
    ax.set_ylabel('Survival Probability (%)', fontsize=11)
    ax.set_title('Theory vs Empirical: P_survive')
    ax.set_ylim(-5, 105)
    ax.legend(fontsize=7, loc='lower right')
    ax.grid(True, alpha=0.3)

    # --- Panel 3: Execution Time vs N₁ ---
    ax = axes[1, 0]
    for p_corr in P_CORR_VALUES:
        subset = [r for r in results if r['p_corr'] == p_corr]
        n1s = [r['n1_absolute'] for r in subset]
        times = [r['avg_time_ms'] for r in subset]
        t_err_lo = [r['avg_time_ms'] - r['time_ci_lo_ms'] for r in subset]
        t_err_hi = [r['time_ci_hi_ms'] - r['avg_time_ms'] for r in subset]

        ax.errorbar(n1s, times, yerr=[t_err_lo, t_err_hi],
                    fmt='s-', label=f'p={p_corr}', color=colors[p_corr],
                    linewidth=2, capsize=4, markersize=5)

    ax.set_xlabel('Absolute N₁ (bits)', fontsize=11)
    ax.set_ylabel('Execution Time (ms)', fontsize=11)
    ax.set_title('Execution Time vs N₁')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # --- Panel 4: Joint (N₁, M) Heatmap ---
    ax = axes[1, 1]
    # Use p=0.75 heatmap
    if 0.75 in heatmap_data:
        data = heatmap_data[0.75]
        n1r = data['n1_range']
        mr = data['m_range']
        hm = data['heatmap']

        cmap = LinearSegmentedColormap.from_list(
            'survival', ['#d73027', '#fee08b', '#1a9850'], N=256
        )
        im = ax.imshow(hm, aspect='auto', cmap=cmap, vmin=0, vmax=1,
                       extent=[n1r[0], n1r[-1], len(mr) - 0.5, -0.5],
                       interpolation='nearest')
        ax.set_yticks(range(len(mr)))
        ax.set_yticklabels([str(m) for m in mr])
        ax.set_xlabel('Absolute N₁ (bits)', fontsize=11)
        ax.set_ylabel('M (survivors)', fontsize=11)
        ax.set_title('P_survive Heatmap (p=0.75)')
        plt.colorbar(im, ax=ax, label='P_survive')

        # Draw 99% contour
        for i in range(len(mr)):
            idx = np.where(hm[i, :] >= 0.99)[0]
            if len(idx) > 0:
                ax.axvline(x=n1r[idx[0]], color='white', alpha=0.3,
                           linewidth=0.5)
                ax.plot(n1r[idx[0]], i, 'w*', markersize=8)

    plt.tight_layout()
    plot_path = os.path.join(os.getcwd(), 'n1_ratio_sweep.png')
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"Plot saved to '{plot_path}'")
    plt.close()


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    # Sweep 1: Absolute N₁ at multiple p values
    results = run_n1_absolute_sweep()
    save_sweep_csv(results)

    # Sweep 2: Joint (N₁, M) heatmap
    heatmap_data = run_joint_n1_m_sweep()

    # Plot everything
    plot_sweep(results, heatmap_data)

    # Summary
    L_max = max(c[0] for c in LFSR_40BIT)
    M_default = max(int(np.sqrt(1 << L_max)), K + 1)

    print("\n" + "=" * 70)
    print("SUMMARY: THEORY-DRIVEN N₁ SELECTION")
    print("=" * 70)
    for p in P_CORR_VALUES:
        eps = 2 * p - 1
        n1_min = compute_optimal_n1(L_max, M_default, p_corr=p,
                                     target_survival=0.99)
        # Find empirical minimum for 100% success
        subset = [r for r in results if r['p_corr'] == p and r['success_pct'] >= 100.0]
        if subset:
            n1_emp = min(r['n1_absolute'] for r in subset)
        else:
            best = max([r for r in results if r['p_corr'] == p],
                       key=lambda r: r['success_pct'])
            n1_emp = f"{best['n1_absolute']} ({best['success_pct']:.0f}%)"

        print(f"  p={p:.3f} (ε={eps:.3f}):  "
              f"Theory N₁_min = {n1_min:4d}  |  "
              f"Empirical N₁_min(100%) = {n1_emp}")

    print("\n✓ W6 parameter sweep complete (v2 — theory-driven)!")
