"""Account registration window shown before the IDS/IPS workspace.

Re-exports unified authentication components from auth_window.
"""

from app.ui.auth_window import (
    AuthResizeHandle,
    AuthTitleBar,
    AuthWindow,
    AuthWindowMixin,
    NetworkBackground,
    RegisterBrandPanel,
    RegisterStage,
    RegisterWindow,
    RegistrationHeroWidget,
)

# Backwards compatibility alias
BrandPanel = RegisterBrandPanel

__all__ = [
    "AuthResizeHandle",
    "AuthTitleBar",
    "AuthWindow",
    "AuthWindowMixin",
    "BrandPanel",
    "NetworkBackground",
    "RegisterBrandPanel",
    "RegisterStage",
    "RegisterWindow",
    "RegistrationHeroWidget",
]
