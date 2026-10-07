"""Extract the Simplified-Chinese Noto Serif CJK faces for the Chapter 5 figures.

The system Noto CJK fonts (Debian/Ubuntu package fonts-noto-cjk) are .ttc collections
whose first face is the Japanese one, and matplotlib only loads the first face of a
collection. This script saves the SC faces as standalone fonts with TrueType (glyf)
outlines, so that matplotlib's pdf.fonttype 42 embedding produces valid PDF fonts.

Usage: python3 prepare_cjk_fonts.py [output_dir]   (default ~/.cache/ch5_cjk_fonts)
Then run the figure scripts with CH5_CJK_FONT_DIR set to the same folder (the scripts
use that default too). Requires fontTools.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTCollection, newTable

DEFAULT_DIR = Path.home() / ".cache" / "ch5_cjk_fonts"
SOURCES = {
    "Regular": Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"),
    "Bold": Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"),
}


def cff_to_glyf(font) -> None:
    """Replace CFF outlines by quadratic TrueType outlines in place."""
    order = font.getGlyphOrder()
    glyphs = font.getGlyphSet()
    glyf = newTable("glyf")
    glyf.glyphOrder = order
    glyf.glyphs = {}
    for name in order:
        pen = TTGlyphPen(None)
        glyphs[name].draw(Cu2QuPen(pen, max_err=1.0, reverse_direction=True))
        glyf[name] = pen.glyph()
    font["glyf"] = glyf
    font["loca"] = newTable("loca")
    for tag in ("CFF ", "VORG"):
        if tag in font:
            del font[tag]
    font["head"].glyphDataFormat = 0
    font["head"].indexToLocFormat = 1
    maxp = font["maxp"]
    maxp.tableVersion = 0x00010000
    for attr in ("maxTwilightPoints", "maxStorage", "maxFunctionDefs", "maxInstructionDefs",
                 "maxStackElements", "maxSizeOfInstructions", "maxComponentElements", "maxComponentDepth"):
        setattr(maxp, attr, 0)
    maxp.maxZones = 1
    post = font["post"]
    post.formatType = 3.0
    post.extraNames = []
    post.mapping = {}
    font.sfntVersion = "\x00\x01\x00\x00"


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    for style, src in SOURCES.items():
        dst = out_dir / f"NotoSerifSC-{style}.ttf"
        if dst.exists():
            print(f"exists {dst}")
            continue
        if not src.exists():
            sys.exit(f"missing {src}; install fonts-noto-cjk")
        face = next(f for f in TTCollection(str(src)).fonts if f["name"].getDebugName(1).endswith(" SC"))
        cff_to_glyf(face)
        face.save(str(dst))
        print(f"wrote {dst}")


if __name__ == "__main__":
    main()
