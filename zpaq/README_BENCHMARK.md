# ZPAQ Compression Benchmark & Verification Suite

## Overview

The `benchmark_zpaq.sh` test suite provides automated performance benchmarking, multi-thread scaling analysis, peak memory tracking, and data integrity verification for the **ZPAQ** journaling compression engine (`/home/cachy/Projects/lrzip-next/zpaq`).

The suite automatically generates test corpora representing diverse real-world data types, executes compression and decompression runs across configurable ZPAQ levels (1 to 5) and block sizes, verifies byte-for-byte fidelity, and outputs formatted benchmark results in **Markdown** (`benchmark_results.md`) and **CSV** (`benchmark_results.csv`) formats.

---

## Directory Structure & Files

- [benchmark_zpaq.sh](file:///home/cachy/Projects/lrzip-next/zpaq/benchmark_zpaq.sh): CLI entry point script for configuring and invoking the benchmark suite.
- [benchmark_runner.py](file:///home/cachy/Projects/lrzip-next/zpaq/benchmark_runner.py): Python benchmark runner handling process memory tracking, microsecond timing, corpus generation, checksum verification, CSV, Markdown, and ASCII console reporting.
- [README_BENCHMARK.md](file:///home/cachy/Projects/lrzip-next/zpaq/README_BENCHMARK.md): Comprehensive documentation.

---

## Test Corpora Categories

The suite generates four distinct test corpora of configurable size (default: 10 MB per file):

1. **Text (`text`)**: Concatenated C++ source code (`zpaq.cpp`, `libzpaq.cpp`, `libzpaq.h`), documentation, POD manuals (`zpaq.pod`), and text licenses. Tests order-N context modeling (ICM/ISSE) and BWT text transformations.
2. **Binary Executable (`binary`)**: Concatenated ELF executables (`zpaq`), compiled object files (`zpaq.o`, `libzpaq.o`), and binary machine code. Tests E8E9 relative branch address transformations and binary modeling.
3. **Highly Redundant (`redundant`)**: Repeating byte sequences, structured headers, and null byte padding. Tests LZ77/RLE deduplication efficiency.
4. **High Entropy (`entropy`)**: Cryptographically random byte streams (`os.urandom`). Tests worst-case entropy modeling and expansion prevention.

---

## Benchmark Metrics Measured

| Metric | Unit | Description |
|---|---|---|
| **Compression Speed** | `MB/s` | Throughput achieved during compression (`Original Size MB / Compress Time Seconds`). |
| **Decompression Speed** | `MB/s` | Throughput achieved during decompression (`Original Size MB / Decompress Time Seconds`). |
| **Compression Ratio** | `%` | Percentage of space saved: `((Original - Compressed) / Original) * 100`. |
| **Ratio Factor** | `x` | Compression factor: `Original Size / Compressed Size`. |
| **Bits per Byte** | `bits` | Compressed representation density: `(Compressed Bytes * 8) / Original Bytes`. |
| **Peak Memory Usage** | `MB` | Peak Resident Set Size (Max RSS) of the `zpaq` process captured via `resource.getrusage`. |
| **Thread Scaling** | `x` / `%` | Speedup factor (`Speed(N) / Speed(1)`) and parallel efficiency across 1, 2, 4, and 8 threads. |
| **Integrity Verification** | `PASS` / `FAIL` | Full validation via MD5 hash comparison and byte-by-byte file comparison (`cmp`). |

---

## Command Line Usage

### Basic Execution

To run the full default benchmark suite (10 MB per corpus, levels 1-5, block sizes 0,4,6, threads 1,2,4,8):

```bash
./benchmark_zpaq.sh
```

### Quick Smoke Test

To run a fast validation check (2 MB corpus, levels 1-2, block size 4, threads 1,4):

```bash
./benchmark_zpaq.sh --quick -v
```

### Custom Configurations

```bash
# Benchmark with 20 MB corpus across levels 1, 3, 5 with 1, 4, 8 threads
./benchmark_zpaq.sh --size 20.0 --levels 1,3,5 --threads 1,4,8

# Benchmark specific data types and custom output directory
./benchmark_zpaq.sh --corpora text,binary --output-dir ./custom_results

# Force rebuild of zpaq before benchmarking
./benchmark_zpaq.sh --rebuild
```

---

## Command Line Options

| Flag | Long Option | Default | Description |
|---|---|---|---|
| `-s` | `--size <MB>` | `10.0` | Target file size in MB for each generated test corpus. |
| `-l` | `--levels <levels>` | `1,2,3,4,5` | Comma-separated ZPAQ compression levels. |
| `-b` | `--blocks <blocks>` | `0,4,6` | Block size exponents ($2^B$ MiB per block: 0=1MB, 4=16MB, 6=64MB). |
| `-t` | `--threads <threads>` | `1,2,4,8` | Thread counts for multi-thread scaling evaluation. |
| `-c` | `--corpora <types>` | `text,binary,redundant,entropy` | Selected data types to test. |
| `-o` | `--output-dir <dir>` | `benchmark_results` | Output directory for CSV and Markdown reports. |
| `-r` | `--rebuild` | off | Rebuild `zpaq` executable with `make` prior to testing. |
| `-q` | `--quick` | off | Preset for quick smoke-test run. |
| `-v` | `--verbose` | off | Display real-time progress for every test case. |
| `-h` | `--help` | - | Display usage help. |

---

## Output Formats

### 1. CSV Format (`benchmark_results.csv`)

Includes standard structured headers suitable for spreadsheet analysis, plotting, and regression tracking:

```csv
corpus,level,block_size_exp,block_size_mb,method,threads,input_bytes,compressed_bytes,space_saved_pct,ratio_factor,bits_per_byte,comp_time_sec,comp_speed_mbs,comp_peak_ram_mb,decomp_time_sec,decomp_speed_mbs,decomp_peak_ram_mb,verification
```

### 2. Markdown Report (`benchmark_results.md`)

A GitHub-style report featuring:
- **Executive Summary Matrix**: High-level comparison across data types and levels.
- **Level Matrix Table**: Compression ratio %, MB/s, and memory across levels 1–5.
- **Multi-Thread Scaling Table**: Thread speedup and efficiency breakdown ($T=1,2,4,8$).
- **Integrity & Verification Log**: MD5 hash comparison results for every archived file.

---

## Verification & Safety

Every test run extracts the generated `.zpaq` archive into an isolated temporary directory and performs two levels of verification:
1. **MD5 Checksum Verification**: Compares the original file MD5 with the extracted file MD5.
2. **Binary `cmp` Check**: Performs exact byte-by-byte file comparison.

If either check fails, the test outcome is flagged as `FAIL` and highlighted in both console and report outputs.
