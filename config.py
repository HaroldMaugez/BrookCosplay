# -*- coding: utf-8 -*-
"""
BrookCosplay -- réglages.

C'est le SEUL fichier que tu as besoin de modifier pour la config de base.
"""

from pathlib import Path

# ------------------------------------------------------------------ dossiers
BASE_DIR = Path(__file__).resolve().parent
SOUNDS_DIR = BASE_DIR / "sounds"   # bruitages : violon, binks, yohohoho
SONGS_DIR = BASE_DIR / "songs"     # chansons parcourues avec le bouton 2

# Formats acceptés (pygame lit surtout bien .wav / .ogg ; le mp3 passe aussi,
# le .m4a/.aac non -> convertis en .ogg si besoin).
AUDIO_EXTENSIONS = (".mp3", ".wav", ".ogg", ".flac", ".opus")

# Les bruitages sont trouvés par PRÉFIXE, sans tenir compte de la casse ni de
# l'extension. Exemple pour "violon" :
#     sounds/violon.mp3  /  sounds/violon_boucle.ogg  /  sounds/Violon.wav
# tous les trois conviennent.
SOUND_FILES = {
    "violin": "violon",
    "binks": "binks",
    "yohoho": "yohoho",
}

# ------------------------------------------------------------------ boutons
# Mapping action -> noms de touches evdev.
# Plusieurs noms sont donnés pour chaque action parce que le pilote Wiimote du
# noyau a changé d'avis selon les versions : le premier nom trouvé gagne.
# Si un bouton ne répond pas, lance :  python3 tools/find_buttons.py
BUTTONS = {
    "violin":    ["BTN_A", "KEY_A"],                      # maintenir A
    "binks":     ["BTN_1", "KEY_1"],                      # 1
    "yohoho":    ["BTN_B", "KEY_B"],                      # B
    "next_song": ["BTN_2", "KEY_2"],                      # 2
    "prev_song": ["KEY_DOWN"],                            # croix bas
    "vol_up":    ["KEY_NEXT", "KEY_EQUAL", "KEY_KPPLUS", "KEY_VOLUMEUP"],      # +
    "vol_down":  ["KEY_PREVIOUS", "KEY_MINUS", "KEY_KPMINUS", "KEY_VOLUMEDOWN"],  # -
    "panic":     ["BTN_MODE", "KEY_HOMEPAGE", "KEY_MENU"],  # Home
}

# ------------------------------------------------------------------ carte son
# Laisse None : pygame essaie plusieurs réglages tout seul. Si ta carte est
# capricieuse (erreur "ALSA: Couldn't open audio device"), mets le nom exact
# renvoyé par `aplay -L`, par exemple "plughw:0,0" ou "hw:0,0".
AUDIO_DEVICE = None
SAMPLE_RATE = 44100     # 48000 si ta carte refuse 44100
BUFFER = 1024           # 2048 ou 4096 si le son craque

# Noms de périphériques essayés à la suite si "default" refuse de s'ouvrir
# (cas classique sur Raspberry Pi OS Lite : "default" renvoie l'erreur -524
# alors que sysdefault:0 ou plughw:0,0 marchent très bien).
FALLBACK_DEVICES = ["sysdefault:0", "plughw:0,0", "hw:0,0"]

# ------------------------------------------------------------------ volume
VOLUME_START = 0.7      # volume au démarrage (0.0 à 1.0)
VOLUME_STEP = 0.1       # pas d'un appui sur + / -
VOLUME_MIN = 0.0
VOLUME_MAX = 1.0

# Gain propre à chaque "couche" (1.0 = pas de changement).
# Pratique pour baisser un violon trop fort par rapport aux chansons.
VOLUME_GAIN = {
    "violin": 1.0,
    "sfx": 1.0,      # binks + yohohoho
    "song": 1.0,
}

# ------------------------------------------------------------------ lecture
VIOLIN_FADE_IN_MS = 150     # fondu enchaîné à l'appui sur A
VIOLIN_FADE_OUT_MS = 400    # fondu au relâchement de A
STOP_FADE_MS = 400          # fondu quand Home / quand on change de chanson

# Le violon continue-t-il par-dessus un bruitage (yohohoho) ou une chanson ?
# True  -> violon maintenu + B = les deux en même temps (comportement Brook)
# False -> un seul son à la fois, le dernier appui coupe le précédent
VIOLIN_OVER_OTHERS = True

# Enchaîner tout seul la chanson suivante quand celle en cours se termine.
AUTO_NEXT_SONG = True

# ------------------------------------------------------------------ wiimote
# Morceaux de nom qui identifient la manette dans /dev/input
WIIMOTE_NAME_HINTS = ["wiimote", "wii remote", "nintendo wii", "nintendo"]

# Laisse None pour l'auto-détection. Sinon mets "/dev/input/event3" (utile si tu
# branches d'autres manettes). Le chemin s'affiche au démarrage du programme.
DEVICE_PATH = None

# Le Pi réessaie-t-il de reconnecter la manette quand elle disparaît ?
AUTO_RECONNECT = True
RECONNECT_EVERY = 5.0   # secondes entre deux tentatives

# ------------------------------------------------------------------ divers
LOG_LEVEL = "INFO"      # DEBUG pour voir absolument tout
