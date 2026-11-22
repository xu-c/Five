"""Build the Cardputer Zero Debian package on Windows or Linux."""

import gzip
import io
import tarfile
from pathlib import Path

from ui import TITLE, icon


def tar_gz(files):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        directories = set()
        for path, (content, mode) in files.items():
            parent = ""
            for component in path.split("/")[:-1]:
                parent += "/" + component
                if parent in directories:
                    continue
                directory = tarfile.TarInfo("." + parent)
                directory.type = tarfile.DIRTYPE
                directory.mode = 0o755
                directory.uname = directory.gname = "root"
                archive.addfile(directory)
                directories.add(parent)
            info = tarfile.TarInfo("./" + path)
            info.mode = mode
            info.size = len(content)
            info.uname = info.gname = "root"
            archive.addfile(info, io.BytesIO(content))
    return gzip.compress(buffer.getvalue(), mtime=0)


def ar_member(name, content):
    header = f"{name + '/':<16}{0:<12}{0:<6}{0:<6}{'100644':<8}{len(content):<10}`\n"
    return header.encode("ascii") + content + (b"\n" if len(content) % 2 else b"")


def main():
    root = Path(__file__).resolve().parent
    share = "usr/share/five"
    launcher = "usr/share/APPLaunch"
    icon_path = f"{launcher}/share/images/five.png"
    control = """Package: five
Version: 1.2.1-3
Section: games
Priority: optional
Architecture: arm64
Maintainer: xu-c <3174585+xu-c@users.noreply.github.com>
Depends: python3 (>= 3.9), python3-pil (>= 9.2), python3-evdev, python3-aiortc, ca-certificates, fonts-noto-cjk, alsa-utils
Description: Gomoku with LAN multiplayer for Cardputer Zero
 Play against the computer, share one device, or play over your local network.
 .
 适用于 Cardputer Zero 的五子棋，支持人机、同机双人和局域网联机。
"""
    desktop = f"""[Desktop Entry]
Type=Application
Name={TITLE}
Exec=/usr/bin/five
Icon=/{icon_path}
Terminal=false
Categories=Game;BoardGame;
"""
    entry = '#!/bin/sh\nexec /usr/bin/python3 -B /usr/share/five/five.py --device "$@"\n'
    image = io.BytesIO()
    icon().save(image, format="PNG")
    payload = {f"{share}/{name}": ((root / name).read_bytes(), 0o644)
               for name in ("five.py", "game.py", "ui.py", "device.py", "stone.wav", "menu.wav", "rapfi_engine.py",
                            "lan.py", "lan_session.py", "rtc_peer.py")}
    engine = root / "dist" / "rapfi-arm64"
    for name in ("rapfi", "config.toml", "model260809.bin"):
        payload[f"{share}/{name}"] = ((engine / name).read_bytes(), 0o755 if name == "rapfi" else 0o644)
    docs = "usr/share/doc/five"
    for name in ("Rapfi-GPL.txt", "CC0.txt", "rapfi-source.tar.gz"):
        payload[f"{docs}/{name}"] = ((engine / name).read_bytes(), 0o644)
    payload.update({
        "usr/bin/five": (entry.encode(), 0o755),
        f"{launcher}/applications/five.desktop": (desktop.encode("utf-8"), 0o644),
        icon_path: (image.getvalue(), 0o644),
        f"{docs}/README.md": ((root / "README.md").read_bytes(), 0o644),
        f"{docs}/LICENSE": ((root / "LICENSE").read_bytes(), 0o644),
        f"{docs}/build_rapfi.ps1": ((root / "build_rapfi.ps1").read_bytes(), 0o644),
    })
    output = root / "dist" / "five_1.2.1-3_arm64.deb"
    output.parent.mkdir(exist_ok=True)
    output.write_bytes(b"!<arch>\n" + b"".join((
        ar_member("debian-binary", b"2.0\n"),
        ar_member("control.tar.gz", tar_gz({"control": (control.encode(), 0o644)})),
        ar_member("data.tar.gz", tar_gz(payload)),
    )))
    print(output)


if __name__ == "__main__":
    main()


