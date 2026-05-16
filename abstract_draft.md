# Abstract

## A Two-Stage Cascade Walsh-Hadamard Transform Correlation Attack on LFSR-Based Stream Ciphers

---

Stream ciphers employing Linear Feedback Shift Registers (LFSRs) with nonlinear combining functions are vulnerable to correlation attacks that exploit statistical dependencies between the keystream and individual LFSR outputs. The standard correlation attack requires O(N × 2^L) complexity, while Fast Correlation Attacks avoid exhaustive enumeration but are constrained by feedback polynomial weight. This thesis proposes a Two-Stage Cascade Walsh-Hadamard Transform (WHT) Correlation Attack that decouples keystream length from the search space. Stage 1 applies the Fast WHT on partial keystream to compute coarse correlations for all 2^L seeds in O(L × 2^L) time, pruning the space to M = √(2^L) candidates. Stage 2 performs precise correlation exclusively on survivors, yielding a total complexity of O(L × 2^L + √(2^L) × N). We derive a Pruning Survival Theorem providing a closed-form survival probability, validated through Monte Carlo simulations. The attack is implemented in Python with Numba JIT acceleration for research-scale verification. Experimental evaluation on a 75-bit three-LFSR generator (L=25) over 100 trials demonstrates substantial wall-clock speedups (up to 102×) over standard correlation and superior performance over Meier-Staffelbach FCA across multiple combining functions. Applicability to practical ciphers like Bluetooth E0 and GSM A5/1 is also discussed.

**Keywords:** Stream Cipher, LFSR, Correlation Attack, Walsh-Hadamard Transform, Spectral Pruning, Cryptanalysis.
