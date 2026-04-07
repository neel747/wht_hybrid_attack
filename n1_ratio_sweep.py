#!/usr/bin/env python3
"""
W6 Fix: N₁/N Ratio Parameter Sweep
====================================
Varies the fraction of keystream used in Stage 1 (WHT pruning) from 0.1 to 0.9
and measures success rate + execution time at each ratio.

Goal: Find the optimal N₁/N split and replace the arbitrary N/4 choice
      with an empirically justified value.

Usage:
    python n1_ratio_sweep.py
"""

import numpy as np
import time
import csv
import os
import matplotlib.pyplot as plt
from scipy import stats

# Import attack components from main module (without triggering the comparison run)
import importlib
import sys

# We need to import just the classes/functions, not run the module-level code.
# So we'll copy the essential pieces or use importlib tricks.
# Safest: import the module but it will run — let's just define what we need inline.

from cascade_wht_attack import (
    LFSR, StreamCipher,
    wht_spectral_pruning, precise_correlation_on_survivors,
    compute_95ci, _wilson_ci
)
from typing import List, Tuple, Optional


# ─────────────────────────────────────────────────────────────
# Modified cascade attack with configurable N₁/N ratio
# ─────────────────────────────────────────────────────────────

def cascade_wht_attack_custom_ratio(
    keystream: np.ndarray,
    configs: List[Tuple[int, List[int]]],
    n1_ratio: float = 0.25,
    K: int = 5
) -> Tuple[bool, Optional[Tuple[int, ...]], float, dict]:
    """
    Cascade WHT attack with configurable N₁/N ratio.

    Args:
        keystream: observed keystream bits
        configs: list of (length, taps) for each LFSR
        n1_ratio: fraction of keystream to use for Stage 1 (0.0 to 1.0)
        K: number of top candidates per LFSR
    """
    start = time.perf_counter()
    N = len(keystream)
    N1 = max(int(N * n1_ratio), 30)  # at least 30 bits for CLT validity

    diagnostics = {
        'N': N, 'N1': N1, 'n1_ratio': n1_ratio,
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


# ─────────────────────────────────────────────────────────────
# Sweep Configuration
# ─────────────────────────────────────────────────────────────

LFSR_40BIT = [
    (14, [0, 2, 5]),
    (13, [0, 3]),
    (13, [0, 1, 4]),
]

RATIOS = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]
KEYSTREAM_LENGTHS = [200, 500, 800, 1500]
N_TRIALS = 30
K = 5


# ─────────────────────────────────────────────────────────────
# Run Sweep
# ─────────────────────────────────────────────────────────────

def run_n1_sweep():
    """Run the N₁/N ratio parameter sweep."""

    print("=" * 90)
    print("W6 FIX: N₁/N RATIO PARAMETER SWEEP")
    print("=" * 90)
    print(f"LFSR Configuration: {LFSR_40BIT}")
    print(f"Keystream lengths: {KEYSTREAM_LENGTHS}")
    print(f"N₁/N ratios: {RATIOS}")
    print(f"Trials per config: {N_TRIALS}")
    print(f"Total experiments: {len(RATIOS) * len(KEYSTREAM_LENGTHS) * N_TRIALS}")
    print()

    all_results = []

    for ks_len in KEYSTREAM_LENGTHS:
        print(f"\n{'─' * 70}")
        print(f"  Keystream length: {ks_len} bits")
        print(f"{'─' * 70}")

        for ratio in RATIOS:
            successes = 0
            times = []

            for trial in range(N_TRIALS):
                cipher = StreamCipher(LFSR_40BIT)
                keystream = cipher.generate_keystream(ks_len)

                ok, seeds, elapsed, diag = cascade_wht_attack_custom_ratio(
                    keystream, LFSR_40BIT, n1_ratio=ratio, K=K
                )

                if ok:
                    successes += 1
                times.append(elapsed * 1000)  # ms

            times_arr = np.array(times)
            mean_t, ci_lo_t, ci_hi_t = compute_95ci(times_arr)
            rate = successes / N_TRIALS * 100
            rate_ci_lo, rate_ci_hi = _wilson_ci(successes, N_TRIALS)

            result = {
                'ks_len': ks_len,
                'n1_ratio': ratio,
                'n1_bits': int(ks_len * ratio),
                'success_pct': round(rate, 1),
                'success_ci_lo': round(rate_ci_lo, 1),
                'success_ci_hi': round(rate_ci_hi, 1),
                'avg_time_ms': round(mean_t, 1),
                'time_ci_lo_ms': round(ci_lo_t, 1),
                'time_ci_hi_ms': round(ci_hi_t, 1),
            }
            all_results.append(result)

            print(f"  N₁/N={ratio:.2f} (N₁={int(ks_len*ratio):4d})  "
                  f"Success: {rate:5.1f}% [{rate_ci_lo:.1f}, {rate_ci_hi:.1f}]  "
                  f"Time: {mean_t:7.1f}ms [{ci_lo_t:.1f}, {ci_hi_t:.1f}]")

    return all_results


# ─────────────────────────────────────────────────────────────
# Save CSV
# ─────────────────────────────────────────────────────────────

def save_sweep_csv(results):
    path = os.path.join(os.getcwd(), 'n1_ratio_sweep.csv')
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'ks_len', 'n1_ratio', 'n1_bits',
            'success_pct', 'success_ci_lo', 'success_ci_hi',
            'avg_time_ms', 'time_ci_lo_ms', 'time_ci_hi_ms',
        ])
        writer.writeheader()
        writer.writerows(results)
    print(f"\nResults saved to '{path}'")


# ─────────────────────────────────────────────────────────────
# Visualization
# ─────────────────────────────────────────────────────────────

def plot_sweep(results):
    """Generate 2-panel plot: success rate & time vs N₁/N ratio."""

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle(
        f'W6: N₁/N Ratio Parameter Sweep ({N_TRIALS} trials/config, 95% CI)\n'
        f'Finding the Optimal Stage 1 Keystream Fraction',
        fontsize=13, fontweight='bold'
    )

    colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(KEYSTREAM_LENGTHS)))

    # --- Panel 1: Success Rate vs Ratio ---
    ax = axes[0]
    for i, ks_len in enumerate(KEYSTREAM_LENGTHS):
        subset = [r for r in results if r['ks_len'] == ks_len]
        ratios = [r['n1_ratio'] for r in subset]
        rates = [r['success_pct'] for r in subset]
        err_lo = [r['success_pct'] - r['success_ci_lo'] for r in subset]
        err_hi = [r['success_ci_hi'] - r['success_pct'] for r in subset]

        ax.errorbar(ratios, rates, yerr=[err_lo, err_hi],
                    fmt='o-', label=f'N={ks_len}', color=colors[i],
                    linewidth=2, capsize=4, markersize=6)

    ax.axvline(x=0.25, color='red', linestyle='--', alpha=0.6,
               label='Current (N/4)')
    ax.set_xlabel('N₁/N Ratio (fraction used for WHT Stage 1)', fontsize=11)
    ax.set_ylabel('Success Rate (%)', fontsize=11)
    ax.set_title('Success Rate vs N₁/N Ratio')
    ax.set_ylim(-5, 105)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # --- Panel 2: Execution Time vs Ratio ---
    ax = axes[1]
    for i, ks_len in enumerate(KEYSTREAM_LENGTHS):
        subset = [r for r in results if r['ks_len'] == ks_len]
        ratios = [r['n1_ratio'] for r in subset]
        times = [r['avg_time_ms'] for r in subset]
        t_err_lo = [r['avg_time_ms'] - r['time_ci_lo_ms'] for r in subset]
        t_err_hi = [r['time_ci_hi_ms'] - r['avg_time_ms'] for r in subset]

        ax.errorbar(ratios, times, yerr=[t_err_lo, t_err_hi],
                    fmt='s-', label=f'N={ks_len}', color=colors[i],
                    linewidth=2, capsize=4, markersize=6)

    ax.axvline(x=0.25, color='red', linestyle='--', alpha=0.6,
               label='Current (N/4)')
    ax.set_xlabel('N₁/N Ratio (fraction used for WHT Stage 1)', fontsize=11)
    ax.set_ylabel('Execution Time (ms)', fontsize=11)
    ax.set_title('Execution Time vs N₁/N Ratio')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plot_path = os.path.join(os.getcwd(), 'n1_ratio_sweep.png')
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"Plot saved to '{plot_path}'")
    plt.show()


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    results = run_n1_sweep()
    save_sweep_csv(results)
    plot_sweep(results)

    # Find optimal ratio per keystream length
    print("\n" + "=" * 70)
    print("OPTIMAL N₁/N RATIOS")
    print("=" * 70)
    for ks_len in KEYSTREAM_LENGTHS:
        subset = [r for r in results if r['ks_len'] == ks_len]
        # Among configs with 100% success, pick the fastest
        perfect = [r for r in subset if r['success_pct'] >= 100.0]
        if perfect:
            best = min(perfect, key=lambda r: r['avg_time_ms'])
            print(f"  N={ks_len:5d}: optimal N₁/N = {best['n1_ratio']:.2f} "
                  f"(N₁={best['n1_bits']}, time={best['avg_time_ms']:.1f}ms)")
        else:
            # Pick highest success rate
            best = max(subset, key=lambda r: r['success_pct'])
            print(f"  N={ks_len:5d}: best N₁/N = {best['n1_ratio']:.2f} "
                  f"(success={best['success_pct']:.1f}%, "
                  f"time={best['avg_time_ms']:.1f}ms)")

    print("\n✓ W6 parameter sweep complete!")
