# installer/macos/rthook_platform.py
# Runtime hook: fix pkg_resources crash on PyInstaller + macOS
# AttributeError: module 'platform' has no attribute 'mac_ver'
import sys
import importlib

# Force reload of stdlib platform module if it got shadowed
if not hasattr(sys.modules.get('platform', None), 'mac_ver'):
    sys.modules.pop('platform', None)
    import platform  # noqa: F401 — reimport stdlib version
