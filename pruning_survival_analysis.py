#!/usr/bin/env python3
"""
W2 Fix: Validation of Pruning Survival Theorem
==============================================
This script empirically validates Theorem 1 from `pruning_theorem.md`.
It directly tests if the correct LFSR seed survives the Fast Walsh-Hadamard
Transform (FWHT) spectral pruning stage by comparing monte-carlo simulation
results against the theoretical closed-form probability.

Usage:
    python pruning_survival_analysis.py
"""

import numpy as np
import scipy.stats as stats
import matplotlib.pyplot as plt
import csv
import os
import time

from cascade_wht_attack import LFSR, fwht, wht_spectral_pruning

# ─────────────────────────────────────────────────────────────
# 1. Theoretical Calculator (Theorem 1)
# ─────────────────────────────────────────────────────────────

def theoretical_survival_probability(N1: int, L: int, M: int, p: float) -> float:
    """
    Computes P_survive from Theorem 1.
    
    P_survive = Φ( (N₁ε - τ) / √(N₁(1 - ε²)) )
    where:
      ε = 2p - 1
      τ = √N₁ * Φ⁻¹(1 - M/(2*2^L))
    """
    if N1 <= 0: return 0.0
    
    epsilon = 2 * p - 1
    
    # 1. Compute pruning threshold τ
    # We use sf (survival function, 1-cdf) instead of cdf to avoid precision issues
    # for extremely small probabilities. 1 - (M / (2*2^L)) is the CDF point.
    tail_prob = M / (2.0 * (1 << L))
    tau = np.sqrt(N1) * stats.norm.isf(tail_prob)
    
    # 2. Compute signal mean and standard deviation
    mean_correct = N1 * epsilon
    std_correct = np.sqrt(N1 * (1 - epsilon**2))
    
    if std_correct == 0:
        return 1.0 if mean_correct > tau else 0.0
        
    # 3. Compute survival probability
    z_score = (mean_correct - tau) / std_correct
    p_survive = stats.norm.cdf(z_score)
    
    return p_survive


# ─────────────────────────────────────────────────────────────
# 2. Empricial Monte-Carlo Validator
# ─────────────────────────────────────────────────────────────

def empirical_survival_probability(
    L: int, taps: list, N1: int, M: int, p: float, n_trials: int = 1000
) -> tuple:
    """
    Runs monte carlo trials of Stage 1 to see how often the correct seed
    makes it into the top-M candidates.
    """
    sys_rand = np.random.default_rng()
    success_count = 0
    start = time.perf_counter()
    
    for _ in range(n_trials):
        # 1. Pick a random correct seed
        s_star = sys_rand.integers(1, 1 << L)
        
        # 2. Generate correct LFSR output
        lfsr = LFSR(L, taps, s_star)
        x = lfsr.generate(N1)
        
        # 3. Apply binary symmetric channel to simulate correlation
        # Flip bits with probability 1-p
        noise = sys_rand.choice([0, 1], size=N1, p=[p, 1-p])
        z = x ^ noise
        
        # 4. Run Stage 1 WHT pruning
        survivors = wht_spectral_pruning(L, taps, z, N1, M)
        
        # 5. Check survival
        if s_star in survivors:
            success_count += 1
            
    elapsed = time.perf_counter() - start
    empirical_p = success_count / n_trials
    
    # Compute 95% Wilson score interval for empirical proportion
    z_95 = 1.96
    denominator = 1 + z_95**2 / n_trials
    center = (empirical_p + z_95**2 / (2 * n_trials)) / denominator
    spread = z_95 * np.sqrt(empirical_p * (1 - empirical_p) / n_trials + z_95**2 / (4 * n_trials**2)) / denominator
    ci_lo = max(0.0, center - spread)
    ci_hi = min(1.0, center + spread)
    
    return empirical_p, ci_lo, ci_hi, elapsed


# ─────────────────────────────────────────────────────────────
# 3. Parameter Sweep Engine
# ─────────────────────────────────────────────────────────────

def run_validation_sweep():
    # Setup LFSR 14
    L = 14
    taps = [0, 2, 5]
    M = int(np.sqrt(1 << L))  # M = 128
    
    p_values = [0.75, 0.625, 0.56]  # Majority, Hybrid, Bent
    N1_range = np.arange(20, 301, 20)  # Sweeping N1 from 20 to 300
    n_trials = 500  # 500 trials per point for solid 95% CI
    
    print("=" * 80)
    print("W2 FIX: THEORETICAL VS EMPIRICAL PRUNING SURVIVAL")
    print("=" * 80)
    print(f"LFSR Length: {L} bits (M = {M})")
    print(f"Sweep N1: {N1_range[0]} to {N1_range[-1]} (steps of 20)")
    print(f"Monte Carlo Trials per point: {n_trials}")
    print()
    
    results = []
    
    for p in p_values:
        print(f"\nEvaluating Correlation Probability p = {p} (ε = {2*p-1:.3f})")
        print("-" * 75)
        print("   N1 | Theory_P | Empir_P | 95% CI Range     | Empir_P in CI? | Time")
        print("-" * 75)
        
        for N1 in N1_range:
            p_theory = theoretical_survival_probability(N1, L, M, p)
            
            p_emp, ci_lo, ci_hi, ms = empirical_survival_probability(
                L, taps, N1, M, p, n_trials
            )
            
            # Check if theory falls within empirical 95% CI
            in_ci = (ci_lo <= p_theory <= ci_hi) or \
                    (p_theory > 0.999 and p_emp == 1.0) or \
                    (p_theory < 0.001 and p_emp == 0.0)
            
            marker = "✓" if in_ci else "x"
            
            print(f" {N1:4d} |   {p_theory:5.3f}  |  {p_emp:5.3f}  | [{ci_lo:5.3f}, {ci_hi:5.3f}] |       {marker}        | {ms:4.1f}s")
            
            results.append({
                'L': L, 'M': M, 'p': p, 'N1': N1,
                'p_theory': p_theory,
                'p_empirical': p_emp,
                'ci_lo': ci_lo,
                'ci_hi': ci_hi
            })
            
    return results


# ─────────────────────────────────────────────────────────────
# 4. Plotting
# ─────────────────────────────────────────────────────────────

def plot_validation(results):
    plt.figure(figsize=(10, 6))
    
    p_values = sorted(list(set(r['p'] for r in results)), reverse=True)
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
    
    for idx, p in enumerate(p_values):
        subset = [r for r in results if r['p'] == p]
        n1 = [r['N1'] for r in subset]
        pt = [r['p_theory'] for r in subset]
        pe = [r['p_empirical'] for r in subset]
        ci_lo = [r['ci_lo'] for r in subset]
        ci_hi = [r['ci_hi'] for r in subset]
        
        # Plot theoretical curve (smooth line)
        plt.plot(n1, pt, '--', color=colors[idx], label=f'Theory (p={p})')
        
        # Plot empirical points with error bars
        yerr_lo = np.maximum(0, np.array(pe) - np.array(ci_lo))
        yerr_hi = np.maximum(0, np.array(ci_hi) - np.array(pe))
        plt.errorbar(n1, pe, yerr=[yerr_lo, yerr_hi], fmt='o', color=colors[idx], 
                     capsize=4, label=f'Empirical (p={p})')
                     
    plt.axhline(0.99, color='k', linestyle=':', alpha=0.5, label='99% Survival Target')
    
    plt.title('Validation of Pruning Survival Theorem (Theorem 1)', fontsize=14, fontweight='bold')
    plt.xlabel('Length of Keystream Used for Pruning (N₁)', fontsize=12)
    plt.ylabel('Probability of Correct Seed Surviving (P_survive)', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend(loc='lower right', framealpha=0.9)
    plt.ylim(-0.05, 1.05)
    
    plot_path = os.path.join(os.getcwd(), 'pruning_survival_validation.png')
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"\nPlot saved to '{plot_path}'")
    # plt.show()

# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    results = run_validation_sweep()
    plot_validation(results)
    
    csv_path = os.path.join(os.getcwd(), 'pruning_survival_validation.csv')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"Data saved to '{csv_path}'")
