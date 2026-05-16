# Abstract

## A Two-Stage Cascade Walsh-Hadamard Transform Correlation Attack on LFSR-Based Stream Ciphers

---

Stream ciphers employing Linear Feedback Shift Registers (LFSRs) with nonlinear combining functions are vulnerable to correlation attacks that exploit statistical dependencies between the keystream and individual LFSR outputs. The standard correlation attack requires O(N × 2^L) complexity, while the Fast Correlation Attack avoids exhaustive enumeration but is constrained by feedback polynomial structure. This thesis proposes a Two-Stage Cascade Walsh-Hadamard Transform (WHT) Correlation Attack. Stage 1 applies the Fast WHT on partial keystream to compute coarse correlations for all 2^L seeds in O(L × 2^L) time, pruning the search space to M = √(2^L) candidates. Stage 2 performs precise correlation exclusively on survivors, yielding total complexity O(L × 2^L + √(2^L) × N). A Pruning Survival Theorem is derived providing a closed-form survival probability, validated through Monte Carlo simulations within 95% confidence intervals. Experimental evaluation on a 40-bit three-LFSR generator over 100 trials demonstrates 78–102× speedup over standard correlation and 3.3–4.2× over the Fast Correlation Attack across three combining functions. Future work includes scaling to larger LFSR sizes and applicability to practical ciphers.

**Keywords:** Stream Cipher, LFSR, Correlation Attack, Walsh-Hadamard Transform, Spectral Pruning, Cryptanalysis.
