#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BrookCosplay -- le jukebox de Brook piloté à la Wiimote.

    A (maintenu)  -> violon en boucle
    1             -> le bon rythme de Bink's
    B             -> Yohohoho !
    2             -> chanson suivante (dossier songs/)
    Bas           -> chanson précédente
    + / -         -> volume
    Home          -> arrêt d'urgence

Usage :
    python3 brook.py            # le programme
    python3 brook.py --list     # montre les fichiers trouvés
    python3 brook.py --debug    # verbeux
"""

import argparse
import logging
import signal
import sys

import config as cfg
from audio import Audio, AudioError
from wiimote_input import Wiimote

log = logging.getLogger("brook")


def setup_logging(level):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )


def list_files():
    print("Bruitages attendus dans %s :" % cfg.SOUNDS_DIR)
    for key, prefix in cfg.SOUND_FILES.items():
        print("   %-8s -> %s.*" % (key, prefix))
    if cfg.SOUNDS_DIR.is_dir():
        print("   présents :", ", ".join(sorted(
            p.name for p in cfg.SOUNDS_DIR.iterdir() if p.is_file()
        )) or "(dossier vide)")
    print("Chansons dans %s :" % cfg.SONGS_DIR)
    if cfg.SONGS_DIR.is_dir():
        songs = sorted(p.name for p in cfg.SONGS_DIR.iterdir()
                       if p.is_file()
                       and p.suffix.lower() in cfg.AUDIO_EXTENSIONS)
        for i, name in enumerate(songs, 1):
            print("   %2d. %s" % (i, name))
        if not songs:
            print("   (dossier vide)")


def handle(audio, action, value):
    """Traduit un bouton en action sonore. value: 1=enfoncé, 0=relâché, 2=répété"""
    pressed = value in (1, 2)

    if action == "violin":
        # maintenir A = jouer du violon, relâcher = s'arrêter
        if value == 1:
            audio.violin_start()
        elif value == 0:
            audio.violin_stop()

    elif action == "binks":
        if value == 1:
            audio.play_binks()

    elif action == "yohoho":
        if value == 1:
            audio.play_yohoho()

    elif action == "next_song":
        if value == 1:
            audio.next_song()

    elif action == "prev_song":
        if value == 1:
            audio.prev_song()

    elif action == "vol_up":
        if pressed:
            audio.change_volume(+cfg.VOLUME_STEP)

    elif action == "vol_down":
        if pressed:
            audio.change_volume(-cfg.VOLUME_STEP)

    elif action == "panic":
        if value == 1:
            audio.stop_all()


def main():
    parser = argparse.ArgumentParser(description="Jukebox Brook à la Wiimote")
    parser.add_argument("--debug", action="store_true", help="logs verbeux")
    parser.add_argument("--list", action="store_true",
                        help="montre les fichiers audio trouvés et quitte")
    parser.add_argument("--device", default=None,
                        help="force un périphérique, ex: /dev/input/event3")
    parser.add_argument("--volume", type=float, default=None,
                        help="volume de démarrage (0.0 à 1.0)")
    args = parser.parse_args()

    setup_logging("DEBUG" if args.debug else cfg.LOG_LEVEL)

    if args.list:
        list_files()
        return 0
    if args.device:
        cfg.DEVICE_PATH = args.device
    if args.volume is not None:
        cfg.VOLUME_START = max(0.0, min(1.0, args.volume))

    try:
        audio = Audio(cfg)
    except AudioError as exc:
        log.error("%s", exc)
        return 1

    if not audio.songs and not any(
        (audio.violin_file, audio.binks_file, audio.yohoho_file)
    ):
        log.warning("Aucun fichier audio trouvé dans sounds/ ni songs/ !")

    wiimote = Wiimote(cfg)

    def bye(signum=None, _frame=None):
        log.info("Arrêt du programme%s",
                 "" if signum is None else " (signal %s)" % signum)
        sys.exit(0)

    signal.signal(signal.SIGTERM, bye)
    signal.signal(signal.SIGINT, bye)

    log.info("Brook est prêt. Volume %d%%.", int(audio.volume * 100))
    try:
        for action, value in wiimote.events():
            log.debug("Bouton %s value=%s", action, value)
            handle(audio, action, value)
            audio.update()
    finally:
        audio.quit()
        wiimote.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
