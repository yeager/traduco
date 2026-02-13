#!/usr/bin/env python3
"""Build .deb package for LinguaEdit."""
import os, sys, shutil, subprocess, stat

VERSION = sys.argv[1] if len(sys.argv) > 1 else "0.0.0"
PKG = "linguaedit-deb-build"

# Directories
os.makedirs(f"{PKG}/DEBIAN", exist_ok=True)
os.makedirs(f"{PKG}/usr/lib/python3/dist-packages/linguaedit", exist_ok=True)
os.makedirs(f"{PKG}/usr/bin", exist_ok=True)
os.makedirs(f"{PKG}/usr/share/linguaedit/translations", exist_ok=True)

# Copy source
shutil.copytree("src/linguaedit", f"{PKG}/usr/lib/python3/dist-packages/linguaedit", dirs_exist_ok=True)

# Copy translations (check both locations)
for tdir in ["src/linguaedit/translations", "translations"]:
    if os.path.isdir(tdir):
        for f in os.listdir(tdir):
            if f.endswith(".qm") or f.endswith(".ts"):
                shutil.copy2(f"{tdir}/{f}", f"{PKG}/usr/share/linguaedit/translations/")

# Launcher script
with open(f"{PKG}/usr/bin/linguaedit", "w") as f:
    f.write("#!/usr/bin/env python3\n")
    f.write("import sys\n")
    f.write("sys.path.insert(0, '/usr/lib/python3/dist-packages')\n")
    f.write("from linguaedit.app import main\n")
    f.write("main()\n")
os.chmod(f"{PKG}/usr/bin/linguaedit", 0o755)

# Control file
with open(f"{PKG}/DEBIAN/control", "w") as f:
    f.write(f"""Package: linguaedit
Version: {VERSION}
Section: devel
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-pip, python3-venv
Recommends: python3-polib, python3-yaml
Maintainer: Daniel Nylander <po@danielnylander.se>
Description: Qt6 translation file editor
 A PySide6/Qt6 translation file editor for PO, TS, JSON, XLIFF,
 Android XML, ARB, PHP, and YAML i18n files with linting,
 pre-translation, and platform integration.
 .
 PySide6 is installed automatically via pip during package setup.
 If the automatic install fails, run: pip install PySide6
""")

# postinst
with open(f"{PKG}/DEBIAN/postinst", "w") as f:
    f.write("""#!/bin/bash
set -e

DEPS="PySide6 polib requests PyYAML pyenchant"

# Try pip install with --break-system-packages (Python 3.11+/PEP 668),
# fall back to regular pip, then pipx as last resort
if python3 -m pip install --break-system-packages --quiet $DEPS 2>/dev/null; then
    echo "LinguaEdit: Python dependencies installed via pip"
elif python3 -m pip install --quiet $DEPS 2>/dev/null; then
    echo "LinguaEdit: Python dependencies installed via pip"
elif command -v pipx >/dev/null 2>&1; then
    pipx install linguaedit 2>/dev/null || true
    echo "LinguaEdit: Installed via pipx"
else
    echo ""
    echo "=========================================="
    echo "  LinguaEdit: Could not auto-install PySide6."
    echo "  Please run manually:"
    echo "    pip install PySide6 polib requests PyYAML pyenchant"
    echo "=========================================="
    echo ""
fi
""")
os.chmod(f"{PKG}/DEBIAN/postinst", 0o755)

# Desktop file
os.makedirs(f"{PKG}/usr/share/applications", exist_ok=True)
shutil.copy2("io.github.yeager.linguaedit.desktop", f"{PKG}/usr/share/applications/")

# Build
subprocess.run(["dpkg-deb", "--build", PKG, f"linguaedit_{VERSION}_all.deb"], check=True)
print(f"Built linguaedit_{VERSION}_all.deb")
