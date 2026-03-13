# installer/macos/rthook_aaa_platform.py
import sys
import os

# ── Fix 1: restore stdlib platform attributes ─────────────────────────────────
import platform as _platform
def _p(name, fn):
    if not hasattr(_platform, name):
        setattr(_platform, name, fn)
_p('system',                lambda: 'Darwin' if sys.platform == 'darwin' else ('Windows' if sys.platform == 'win32' else 'Linux'))
_p('node',                  lambda: '')
_p('release',               lambda: '')
_p('version',               lambda: '')
_p('machine',               lambda: sys.platform)
_p('processor',             lambda: '')
_p('architecture',          lambda bits='', linkage='': (bits, linkage))
_p('python_implementation', lambda: 'CPython')
_p('python_version',        lambda: '.'.join(str(x) for x in sys.version_info[:3]))
_p('python_version_tuple',  lambda: tuple(str(x) for x in sys.version_info[:3]))
_p('python_build',          lambda: ('', ''))
_p('python_compiler',       lambda: '')
_p('python_branch',         lambda: '')
_p('python_revision',       lambda: '')
_p('mac_ver',               lambda terse=False, release='', versioninfo=('','',''), machine='': (release, versioninfo, machine))
_p('win32_ver',             lambda release='', version='', csd='', ptype='': (release, version, csd, ptype))
_p('win32_edition',         lambda: '')
_p('win32_is_iot',          lambda: False)
_p('uname',                 lambda: ('','','','','',''))
_p('platform',              lambda aliased=False, terse=False: '')
del _p

# ── Fix 2: strip external site-packages so aiogram loads from bundle ONLY ─────
# When user has Python + aiogram installed system-wide, PyInstaller bundles its
# own copy in Frameworks/ but sys.path still contains system site-packages.
# Python then loads aiogram twice → two Router class objects → isinstance fails.
if hasattr(sys, '_MEIPASS'):
    meipass = sys._MEIPASS
    cleaned = []
    for p in sys.path:
        norm = os.path.normpath(p)
        # Keep: _MEIPASS itself, stdlib paths, empty string (cwd)
        # Drop: anything containing 'site-packages' or 'dist-packages'
        if 'site-packages' in norm or 'dist-packages' in norm:
            continue
        cleaned.append(p)
    # Always keep _MEIPASS first
    if meipass not in cleaned:
        cleaned.insert(0, meipass)
    sys.path[:] = cleaned
