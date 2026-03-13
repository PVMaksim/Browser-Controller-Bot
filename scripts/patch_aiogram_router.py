#!/usr/bin/env python3
"""Patch aiogram Router.include_router before PyInstaller freezes it."""
import subprocess, sys

result = subprocess.run(
    [sys.executable, "-c",
     "import aiogram.dispatcher.router as m; print(m.__file__)"],
    capture_output=True, text=True
)
if result.returncode != 0:
    print(f"Cannot locate aiogram router: {result.stderr}")
    sys.exit(0)

router_py = result.stdout.strip()
print(f"Patching {router_py}")

src = open(router_py).read()

OLD = '''    def include_router(self, router: "Router") -> "Router":
        if not isinstance(router, Router):
            raise ValueError(
                f"router should be instance of Router not type"
            )'''

NEW = '''    def include_router(self, router: "Router") -> "Router":
        if not isinstance(router, Router):
            # Duck-type fallback for PyInstaller double-import issue.
            # When aiogram is imported from two paths (frozen + site-packages),
            # isinstance fails because the class objects differ.
            if type(router).__name__ == "Router" and hasattr(router, "observers"):
                pass  # accept it
            else:
                raise ValueError(
                    f"router should be instance of Router not type"
                )'''

if OLD in src:
    open(router_py, "w").write(src.replace(OLD, NEW))
    print("  Patched successfully")
else:
    print("  Pattern not found — may already be patched or version differs")
