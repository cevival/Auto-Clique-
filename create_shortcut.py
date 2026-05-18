#!/usr/bin/env python3
"""Crée un raccourci AutoClic.lnk sur le Bureau pointant vers la GUI."""
import os
import subprocess
import sys

try:
    import win32com.client
except Exception:
    print("pywin32 requis. Exécutez : python -m pip install pywin32")
    sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))


def ensure_icon() -> str:
    """Génère icon.ico si absent. Retourne son chemin (ou .png si echec)."""
    ico = os.path.join(HERE, "icon.ico")
    if os.path.exists(ico):
        return ico
    make_icon = os.path.join(HERE, "make_icon.py")
    if os.path.exists(make_icon):
        try:
            subprocess.check_call([sys.executable, make_icon])
        except Exception as e:
            print(f"Génération de l'icône échouée : {e}")
    if os.path.exists(ico):
        return ico
    png = os.path.join(HERE, "icon.png")
    return png if os.path.exists(png) else ""


def create_shortcut(target_script: str, name: str = "AutoClic") -> str:
    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
    lnk_path = os.path.join(desktop, f"{name}.lnk")

    base = os.path.dirname(sys.executable)
    pythonw = os.path.join(base, "pythonw.exe")
    launcher = pythonw if os.path.exists(pythonw) else sys.executable

    icon = ensure_icon()

    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(lnk_path)
    shortcut.Targetpath = launcher
    shortcut.Arguments = f'"{os.path.abspath(target_script)}"'
    shortcut.WorkingDirectory = os.path.dirname(os.path.abspath(target_script))
    if icon:
        shortcut.IconLocation = icon
    shortcut.Description = "AutoClic - Auto-clicker pour Windows"
    shortcut.save()
    return lnk_path


if __name__ == "__main__":
    script = os.path.join(HERE, "auto_clicker_gui.py")
    path = create_shortcut(script)
    print(f"Raccourci créé sur le Bureau : {path}")
