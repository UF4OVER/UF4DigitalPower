# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 01-13 20:11
#  @FileName: pic_start.py
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact : 生成.ico .png等图片资产文件
#  @Python  :
# -------------------------------

from __future__ import annotations

from pathlib import Path
from typing import List, Sequence, Tuple

from PIL import Image, ImageOps

# Default output folder: repo_root/Assets
_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSETS_DIR = _REPO_ROOT / "Assets"

DEFAULT_ICO_SIZES: Tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256)
DEFAULT_SQUARE_PNG_SIZES: Tuple[int, ...] = (100, 200, 400, 800, 1200)
DEFAULT_2TO1_SIZE: Tuple[int, int] = (1200, 600)

ICO_PATH = DEFAULT_ASSETS_DIR / "F4CP_ICO.jpg"
PNG1_PATH = DEFAULT_ASSETS_DIR / "F4CP_PNG1.jpg"
PNG2_PATH = DEFAULT_ASSETS_DIR / "F4CP_PNG2.jpg"


def _ensure_dir(path: Path | str) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load_image(input_path: Path | str) -> Image.Image:
    p = Path(input_path)
    if not p.exists():
        raise FileNotFoundError(f"Input image not found: {p}")

    img = Image.open(p)
    # Respect EXIF orientation (common for photos)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception as e:
        # If EXIF handling fails, continue with raw image.
        print(e)
    return img


def _center_crop_to_aspect(img: Image.Image, target_aspect: float) -> Image.Image:
    """Center-crop image to target aspect ratio (w/h) without stretching."""
    w, h = img.size
    if w <= 0 or h <= 0:
        raise ValueError(f"Invalid image size: {img.size}")

    current_aspect = w / h
    if abs(current_aspect - target_aspect) < 1e-9:
        return img

    if current_aspect > target_aspect:
        # Too wide -> crop width
        new_w = int(round(h * target_aspect))
        new_w = max(1, min(new_w, w))
        left = (w - new_w) // 2
        box = (left, 0, left + new_w, h)
    else:
        # Too tall -> crop height
        new_h = int(round(w / target_aspect))
        new_h = max(1, min(new_h, h))
        top = (h - new_h) // 2
        box = (0, top, w, top + new_h)

    return img.crop(box)


def _center_crop_square(img: Image.Image) -> Image.Image:
    return _center_crop_to_aspect(img, 1.0)


def _resize(img: Image.Image, size: Tuple[int, int]) -> Image.Image:
    # Pillow>=10: Image.Resampling.LANCZOS
    resample = getattr(Image, "Resampling", Image).LANCZOS
    return img.resize(size, resample=resample)


def generate_square_pngs(
        input_path: Path | str,
        *,
        out_dir: Path | str = DEFAULT_ASSETS_DIR,
        sizes: Sequence[int] = DEFAULT_SQUARE_PNG_SIZES,
        prefix: str = "F4CP",
) -> List[str]:
    """Generate 1:1 square PNG icons (no stretching).

    Output names: {prefix}_PNG_{size}.png in out_dir.
    """
    out_dir_p = _ensure_dir(out_dir)

    img = _load_image(input_path)
    img = img.convert("RGBA")
    img_sq = _center_crop_square(img)

    out_paths: List[str] = []
    for s in sizes:
        if s <= 0:
            raise ValueError(f"Invalid size: {s}")
        out_img = _resize(img_sq, (int(s), int(s)))
        out_path = out_dir_p / f"{prefix}_PNG_{int(s)}.png"
        out_img.save(out_path, format="PNG", optimize=True)
        out_paths.append(str(out_path))

    return out_paths


def generate_2to1_png(
        input_path: Path | str,
        *,
        out_dir: Path | str = DEFAULT_ASSETS_DIR,
        size: Tuple[int, int] = DEFAULT_2TO1_SIZE,
        prefix: str = "F4CP",
) -> str:
    """Generate a 2:1 PNG (default 1200x600) by center-cropping to 2:1 then resizing."""
    out_dir_p = _ensure_dir(out_dir)
    target_w, target_h = size
    if target_w <= 0 or target_h <= 0:
        raise ValueError(f"Invalid target size: {size}")

    img = _load_image(input_path).convert("RGBA")
    cropped = _center_crop_to_aspect(img, target_w / target_h)
    out_img = _resize(cropped, (int(target_w), int(target_h)))

    out_path = out_dir_p / f"{prefix}_2x1_{int(target_w)}x{int(target_h)}.png"
    out_img.save(out_path, format="PNG", optimize=True)
    return str(out_path)


def _to_rgba(img: Image.Image) -> Image.Image:
    """Normalize image mode for icon generation."""
    return img.convert("RGBA")


def _downscale_from_master(master: Image.Image, target: int) -> Image.Image:
    """Downscale from a (usually) larger master image for better small-size quality."""
    if target <= 0:
        raise ValueError(f"Invalid size: {target}")
    if master.size != (target, target):
        return _resize(master, (target, target))
    return master


def _apply_rounded_corners(img: Image.Image, radius_px: int) -> Image.Image:
    """Apply rounded corners by masking alpha.

    - img: RGBA image
    - radius_px: corner radius in pixels (>=0)

    Returns a new RGBA image.
    """
    if radius_px <= 0:
        return img

    img = img.convert("RGBA")
    w, h = img.size
    r = int(min(radius_px, w // 2, h // 2))

    # Create a mask with rounded rectangle.
    mask = Image.new("L", (w, h), 0)

    # Pillow >= 8 has rounded_rectangle on ImageDraw; to avoid extra import complexity,
    # we compose it using rectangles + ellipses.
    from PIL import ImageDraw

    draw = ImageDraw.Draw(mask)
    # center rectangles
    draw.rectangle((r, 0, w - r, h), fill=255)
    draw.rectangle((0, r, w, h - r), fill=255)
    # four corner circles
    draw.ellipse((0, 0, 2 * r, 2 * r), fill=255)
    draw.ellipse((w - 2 * r, 0, w, 2 * r), fill=255)
    draw.ellipse((0, h - 2 * r, 2 * r, h), fill=255)
    draw.ellipse((w - 2 * r, h - 2 * r, w, h), fill=255)

    out = img.copy()
    out.putalpha(mask)
    return out


def generate_ico_sizes(
        input_path: Path | str,
        *,
        out_dir: Path | str = DEFAULT_ASSETS_DIR,
        sizes: Sequence[int] = DEFAULT_ICO_SIZES,
        prefix: str = "F4CP",
        rounded: bool = True,
        rounded_radius_ratio: float = 0.22,
) -> List[str]:
    """Generate 1:1 ICO icons of common sizes.

    Per your naming requirement, this writes one ico file per size:
    {prefix}_ICO_{size}.ico

    Quality:
    - Create a high-quality master image at the largest requested size first,
      then downscale to each smaller size using LANCZOS.

    Rounded corners:
    - If rounded=True, apply rounded-corner alpha mask before resizing.
    - rounded_radius_ratio is relative to the output size (e.g. 0.22 -> radius ~= 256*0.22).
    """
    out_dir_p = _ensure_dir(out_dir)

    sizes_list = [int(s) for s in sizes]
    if not sizes_list:
        return []
    if any(s <= 0 for s in sizes_list):
        raise ValueError(f"Invalid sizes: {sizes_list}")

    img = _to_rgba(_load_image(input_path))
    img_sq = _center_crop_square(img)

    # Make a master at the largest size, then (optionally) round corners, then downscale from it.
    max_size = max(sizes_list)
    master = _resize(img_sq, (max_size, max_size))

    if rounded:
        radius_px = int(round(max_size * float(rounded_radius_ratio)))
        master = _apply_rounded_corners(master, radius_px)

    out_paths: List[str] = []
    for s in sizes_list:
        out_img = _downscale_from_master(master, s)
        out_path = out_dir_p / f"{prefix}_ICO_{int(s)}.ico"
        out_img.save(out_path, format="ICO", sizes=[(int(s), int(s))])
        out_paths.append(str(out_path))

    return out_paths


def _parse_sizes_csv(text: str) -> List[int]:
    items: List[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        items.append(int(part))
    return items



def generate_all_assets(
        out_dir: Path | str = DEFAULT_ASSETS_DIR,
        prefix: str = "F4CP",
        ico_sizes: Sequence[int] = DEFAULT_ICO_SIZES,
        square_png_sizes: Sequence[int] = DEFAULT_SQUARE_PNG_SIZES,
        size_2to1: Tuple[int, int] = DEFAULT_2TO1_SIZE,
        ico_rounded: bool = True,
        ico_rounded_radius_ratio: float = 0.22,
        generate_tiles: bool = True,
) -> dict[str, object]:
    """脚本内一键生成所有资产文件（不需要命令行参数）。

    - 1:1 ICO：按尺寸分别输出 {prefix}_ICO_{size}.ico
    - 1:1 PNG：输出 {prefix}_PNG_{size}.png（默认 100/200/400/800/1200）
    - 2:1 PNG：输出 {prefix}_2x1_{w}x{h}.png（默认 1200x600）

    返回：包含生成文件路径的 dict，方便你在代码里继续使用。
    """

    ico_paths = generate_ico_sizes(
        ICO_PATH,
        out_dir=out_dir,
        sizes=ico_sizes,
        prefix=prefix,
        rounded=ico_rounded,
        rounded_radius_ratio=ico_rounded_radius_ratio,
    )
    square_png_paths = generate_square_pngs(PNG1_PATH, out_dir=out_dir, sizes=square_png_sizes, prefix=prefix)
    png_2x1_path = generate_2to1_png(PNG2_PATH, out_dir=out_dir, size=size_2to1, prefix=prefix)

    return {
        "ico": ico_paths,
        "square_png": square_png_paths,
        "png_2x1": png_2x1_path,
    }


if __name__ == "__main__":
    raise SystemExit(generate_all_assets())
