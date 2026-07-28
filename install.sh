#!/usr/bin/env bash
# One-line installer script for lrzip-next on Linux / Unix systems

set -euo pipefail

PREFIX="${PREFIX:-/usr/local}"
BINDIR="${BINDIR:-${PREFIX}/bin}"
MANDIR="${MANDIR:-${PREFIX}/share/man/man1}"

echo "==> Building and installing lrzip-next to ${PREFIX}..."

if [ ! -f "configure" ]; then
    echo "==> Generating configure scripts with autogen.sh..."
    ./autogen.sh
fi

if [ ! -f "Makefile" ]; then
    echo "==> Configuring build environment..."
    ./configure --prefix="${PREFIX}"
fi

echo "==> Compiling lrzip-next..."
make -j"$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 2)"

echo "==> Installing binaries to ${BINDIR}..."
if [ "$(id -u)" -eq 0 ]; then
    make install
else
    echo "==> Root privileges required for installation into ${PREFIX}. Using sudo..."
    sudo make install
fi

echo "==> Installation complete!"
echo "    lrzip-next: $(which lrzip-next 2>/dev/null || echo "${BINDIR}/lrzip-next")"
