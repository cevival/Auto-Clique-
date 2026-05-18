#!/usr/bin/env python3
import threading
import time
import sys
from pynput.mouse import Controller, Button
from pynput.keyboard import Key, KeyCode, Listener


def parse_key(s: str):
    s = s.strip()
    if not s:
        return KeyCode.from_char('²')
    if len(s) == 1:
        return KeyCode.from_char(s)
    name = s.lower()
    if hasattr(Key, name):
        return getattr(Key, name)
    return Key.f6


def main():
    try:
        interval_ms = int(input("Intervalle entre clics en millisecondes (ex: 100): ").strip())
    except Exception:
        interval_ms = 100
    try:
        clicks = int(input("Nombre de clics (0 pour infini): ").strip())
    except Exception:
        clicks = 0
    tk = input("Touche pour activer/désactiver (ex: ² ou a) [²]: ").strip() or "²"
    exit_tk = input("Touche pour quitter (ex: ESC) [ESC]: ").strip() or "ESC"
    toggle_key = parse_key(tk)
    exit_key = parse_key(exit_tk)

    run_event = threading.Event()
    stop_event = threading.Event()
    counter_lock = threading.Lock()
    count = {"n": 0}

    mouse = Controller()

    def click_loop():
        while not stop_event.is_set():
            run_event.wait()
            if stop_event.is_set():
                break
            with counter_lock:
                if clicks > 0 and count["n"] >= clicks:
                    run_event.clear()
                    print("Nombre de clics atteint.")
                    continue
            mouse.click(Button.left, 1)
            with counter_lock:
                count["n"] += 1
            time.sleep(interval_ms / 1000.0)

    t = threading.Thread(target=click_loop, daemon=True)
    t.start()

    print(f"Appuyez sur {tk} pour démarrer/arrêter, {exit_tk} pour quitter.")
    print(f"Intervalle: {interval_ms} ms, Clics: {'infini' if clicks == 0 else clicks}")

    def on_press(key):
        try:
            toggled = False
            if isinstance(toggle_key, Key) and key == toggle_key:
                toggled = True
            elif isinstance(toggle_key, KeyCode) and hasattr(key, 'char') and key.char == toggle_key.char:
                toggled = True

            if toggled:
                if run_event.is_set():
                    run_event.clear()
                    print("Arrêté.")
                else:
                    with counter_lock:
                        count["n"] = 0
                    run_event.set()
                    print("Démarré.")
                return

            exited = False
            if isinstance(exit_key, Key) and key == exit_key:
                exited = True
            elif isinstance(exit_key, KeyCode) and hasattr(key, 'char') and key.char == exit_key.char:
                exited = True

            if exited:
                print("Sortie...")
                stop_event.set()
                run_event.set()
                return False
        except Exception:
            pass

    with Listener(on_press=on_press) as listener:
        listener.join()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
