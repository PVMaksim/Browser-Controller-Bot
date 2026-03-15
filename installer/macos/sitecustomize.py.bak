# sitecustomize.py — bundled in _MEIPASS, runs before all user code
# Patches aiogram Router.include_router to use duck-typing.
# This fires before rthooks, before main.py, before any import.
import sys

class _RouterImportHook:
    def find_module(self, name, path=None):
        return self if name == 'aiogram.dispatcher.router' else None

    def load_module(self, name):
        if name in sys.modules:
            self._patch(sys.modules[name])
            return sys.modules[name]
        sys.meta_path.remove(self)
        try:
            import importlib
            mod = importlib.import_module(name)
        finally:
            sys.meta_path.insert(0, self)
        self._patch(mod)
        return mod

    @staticmethod
    def _patch(mod):
        Router = getattr(mod, 'Router', None)
        if Router is None or getattr(Router, '_include_patched', False):
            return
        _orig = Router.include_router
        def _duck_include(self, router):
            if not isinstance(router, Router):
                if type(router).__name__ == 'Router' and hasattr(router, 'observers'):
                    # Unify sys.modules entry so future imports get same class
                    other = sys.modules.get(type(router).__module__)
                    if other is not None and hasattr(other, 'Router'):
                        other.Router = Router
                    # Re-create router as proper Router by copying internal state
                    new_r = object.__new__(Router)
                    new_r.__dict__.update(getattr(router, '__dict__', {}))
                    for slot in getattr(Router, '__slots__', []):
                        try:
                            setattr(new_r, slot, getattr(router, slot))
                        except (AttributeError, TypeError):
                            pass
                    router = new_r
                else:
                    raise ValueError("router should be instance of Router not type")
            return _orig(self, router)
        Router.include_router = _duck_include
        Router._include_patched = True

sys.meta_path.insert(0, _RouterImportHook())
