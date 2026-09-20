#!/usr/bin/env bash
# Appaire la Wiimote avec le Raspberry Pi (à faire une seule fois).
set -euo pipefail

echo "=== Appairage de la Wiimote ==="
echo
echo "Deux méthodes, au choix :"
echo "  1) bouton rouge sous le cache-piles : appairage permanent (recommandé)"
echo "  2) appui simultané sur 1 + 2 : appairage temporaire"
echo

# bluetoothctl en mode interactif piloté par stdin
read -r -p "Bluetooth activé ? [O/n] " rep
rep="${rep:-O}"
if [[ "$rep" =~ ^[oO]$ ]]; then
  sudo systemctl enable --now bluetooth
fi

sudo bluetoothctl <<'EOF'
power on
agent on
default-agent
discoverable on
pairable on
scan on
EOF

echo
echo "Scan lancé. Maintenant appuie sur 1 + 2 (ou sur le bouton rouge)"
echo "de la Wiimote : les 4 LED clignotent."
echo
read -r -p "Adresse MAC de la manette (ex: 00:1F:32:A1:B2:C3) : " MAC

if [[ -z "$MAC" ]]; then
  echo "Pas d'adresse, on s'arrête là."
  exit 1
fi

sudo bluetoothctl -- connect "$MAC" || true
sudo bluetoothctl -- pair "$MAC" || true
sudo bluetoothctl -- trust "$MAC"
sudo bluetoothctl -- connect "$MAC" || true

echo
echo "Fait. Vérifie avec :  python3 tools/find_buttons.py"
echo "(si ça ne se connecte pas du premier coup, relance juste :"
echo " bluetoothctl connect $MAC )"
