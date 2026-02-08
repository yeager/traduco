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

# Copy translations
if os.path.isdir("translations"):
    for f in os.listdir("translations"):
        if f.endswith(".qm"):
            shutil.copy2(f"translations/{f}", f"{PKG}/usr/share/linguaedit/translations/")

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
Maintainer: Daniel Nylander <po@danielnylander.se>
Description: Qt6 translation file editor
 A PySide6/Qt6 translation file editor for PO, TS, JSON, XLIFF,
 Android XML, ARB, PHP, and YAML i18n files with linting,
 pre-translation, and platform integration.
""")

# postinst
with open(f"{PKG}/DEBIAN/postinst", "w") as f:
    f.write("#!/bin/bash\nset -e\n")
    f.write("pip install --break-system-packages --quiet PySide6 polib requests PyYAML 2>/dev/null || ")
    f.write("pip install --quiet PySide6 polib requests PyYAML\n")
os.chmod(f"{PKG}/DEBIAN/postinst", 0o755)

# Build
subprocess.run(["dpkg-deb", "--build", PKG, f"linguaedit_{VERSION}_all.deb"], check=True)
print(f"Built linguaedit_{VERSION}_all.deb")
