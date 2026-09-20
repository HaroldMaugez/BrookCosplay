# 🎻 BrookCosplay

Jukebox pour cosplay de **Brook** (One Piece), piloté avec une **Wiimote** depuis un
**Raspberry Pi 4B** (Raspberry Pi OS Lite, headless). Le Pi est planqué dans le
costume, branché sur des enceintes : tu joues du violon, tu balances le bon rythme
de Bink's Sake, tu fais « Yohohoho ! » et tu lances tes chansons, le tout à la
manette.

## Ce que font les boutons

| Bouton            | Action                                                        |
|-------------------|---------------------------------------------------------------|
| **A** (maintenu)  | joue du violon en boucle, s'arrête quand tu relâches           |
| **1**             | le bon rythme de Bink's Sake (one-shot)                        |
| **B**             | « Yohohoho ! » (one-shot)                                      |
| **2**             | chanson suivante du dossier `songs/`                           |
| **Croix bas**     | chanson précédente                                             |
| **+ / −**         | volume (+10 % / −10 % par appui)                               |
| **Home**          | arrêt d'urgence : coupe tout                                   |

Le violon continue par-dessus les bruitages (c'est tout l'intérêt de Brook).
Si tu préfères un seul son à la fois, mets `VIOLIN_OVER_OTHERS = False` dans
`config.py`.

## Comment ça marche

```
Wiimote ──Bluetooth──> BlueZ ──> pilote noyau hid-wiimote ──> /dev/input/eventX
                                                                    │
                                              brook.py <── evdev ───┘
                                                  │
                                              pygame ──> ALSA ──> enceintes
```

Pas de `cwiid` à compiler : depuis des années le noyau sait causer à la Wiimote
tout seul, il suffit de lire ses événements comme ceux d'un clavier.

Codes de touches réellement utilisés (pilote `hid-wiimote`) :
`BTN_A`, `BTN_B`, `BTN_1`, `BTN_2`, `BTN_MODE` (Home), `KEY_NEXT` (+),
`KEY_PREVIOUS` (−), `KEY_DOWN` (croix bas). Ils sont déjà dans `config.py`.

## Installation

```bash
# 1. sur le Pi
sudo apt update && sudo apt upgrade -y
git clone https://github.com/TOI/BrookCosplay.git
cd BrookCosplay

# 2. dépendances (paquets système, sinon pip)
./install.sh

# 3. appaire la manette
./tools/pair_wiimote.sh
#   -> appuie sur 1+2 (ou sur le bouton rouge sous le cache-piles)
#   -> note l'adresse MAC affichée par le scan

# 4. vérifie que les boutons sont bien vus
python3 tools/find_buttons.py

# 5. dépose tes fichiers audio dans sounds/ et songs/
#    (puis : python3 brook.py --list  pour vérifier)

# 6. test à la main
python3 brook.py

# 7. démarrage automatique au boot
./install.sh --service
```

## Où mettre les fichiers audio

```
sounds/            # bruitages, trouvés par préfixe de nom
  violon.*         #   boucle de violon, déclenchée par A
  binks.*          #   le bon rythme de Bink's, déclenché par 1
  yohoho.*         #   « Yohohoho ! », déclenché par B
songs/             # chansons, jouées dans l'ordre alphabétique
  01-binks-no-sake.ogg
  02-yohoho.ogg
```

Formats : **.ogg** et **.wav** nickel, **.mp3** ça passe, **.m4a/.aac** non
(convertis avec `ffmpeg -i truc.m4a truc.ogg`).

## Commandes utiles

```bash
python3 brook.py            # lancer
python3 brook.py --list     # voir les fichiers détectés
python3 brook.py --debug    # voir chaque appui dans les logs
python3 brook.py --device /dev/input/event3   # forcer une manette
sudo systemctl status brook
journalctl -u brook -f      # logs en direct
sudo systemctl restart brook
```

## Dépannage

**Aucun son** – vérifie la sortie audio : `sudo raspi-config` → *System Options*
→ *Audio* → jack 3.5 mm. Puis `speaker-test -c2 -t wav`. Le programme force
`SDL_AUDIODRIVER=alsa` au démarrage.

**La Wiimote n'est pas détectée** – `bluetoothctl devices` doit la lister
(*Nintendo RVL-CNT-01*). Sinon : `sudo bluetoothctl` → `scan on`, appuie sur
1 + 2, puis `pair`, `trust`, `connect <MAC>`. Être dans le groupe `input` est
nécessaire (`sudo usermod -aG input $USER`, puis reconnecte-toi).

**La manette se déconnecte et ne revient pas** – c'est classique : la Wiimote se
met en veille. Le programme retente `bluetoothctl connect` toutes les 5 s
(`AUTO_RECONNECT` dans `config.py`). Si ça ne suffit pas, ajoute dans
`/etc/bluetooth/main.conf` :

```ini
[General]
Privacy=off
ClassicBondedOnly=false
```
puis `sudo systemctl restart bluetooth`.

**Un bouton ne fait rien** – `python3 tools/find_buttons.py`, note le nom affiché
(`BTN_A`, `KEY_1`…) et ajoute-le dans `BUTTONS` dans `config.py`.

**Le son saccade** – augmente `buffer` dans `audio.py` (`pygame.mixer.init(...
buffer=2048)`), et utilise des `.ogg` plutôt que des `.mp3`.

**Volume trop faible** – `alsamixer` (touche F6 pour choisir la carte), puis
`/etc/systemd/system/brook.service` garde `VOLUME_START` dans `config.py`.

## Perso

Tout est dans **`config.py`** : chemins, mapping des boutons, volume, fondus,
enchaînement auto des chansons, reconnexion. Le reste du code n'a pas besoin
d'être touché.

## Structure

```
brook.py            boucle principale : bouton -> action
wiimote_input.py    recherche de la manette, lecture evdev, reconnexion BlueZ
audio.py            les 3 canaux son (violon / bruitages / chansons)
config.py           ⚙️ tout ce qui se règle
tools/find_buttons.py   affiche le nom evdev des boutons pressés
tools/pair_wiimote.sh   appairage Bluetooth guidé
install.sh          installe les dépendances + le service
brook.service       unité systemd (démarrage au boot)
sounds/             violon.*, binks.*, yohoho.*
songs/              tes chansons
```
