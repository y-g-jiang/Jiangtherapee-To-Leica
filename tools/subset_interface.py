import sys
from pathlib import Path
from fontTools import subset
from fontTools.ttLib import TTFont

root=Path(__file__).resolve().parents[1];target=root/'assets/Interface.ttf'
characters=set(range(32,127))|set(TTFont(target).getBestCmap())
for name in ('app.py','startup_notices.py','engine.py','inspection.py','grade_ui.py','darkroom.py','sensor.py','highlights.py','texture.py','m9_grain.py'):
    characters.update(ord(letter) for letter in (root/name).read_text(encoding='utf-8') if ord(letter)>=32)
font=TTFont(sys.argv[1]);options=subset.Options();options.name_IDs=['*'];options.name_languages=['*'];options.name_legacy=True
subsetter=subset.Subsetter(options=options);subsetter.populate(unicodes=characters);subsetter.subset(font)
for record in font['name'].names:
    if record.nameID in (1,3,4,6,16,21,25):record.string=('JTLInterface' if record.nameID in (6,25) else 'JTL Interface').encode(record.getEncoding())
font.save(target)
assert all(code in font.getBestCmap() for code in characters if 0x4e00<=code<=0x9fff)
