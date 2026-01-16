from __future__ import annotations

from pathlib import Path

from PIL import Image

from Script.pic_start import generate_tile_assets_from_existing_assets


def _make_png(path: Path, size: tuple[int, int]) -> None:
    img = Image.new("RGBA", size, (0, 128, 255, 255))
    img.save(path)


def test_generate_tile_assets_from_existing_assets(tmp_path: Path) -> None:
    # create minimal existing assets
    assets_dir = tmp_path / "Assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    _make_png(assets_dir / "F4CP_PNG_1200.png", (1200, 1200))
    _make_png(assets_dir / "F4CP_2x1_1200x600.png", (1200, 600))

    out = generate_tile_assets_from_existing_assets(assets_dir=assets_dir, prefix="F4CP")

    expected = {
        "Square70x70Logo.png": (70, 70),
        "Square150x150Logo.png": (150, 150),
        "Square310x310Logo.png": (310, 310),
        "Wide310x150Logo.png": (310, 150),
    }

    for name, size in expected.items():
        p = Path(out[name])
        assert p.exists()
        img = Image.open(p)
        assert img.size == size

