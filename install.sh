#!/usr/bin/env bash
# Installation sur le Raspberry Pi (Raspberry Pi OS Lite 64 bits conseillé).
#   ./install.sh              -> installe les dépendances
#   ./install.sh --service    -> installe ET active le service systemd
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_NAME="$(whoami)"

echo "=== BrookCosplay : installation ==="

# ---------------------------------------------------------------- dépendances
echo "-> paquets système"
sudo apt update
sudo apt install -y --no-install-recommends \
    python3 python3-pip python3-dev \
    bluez bluetooth \
    python3-evdev || true

# pygame : par les paquets si dispo, sinon par pip
echo "-> pygame"
if ! python3 -c "import pygame" 2>/dev/null; then
    if ! sudo apt install -y python3-pygame 2>/dev/null; then
        pip3 install --break-system-packages pygame ||
            pip3 install pygame
    fi
fi

# ------------------------------------------------------------------- sortie audio
# 1 = jack 3.5 mm, 2 = HDMI
if command -v raspi-config >/dev/null 2>&1; then
    read -r -p "Sortie audio : jack 3.5mm (1) ou HDMI (2) ? [1] " AUDIO_OUT
    AUDIO_OUT="${AUDIO_OUT:-1}"
    sudo raspi-config nonint do_audio "$AUDIO_OUT" || true
fi

# ------------------------------------------------------------------- droits
# Lire /dev/input demande d'être dans le groupe input.
sudo usermod -aG input "$USER_NAME" || true
echo "   (le groupe 'input' prend effet à la prochaine connexion)"

echo
echo "-> vérification"
python3 -c "import evdev; print('evdev  OK')"
python3 -c "import pygame; print('pygame OK', pygame.version.ver)"
python3 "$REPO_DIR/brook.py" --list

# ------------------------------------------------------------------- service
if [[ "${1:-}" == "--service" ]]; then
    echo "-> service systemd"
    sed -e "s|__USER__|$USER_NAME|g" -e "s|__DIR__|$REPO_DIR|g" \
        "$REPO_DIR/brook.service" | sudo tee /etc/systemd/system/brook.service >/dev/null
    sudo systemctl daemon-reload
    sudo systemctl enable --now brook.service
    echo
    echo "Service actif. Commandes utiles :"
    echo "  sudo systemctl status brook"
    echo "  journalctl -u brook -f        # logs en direct"
    echo "  sudo systemctl restart brook"
else
    echo
    echo "Pour démarrer à la main :      python3 $REPO_DIR/brook.py"
    echo "Pour démarrer au boot :        ./install.sh --service"
fi

echo
echo "=== Terminé ==="
