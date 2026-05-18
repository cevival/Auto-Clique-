# AutoClic (script Python)

Petit utilitaire d'auto-clic pour Windows. L'interface graphique permet de configurer :

- cadence en **intervalle** (ms / s / min / h) ou en **CPS** (clics par seconde)
- **variation aléatoire** de l'intervalle (humanisation, anti-détection simple)
- **bouton souris** (gauche / droite / milieu) et **simple ou double clic**
- nombre de clics (0 = infini), avec **compteur live** et bouton de réinitialisation
- **position** : suivre le curseur ou cliquer sur une **position fixe** capturée via `F8`
- **touche raccourci** démarrer/arrêter, configurable par capture clavier
- option **« toujours au-dessus »**
- **minimisation dans la zone de notification** (tray), avec confirmation à la fermeture pendant l'exécution
- **sauvegarde automatique** des paramètres dans `autoclic_config.json`

Installation et exécution :

1. Installer les dépendances :

```bash
python -m pip install -r requirements.txt
```

2. Interface graphique (recommandée) :

```bash
python auto_clicker_gui.py
```

3. Créer un raccourci épinglable (optionnel) :

```bash
python create_shortcut.py
```

Le script `create_shortcut.py` crée un fichier `AutoClic.lnk` sur votre Bureau. Vous pouvez ensuite glisser ce raccourci dans la barre des tâches pour l'épingler.

Notes :

- L'interface utilise `PyQt5` et `pynput`.
- Par défaut, la touche de toggle est `²` (adapté pour AZERTY). Vous pouvez la changer dans l'interface.
- Si la capture globale ne fonctionne pas, exécutez en administrateur.
- Sur Windows, si vous préférez ne pas avoir de fenêtre console lors du lancement via le raccourci, le raccourci utilise `pythonw.exe` quand il est disponible.
