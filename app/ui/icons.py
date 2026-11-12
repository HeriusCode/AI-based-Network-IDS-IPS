"""Small SVG icon set for the Traffic Generator interface."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


PATHS = {
    "logo": '<path d="M12 2 4 6v6c0 5 3.4 8.3 8 10 4.6-1.7 8-5 8-10V6l-8-4Z"/><path d="M8 13h2l2-5 2 8 2-4h2"/>',
    "dashboard": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "connection": '<circle cx="6" cy="12" r="3"/><circle cx="18" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><path d="m9 11 6-3M9 13l6 3"/>',
    "generator": '<path d="M13 2 5 14h7l-1 8 8-12h-7l1-8Z"/>',
    "scenario": '<path d="M4 5h7v6H4zM13 13h7v6h-7zM15 5h5M4 17h5M11 8h4v8"/>',
    "statistics": '<path d="M4 20V10M10 20V4M16 20v-7M22 20V7"/>',
    "logs": '<path d="M5 2h10l4 4v16H5V2Z"/><path d="M15 2v5h4M8 12h8M8 16h8"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M10 2h4l.6 2.3 1.7.8 2.1-1.1 2.8 2.8-1.1 2.1.8 1.7L23 11v4l-2.3.6-.8 1.7 1.1 2.1-2.8 2.8-2.1-1.1-1.7.8L14 24h-4l-.6-2.3-1.7-.8-2.1 1.1-2.8-2.8 1.1-2.1-.8-1.7L1 15v-4l2.3-.6.8-1.7L3 6.6l2.8-2.8 2.1 1.1 1.7-.8L10 2Z" transform="translate(1) scale(.91)"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "bell": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4"/>',
    "minimize": '<path d="M5 12h14"/>',
    "maximize": '<rect x="5" y="5" width="14" height="14" rx="1"/>',
    "restore": '<path d="M8 8V5h11v11h-3"/><rect x="5" y="8" width="11" height="11" rx="1"/>',
    "close": '<path d="m6 6 12 12M18 6 6 18"/>',
    "shield": '<path d="M12 2 4 5v6c0 5 3.3 8.8 8 11 4.7-2.2 8-6 8-11V5l-8-3Z"/><path d="m8.5 12 2.2 2.2 4.8-5"/>',
}


def icon(name: str, color: str = "#94A3B8", size: int = 20) -> QIcon:
    if name not in PATHS:
        raise KeyError(f"Unknown icon: {name}")
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        f'{PATHS[name]}</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)
