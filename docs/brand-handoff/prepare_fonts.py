"""Instance original variable WOFF2 fonts for predictable PDF embedding.

Requires fontTools and brotli in the authoring environment only.
Original packaged WOFF2 and their license are unchanged.
"""
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

here = Path(__file__).resolve().parent
tmp = here.parent.parent / 'tmp/pdfs/brand-handoff'
tmp.mkdir(parents=True, exist_ok=True)
for subset in ('cyrillic', 'latin'):
    for weight in (400, 700, 800):
        font = TTFont(here / 'fonts' / f'manrope-{subset}.woff2')
        result = instantiateVariableFont(font, {'wght':weight}, inplace=False)
        result.flavor = None
        result.save(tmp / f'manrope-{subset}-{weight}.ttf')
print('Prepared six static Manrope subsets from original WOFF2 files.')
