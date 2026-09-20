# -*- coding: utf-8 -*-
"""
Lecture de la Wiimote.

Approche retenue : on laisse le noyau + BlueZ faire le travail Bluetooth.
Une fois la manette appairée, elle apparaît comme une manette standard dans
/dev/input/eventX, et on lit ses boutons avec evdev. Pas de cwiid à compiler.
"""

import logging
import subprocess
import time

from evdev import InputDevice, ecodes, list_devices

log = logging.getLogger("brook.wiimote")


class Wiimote:
    def __init__(self, cfg):
        self.cfg = cfg
        self.device = None
        self.keymap = self._build_keymap()
        self._last_reconnect = 0.0

    # ------------------------------------------------------------- keymap
    def _build_keymap(self):
        """{code_evdev: action} à partir des noms de touches de config.py."""
        keymap = {}
        for action, names in self.cfg.BUTTONS.items():
            for name in names:
                code = getattr(ecodes, name, None)
                if code is None:
                    continue
                if isinstance(code, list):        # certains noms sont des listes
                    for c in code:
                        keymap.setdefault(c, action)
                else:
                    keymap.setdefault(code, action)
                break                              # premier nom trouvé suffit
        if not keymap:
            log.error("Aucun bouton reconnu, vérifie config.BUTTONS")
        else:
            log.debug("Keymap : %s", keymap)
        return keymap

    # ------------------------------------------------------- recherche / BT
    def _looks_like_wiimote(self, device):
        name = device.name.lower()
        return any(hint in name for hint in self.cfg.WIIMOTE_NAME_HINTS)

    def _find(self):
        """Renvoie un InputDevice wiimote, ou None."""
        if self.cfg.DEVICE_PATH:
            try:
                return InputDevice(self.cfg.DEVICE_PATH)
            except (OSError, IOError) as exc:
                log.warning("%s illisible : %s", self.cfg.DEVICE_PATH, exc)
                return None
        for path in list_devices():
            try:
                dev = InputDevice(path)
            except (OSError, IOError):
                continue
            if self._looks_like_wiimote(dev):
                return dev
        return None

    def _bluetooth_reconnect(self):
        """Demande à BlueZ de reconnecter les manettes Nintendo connues."""
        now = time.time()
        if now - self._last_reconnect < self.cfg.RECONNECT_EVERY:
            return
        self._last_reconnect = now
        try:
            out = subprocess.run(
                ["bluetoothctl", "devices"],
                capture_output=True, text=True, timeout=10,
            ).stdout
        except (OSError, subprocess.SubprocessError) as exc:
            log.debug("bluetoothctl injoignable : %s", exc)
            return
        macs = [
            line.split()[1]
            for line in out.splitlines()
            if len(line.split()) >= 3 and any(
                hint in line.lower() for hint in self.cfg.WIIMOTE_NAME_HINTS
            )
        ]
        if not macs:
            log.debug("Aucune manette Nintendo connue de bluetoothctl")
            return
        for mac in macs:
            log.info("Tentative de reconnexion de %s ...", mac)
            try:
                subprocess.run(
                    ["bluetoothctl", "connect", mac],
                    capture_output=True, text=True, timeout=15,
                )
            except subprocess.SubprocessError:
                pass

    def _open(self):
        """Attend qu'une manette apparaisse (en reconnectant au besoin)."""
        while True:
            dev = self._find()
            if dev:
                return dev
            if self.cfg.AUTO_RECONNECT:
                self._bluetooth_reconnect()
            log.info("En attente de la Wiimote... "
                     "(maintiens 1+2 ou appuie sur le bouton rouge)")
            time.sleep(self.cfg.RECONNECT_EVERY)

    # -------------------------------------------------------------- événements
    def events(self):
        """Génère (action, valeur) sans jamais s'arrêter.

        valeur : 1 = enfoncé, 0 = relâché, 2 = répétition.
        Se reconnecte tout seul si la manette se débranche.
        """
        while True:
            self.device = self._open()
            log.info("Wiimote connectée : %s (%s)",
                     self.device.name, self.device.path)
            try:
                for event in self.device.read_loop():
                    if event.type != ecodes.EV_KEY:
                        continue
                    action = self.keymap.get(event.code)
                    if action is None:
                        continue
                    yield action, event.value
            except (OSError, IOError) as exc:
                log.warning("Wiimote déconnectée : %s", exc)
            finally:
                try:
                    self.device.close()
                except Exception:
                    pass
                self.device = None
                time.sleep(1)

    def close(self):
        if self.device is not None:
            try:
                self.device.close()
            except Exception:
                pass
            self.device = None
