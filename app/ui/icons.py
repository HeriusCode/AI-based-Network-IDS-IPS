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
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    "box": '<path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 7 9 5 9-5M3 7v10l9 5 9-5V7M12 12v10"/>',
    "warning": '<path d="M10.3 3.7 1.8 18.4A2 2 0 0 0 3.5 21h17a2 2 0 0 0 1.7-2.6L13.7 3.7a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/>',
    "blocked": '<circle cx="12" cy="12" r="9"/><path d="m7 7 10 10M17 7 7 17"/>',
    "logout": '<path d="M10 4H4v16h6M14 8l4 4-4 4M8 12h10"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "minimize": '<path d="M5 12h14"/>',
    "maximize": '<rect x="5" y="5" width="14" height="14" rx="1"/>',
    "restore": '<path d="M8 8V5h11v11h-3"/><rect x="5" y="8" width="11" height="11" rx="1"/>',
    "close": '<path d="m6 6 12 12M18 6 6 18"/>',
    "database": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    "arrow_up": '<path d="M12 20V5M6 11l6-6 6 6"/>',
    "arrow_down": '<path d="M12 4v15M6 13l6 6 6-6"/>',
    "refresh": '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6.1 8a7 7 0 0 1 11.7-1L20 12M4 12l2.2 5a7 7 0 0 0 11.7-1"/>',
    "pause": '<path d="M8 5v14M16 5v14"/>',
    "download": '<path d="M12 3v12M7 10l5 5 5-5M5 20h14"/>',
    "bug": '<path d="M8 9h8v8a4 4 0 0 1-8 0V9ZM9 9V7a3 3 0 0 1 6 0v2M4 13h4M16 13h4M5 8l3 2M19 8l-3 2M5 19l3-2M19 19l-3-2M12 12v8"/>',
    "brain": '<path d="M9 4a3 3 0 0 0-5 2.2A3.5 3.5 0 0 0 4 13a3 3 0 0 0 3 5h2M15 4a3 3 0 0 1 5 2.2 3.5 3.5 0 0 1 0 6.8 3 3 0 0 1-3 5h-2M9 3v18M15 3v18M6 9h3M15 9h3M6 15h3M15 15h3"/>',
    "siren": '<path d="M6 16h12l-1-8a5 5 0 0 0-10 0l-1 8ZM4 20h16M12 3V1M3 8H1M23 8h-2M5 3 3 1M19 3l2-2"/>',
    "eye": '<path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="2.5"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18"/>',
    "speed": '<path d="M4 17a8 8 0 1 1 16 0M12 17l4-6M7 15h.01M17 15h.01M12 9h.01"/>',
    "edit": '<path d="m4 20 4-1 11-11-3-3L5 16l-1 4ZM14 7l3 3"/>',
    "trash": '<path d="M4 7h16M9 7V4h6v3M7 7l1 14h8l1-14M10 11v6M14 11v6"/>',
    "check": '<path d="m5 12 4 4L19 6"/>',
    "switch": '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M7 9h10M7 15h10M9 7 7 9l2 2M15 13l2 2-2 2"/>',
    "server": '<rect x="4" y="3" width="16" height="6" rx="1"/><rect x="4" y="9" width="16" height="6" rx="1"/><rect x="4" y="15" width="16" height="6" rx="1"/><path d="M7 6h.01M7 12h.01M7 18h.01"/>',
    "monitor": '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>',
    "firewall": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M3 16h18M9 4v6M15 10v6M8 16v4"/>',
    "cloud": '<path d="M6 19h12a4 4 0 0 0 .5-8A6.5 6.5 0 0 0 6 9a5 5 0 0 0 0 10Z"/>',
    "expand": '<path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 11v6M12 7h.01"/>',
    "palette": '<path d="M12 3a9 9 0 0 0 0 18h1.5a2 2 0 0 0 0-4H12a2 2 0 0 1 0-4h3a6 6 0 0 0-3-10Z"/><circle cx="7" cy="10" r="1"/><circle cx="9" cy="6" r="1"/><circle cx="14" cy="6" r="1"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-2 2M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l2-2"/>',
    "save": '<path d="M5 3h12l2 2v16H5V3Z"/><path d="M8 3v6h8V3M8 21v-7h8v7"/>',
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
