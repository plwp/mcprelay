"""Community-edition license manager (the open-source default).

The commercial ``mcprelay.license`` module — shipped by the separate
``mcprelay-enterprise`` package — gates paid features. When it is not installed
(the OSS default), :mod:`mcprelay.server` falls back to this no-op community
manager so the core runs, and its tests run, standalone. Enterprise features
simply report as unavailable.
"""

from typing import Any, Dict, Optional


class CommunityLicenseManager:
    """A no-op license manager: community tier, no enterprise features."""

    def get_license_info(self) -> Dict[str, Any]:
        return {"tier": "community", "licensed": False, "valid": True}

    def get_feature_status(self) -> Dict[str, Any]:
        return {"enterprise": False, "features": []}


_manager: Optional[CommunityLicenseManager] = None


def init_license_manager(
    license_key: Optional[str] = None, license_file: Optional[str] = None
) -> CommunityLicenseManager:
    """Initialise the community license manager (any key/file is ignored)."""
    global _manager
    _manager = CommunityLicenseManager()
    return _manager


def get_license_manager() -> Optional[CommunityLicenseManager]:
    return _manager
