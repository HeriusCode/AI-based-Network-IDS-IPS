"""Small monochrome SVG icon set shared by the shell widgets."""

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtSvg import QSvgRenderer


PATHS = {
    "logo": '<path d="M12 2 3.5 5.5v6.2c0 5.2 3.5 8.8 8.5 10.3 5-1.5 8.5-5.1 8.5-10.3V5.5L12 2Z"/><path d="m8.5 12 2.3 2.3 4.8-5"/>',
    "dashboard": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "activity": '<path d="M3 12h4l3-7 4 14 3-7h4"/>',
    "shield": '<path d="M12 2 4 5v6c0 5 3.3 8.8 8 11 4.7-2.2 8-6 8-11V5l-8-3Z"/><path d="M9 12h6M12 9v6"/>',
    "trend": '<path d="m3 17 6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    "lock": '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/><path d="M12 14v3"/>',
    "nodes": '<rect x="9" y="2" width="6" height="5" rx="1"/><rect x="2" y="17" width="6" height="5" rx="1"/><rect x="16" y="17" width="6" height="5" rx="1"/><path d="M12 7v5M5 17v-5h14v5"/>',
    "bell": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4"/>',
    "document": '<path d="M5 2h10l4 4v16H5V2Z"/><path d="M15 2v5h4M8 12h8M8 16h8"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M10 2h4l.6 2.3 1.7.8 2.1-1.1 2.8 2.8-1.1 2.1.8 1.7L23 11v4l-2.3.6-.8 1.7 1.1 2.1-2.8 2.8-2.1-1.1-1.7.8L14 24h-4l-.6-2.3-1.7-.8-2.1 1.1-2.8-2.8 1.1-2.1-.8-1.7L1 15v-4l2.3-.6.8-1.7L3 6.6l2.8-2.8 2.1 1.1 1.7-.8L10 2Z" transform="translate(1 0) scale(.91)"/>',
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "chevron": '<path d="m9 18 6-6-6-6"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
}


def icon(name: str, color: str = "#94A3B8", size: int = 20) -> QIcon:
    """Render a crisp Qt icon without an external icon-font dependency."""
    if name not in PATHS:
        raise KeyError(f"Unknown icon: {name}")
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" '
        f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        f'{PATHS[name]}</svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    from PySide6.QtGui import QPainter
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)
