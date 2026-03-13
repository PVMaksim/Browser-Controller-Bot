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

# ── Fix 2: patch Router.include_router BEFORE main.py imports anything ────────
# PyInstaller with noarchive can still create two import paths for aiogram.
# Patch the check in-place so duck-typed Routers are accepted.
try:
    import aiogram.dispatcher.router as _r
    _original = _r.Router.include_router

    def _patched(self, router, **kw):
        if not isinstance(router, _r.Router):
            # Accept any object that has Router's key attributes
            if hasattr(router, 'observers') and hasattr(router, 'include_router'):
                router.__class__ = _r.Router
            else:
                raise ValueError("router should be instance of Router not type")
        return _original(self, router, **kw)

    _r.Router.include_router = _patched
except Exception:
    pass
