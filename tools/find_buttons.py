#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Outil de dépannage : affiche le nom evdev de chaque bouton pressé.

Si un bouton ne marche pas dans brook.py, lance ça :

    python3 tools/find_buttons.py

Appuie sur les boutons de la Wiimote, note les noms affichés, et mets-les
dans la table BUTTONS de config.py.
"""

import sys
import time

from evdev import InputDevice, categorize, ecodes, list_devices


def choose_device():
    devices = []
    for path in list_devices():
        try:
            devices.append(InputDevice(path))
        except (OSError, IOError):
            continue

    if not devices:
        print("Aucun périphérique d'entrée trouvé dans /dev/input.")
        print("La Wiimote est-elle appairée ? Lance d'abord tools/pair_wiimote.sh")
        sys.exit(1)

    print("Périphériques disponibles :")
    for i, dev in enumerate(devices):
        print("  %d. %-40s %s" % (i, dev.name, dev.path))

    # Une manette Nintendo ? on la prend directement.
    nintendo = [d for d in devices
                if any(h in d.name.lower()
                       for h in ("nintendo", "wii", "wiimote", "rvl"))]
    if len(nintendo) == 1:
        print("\n-> %s sélectionné automatiquement" % nintendo[0].name)
        return nintendo[0]
    if not nintendo:
        print("\n/!\\ Aucune manette Nintendo dans la liste.")
        print("   Elle n'est probablement pas connectée : appuie sur un bouton")
        print("   puis relance  bluetoothctl connect <MAC>")

    if len(devices) == 1:
        return devices[0]

    choice = input("Lequel est la Wiimote ? [0] ").strip() or "0"
    try:
        return devices[int(choice)]
    except (ValueError, IndexError):
        print("Choix invalide.")
        sys.exit(1)


def main():
    dev = choose_device()
    print("\nBranché sur %s (%s)" % (dev.name, dev.path))
    print("Appuie sur les boutons (Ctrl+C pour quitter)...\n")

    seen = {}
    try:
        for event in dev.read_loop():
            if event.type != ecodes.EV_KEY:
                continue
            try:
                name = categorize(event).keycode
            except Exception:
                name = ecodes.KEY.get(event.code, "?")
            # evdev renvoie parfois plusieurs alias : ('BTN_A', 'BTN_SOUTH')
            if isinstance(name, (list, tuple)):
                names = list(name)
                name = "/".join(names)
            else:
                names = [name]
            label = {0: "relâché", 1: "enfoncé", 2: "répété"}.get(event.value, "?")
            print("  %-30s code=%-5d %s" % (name, event.code, label))
            # le premier alias est celui à copier dans config.BUTTONS
            seen[names[0]] = event.code
    except KeyboardInterrupt:
        pass

    if seen:
        print("\nCopie ces noms dans config.py (table BUTTONS) :")
        for name, code in sorted(seen.items(), key=lambda kv: kv[1]):
            print('    "mon_action": ["%s"],   # code %d' % (name, code))


if __name__ == "__main__":
    main()
