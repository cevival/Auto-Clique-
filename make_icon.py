#!/usr/bin/env python3
"""Génère une icône AutoClic propre (PNG + ICO multi-tailles) avec PyQt5."""
import os
import sys

from PyQt5.QtCore import QPoint, QRect, Qt
from PyQt5.QtGui import QBrush, QColor, QFont, QImage, QLinearGradient, QPainter, QPen
from PyQt5.QtWidgets import QApplication

HERE = os.path.dirname(os.path.abspath(__file__))


def render(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)

    grad = QLinearGradient(0, 0, 0, size)
    grad.setColorAt(0.0, QColor("#42a5f5"))
    grad.setColorAt(1.0, QColor("#1565c0"))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.NoPen)
    p.drawEllipse(1, 1, size - 2, size - 2)

    pen = QPen(QColor(255, 255, 255, 230))
    pen.setWidth(max(2, size // 20))
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    inset = size // 6
    p.drawEllipse(inset, inset, size - 2 * inset, size - 2 * inset)

    cx = size // 2
    cy = size // 2
    arm = size // 10
    pen.setWidth(max(2, size // 22))
    p.setPen(pen)
    p.drawLine(cx - arm, cy, cx + arm, cy)
    p.drawLine(cx, cy - arm, cx, cy + arm)

    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#e53935"))
    r = max(2, size // 16)
    p.drawEllipse(QPoint(cx, cy), r, r)

    p.end()
    return img


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    _ = app  # silence linter

    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [render(s) for s in sizes]

    png_path = os.path.join(HERE, "icon.png")
    images[-1].save(png_path, "PNG")
    print(f"PNG  -> {png_path}")

    ico_path = os.path.join(HERE, "icon.ico")
    try:
        from PIL import Image  # type: ignore

        pil_imgs = []
        for img, s in zip(images, sizes):
            ba = img.bits().asstring(img.byteCount())
            pil = Image.frombuffer("RGBA", (s, s), ba, "raw", "BGRA", 0, 1)
            pil_imgs.append(pil)
        pil_imgs[0].save(
            ico_path,
            format="ICO",
            sizes=[(s, s) for s in sizes],
            append_images=pil_imgs[1:],
        )
        print(f"ICO  -> {ico_path} (multi-tailles)")
    except Exception as e:
        images[-1].save(ico_path, "ICO")
        print(f"ICO  -> {ico_path} (mono-taille, Pillow indisponible: {e})")


if __name__ == "__main__":
    main()
