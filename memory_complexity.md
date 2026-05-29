# Memory Complexity Analysis: WHT Spectral Accumulator

The Cascade WHT Correlation Attack achieves significant time complexity speedups, but it introduces a memory-space trade-off. This document analyzes the memory requirements and the "Memory Wall" for large LFSR lengths.

## 1. Theoretical Memory Complexity

The core of the attack lies in Stage 1, which uses the **Walsh-Hadamard Transform (WHT)** to compute correlations for all $2^L$ seeds simultaneously.

*   **Spectral Accumulator (f)**: To apply the WHT, we must first construct a spectral accumulator array $f$ of size $2^L$.
*   **Data Type**: Each entry in $f$ represents a sum of $\pm 1$ values (the biased connection counts). For $L \geq 20$, these values are stored as **64-bit floats** (8 bytes) to maintain precision during the WHT butterfly operations.
*   **Total Memory**: $M(L) = 2^L \times 8 \text{ bytes}$.

## 2. Practical Scalability (The Memory Wall)

As $L$ increases linearly, the memory requirement grows exponentially. This is a critical practical bottleneck for cryptanalysis.

| LFSR Length (L) | Number of Entries ($2^L$) | Memory Required | Practical Hardware |
|:---:|:---:|:---:|:---:|
| 14 | 16,384 | 128 KB | Cache-resident (extremely fast) |
| 20 | 1,048,576 | 8 MB | Standard Desktop/Laptop |
| 25 | 33,554,432 | 256 MB | Standard Desktop/Laptop |
| 28 | 268,435,456 | 2 GB | Modern Laptop (16GB RAM) |
| 30 | 1,073,741,824 | **8 GB** | High-end Desktop / Workstation |
| 32 | 4,294,967,296 | **32 GB** | Server / High-end Workstation |
| 34 | 17,179,869,184 | 128 GB | High-performance Server Cluster |

### 2.1 The $L=30$ Threshold
For most researchers, **$L=30$** represents the "Memory Wall." An 8 GB array is the maximum that can comfortably fit in the RAM of a standard 16GB machine without causing significant disk swapping (which would destroy the WHT's speed advantage).

## 3. Mitigation Strategies

For attacks on LFSRs where $L > 30$, the standard WHT implementation must be modified:

1.  **Memory-Efficient WHT**: Implementing the WHT in chunks or using a recursive disk-based approach. However, this reintroduces $O(N \cdot 2^L)$ style disk I/O bottlenecks.
2.  **GPU Offloading**: Using GPU VRAM (e.g., 24GB on an RTX 4090) allows for much faster butterfly operations, but the $2^L$ limit still applies.
3.  **Hybrid Approach**: If $L=40$, one could exhaustively search 10 bits and run a $L=30$ WHT attack for each of the $2^{10}$ cases. This combines $O(2^{10})$ exhaustive search with $O(2^{30})$ WHT.

## 4. Conclusion for Submission

In your thesis, you should emphasize that while the time complexity is greatly improved, the attack is **memory-bounded**. The ability to break an LFSR is limited not by how long you can wait, but by how much RAM your system has. 

> [!IMPORTANT]
> For the $L=25$ experiments you are running, the memory usage is only **256 MB**, which is negligible. This proves the attack is extremely efficient at the "Journal Standard" scale.
