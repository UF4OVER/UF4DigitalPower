from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from Script.pic_start import generate_2to1_png, generate_ico_sizes, generate_square_pngs


def _make_test_image(path: Path, size: tuple[int, int], mode: str = "RGBA") -> None:
    img = Image.new(mode, size, (255, 0, 0, 255) if mode == "RGBA" else (255, 0, 0))
    img.save(path)


def test_generate_square_pngs_sizes(tmp_path: Path) -> None:
    src = tmp_path / "src.png"
    _make_test_image(src, (300, 200))

    out = tmp_path / "out"
    paths = generate_square_pngs(src, out_dir=out, sizes=(100, 200, 400), prefix="FACP")
    assert len(paths) == 3

    for p in paths:
        img = Image.open(p)
        w, h = img.size
        assert w == h
        assert w in (100, 200, 400)


def test_generate_2to1_png(tmp_path: Path) -> None:
    src = tmp_path / "src.png"
    _make_test_image(src, (1000, 2000))

    out = tmp_path / "out"
    p = generate_2to1_png(src, out_dir=out, size=(1200, 600), prefix="FACP")
    img = Image.open(p)
    assert img.size == (1200, 600)


def test_generate_ico_sizes_creates_files(tmp_path: Path) -> None:
    src = tmp_path / "src.png"
    _make_test_image(src, (512, 512))

    out = tmp_path / "out"
    paths = generate_ico_sizes(src, out_dir=out, sizes=(16, 32), prefix="FACP")
    assert len(paths) == 2
    for p in paths:
        assert Path(p).exists()
        # basic validity: Pillow can open ICO
        img = Image.open(p)
        assert img.size[0] in (16, 32)


def test_missing_input_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        generate_square_pngs(tmp_path / "missing.png", out_dir=tmp_path / "out")

