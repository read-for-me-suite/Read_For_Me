"""
Pont de compatibilité vers le loader central de configuration.

Le point d'entrée officiel est ``config.config_loader``.
"""

from __future__ import annotations

from typing import Any, Dict

from config.config_loader import get_app_config as load_config


def get_config() -> Dict[str, Any]:
    """Alias lisible pour récupérer la configuration complète."""
    return load_config()
