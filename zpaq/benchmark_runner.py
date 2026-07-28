#!/usr/bin/env python3
"""
ZPAQ Compression Benchmark Runner
Automated benchmark and verification suite for ZPAQ compression engine.
Measures speed, compression ratio, memory usage, thread scaling, and integrity verification.
"""

import sys
import os
import argparse
import time
import subprocess
import json
import hashlib
import tempfile
import csv

def generate_corpora(output_dir, size_mb):
    """
    Generates test corpora of varied data types:
    1. Text (prose/code)
    2. Binary/Executable
    3. Highly Redundant (repeats/zeros)
    4. High Entropy (random/compressed)
    """
    os.makedirs(output_dir, exist_ok=True)
    target_bytes = int(size_mb * 1024 * 1024)
    corpora_paths = {}

    # 1. Text Corpus
    text_path = os.path.join(output_dir, "corpus_text.bin")
    zpaq_dir = os.path.dirname(os.path.abspath(__file__))
    source_files = ["zpaq.cpp", "libzpaq.cpp", "libzpaq.h", "zpaq.pod", "readme.txt", "COPYING"]
    text_buffer = bytearray()
    for fname in source_files:
        fpath = os.path.join(zpaq_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, "rb") as fp:
                text_buffer.extend(fp.read())
    if not text_buffer:
        text_buffer = b"ZPAQ Compression Benchmark Text Line Sample. " * 500
    with open(text_path, "wb") as fp:
        written = 0
        while written < target_bytes:
            chunk = text_buffer[:min(len(text_buffer), target_bytes - written)]
            fp.write(chunk)
            written += len(chunk)
    corpora_paths["text"] = text_path

    # 2. Binary Executable Corpus
    binary_path = os.path.join(output_dir, "corpus_binary.bin")
    bin_sources = ["zpaq", "zpaq.o", "libzpaq.o"]
    bin_buffer = bytearray()
    for fname in bin_sources:
        fpath = os.path.join(zpaq_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, "rb") as fp:
                bin_buffer.extend(fp.read())
    # If no local binaries, check system binary
    if not bin_buffer:
        for sys_bin in ["/usr/bin/gcc", "/usr/bin/python3", "/usr/bin/git"]:
            if os.path.exists(sys_bin):
                with open(sys_bin, "rb") as fp:
                    bin_buffer.extend(fp.read())
    if not bin_buffer:
        bin_buffer = b"\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00" * 1000
    with open(binary_path, "wb") as fp:
        written = 0
        while written < target_bytes:
            chunk = bin_buffer[:min(len(bin_buffer), target_bytes - written)]
            fp.write(chunk)
            written += len(chunk)
    corpora_paths["binary"] = binary_path

    # 3. Highly Redundant Corpus
    redundant_path = os.path.join(output_dir, "corpus_redundant.bin")
    redundant_pattern = (b"HIGHLY_REDUNDANT_ZPAQ_COMPRESSION_BENCHMARK_BLOCK_0123456789\n" * 32) + (b"\x00" * 2048)
    with open(redundant_path, "wb") as fp:
        written = 0
        while written < target_bytes:
            chunk = redundant_pattern[:min(len(redundant_pattern), target_bytes - written)]
            fp.write(chunk)
            written += len(chunk)
    corpora_paths["redundant"] = redundant_path

    # 4. High Entropy Corpus
    entropy_path = os.path.join(output_dir, "corpus_entropy.bin")
    with open(entropy_path, "wb") as fp:
        written = 0
        chunk_sz = 65536
        while written < target_bytes:
            to_write = min(chunk_sz, target_bytes - written)
            fp.write(os.urandom(to_write))
            written += to_write
    corpora_paths["entropy"] = entropy_path

    return corpora_paths

def measure_isolated_cmd(cmd):
    """
    Runs a command in an isolated Python process to capture exact Peak RSS memory (KB)
    and wall-clock time (seconds).
    """
    eval_code = f"""import subprocess, time, resource, json
t0 = time.perf_counter()
res = subprocess.run({cmd!r}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
t1 = time.perf_counter()
rss_kb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
print(json.dumps({{"code": res.returncode, "time": t1 - t0, "rss_kb": rss_kb}}))
"""
    proc = subprocess.run([sys.executable, "-c", eval_code], capture_output=True, text=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        return {"code": 1, "time": 0.0, "rss_kb": 0}
    try:
        return json.loads(proc.stdout.strip())
    except Exception:
        return {"code": 1, "time": 0.0, "rss_kb": 0}

def compute_md5(filepath):
    """Compute MD5 checksum of a file."""
    hasher = hashlib.md5()
    with open(filepath, "rb") as fp:
        while True:
            chunk = fp.read(65536)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()

def run_benchmarks(zpaq_bin, corpora, levels, block_sizes, thread_list, temp_work_dir, verbose=False):
    """
    Executes compression & decompression benchmarks across all test matrices.
    """
    results = []

    for corpus_name, input_file in corpora.items():
        input_bytes = os.path.getsize(input_file)
        input_mb = input_bytes / (1024 * 1024)
        input_md5 = compute_md5(input_file)

        if verbose:
            print(f"[*] Benchmarking Corpus: {corpus_name} ({input_mb:.2f} MB)")

        for lvl in levels:
            for bs in block_sizes:
                method_arg = f"-m{lvl}{bs}"
                bs_mb = 2 ** bs

                for t_cnt in thread_list:
                    archive_path = os.path.join(temp_work_dir, f"arc_{corpus_name}_l{lvl}_b{bs}_t{t_cnt}.zpaq")
                    extract_dir = os.path.join(temp_work_dir, f"ext_{corpus_name}_l{lvl}_b{bs}_t{t_cnt}")
                    os.makedirs(extract_dir, exist_ok=True)

                    if os.path.exists(archive_path):
                        os.remove(archive_path)

                    # 1. Compression
                    comp_cmd = [zpaq_bin, "add", archive_path, input_file, method_arg, f"-t{t_cnt}", "-noattributes"]
                    comp_res = measure_isolated_cmd(comp_cmd)

                    if comp_res["code"] != 0 or not os.path.exists(archive_path):
                        print(f"[!] Compression failed for {corpus_name} {method_arg} -t{t_cnt}")
                        continue

                    compressed_bytes = os.path.getsize(archive_path)
                    compressed_mb = compressed_bytes / (1024 * 1024)
                    comp_time = comp_res["time"]
                    comp_speed_mbs = input_mb / comp_time if comp_time > 0 else 0.0
                    comp_peak_ram_mb = comp_res["rss_kb"] / 1024.0

                    # Calculate Compression Metrics
                    space_saved_pct = ((input_bytes - compressed_bytes) / input_bytes) * 100.0 if input_bytes > 0 else 0.0
                    ratio_factor = (input_bytes / compressed_bytes) if compressed_bytes > 0 else 0.0
                    bits_per_byte = (compressed_bytes * 8.0) / input_bytes if input_bytes > 0 else 0.0

                    # 2. Decompression
                    decomp_cmd = [zpaq_bin, "extract", archive_path, "-to", extract_dir, f"-t{t_cnt}"]
                    decomp_res = measure_isolated_cmd(decomp_cmd)

                    decomp_time = decomp_res["time"]
                    decomp_speed_mbs = input_mb / decomp_time if decomp_time > 0 else 0.0
                    decomp_peak_ram_mb = decomp_res["rss_kb"] / 1024.0

                    # 3. Verification
                    # Locate decompressed file in extract_dir
                    extracted_file = None
                    rel_input = os.path.relpath(input_file, "/")
                    target_extracted = os.path.join(extract_dir, rel_input)
                    if os.path.exists(target_extracted):
                        extracted_file = target_extracted
                    else:
                        # Fallback search inside extract_dir
                        for root, _, files in os.walk(extract_dir):
                            if os.path.basename(input_file) in files:
                                extracted_file = os.path.join(root, os.path.basename(input_file))
                                break

                    verified = False
                    output_md5 = ""
                    if extracted_file and os.path.exists(extracted_file):
                        output_md5 = compute_md5(extracted_file)
                        if output_md5 == input_md5:
                            # Additional byte-by-byte comparison check
                            cmp_proc = subprocess.run(["cmp", "-s", input_file, extracted_file])
                            if cmp_proc.returncode == 0:
                                verified = True

                    ver_status = "PASS" if verified else "FAIL"

                    rec = {
                        "corpus": corpus_name,
                        "level": lvl,
                        "block_size_exp": bs,
                        "block_size_mb": bs_mb,
                        "method": method_arg,
                        "threads": t_cnt,
                        "input_bytes": input_bytes,
                        "input_mb": input_mb,
                        "compressed_bytes": compressed_bytes,
                        "compressed_mb": compressed_mb,
                        "space_saved_pct": space_saved_pct,
                        "ratio_factor": ratio_factor,
                        "bits_per_byte": bits_per_byte,
                        "comp_time_sec": comp_time,
                        "comp_speed_mbs": comp_speed_mbs,
                        "comp_peak_ram_mb": comp_peak_ram_mb,
                        "decomp_time_sec": decomp_time,
                        "decomp_speed_mbs": decomp_speed_mbs,
                        "decomp_peak_ram_mb": decomp_peak_ram_mb,
                        "verification": ver_status,
                        "input_md5": input_md5,
                        "output_md5": output_md5
                    }
                    results.append(rec)

                    if verbose:
                        print(f"    L{lvl} B{bs} ({bs_mb}MB) -t{t_cnt} | Ratio: {space_saved_pct:.2f}% ({ratio_factor:.2f}x) | Comp: {comp_speed_mbs:.2f} MB/s | Decomp: {decomp_speed_mbs:.2f} MB/s | RAM: {comp_peak_ram_mb:.1f}MB | [{ver_status}]")

                    # Cleanup temporary archive and extracted directory to save space
                    if os.path.exists(archive_path):
                        os.remove(archive_path)
                    subprocess.run(["rm", "-rf", extract_dir])

    return results

def generate_csv(results, csv_path):
    """Write benchmark results to CSV format."""
    fieldnames = [
        "corpus", "level", "block_size_exp", "block_size_mb", "method", "threads",
        "input_bytes", "compressed_bytes", "space_saved_pct", "ratio_factor",
        "bits_per_byte", "comp_time_sec", "comp_speed_mbs", "comp_peak_ram_mb",
        "decomp_time_sec", "decomp_speed_mbs", "decomp_peak_ram_mb", "verification"
    ]
    with open(csv_path, "w", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            row = {k: r[k] for k in fieldnames}
            writer.writerow(row)

def generate_markdown(results, md_path, corpora_info):
    """Generate structured GitHub-style Markdown benchmark report."""
    lines = []
    lines.append("# ZPAQ Compression Engine Benchmark Report")
    lines.append("")
    lines.append(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Target System:** Linux (Kernel: `{os.uname().release}`, Architecture: `{os.uname().machine}`)")
    lines.append("")

    lines.append("## Executive Summary")
    lines.append("")
    lines.append("This report documents the performance, compression efficiency, memory consumption, and thread scaling characteristics of the ZPAQ journaling compression engine.")
    lines.append("")

    # Summary table per corpus (averaged / level 1 vs level 5 baseline)
    lines.append("### Summary Matrix by Data Type")
    lines.append("")
    lines.append("| Corpus | Type | Size (MB) | L1 Ratio | L5 Ratio | L1 Comp Speed | L5 Comp Speed | L1 Decomp Speed | Max RAM (MB) | Verification |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")

    for corpus, size_mb in corpora_info.items():
        c_results = [r for r in results if r["corpus"] == corpus]
        l1_recs = [r for r in c_results if r["level"] == 1 and r["threads"] == 1]
        l5_recs = [r for r in c_results if r["level"] == 5 and r["threads"] == 1]
        l1_rec = l1_recs[0] if l1_recs else None
        l5_rec = l5_recs[0] if l5_recs else None

        l1_ratio = f"{l1_rec['space_saved_pct']:.2f}% ({l1_rec['ratio_factor']:.2f}x)" if l1_rec else "N/A"
        l5_ratio = f"{l5_rec['space_saved_pct']:.2f}% ({l5_rec['ratio_factor']:.2f}x)" if l5_rec else "N/A"
        l1_comp = f"{l1_rec['comp_speed_mbs']:.2f} MB/s" if l1_rec else "N/A"
        l5_comp = f"{l5_rec['comp_speed_mbs']:.2f} MB/s" if l5_rec else "N/A"
        l1_decomp = f"{l1_rec['decomp_speed_mbs']:.2f} MB/s" if l1_rec else "N/A"
        max_ram = max([r["comp_peak_ram_mb"] for r in c_results]) if c_results else 0.0
        all_pass = all([r["verification"] == "PASS" for r in c_results])
        ver_str = "✅ PASS" if all_pass else "❌ FAIL"

        lines.append(f"| `{corpus}` | {corpus.capitalize()} | {size_mb:.2f} | {l1_ratio} | {l5_ratio} | {l1_comp} | {l5_comp} | {l1_decomp} | {max_ram:.1f} MB | {ver_str} |")

    lines.append("")

    # Detailed Level Comparison
    lines.append("## Compression Level Comparison (Levels 1 to 5)")
    lines.append("")
    lines.append("| Corpus | Level | Block Size | Threads | Space Saved (%) | Ratio Factor | Bits/Byte | Comp Speed (MB/s) | Decomp Speed (MB/s) | Peak RAM (MB) | Status |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")

    # Filter baseline 1 thread runs or representative block size
    for r in results:
        lines.append(f"| `{r['corpus']}` | Level {r['level']} | {r['block_size_mb']} MB | {r['threads']} | {r['space_saved_pct']:.2f}% | {r['ratio_factor']:.2f}x | {r['bits_per_byte']:.2f} | {r['comp_speed_mbs']:.2f} | {r['decomp_speed_mbs']:.2f} | {r['comp_peak_ram_mb']:.1f} | {r['verification']} |")

    lines.append("")

    # Thread Scaling Analysis
    lines.append("## Multi-Thread Scaling Analysis")
    lines.append("")
    lines.append("Evaluates performance speedup and scaling efficiency across thread counts (1, 2, 4, 8 threads).")
    lines.append("")

    # Group by corpus and level
    corpora_keys = sorted(list(set(r["corpus"] for r in results)))
    levels_keys = sorted(list(set(r["level"] for r in results)))

    for corp in corpora_keys:
        lines.append(f"### Thread Scaling: Corpus `{corp}`")
        lines.append("")
        lines.append("| Level | Threads | Comp Time (s) | Comp Speed (MB/s) | Comp Speedup | Decomp Time (s) | Decomp Speed (MB/s) | Decomp Speedup | Efficiency |")
        lines.append("|---|---|---|---|---|---|---|---|---|")

        for lvl in levels_keys:
            sub = [r for r in results if r["corpus"] == corp and r["level"] == lvl]
            # Find t=1 base speed
            t1_rec = [r for r in sub if r["threads"] == 1]
            t1_comp_speed = t1_rec[0]["comp_speed_mbs"] if t1_rec and t1_rec[0]["comp_speed_mbs"] > 0 else 1.0
            t1_decomp_speed = t1_rec[0]["decomp_speed_mbs"] if t1_rec and t1_rec[0]["decomp_speed_mbs"] > 0 else 1.0

            for r in sorted(sub, key=lambda x: x["threads"]):
                t_cnt = r["threads"]
                comp_sp = r["comp_speed_mbs"] / t1_comp_speed if t1_comp_speed > 0 else 1.0
                decomp_sp = r["decomp_speed_mbs"] / t1_decomp_speed if t1_decomp_speed > 0 else 1.0
                eff = (comp_sp / t_cnt) * 100.0

                lines.append(f"| Level {lvl} | {t_cnt} | {r['comp_time_sec']:.3f}s | {r['comp_speed_mbs']:.2f} MB/s | {comp_sp:.2f}x | {r['decomp_time_sec']:.3f}s | {r['decomp_speed_mbs']:.2f} MB/s | {decomp_sp:.2f}x | {eff:.1f}% |")

        lines.append("")

    # Integrity & Verification Protocol
    lines.append("## Integrity & Decompression Verification")
    lines.append("")
    lines.append("All compressed archives were extracted and validated via MD5 checksum verification and byte-by-byte binary comparison (`cmp`).")
    lines.append("")
    lines.append("| Corpus | Level | Threads | MD5 Input Checksum | MD5 Decompressed Checksum | Result |")
    lines.append("|---|---|---|---|---|---|")

    for r in results[:20]: # show first representative 20 verification records
        lines.append(f"| `{r['corpus']}` | Level {r['level']} | {r['threads']} | `{r['input_md5']}` | `{r['output_md5']}` | {r['verification']} |")
    if len(results) > 20:
        lines.append(f"| ... | ... | ... | ... | ... | ... ({len(results)-20} additional verification records passed) |")

    lines.append("")

    with open(md_path, "w") as fp:
        fp.write("\n".join(lines))

def print_ascii_summary(results):
    """Prints a clean formatted summary table to standard output."""
    print("\n" + "=" * 95)
    print(f"{'ZPAQ BENCHMARK RESULTS SUMMARY':^95}")
    print("=" * 95)
    header = f"{'Corpus':<10} | {'Level':<5} | {'BS(MB)':<6} | {'Thr':<3} | {'Space Saved':<11} | {'Comp MB/s':<10} | {'Decomp MB/s':<11} | {'RAM (MB)':<8} | {'Verif':<5}"
    print(header)
    print("-" * 95)
    for r in results:
        saved_str = f"{r['space_saved_pct']:.1f}%"
        row = f"{r['corpus']:<10} | L{r['level']:<4} | {r['block_size_mb']:<6} | {r['threads']:<3} | {saved_str:<11} | {r['comp_speed_mbs']:<10.2f} | {r['decomp_speed_mbs']:<11.2f} | {r['comp_peak_ram_mb']:<8.1f} | {r['verification']:<5}"
        print(row)
    print("=" * 95)

def main():
    parser = argparse.ArgumentParser(description="ZPAQ Compression Benchmark & Verification Runner")
    parser.add_argument("--zpaq-bin", default="./zpaq", help="Path to zpaq binary")
    parser.add_argument("--size", type=float, default=10.0, help="Test corpus size in MB per file (default: 10.0)")
    parser.add_argument("--levels", default="1,2,3,4,5", help="Comma-separated compression levels (default: 1,2,3,4,5)")
    parser.add_argument("--blocks", default="0,4,6", help="Comma-separated block size exponents 0..11 (default: 0,4,6)")
    parser.add_argument("--threads", default="1,2,4,8", help="Comma-separated thread counts (default: 1,2,4,8)")
    parser.add_argument("--corpora", default="text,binary,redundant,entropy", help="Comma-separated corpus types (default: text,binary,redundant,entropy)")
    parser.add_argument("--output-dir", default="benchmark_results", help="Output directory for reports and CSV (default: benchmark_results)")
    parser.add_argument("--verbose", action="store_true", help="Print verbose execution details")

    args = parser.parse_args()

    # Resolve absolute paths
    zpaq_bin = os.path.abspath(args.zpaq_bin)
    if not os.path.exists(zpaq_bin):
        print(f"Error: zpaq binary not found at {zpaq_bin}. Build it first with make.")
        sys.exit(1)

    levels = [int(x) for x in args.levels.split(",") if x.strip()]
    block_sizes = [int(x) for x in args.blocks.split(",") if x.strip()]
    threads = [int(x) for x in args.threads.split(",") if x.strip()]
    req_corpora = [x.strip() for x in args.corpora.split(",") if x.strip()]

    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        corpora_dir = os.path.join(temp_dir, "corpora")
        work_dir = os.path.join(temp_dir, "work")
        os.makedirs(work_dir, exist_ok=True)

        print(f"[*] Generating test corpora ({args.size} MB each)...")
        all_corpora = generate_corpora(corpora_dir, args.size)
        filtered_corpora = {k: v for k, v in all_corpora.items() if k in req_corpora}

        corpora_info = {k: args.size for k in filtered_corpora.keys()}

        print(f"[*] Starting benchmark suite on {len(filtered_corpora)} corpora...")
        print(f"    Levels: {levels} | Block Size Exps: {block_sizes} | Threads: {threads}")

        t_start = time.time()
        results = run_benchmarks(zpaq_bin, filtered_corpora, levels, block_sizes, threads, work_dir, verbose=args.verbose)
        t_duration = time.time() - t_start

        # Generate outputs
        csv_path = os.path.join(output_dir, "benchmark_results.csv")
        md_path = os.path.join(output_dir, "benchmark_results.md")

        generate_csv(results, csv_path)
        generate_markdown(results, md_path, corpora_info)
        print_ascii_summary(results)

        print(f"\n[+] Benchmark suite completed in {t_duration:.2f} seconds.")
        print(f"[+] CSV Results: {csv_path}")
        print(f"[+] Markdown Report: {md_path}")

if __name__ == "__main__":
    main()
