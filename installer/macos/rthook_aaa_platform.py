# installer/macos/rthook_aaa_platform.py
# Must run before ALL other hooks — fixes PyInstaller stub platform module
# that is missing mac_ver, python_implementation, etc.
import sys

def _fix_platform():
    import importlib, types
    plat = sys.modules.get('platform')
    # Check if PyInstaller gave us a broken stub
    if plat is None or not callable(getattr(plat, 'python_implementation', None)):
        sys.modules.pop('platform', None)
        # Load real stdlib platform bypassing PyInstaller importer
        import importlib.util, os
        stdlib_path = os.path.join(os.path.dirname(os.__file__), 'platform.py')
        if os.path.exists(stdlib_path):
            spec = importlib.util.spec_from_file_location('platform', stdlib_path)
            real_plat = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(real_plat)
            sys.modules['platform'] = real_plat

_fix_platform()
