"""Create responsive WebP files from the retained originals. Local Pillow only.

Run with a Python environment containing Pillow. No package is needed on the VPS.
Do not edit the originals or repeatedly recompress generated files.
"""
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'dist'
HOME_IMAGES = ['textile-hero.png', 'atv-cover.png', 'pocket-organizer.png', 'black-fabric-rolls.png']
WIDTHS = (160, 480, 800, 1200, 1536)


def render():
    output = DIST / 'images'
    output.mkdir(exist_ok=True)
    manifest = {}
    products = json.loads((ROOT / 'catalog/products.json').read_text())['products']
    sources = dict.fromkeys(HOME_IMAGES + [image['src'].lstrip('/') for product in products for image in product['images']])
    for name in sources:
        source = DIST / name
        if not source.resolve().is_relative_to(DIST.resolve()):
            raise ValueError('Image must be inside dist: ' + name)
        with Image.open(source) as original:
            image = ImageOps.exif_transpose(original).convert('RGB')
            variants = []
            for width in sorted({min(width, image.width) for width in WIDTHS}):
                height = round(image.height * width / image.width)
                target = output / f'{source.stem}-{width}.webp'
                resized = image.resize((width, height), Image.Resampling.LANCZOS)
                resized.save(target, 'WEBP', quality=82, method=6)
                variants.append({'src': '/' + target.relative_to(DIST).as_posix(),
                                 'width': width, 'height': height, 'bytes': target.stat().st_size})
            manifest['/' + name] = {'width': image.width, 'height': image.height,
                                     'originalBytes': source.stat().st_size,
                                     'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                                     'variants': variants}
    (ROOT / 'ops/image-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(f'Created {sum(len(item["variants"]) for item in manifest.values())} responsive images; originals retained.')


if __name__ == '__main__':
    render()
