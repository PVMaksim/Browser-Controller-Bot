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

# ── Fix 2: patch aiogram Router.include_router ────────────────────────────────
try:
    import aiogram.dispatcher.router as _r

    def _patched(self, router):
        # Log diagnostics to help debug
        import sys as _sys
        _is = isinstance(router, _r.Router)
        _name = type(router).__name__
        _mod = type(router).__module__
        _mro = [c.__name__ for c in type(router).__mro__]
        print(f"[RTHOOK DEBUG] include_router called:"
              f" isinstance={_is}, name={_name}, module={_mod}, mro={_mro}",
              file=_sys.stderr, flush=True)

        if not _is:
            # Force class identity — same structure, different class object
            try:
                router.__class__ = _r.Router
                print("[RTHOOK DEBUG] __class__ reassigned OK", file=_sys.stderr)
            except TypeError as e:
                print(f"[RTHOOK DEBUG] __class__ reassign failed: {e}", file=_sys.stderr)
                raise ValueError("router should be instance of Router not type") from e

        return _r.Router._orig_include(self, router)

    _r.Router._orig_include = _r.Router.include_router
    _r.Router.include_router = _patched
except Exception as e:
    import sys as _sys
    print(f"[RTHOOK DEBUG] patch failed: {e}", file=_sys.stderr)
