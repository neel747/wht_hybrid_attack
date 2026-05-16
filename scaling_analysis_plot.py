import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.stats import norm
import os

def compute_theoretical_speedup(L, N, p=0.75):
    """
    Theoretical speedup of Cascade WHT over Standard Correlation.
    Standard: O(N * 2^L)
    Cascade:  O(L * 2^L + sqrt(2^L) * N)
    """
    standard = N * (2**L)
    # Using L * 2^L for WHT and sqrt(2^L) * N for Stage 2
    cascade = L * (2**L) + np.sqrt(2**L) * N
    return standard / cascade

def generate_scaling_plots():
    print("Generating Scaling Analysis Plots...")
    
    # --- 1. 3D Surface Plot: Speedup vs L and N ---
    L_range = np.arange(14, 31)
    N_range = np.arange(500, 5001, 500)
    L_grid, N_grid = np.meshgrid(L_range, N_range)
    
    speedup_grid = np.zeros_like(L_grid, dtype=float)
    for i in range(len(N_range)):
        for j in range(len(L_range)):
            speedup_grid[i, j] = compute_theoretical_speedup(L_grid[i, j], N_grid[i, j])
            
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    surf = ax.plot_surface(L_grid, N_grid, speedup_grid, cmap='viridis', edgecolor='none', alpha=0.8)
    
    ax.set_xlabel('LFSR Length (L)')
    ax.set_ylabel('Keystream Length (N)')
    ax.set_zlabel('Speedup Factor')
    ax.set_title('Theoretical Speedup: Cascade WHT vs Standard Correlation', fontsize=14, fontweight='bold')
    
    fig.colorbar(surf, ax=ax, shrink=0.5, aspect=5, label='Speedup Ratio')
    
    # Add a note about the trend
    ax.text2D(0.05, 0.95, "Trend: Speedup grows linearly with N and remains high as L scales.", 
              transform=ax.transAxes, fontsize=10, bbox=dict(facecolor='white', alpha=0.5))
    
    plot_path_3d = os.path.join(os.getcwd(), 'scaling_3d_surface.png')
    plt.savefig(plot_path_3d, dpi=150)
    print(f"  ✓ 3D Surface saved to '{plot_path_3d}'")
    
    # --- 2. Heatmap: Survival Probability (N1 vs M) for L=25 ---
    plt.figure(figsize=(10, 8))
    L = 25
    p = 0.75
    epsilon = 2*p - 1
    
    N1_vals = np.linspace(50, 500, 50)
    M_powers = np.linspace(5, 20, 50) # M = 2^power
    
    N1_grid, M_pow_grid = np.meshgrid(N1_vals, M_powers)
    prob_grid = np.zeros_like(N1_grid)
    
    for i in range(len(M_powers)):
        for j in range(len(N1_vals)):
            n1 = N1_grid[i, j]
            m = 2**M_pow_grid[i, j]
            
            # Threshold tau from Theorem
            tau = np.sqrt(n1) * norm.ppf(1 - m / (2 * 2**L))
            # Survival prob from Theorem
            prob = norm.cdf((n1 * epsilon - tau) / np.sqrt(n1 * (1 - epsilon**2)))
            prob_grid[i, j] = prob
            
    plt.pcolormesh(N1_vals, M_powers, prob_grid, cmap='RdYlGn', shading='auto')
    plt.colorbar(label='P(Survival)')
    
    # Contours for 99% and 90%
    cp = plt.contour(N1_vals, M_powers, prob_grid, levels=[0.9, 0.99], colors='white', linestyles='--')
    plt.clabel(cp, inline=True, fontsize=10)
    
    plt.xlabel('Partial Keystream Length (N1)')
    plt.ylabel('Candidate Set Size (log2 M)')
    plt.title(f'Pruning Survival Probability (L={L}, p={p})', fontsize=14, fontweight='bold')
    
    plot_path_heatmap = os.path.join(os.getcwd(), 'survival_n1_m_heatmap.png')
    plt.savefig(plot_path_heatmap, dpi=150)
    print(f"  ✓ Survival Heatmap saved to '{plot_path_heatmap}'")
    
    plt.show()

if __name__ == "__main__":
    generate_scaling_plots()
