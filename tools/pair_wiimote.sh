#!/usr/bin/env bash
# Appaire une Wiimote avec le Raspberry Pi. À faire une seule fois.
#
# Usage :
#   ./tools/pair_wiimote.sh              -> scan et appairage guidés
#   ./tools/pair_wiimote.sh AA:BB:CC:DD:EE:FF   -> appaire direct cette MAC
#
# Corrige au passage les problèmes classiques :
#   * Bluetooth soft-bloqué par rfkill          -> "Failed to set power on"
#   * service hciuart pas démarré               -> pas de hci0
#   * commandes envoyées avant bluetoothd       -> "Failed to register agent"
#   * agent qui demande un code PIN             -> agent NoInputNoOutput
set -uo pipefail

MAC="${1:-}"
LOG="$(mktemp)"
bold() { printf '\033[1m%s\033[0m\n' "$*"; }
bad()  { printf '\033[31m%s\033[0m\n' "$*"; }
good() { printf '\033[32m%s\033[0m\n' "$*"; }

# ----------------------------------------------------------------- services
bold "0/5  Remise en route du Bluetooth"
sudo rfkill unblock bluetooth 2>/dev/null || true
sudo rfkill unblock all 2>/dev/null || true
sudo systemctl enable --now bluetooth >/dev/null 2>&1 || true
if systemctl list-unit-files 2>/dev/null | grep -q '^hciuart'; then
    echo "  hciuart : démarrage"
    sudo systemctl enable --now hciuart >/dev/null 2>&1 || true
fi

# bluetoothd met parfois quelques secondes à répondre
for _ in $(seq 1 20); do
    bluetoothctl -- list >/dev/null 2>&1 && break
    sleep 1
done

if ! bluetoothctl -- list 2>/dev/null | grep -q '^Controller'; then
    bad "Aucun contrôleur Bluetooth (pas de hci0)."
    echo "Pistes :"
    echo "  grep -iE 'disable-bt|enable_uart' /boot/firmware/config.txt /boot/config.txt"
    echo "  sudo systemctl status hciuart --no-pager"
    echo "  dmesg | grep -iE 'bluetooth|hci0|brcm|ttyAMA'"
    exit 1
fi
bluetoothctl -- list

# ------------------------------------------------------------- alimentation
bold "1/5  Allumage de l'adaptateur"
power_on() {
    sudo btmgmt power on >/dev/null 2>&1 ||
        sudo hciconfig hci0 up >/dev/null 2>&1 ||
        sudo bluetoothctl -- power on >/dev/null 2>&1
}
for _ in $(seq 1 6); do
    bluetoothctl -- show 2>/dev/null | grep -q "Powered: yes" && break
    power_on
    sleep 2
done

if ! bluetoothctl -- show 2>/dev/null | grep -q "Powered: yes"; then
    bad "Impossible d'allumer l'adaptateur (org.bluez.Error.Failed)."
    echo
    echo "État rfkill :"; rfkill list 2>/dev/null | sed 's/^/  /'
    echo "Si tu vois 'Soft blocked: yes' :  sudo rfkill unblock bluetooth"
    echo "Si tu vois 'Hard blocked: yes' :  bloqué matériellement (rare sur Pi)."
    echo
    echo "Autre cause fréquente sur Pi 4 : le port série qui vole l'UART du BT."
    echo "  grep -iE 'enable_uart|console=' /boot/firmware/cmdline.txt /boot/firmware/config.txt"
    echo "  -> commente 'enable_uart=1' et 'console=serial0,115200', puis reboot."
    echo
    echo "Derniers messages noyau :"
    dmesg 2>/dev/null | grep -iE 'hci|bluetooth|brcm' | tail -10 | sed 's/^/  /'
    exit 1
fi
good "  adaptateur allumé"

# ------------------------------------------------------- session bluetoothctl
# Une seule session longue : l'agent doit rester en vie pendant l'appairage.
FIFO_DIR="$(mktemp -d)"
FIFO="$FIFO_DIR/fifo"
mkfifo "$FIFO"
if command -v stdbuf >/dev/null 2>&1; then
    sudo stdbuf -oL -eL bluetoothctl <"$FIFO" >"$LOG" 2>&1 &
else
    sudo bluetoothctl <"$FIFO" >"$LOG" 2>&1 &
fi
BT_PID=$!
exec 3>"$FIFO"
bt() { printf '%s\n' "$1" >&3; sleep "${2:-1}"; }
cleanup() { exec 3>&- 2>/dev/null; kill "$BT_PID" 2>/dev/null; rm -rf "$FIFO_DIR" "$LOG"; }
trap cleanup EXIT

bt "power on" 2
bt "agent NoInputNoOutput" 1
bt "default-agent" 1
bt "pairable on" 1
bt "discoverable on" 1

# ------------------------------------------------------------- recherche
if [ -n "$MAC" ]; then
    bold "2/5  Appairage de $MAC (scan ignoré)"
else
    bold "2/5  Recherche de la Wiimote"
    echo
    echo "  ==> Appuie MAINTENANT sur 1 + 2 en même temps"
    echo "      (ou sur le bouton rouge sous le cache-piles si la manette a"
    echo "       déjà servi sur une vraie Wii) : les 4 LED clignotent."
    echo
    bt "scan on" 2
    MAC=""
    for _ in $(seq 1 30); do
        MAC="$(timeout 5 bluetoothctl -- devices 2>/dev/null \
                | grep -iE 'nintendo|rvl-cnt|wiimote|wii' \
                | awk '{print $2}' | head -1)"
        [ -n "$MAC" ] && break
        printf '.'
        sleep 1
    done
    echo
    bt "scan off" 1
    if [ -z "$MAC" ]; then
        bad "Rien trouvé pendant 30 s."
        echo "  * Vérifie les piles de la manette."
        echo "  * Réessaie en appuyant sur le bouton rouge plutôt que 1+2."
        echo "  * Certaines manettes 'non officielles' refusent de s'appairer."
        echo
        echo "Périphériques connus de bluetoothctl :"
        bluetoothctl -- devices 2>/dev/null | sed 's/^/  /'
        tail -20 "$LOG" | sed 's/^/  /'
        exit 1
    fi
fi
good "  manette trouvée : $MAC"

# ------------------------------------------------------------- appairage
bold "3/5  Appairage"
bt "pair $MAC" 12
bt "trust $MAC" 2

if grep -q "Failed to pair\|AuthenticationFailed\|org.bluez.Error" "$LOG"; then
    bad "L'appairage a échoué. Deuxième essai, rappuie sur 1 + 2 juste avant."
    echo "  (appuie sur 1+2 MAINTENANT, l'essai démarre dans 3 s)"
    sleep 3
    bt "remove $MAC" 1
    bt "pair $MAC" 12
    bt "trust $MAC" 2
fi

if ! bluetoothctl -- info "$MAC" 2>/dev/null | grep -q "Paired: yes"; then
    bad "Toujours pas appairé. Journal bluetoothctl :"
    tail -25 "$LOG" | sed 's/^/  /'
    echo
    echo "Si bluetoothctl réclame un code PIN : c'est une vieille manette."
    echo "Tente 0000, ou l'astuce connue : la MAC à l'envers"
    echo "(ex: 00:1F:32:A1:B2:C3 -> C3:B2:A1:32:1F:00)."
    exit 1
fi
good "  appairée et de confiance (trusted)"

# ------------------------------------------------------------- connexion
bold "4/5  Connexion"
for essai in 1 2 3; do
    bt "connect $MAC" 6
    if bluetoothctl -- info "$MAC" 2>/dev/null | grep -q "Connected: yes"; then
        break
    fi
    echo "  essai $essai raté, on réessaie..."
done

if ! bluetoothctl -- info "$MAC" 2>/dev/null | grep -q "Connected: yes"; then
    bad "Connecté mais pas de profil HID."
    echo "Cas classique sur BlueZ récent : ajoute dans /etc/bluetooth/main.conf"
    echo
    echo "  [General]"
    echo "  Privacy=off"
    echo "  ClassicBondedOnly=false"
    echo
    echo "puis : sudo systemctl restart bluetooth && bluetoothctl connect $MAC"
    exit 1
fi
good "  connectée"

# ------------------------------------------------------------- vérification
bold "5/5  Vérification côté Linux"
if grep -i -A4 'Nintendo' /proc/bus/input/devices 2>/dev/null | grep -q 'Handlers'; then
    good "  la manette est bien vue comme périphérique d'entrée :"
    grep -i -B2 -A6 'Nintendo' /proc/bus/input/devices | sed 's/^/  /'
else
    echo "  pas encore visible dans /proc/bus/input/devices."
    echo "  Réveille-la (appuie sur un bouton) puis regarde :"
    echo "    grep -i -A6 Nintendo /proc/bus/input/devices"
fi

echo
bold "Terminé."
echo "  Tester les boutons :  python3 tools/find_buttons.py"
echo "  Lancer Brook       :  python3 brook.py --debug"
echo "  Reconnecter à la main : bluetoothctl connect $MAC"
