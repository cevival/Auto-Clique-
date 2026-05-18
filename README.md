# 🖱️ AutoClic

> Auto-clicker léger pour Windows avec interface graphique PyQt5.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey?logo=windows)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Fonctionnalités

| Catégorie | Détail |
|-----------|--------|
| **Cadence** | Intervalle en ms / s / min / h, ou directement en CPS (clics par seconde) |
| **Humanisation** | Variation aléatoire de l'intervalle (±x ms) pour simuler un comportement humain |
| **Bouton souris** | Gauche, droite ou milieu — simple ou double clic |
| **Compteur** | Nombre de clics cible (0 = infini), compteur live, bouton de réinitialisation |
| **Position** | Suivre le curseur **ou** cliquer sur une position fixe capturée via `F8` |
| **Hotkey** | Touche démarrer/arrêter configurable par capture clavier (défaut : `²` AZERTY) |
| **Interface** | Option « toujours au-dessus », minimisation dans la zone de notification (tray) |
| **Persistance** | Sauvegarde automatique des réglages dans `autoclic_config.json` |

---

## 📋 Prérequis

- **Windows** 10 / 11
- **Python 3.9+** — [Télécharger](https://www.python.org/downloads/)

> Si Python n'est pas dans votre PATH, exécutez `update_path.ps1` en PowerShell (une seule fois).

---

## 🚀 Installation

```bash
# 1. Cloner le dépôt
git clone https://github.com/cevival/Auto-Clique-.git
cd Auto-Clique-

# 2. Installer les dépendances
python -m pip install -r requirements.txt
```

---

## ▶️ Utilisation

### Interface graphique (recommandée)

```bash
python auto_clicker_gui.py
```

1. Configurez la cadence, le bouton et la position.
2. Cliquez sur **Démarrer** ou appuyez sur votre hotkey (`²` par défaut).
3. Appuyez à nouveau sur la hotkey (ou cliquez **Arrêter**) pour stopper.

### Mode CLI (sans interface)

```bash
python auto_clicker.py
```

Répondez aux questions interactives (intervalle, nombre de clics, touches).

### Créer un raccourci Bureau épinglable (optionnel)

```bash
python create_shortcut.py
```

Génère `AutoClic.lnk` sur le Bureau. Glissez-le dans la barre des tâches pour l'épingler. Le raccourci utilise `pythonw.exe` quand disponible (pas de fenêtre console).

---

## 📁 Structure du projet

```
Auto-Clique-/
├── auto_clicker.py       # Auto-clicker en ligne de commande
├── auto_clicker_gui.py   # Interface graphique PyQt5
├── create_shortcut.py    # Crée un raccourci .lnk sur le Bureau
├── make_icon.py          # Génère icon.png et icon.ico via PyQt5
├── update_path.ps1       # Ajoute Python au PATH utilisateur
└── requirements.txt      # Dépendances Python
```

---

## 🔧 Dépendances

| Package | Rôle |
|---------|------|
| `pynput` | Contrôle souris et écoute clavier global |
| `PyQt5` | Interface graphique et icône tray |
| `pywin32` | Création du raccourci `.lnk` Windows |

---

## ⚠️ Notes

- Si la capture globale des touches ne fonctionne pas, **exécutez en administrateur**.
- Le fichier `autoclic_config.json` est créé automatiquement au premier lancement et ignoré par git.
- Les icônes (`icon.png`, `icon.ico`) sont générées par `make_icon.py` et ignorées par git.
