# -*- coding: utf-8 -*-
"""Post-build cleanup and UPX compression for cx_Freeze output.

Run after ``Script/package_exe.ps1``::

    uv run python Script/upx_zip.py

What it does:
1. Deletes unused Qt5 translations (5.2 MB)
2. Deletes QtQuick / QML DLLs (7.8 MB)
3. Deletes unused Qt5 platform/plugin DLLs (~2 MB)
4. Deletes pyOCD SVD debug data (14.5 MB)
5. Deletes capstone disassembly DLL (7.2 MB)
6. Strips CMSIS Pack files — keep STM32G474/H743/H750 related packs only
7. UPX-compresses remaining .exe / .dll / .pyd files
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# ── files / subdirs to delete ──────────────────────────────────────────────

QT5_BIN_EXCLUDES = [
    "Qt5Quick.dll",
    "Qt5Qml.dll",
    "Qt5QmlModels.dll",
    "Qt5QmlWorkerScript.dll",
]

QT5_PLUGIN_EXCLUDES = [
    "generic/qtuiotouchplugin.dll",
    "platforms/qminimal.dll",
    "platforms/qoffscreen.dll",
    "platforms/qwebgl.dll",
    "platformthemes/qxdgdesktopportal.dll",
    "imageformats/qicns.dll",
    "imageformats/qtga.dll",
    "imageformats/qwbmp.dll",
]

LIB_EXCLUDES = [
    os.path.join("pyocd", "debug", "svd", "svd_data.zip"),
]

LIB_DLL_EXCLUDES = [
    "capstone.dll",
]

PACK_KEEP_KEYWORDS = ("g474", "h743", "h750")
MAX_CMSIS_PACKS = 2


def _delete(path: Path) -> bool:
    try:
        if path.is_file():
            path.unlink()
            print(f"  DEL file  {path}")
            return True
        if path.is_dir():
            shutil.rmtree(path)
            print(f"  DEL dir   {path}")
            return True
    except FileNotFoundError:
        pass
    except Exception as exc:
        print(f"  SKIP      {path} ({exc})")
    return False


def delete_qt_translations(exe_dir: Path):
    translations_dir = exe_dir / "lib" / "PyQt5" / "Qt5" / "translations"
    if translations_dir.is_dir():
        size_mb = sum(f.stat().st_size for f in translations_dir.rglob("*.qm")) / (1024 * 1024)
        shutil.rmtree(translations_dir)
        print(f"[translations] deleted {size_mb:.1f} MB ({translations_dir})")


def delete_qt_quick_dlls(exe_dir: Path):
    bin_dir = exe_dir / "lib" / "PyQt5" / "Qt5" / "bin"
    total = 0
    for name in QT5_BIN_EXCLUDES:
        path = bin_dir / name
        if path.is_file():
            total += path.stat().st_size
            path.unlink()
            print(f"  DEL DLL   {path}")
    if total:
        print(f"[Qt5 bin]    deleted {total / (1024 * 1024):.1f} MB of QtQuick/QML DLLs")


# def delete_unused_qt_plugins(exe_dir: Path):
#     plugins_dir = exe_dir / "lib" / "PyQt5" / "Qt5" / "plugins"
#     total = 0
#     for rel in QT5_PLUGIN_EXCLUDES:
#         path = plugins_dir / rel
#         if path.is_file():
#             total += path.stat().st_size
#             path.unlink()
#             print(f"  DEL plug  {path}")
#     if total:
#         print(f"[plugins]    deleted {total / (1024 * 1024):.1f} MB of unused Qt plugins")


def delete_lib_excludes(exe_dir: Path):
    for rel in LIB_EXCLUDES:
        _delete(exe_dir / "lib" / rel)
    for name in LIB_DLL_EXCLUDES:
        for found in (exe_dir / "lib").rglob(name):
            _delete(found)


def trim_cmsis_packs(exe_dir: Path):
    pack_dir = exe_dir / "Resources" / "Tools" / "Pack"
    if not pack_dir.is_dir():
        return

    packs = sorted(pack_dir.glob("*.pack"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not packs:
        print("[CMSIS Pack] no pack files found")
        return

    keep = [pack for pack in packs if any(key in pack.name.lower() for key in PACK_KEEP_KEYWORDS)]

    # If pack filenames are generic and cannot be recognised, keep the previous
    # fallback behaviour instead of deleting every pack and breaking flashing.
    if not keep:
        keep = packs[:MAX_CMSIS_PACKS]
        print(f"[CMSIS Pack] no G474/H743/H750 filename match, fallback keep latest {len(keep)} pack(s)")

    keep_set = set(keep)
    removed = 0
    removed_size = 0
    for pack in packs:
        if pack in keep_set:
            continue
        size = pack.stat().st_size
        pack.unlink()
        removed += 1
        removed_size += size
        print(f"[CMSIS Pack] removed {pack.name} ({size / (1024 * 1024):.1f} MB)")

    kept_names = ", ".join(pack.name for pack in sorted(keep_set, key=lambda p: p.name.lower()))
    print(
        f"[CMSIS Pack] kept {len(keep_set)} pack(s): {kept_names}; "
        f"removed {removed} pack(s), {removed_size / (1024 * 1024):.1f} MB"
    )


def compress_with_upx(exe_dir: Path):
    exe_files = list(exe_dir.rglob("*.exe"))
    dll_files = []
    pyd_files = []
    for root, dirs, files in os.walk(exe_dir):
        if "plugins" in str(root).split(os.sep):
            continue
        for f in files:
            fp = Path(root) / f
            if f.lower().endswith(".dll"):
                dll_files.append(fp)
            elif f.lower().endswith(".pyd"):
                pyd_files.append(fp)

    upx_exe = shutil.which("upx.exe") or "upx.exe"
    all_targets = exe_files + dll_files + pyd_files
    print(f"[UPX] compressing {len(all_targets)} files ({len(exe_files)} exe, {len(dll_files)} dll, {len(pyd_files)} pyd)...")

    compressed = 0
    for fp in all_targets:
        try:
            subprocess.run([upx_exe, "--best", str(fp)], check=True, capture_output=True, timeout=120)
            compressed += 1
        except Exception as exc:
            print(f"  SKIP UPX  {fp.name}: {exc}")
    print(f"[UPX] compressed {compressed}/{len(all_targets)} files")


def main():
    repo_root = Path(__file__).resolve().parent.parent
    exe_dir = repo_root / "Build" / "exe"
    if not exe_dir.is_dir():
        print(f"[ERROR] {exe_dir} does not exist. Run package_exe.ps1 first.")
        sys.exit(1)

    print("=" * 60)
    print("F4CP post-build optimiser")
    print("=" * 60)

    delete_qt_translations(exe_dir)
    delete_qt_quick_dlls(exe_dir)
    # delete_unused_qt_plugins(exe_dir)
    delete_lib_excludes(exe_dir)
    trim_cmsis_packs(exe_dir)
    compress_with_upx(exe_dir)

    total = sum(f.stat().st_size for f in exe_dir.rglob("*") if f.is_file())
    file_count = sum(1 for f in exe_dir.rglob("*") if f.is_file())
    print("=" * 60)
    print(f"Done. {file_count} files, {total / (1024 * 1024):.1f} MB")
    print("=" * 60)


if __name__ == "__main__":
    main()
