"""Shared build options for the public handouts; no desktop automation."""
import argparse
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def options(root, description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--output-dir', type=Path, default=root / 'build/handouts')
    parser.add_argument('--font-regular', type=Path,
                        default=Path('/System/Library/Fonts/STHeiti Light.ttc'))
    parser.add_argument('--font-bold', type=Path,
                        default=Path('/System/Library/Fonts/STHeiti Medium.ttc'))
    parser.add_argument('--font-index', type=int, default=1,
                        help='TTC subfont index; use 0 for a standalone TTF')
    args = parser.parse_args()
    output = args.output_dir.expanduser().resolve()
    archive = (root / 'delivery/releases').resolve()
    if output == archive or archive in output.parents:
        parser.error('Build outside delivery/releases; archived artifacts are immutable.')
    if args.font_index < 0:
        parser.error('--font-index must be nonnegative')
    for font in (args.font_regular, args.font_bold):
        if not font.expanduser().is_file():
            parser.error(f'Font missing: {font}. Provide CJK TrueType fonts with --font-regular/--font-bold.')
    output.mkdir(parents=True, exist_ok=True)
    return output, args


def register_fonts(regular_name, bold_name, args):
    for name, path in ((regular_name, args.font_regular), (bold_name, args.font_bold)):
        pdfmetrics.registerFont(TTFont(name, str(path.expanduser()), subfontIndex=args.font_index))
    pdfmetrics.registerFontFamily(regular_name, normal=regular_name, bold=bold_name,
                                  italic=regular_name, boldItalic=bold_name)
