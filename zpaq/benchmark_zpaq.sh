#!/usr/bin/env bash
#
# benchmark_zpaq.sh - Comprehensive ZPAQ Compression Testing & Benchmark Suite
#
# Measures compression speed (MB/s), decompression speed (MB/s), compression ratio %,
# peak memory usage (MB), multi-thread scaling (1, 2, 4, 8 threads), and integrity verification.
# Outputs CSV and Markdown reports.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZPAQ_BIN="${SCRIPT_DIR}/zpaq"
RUNNER="${SCRIPT_DIR}/benchmark_runner.py"

SIZE="10.0"
LEVELS="1,2,3,4,5"
BLOCKS="0,4,6"
THREADS="1,2,4,8"
CORPORA="text,binary,redundant,entropy"
OUTPUT_DIR="${SCRIPT_DIR}/benchmark_results"
VERBOSE=""
BUILD_FIRST=0

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Comprehensive ZPAQ Compression Testing and Benchmark Suite

Options:
  -s, --size <MB>         Test corpus size in MB per data type (default: 10.0)
  -l, --levels <levels>   Comma-separated ZPAQ levels 1..5 (default: 1,2,3,4,5)
  -b, --blocks <blocks>   Comma-separated block size exponents 0..11 (default: 0,4,6 -> 1MB, 16MB, 64MB)
  -t, --threads <threads> Comma-separated thread counts for scaling (default: 1,2,4,8)
  -c, --corpora <types>   Comma-separated data types: text, binary, redundant, entropy (default: all)
  -o, --output-dir <dir>  Output directory for CSV and Markdown reports (default: benchmark_results)
  -r, --rebuild           Force rebuild of zpaq binary before benchmarking
  -q, --quick             Run quick smoke test (2MB size, levels 1,2, block 4, threads 1,4)
  -v, --verbose           Enable verbose progress output
  -h, --help              Show this help message and exit

Examples:
  $(basename "$0") --quick
  $(basename "$0") --size 20 --levels 1,3,5 --threads 1,4,8
  $(basename "$0") --corpora text,binary --output-dir ./my_results

EOF
    exit 0
}

# Parse command line options
while [[ $# -gt 0 ]]; do
    case "$1" in
        -s|--size)
            SIZE="$2"
            shift 2
            ;;
        -l|--levels)
            LEVELS="$2"
            shift 2
            ;;
        -b|--blocks)
            BLOCKS="$2"
            shift 2
            ;;
        -t|--threads)
            THREADS="$2"
            shift 2
            ;;
        -c|--corpora)
            CORPORA="$2"
            shift 2
            ;;
        -o|--output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -r|--rebuild)
            BUILD_FIRST=1
            shift
            ;;
        -q|--quick)
            SIZE="2.0"
            LEVELS="1,2"
            BLOCKS="4"
            THREADS="1,4"
            shift
            ;;
        -v|--verbose)
            VERBOSE="--verbose"
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Error: Unknown option $1"
            usage
            ;;
    esac
done

# Ensure Python 3 is available
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 is required to run the benchmark suite." >&2
    exit 1
fi

# Rebuild or compile zpaq if necessary
if [[ ${BUILD_FIRST} -eq 1 ]] || [[ ! -f "${ZPAQ_BIN}" ]]; then
    echo "[*] Building ZPAQ binary..."
    make -C "${SCRIPT_DIR}" zpaq
fi

if [[ ! -x "${ZPAQ_BIN}" ]]; then
    echo "Error: ZPAQ binary '${ZPAQ_BIN}' is not executable or not found." >&2
    exit 1
fi

echo "=========================================================="
echo "    ZPAQ COMPRESSION BENCHMARK & VERIFICATION SUITE       "
echo "=========================================================="
echo " Binary:     ${ZPAQ_BIN}"
echo " Corpus Size: ${SIZE} MB per file"
echo " Levels:     ${LEVELS}"
echo " Block Sizes: ${BLOCKS}"
echo " Threads:    ${THREADS}"
echo " Corpora:    ${CORPORA}"
echo " Output Dir: ${OUTPUT_DIR}"
echo "=========================================================="
echo ""

# Execute benchmark runner
python3 "${RUNNER}" \
    --zpaq-bin "${ZPAQ_BIN}" \
    --size "${SIZE}" \
    --levels "${LEVELS}" \
    --blocks "${BLOCKS}" \
    --threads "${THREADS}" \
    --corpora "${CORPORA}" \
    --output-dir "${OUTPUT_DIR}" \
    ${VERBOSE}

echo ""
echo "[+] Benchmark suite completed successfully!"
