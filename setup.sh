#!/bin/bash
set -e

echo "╔═══════════════════════════════════════════╗"
echo "║  Code Assistant Setup - Raspberry Pi 5   ║"
echo "╚═══════════════════════════════════════════╝"
echo

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Detect if running on Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo -e "${YELLOW}Warning: Not running on Raspberry Pi. Continuing anyway...${NC}"
fi

# Check available RAM
TOTAL_RAM=$(free -m | awk '/^Mem:/{print $2}')
if [ "$TOTAL_RAM" -lt 8000 ]; then
    echo -e "${RED}Error: Insufficient RAM (${TOTAL_RAM}MB). Need at least 8GB.${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} RAM check passed (${TOTAL_RAM}MB available)"

# System dependencies
echo
echo "==> Installing system dependencies..."
sudo apt update
sudo apt install -y \
    build-essential \
    cmake \
    git \
    python3-pip \
    python3-venv \
    wget \
    curl \
    htop

echo -e "${GREEN}✓${NC} System dependencies installed"

# Optimize swap
echo
echo "==> Configuring swap..."
CURRENT_SWAP=$(swapon --show=SIZE --noheadings --bytes | head -1)
SWAP_SIZE_GB=8

if [ -z "$CURRENT_SWAP" ] || [ "$CURRENT_SWAP" -lt $((SWAP_SIZE_GB * 1024 * 1024 * 1024)) ]; then
    sudo dphys-swapfile swapoff || true
    sudo sed -i "s/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=$((SWAP_SIZE_GB * 1024))/" /etc/dphys-swapfile
    sudo dphys-swapfile setup
    sudo dphys-swapfile swapon
    echo -e "${GREEN}✓${NC} Swap configured to ${SWAP_SIZE_GB}GB"
else
    echo -e "${GREEN}✓${NC} Swap already configured"
fi

# Clone llama.cpp
echo
echo "==> Installing llama.cpp..."
if [ ! -d "llama.cpp" ]; then
    git clone https://github.com/ggerganov/llama.cpp
    cd llama.cpp
    
    # Build with optimizations for Pi 5
    make clean
    make -j4
    
    cd ..
    echo -e "${GREEN}✓${NC} llama.cpp built successfully"
else
    echo -e "${YELLOW}ℹ${NC} llama.cpp already exists, skipping..."
fi

# Verify llama.cpp build
if [ ! -f "llama.cpp/main" ]; then
    echo -e "${RED}✗${NC} llama.cpp build failed"
    exit 1
fi

# Create models directory
echo
echo "==> Setting up models directory..."
mkdir -p models

# Download model
echo
echo "==> Downloading model..."
echo "Choose a model:"
echo "  1) Qwen2.5-Coder-7B (Recommended for code, 4.5GB)"
echo "  2) DeepSeek-Coder-6.7B (Good alternative, 4.3GB)"
echo "  3) Phi-3.5-mini (Fast but less capable, 2.5GB)"
echo "  4) Skip download (I'll provide my own)"
echo
read -p "Enter choice [1-4]: " MODEL_CHOICE

case $MODEL_CHOICE in
    1)
        MODEL_FILE="qwen2.5-coder-7b-instruct-q4_k_m.gguf"
        MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf"
        ;;
    2)
        MODEL_FILE="deepseek-coder-6.7b-instruct.Q4_K_M.gguf"
        MODEL_URL="https://huggingface.co/TheBloke/deepseek-coder-6.7B-instruct-GGUF/resolve/main/deepseek-coder-6.7b-instruct.Q4_K_M.gguf"
        ;;
    3)
        MODEL_FILE="Phi-3.5-mini-instruct-Q4_K_M.gguf"
        MODEL_URL="https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q4_K_M.gguf"
        ;;
    4)
        echo "Skipping model download"
        MODEL_FILE=""
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

if [ -n "$MODEL_FILE" ]; then
    if [ ! -f "models/$MODEL_FILE" ]; then
        echo "Downloading $MODEL_FILE (this will take a while)..."
        cd models
        wget --progress=bar:force:noscroll "$MODEL_URL" -O "$MODEL_FILE"
        cd ..
        echo -e "${GREEN}✓${NC} Model downloaded"
    else
        echo -e "${GREEN}✓${NC} Model already exists"
    fi
    
    # Record the chosen model as the default in config.yaml (read by
    # pi_ai_coder.config -- see config.example.yaml). Only written if no
    # config.yaml exists yet, so a customized config is never clobbered.
    if [ ! -f "config.yaml" ]; then
        cat > config.yaml << EOF
model:
  path: "./models/$MODEL_FILE"
EOF
        echo -e "${GREEN}✓${NC} Wrote config.yaml with model.path"
    else
        echo -e "${YELLOW}ℹ${NC} config.yaml already exists -- set model.path to ./models/$MODEL_FILE yourself if needed"
    fi
fi

# Python virtual environment
echo
echo "==> Setting up Python environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate

# Install Python packages: PyYAML for config, Textual+Rich for the TUI
pip install --upgrade pip
pip install textual rich pyyaml
echo -e "${GREEN}✓${NC} Python environment ready"

# Make scripts executable
chmod +x assistant.py context_manager.py model_runner.py

# Create launcher script
echo
echo "==> Creating launcher script..."
cat > run.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python3 assistant.py "$@"
EOF

chmod +x run.sh

echo -e "${GREEN}✓${NC} Launcher created"

# Test installation
echo
echo "==> Testing installation..."

if python3 -c "from model_runner import LlamaRunner; print('OK')" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Python modules working"
else
    echo -e "${RED}✗${NC} Python modules test failed"
    exit 1
fi

# Create a minimal README only if one doesn't already exist -- never
# clobber the project's real README.md on repeat runs.
if [ ! -f "README.md" ]; then
cat > README.md << 'EOF'
# Code Assistant for Raspberry Pi 5

Local AI coding assistant powered by llama.cpp and Qwen2.5-Coder.

## Quick Start

```bash
# Interactive mode
./run.sh

# Full-screen TUI workspace
./run.sh tui

# With specific files
./run.sh main.py utils.py

# One-shot query
./run.sh -q "Write a function to parse CSV files"

# Help
./run.sh --help
```

## Commands (in interactive mode)

- `add *.py` - Add files to context
- `files` - List context files
- `clear` - Clear context
- `auto` - Toggle auto file detection
- `exec <cmd>` - Run shell command
- `save <file>` - Save last code block
- `reset` - Reset conversation
- `help` - Show all commands
- `quit` - Exit

## Performance Tips

1. Use 4-bit quantized models (Q4_K_M)
2. Keep context under 10 files
3. Monitor with `htop` in another terminal
4. First query is slowest (model loading)

## Troubleshooting

**Out of memory:**
- Use smaller model (Phi-3.5-mini)
- Reduce context window: `--model-ctx 2048`
- Close other applications

**Slow inference:**
- Normal for Pi 5 (~5-10 tokens/sec)
- First response is slowest
- Use shorter prompts

**Model not found:**
Download manually:
```bash
cd models
wget <model-url>
```

## File Structure

```
.
├── assistant.py          # Main CLI
├── pi_ai_coder/          # Backend (context, models, tools, TUI)
├── context_manager.py    # Backward-compat shim
├── model_runner.py       # Backward-compat shim
├── llama.cpp/           # llama.cpp build
├── models/              # GGUF models
└── run.sh               # Launcher script
```
EOF
fi

# Final instructions
echo
echo "╔═══════════════════════════════════════════╗"
echo "║          Installation Complete!           ║"
echo "╚═══════════════════════════════════════════╝"
echo
echo "Quick test:"
echo "  ${GREEN}./run.sh -q 'Write a hello world in Python'${NC}"
echo
echo "Interactive mode:"
echo "  ${GREEN}./run.sh${NC}"
echo
echo "See README.md for full documentation"
echo

# Performance info
echo "System Info:"
echo "  RAM: ${TOTAL_RAM}MB"
echo "  Swap: ${SWAP_SIZE_GB}GB"
echo "  Cores: $(nproc)"
echo "  Model: ${MODEL_FILE:-'Not downloaded'}"
echo

echo -e "${YELLOW}Note:${NC} First query will be slow (model loading)"
echo -e "${YELLOW}Note:${NC} Expect ~5-10 tokens/second on Pi 5"
