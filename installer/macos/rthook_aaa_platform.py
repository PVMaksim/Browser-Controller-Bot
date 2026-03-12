# installer/macos/rthook_aaa_platform.py
# Replaces PyInstaller's frozen platform stub with the real stdlib platform.py
# Must be listed first in runtime_hooks so it runs before pyi_rth_pkgres
import sys
import os
import importlib.util

_meipass = getattr(sys, '_MEIPASS', None)
if _meipass:
    _plat_path = os.path.join(_meipass, '_real_platform.py')
    if os.path.exists(_plat_path):
        _spec = importlib.util.spec_from_file_location('platform', _plat_path)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        sys.modules['platform'] = _mod
