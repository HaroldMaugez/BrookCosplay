# -*- coding: utf-8 -*-
"""
Gestion du son.

Trois "couches" indépendantes (3 canaux pygame) :
    violin -> la boucle de violon, jouée tant que A est maintenu
    sfx    -> les bruitages (binks, yohohoho)
    song   -> les chansons du dossier songs/
"""

import logging
import os
import re

# Pas d'écran sur un Pi Lite : on le dit à SDL avant d'importer pygame.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "alsa")

import pygame  # noqa: E402  (import après les réglages d'environnement)

log = logging.getLogger("brook.audio")


class AudioError(Exception):
    pass


# Liste des cartes son du système ("/proc/asound/cards"). Surchargeable dans
# les tests.
CARDS_PATH = "/proc/asound/cards"


def _alsa_card_ids():
    """Noms ALSA des cartes, jack/HDMI exclus en premier.

    Après un reboot l'ordre des cartes peut changer (le jack passe de card 0 à
    card 1...), donc on s'adresse aux cartes par leur NOM et on laisse les
    cartes HDMI pour la fin : un écran éteint = pas de son.
    """
    ids = []
    try:
        with open(CARDS_PATH) as handle:
            for line in handle:
                match = re.match(r"\s*\d+\s+\[(\S+?)\s*\]", line)
                if match:
                    ids.append(match.group(1))
    except OSError:
        return []
    #sort stable : les non-HDMI remontent en tête
    ids.sort(key=lambda name: "hdmi" in name.lower())
    return ids


class Audio:
    def __init__(self, cfg):
        self.cfg = cfg
        self._init_mixer()
        pygame.mixer.set_num_channels(3)

        self.violin_ch = pygame.mixer.Channel(0)
        self.sfx_ch = pygame.mixer.Channel(1)
        self.song_ch = pygame.mixer.Channel(2)

        self.volume = cfg.VOLUME_START
        self._apply_volume()

        self._cache = {}
        self.violin_file = self._find_sound(cfg.SOUND_FILES["violin"])
        self.binks_file = self._find_sound(cfg.SOUND_FILES["binks"])
        self.yohoho_file = self._find_sound(cfg.SOUND_FILES["yohoho"])

        self.songs = self._list_songs()
        self.song_index = -1
        self._song_playing = False
        self._violin_on = False

        log.info("Violon : %s", self.violin_file or "AUCUN FICHIER TROUVÉ")
        log.info("Bink's : %s", self.binks_file or "AUCUN FICHIER TROUVÉ")
        log.info("Yohoho : %s", self.yohoho_file or "AUCUN FICHIER TROUVÉ")
        log.info("%d chanson(s) dans %s", len(self.songs), cfg.SONGS_DIR)

    # ------------------------------------------------------ init de la carte
    def _init_mixer(self):
        """Ouvre la carte son en essayant plusieurs réglages.

        Certaines cartes (HDMI du Pi, vieux chipsets) refusent 44100 Hz ou la
        stéréo : on retente en 48000, en mono, sur un autre driver, et sur le
        périphérique demandé dans config.AUDIO_DEVICE.
        """
        # Sur Raspberry Pi OS Lite, "default" échoue souvent (-524) alors que
        # sysdefault / plughw marchent. Et comme l'ordre des cartes change
        # d'un reboot à l'autre, on les nomme explicitement, HDMI en dernier.
        device_list = [self.cfg.AUDIO_DEVICE]
        for card in _alsa_card_ids():
            device_list += ["sysdefault:CARD=%s" % card,
                            "plughw:CARD=%s,DEV=0" % card]
        device_list += list(getattr(self.cfg, "FALLBACK_DEVICES", []))
        device_list += [None]
        devices = list(dict.fromkeys(device_list))
        log.debug("Périphériques à essayer : %s", devices)
        drivers = ["alsa", "pulse", ""]
        formats = [
            dict(frequency=self.cfg.SAMPLE_RATE, size=-16, channels=2,
                 buffer=self.cfg.BUFFER),
            dict(frequency=48000, size=-16, channels=2, buffer=2048),
            dict(frequency=44100, size=-16, channels=1, buffer=2048),
            dict(),                       # on laisse pygame choisir
        ]
        tried = []
        for drv in drivers:
            if drv:
                os.environ["SDL_AUDIODRIVER"] = drv
            else:
                os.environ.pop("SDL_AUDIODRIVER", None)
            for device in devices:
                for fmt in formats:
                    kw = dict(fmt)
                    if device:
                        kw["devicename"] = device
                    try:
                        pygame.mixer.init(**kw)
                        log.info("Carte son ouverte : driver=%s device=%s %s",
                                 drv or "auto", device or "default", kw)
                        return
                    except Exception as exc:
                        tried.append("%s / %s / %s -> %s"
                                     % (drv or "auto", device or "default",
                                        kw, exc))
                        try:
                            pygame.mixer.quit()
                        except Exception:
                            pass

        detail = "\n  ".join(tried[:8])
        raise AudioError(
            "Impossible d'ouvrir la carte son (ALSA).\n"
            "  Tentatives :\n  %s\n\n"
            "  À essayer dans l'ordre :\n"
            "    1) aplay -l                     -> quelle carte est dispo ?\n"
            "    2) sudo raspi-config            -> System Options > Audio >\n"
            "                                       Headphones (jack 3.5 mm)\n"
            "    3) speaker-test -c2 -t wav      -> tu dois entendre du bruit\n"
            "    4) un autre programme garde peut-être la carte :\n"
            "         sudo systemctl stop brook ; fuser -v /dev/snd/*\n"
            "    5) force la carte dans config.py :\n"
            "         AUDIO_DEVICE = \"plughw:0,0\"   (vois aplay -L)\n"
            "         SAMPLE_RATE = 48000\n" % detail
        )

    # ------------------------------------------------------------- fichiers
    def _find_sound(self, prefix):
        """Premier fichier du dossier sounds/ dont le nom commence par prefix."""
        d = self.cfg.SOUNDS_DIR
        if not d.is_dir():
            return None
        prefix = prefix.lower()
        for path in sorted(d.iterdir()):
            if path.is_file() and path.suffix.lower() in self.cfg.AUDIO_EXTENSIONS:
                if path.stem.lower().startswith(prefix):
                    return path
        return None

    def _list_songs(self):
        d = self.cfg.SONGS_DIR
        if not d.is_dir():
            return []
        return sorted(
            p for p in d.iterdir()
            if p.is_file() and p.suffix.lower() in self.cfg.AUDIO_EXTENSIONS
        )

    def _load(self, path):
        if path is None:
            return None
        if path not in self._cache:
            try:
                self._cache[path] = pygame.mixer.Sound(str(path))
            except Exception as exc:          # fichier corrompu / format inconnu
                log.error("Impossible de lire %s : %s", path.name, exc)
                self._cache[path] = None
        return self._cache[path]

    # --------------------------------------------------------------- volume
    def _gain(self, layer):
        return self.cfg.VOLUME_GAIN.get(layer, 1.0)

    def _apply_volume(self):
        self.violin_ch.set_volume(self.volume * self._gain("violin"))
        self.sfx_ch.set_volume(self.volume * self._gain("sfx"))
        self.song_ch.set_volume(self.volume * self._gain("song"))

    def set_volume(self, value):
        value = max(self.cfg.VOLUME_MIN, min(self.cfg.VOLUME_MAX, value))
        self.volume = round(value, 2)
        self._apply_volume()
        log.info("Volume : %d%%", int(self.volume * 100))
        return self.volume

    def change_volume(self, delta):
        return self.set_volume(self.volume + delta)

    # -------------------------------------------------------------- violon
    @property
    def violin_playing(self):
        return self._violin_on

    def violin_start(self):
        sound = self._load(self.violin_file)
        if sound is None:
            return
        if self._violin_on:
            return
        self._violin_on = True
        self.violin_ch.play(sound, loops=-1, fade_ms=self.cfg.VIOLIN_FADE_IN_MS)
        log.debug("Violon : démarré")

    def violin_stop(self):
        if self._violin_on:
            self._violin_on = False
            self.violin_ch.fadeout(self.cfg.VIOLIN_FADE_OUT_MS)
            log.debug("Violon : arrêté")

    # ------------------------------------------------------------ bruitages
    def play_binks(self):
        self._play_sfx(self.binks_file, "Bink's")

    def play_yohoho(self):
        self._play_sfx(self.yohoho_file, "Yohohoho")

    def _play_sfx(self, path, label):
        sound = self._load(path)
        if sound is None:
            return
        if not self.cfg.VIOLIN_OVER_OTHERS:
            self.violin_stop()
        self.sfx_ch.play(sound)
        log.debug("%s : joué", label)

    # ------------------------------------------------------------- chansons
    def play_song_at(self, index):
        if not self.songs:
            log.warning("Aucune chanson dans %s", self.cfg.SONGS_DIR)
            return
        index %= len(self.songs)
        sound = self._load(self.songs[index])
        if sound is None:
            return
        self.song_index = index
        if self.song_ch.get_busy():
            self.song_ch.stop()
        self.song_ch.play(sound, fade_ms=150)
        self._song_playing = True
        if not self.cfg.VIOLIN_OVER_OTHERS:
            self.violin_stop()
        log.info("Chanson %d/%d : %s", index + 1, len(self.songs),
                 self.songs[index].name)

    def next_song(self):
        self.play_song_at(self.song_index + 1 if self.songs else 0)

    def prev_song(self):
        self.play_song_at(self.song_index - 1 if self.songs else 0)

    def stop_song(self):
        self.song_ch.fadeout(self.cfg.STOP_FADE_MS)
        self._song_playing = False

    # ------------------------------------------------------------- boucle
    def update(self):
        """À appeler à chaque tour de boucle : gère l'enchaînement des chansons."""
        if self._song_playing and not self.song_ch.get_busy():
            self._song_playing = False
            if self.cfg.AUTO_NEXT_SONG and len(self.songs) > 1:
                self.next_song()

    def stop_all(self):
        """Home : on coupe tout."""
        self.song_ch.fadeout(self.cfg.STOP_FADE_MS)
        self.sfx_ch.fadeout(self.cfg.STOP_FADE_MS)
        self.violin_ch.fadeout(self.cfg.STOP_FADE_MS)
        self._song_playing = False
        log.info("Arrêt général")

    def quit(self):
        self.stop_all()
        pygame.mixer.quit()
