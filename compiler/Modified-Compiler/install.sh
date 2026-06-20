#!/usr/bin/env bash
# install.sh - Installation script for mcomp compiler

set -e

echo "========================================="
echo "  mcomp - Advanced C/C++ Compiler"
echo "  with Multi-Condition Switch Support"
echo "========================================="
echo ""

# Check for g++
if ! command -v g++ &> /dev/null; then
    echo "ERROR: g++ not found. Please install build-essential:"
    echo "  sudo apt install build-essential"
    exit 1
fi

# Check for sudo
if ! command -v sudo &> /dev/null; then
    echo "ERROR: sudo not found. Install as root manually."
    exit 1
fi

echo "[1/4] Building mcomp compiler..."
g++ -O2 -std=c++17 -Wall -Wextra mcomp.cpp -o mcomp

if [ ! -f mcomp ]; then
    echo "ERROR: Build failed!"
    exit 1
fi

echo "[2/4] Installing mcomp to /usr/local/bin..."
sudo cp mcomp /usr/local/bin/mcomp
sudo chmod +x /usr/local/bin/mcomp

echo "[3/4] Verifying installation..."
if command -v mcomp &> /dev/null; then
    echo "✓ mcomp installed successfully!"
else
    echo "⚠ mcomp might not be in PATH. Check /usr/local/bin"
fi

echo "[4/4] Creating convenience scripts..."

# Create g++ wrapper
cat > /tmp/mcomp-gpp << 'EOF'
#!/usr/bin/env bash
mcomp g++ "$@"
EOF
sudo cp /tmp/mcomp-gpp /usr/local/bin/gpp
sudo chmod +x /usr/local/bin/gpp

# Create gcc wrapper
cat > /tmp/mcomp-gcc-wrap << 'EOF'
#!/usr/bin/env bash
mcomp gcc "$@"
EOF
sudo cp /tmp/mcomp-gcc-wrap /usr/local/bin/gccm
sudo chmod +x /usr/local/bin/gccm

rm -f /tmp/mcomp-*

echo ""
echo "========================================="
echo "  Installation Complete!"
echo "========================================="
echo ""
echo "Usage examples:"
echo "  mcomp g++ test.cpp -o a.out"
echo "  mcomp gcc test.c -o program"
echo "  mcomp test.cpp -O2 -o optimized"
echo ""
echo "Shortcuts:"
echo "  gpp test.cpp -o a.out     (uses mcomp with g++)"
echo "  gccm test.c -o program    (uses mcomp with gcc)"
echo ""
echo "Features:"
echo "  case (1 | 5 | 9):         // Multiple values"
echo "  case (2..4):              // Range"
echo "  case (10 | 20..25 | 30):  // Mixed"
echo ""
echo "See README.md for more details."
echo ""