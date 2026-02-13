Name:           linguaedit
Version:        1.8.0
Release:        1%{?dist}
Summary:        Professional translation editor
License:        GPL-3.0-or-later
URL:            https://github.com/yeager/linguaedit
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
Requires:       python3 >= 3.10
Recommends:     ffmpeg hunspell python3-polib python3-pyyaml

%prep
%setup -q

%description
A PySide6/Qt6 translation editor supporting 17+ file formats with
translation memory, glossary, AI review, linting, Zen mode, and more.

%install
# Python package
mkdir -p %{buildroot}/usr/lib/python3/dist-packages
cp -r src/linguaedit %{buildroot}/usr/lib/python3/dist-packages/
find %{buildroot} -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Binary
mkdir -p %{buildroot}/usr/bin
install -m 755 scripts/linguaedit-gui %{buildroot}/usr/bin/

# Desktop + MIME + icon
mkdir -p %{buildroot}/usr/share/applications
mkdir -p %{buildroot}/usr/share/mime/packages
mkdir -p %{buildroot}/usr/share/icons/hicolor/scalable/apps
install -m 644 data/io.github.yeager.linguaedit.desktop %{buildroot}/usr/share/applications/
install -m 644 data/io.github.yeager.linguaedit.xml %{buildroot}/usr/share/mime/packages/
install -m 644 data/icons/io.github.yeager.linguaedit.svg %{buildroot}/usr/share/icons/hicolor/scalable/apps/

# Man page
mkdir -p %{buildroot}/usr/share/man/man1
install -m 644 man/linguaedit-gui.1.gz %{buildroot}/usr/share/man/man1/

# Docs
mkdir -p %{buildroot}/usr/share/doc/%{name}
install -m 644 README.md CHANGELOG.md %{buildroot}/usr/share/doc/%{name}/

%post
update-desktop-database /usr/share/applications 2>/dev/null || true
update-mime-database /usr/share/mime 2>/dev/null || true
gtk-update-icon-cache /usr/share/icons/hicolor 2>/dev/null || true

%postun
update-desktop-database /usr/share/applications 2>/dev/null || true
update-mime-database /usr/share/mime 2>/dev/null || true

%files
/usr/bin/linguaedit-gui
/usr/lib/python3/dist-packages/linguaedit/
/usr/share/applications/io.github.yeager.linguaedit.desktop
/usr/share/mime/packages/io.github.yeager.linguaedit.xml
/usr/share/icons/hicolor/scalable/apps/io.github.yeager.linguaedit.svg
/usr/share/man/man1/linguaedit-gui.1.gz
%doc /usr/share/doc/%{name}/README.md
%doc /usr/share/doc/%{name}/CHANGELOG.md
%license LICENSE

%changelog
* Thu Feb 13 2026 Daniel Nylander <daniel@danielnylander.se> - 1.8.0-1
- Video preview rewrite, live-update tree view, extended selection
- Unity MonoBehaviour parser, SRT roundtrip fix, QThread crash fix
- macOS SIGSEGV fix, dark mode contrast, Python 3.13+ compat

* Mon Feb 09 2026 Daniel Nylander <daniel@danielnylander.se> - 1.3.2-1
- Bug fixes, QSettings, 90 unit tests (see CHANGELOG.md)

* Sun Feb 09 2026 Daniel Nylander <daniel@danielnylander.se> - 1.3.1-1
- Bug fixes and UI polish (see CHANGELOG.md)

* Mon Feb 09 2026 Daniel Nylander <daniel@danielnylander.se> - 1.3.0-1
- Cross-platform credential storage
- Video preview synced with subtitle editing
- Concordance search, segment split/merge
- Security: XXE protection in all XML parsers
