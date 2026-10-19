"""Build the portable text guide and self-contained print HTML. No network."""
from pathlib import Path
import base64
import html
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TMP = ROOT / "tmp/pdfs/brand-handoff"
TMP.mkdir(parents=True, exist_ok=True)
data = json.loads((HERE / "knowledge.json").read_text())


def clean(text):
    return text.replace("—", "-").replace("–", "-").replace("−", "-").replace("‑", "-")


def esc(text):
    return html.escape(clean(text))


def uri(path, mime):
    return "data:" + mime + ";base64," + base64.b64encode(path.read_bytes()).decode()


def asset(name, mime):
    return uri(HERE / "assets" / name, mime)


logo = asset("logo.svg", "image/svg+xml")
md = ["# " + data["title"], "Версия " + data["version"] + " · " + data["date"]]
pages = []
agent_text = ""

for n, page in enumerate(data["pages"], 1):
    md.extend(["## " + page["title"], page["lead"]])
    blocks = []
    for b in page["blocks"]:
        t = b["type"]
        if t in ("p", "small", "callout", "h"):
            tag = "h3" if t == "h" else "p"
            blocks.append(f'<{tag} class="{t}">{esc(b["text"])}</{tag}>')
            md.append(("### " if t == "h" else "> " if t == "callout" else "") + b["text"])
        elif t == "list":
            blocks.append('<ul>' + ''.join('<li>'+esc(i)+'</li>' for i in b['items']) + '</ul>')
            md.append('\n'.join('- '+i for i in b['items']))
        elif t == "table":
            blocks.append('<table><thead><tr>' + ''.join('<th>'+esc(i)+'</th>' for i in b['headers']) + '</tr></thead><tbody>' + ''.join('<tr>'+''.join('<td>'+esc(c)+'</td>' for c in row)+'</tr>' for row in b['rows']) + '</tbody></table>')
            md.append('| '+' | '.join(b['headers'])+' |\n| '+' | '.join('---' for _ in b['headers'])+' |\n'+'\n'.join('| '+' | '.join(r)+' |' for r in b['rows']))
        elif t == "logo":
            blocks.append(f'<div class="logo-panel"><img src="{logo}" alt="Исходный логотип Needle Shark"></div>')
            md.append('![Исходный логотип Needle Shark](assets/logo.svg)')
        elif t == "palette":
            blocks.append('<div class="palette">'+''.join(f'<div class="swatch"><span style="background:{hex_}"></span><div><strong>{esc(name)}</strong><code>{hex_}</code><small>{esc(role)}</small></div></div>' for name,hex_,role in b['colors'])+'</div>')
            md.append('| Цвет | HEX | Назначение |\n| --- | --- | --- |\n'+'\n'.join('| '+' | '.join(r)+' |' for r in b['colors']))
        elif t == "type_sample":
            blocks.append('<div class="type-sample"><div>Швейное<br><em>производство</em></div><p>Manrope 800 / Manrope 400</p><p>Чёткая форма. Спокойный текст. 0123456789</p></div>')
            md.append('Пример иерархии: «Швейное производство» крупным Manrope 800; пояснение обычным Manrope 400. Образец набора: АБВГД абвгд 0123456789.')
        elif t == "layout":
            blocks.append('<div class="layout"><div class="diagram-title">Порядок элементов</div><div class="diagram-grid"><div><b>Главный<br>заголовок</b><p>Короткое пояснение</p><span>Действие</span></div><div class="photo-slot">Изображение<br>предмета</div></div></div>')
            md.append('Схема компоновки: заголовок и пояснение расположены рядом с изображением предмета; действие следует после пояснения. Это схема порядка элементов, а не готовый рекламный макет.')
        elif t == "examples":
            blocks.append('<div class="examples"><figure><img src="'+asset('email-received.png','image/png')+'"><figcaption>Подтверждение обращения</figcaption></figure><figure><img src="'+asset('email-quote.jpg','image/jpeg')+'"><figcaption>Коммерческое предложение</figcaption></figure></div>')
            md.append('![Согласованное подтверждение обращения](assets/email-received.png)\n\n![Согласованное коммерческое предложение](assets/email-quote.jpg)')
        elif t == "agent":
            blocks.append('<div class="agent">'+''.join('<p>'+esc(p)+'</p>' for p in b['paragraphs'])+'</div>')
            md.extend(b['paragraphs'])
            agent_text = '\n\n'.join(b['paragraphs'])+'\n'
    cover = page.get('kind') == 'cover'
    heading = (f'<img class="cover-logo" src="{logo}"><div class="eyebrow">Руководство по бренду / версия {data["version"]}</div>' if cover else '<div class="eyebrow">Needle Shark / визуальная система</div>')
    heading += '<h1>'+esc(page['title'])+'</h1><div class="lead">'+esc(page['lead'])+'</div>'
    pages.append(f'<section class="page {"cover" if cover else ""}" data-page="{n}"><main>{heading}{"".join(blocks)}</main><footer><span>NEEDLE SHARK · 19.10.2026</span><span>{n:02d} / {len(data["pages"]):02d}</span></footer></section>')

css = '''
@page { size: A4; margin: 0; }
* { box-sizing: border-box; }
html,body { margin:0; padding:0; color:#1B1F21; background:#ECEEE9; font-family:Manrope,Arial,sans-serif; }
body { font-size:13.5px; line-height:1.56; }
.page { width:210mm; height:297mm; padding:16mm 17mm 17mm; position:relative; background:#F6F7F4; break-after:page; }
.page:last-child { break-after:auto; }
main { width:100%; }
.eyebrow { text-transform:uppercase; font-size:10px; letter-spacing:.13em; color:#636963; font-weight:700; border-top:2px solid #BE3E3E; padding-top:11px; margin-bottom:17px; }
h1 { font-size:31px; line-height:1.14; letter-spacing:-1.1px; font-weight:800; margin:0 0 12px; max-width:650px; }
.lead { font-size:16px; line-height:1.45; color:#636963; margin-bottom:24px; }
h3 { font-size:16px; line-height:1.4; margin:21px 0 9px; font-weight:800; letter-spacing:-.2px; }
p { margin:0 0 13px; }
ul { padding-left:18px; margin:0 0 17px; }
li { padding-left:3px; margin-bottom:9px; }
li::marker { color:#BE3E3E; }
.callout { background:#ECEEE9; border-left:3px solid #BE3E3E; padding:15px 17px; margin:16px 0; }
.small { font-size:10.8px; line-height:1.6; color:#636963; margin-top:12px; }
table { border-collapse:collapse; width:100%; font-size:12.1px; line-height:1.55; margin:15px 0 18px; table-layout:fixed; }
th { text-align:left; font-size:10px; text-transform:uppercase; letter-spacing:.07em; color:#636963; border-top:1px solid #1B1F21; border-bottom:1px solid #D7DAD4; padding:10px 9px; }
td { vertical-align:top; padding:10px 9px; border-bottom:1px solid #D7DAD4; overflow-wrap:anywhere; }
th:first-child,td:first-child { width:29%; padding-left:0; }
td:first-child { font-weight:700; }
footer { position:absolute; bottom:10mm; left:17mm; right:17mm; display:flex; justify-content:space-between; border-top:1px solid #D7DAD4; padding-top:9px; font-size:9px; letter-spacing:.08em; color:#636963; }
.cover-logo { width:181px; height:auto; display:block; margin:5px 0 68px; }
.cover .eyebrow { border:0; padding:0; margin-bottom:18px; }
.cover h1 { font-size:53px; letter-spacing:-2.3px; line-height:1.04; max-width:610px; margin-bottom:23px; }
.cover .lead { font-size:21px; max-width:490px; margin-bottom:31px; }
.cover .callout { background:transparent; border:0; border-top:2px solid #BE3E3E; border-bottom:1px solid #D7DAD4; padding:18px 0; font-size:17px; font-weight:700; }
.cover h3 { margin-top:25px; }
.logo-panel { background:#ECEEE9; height:145px; display:flex; justify-content:center; align-items:center; margin-bottom:18px; }
.logo-panel img { width:270px; height:auto; }
.palette { display:grid; grid-template-columns:1fr 1fr; gap:15px 24px; margin:24px 0; }
.swatch { display:flex; gap:13px; align-items:flex-start; }
.swatch>span { width:65px; height:65px; border:1px solid #D7DAD4; flex-shrink:0; }
.swatch strong { display:block; font-size:12px; }
.swatch code { display:block; font:700 12px Manrope; margin:1px 0 4px; }
.swatch small { display:block; font-size:10.5px; color:#636963; line-height:1.4; }
.type-sample { border-top:1px solid #D7DAD4; border-bottom:1px solid #D7DAD4; padding:17px 0 8px; margin:0 0 18px; }
.type-sample>div { font-size:37px; font-weight:800; line-height:1.1; letter-spacing:-1.6px; margin:0 0 12px; }
.type-sample em { font-style:normal; color:#BE3E3E; }
.type-sample p { font-size:11px; margin:7px 0; }
.layout { background:#ECEEE9; padding:17px 20px; margin-bottom:10px; }
.diagram-title { font-size:9px; letter-spacing:.09em; text-transform:uppercase; color:#636963; margin-bottom:12px; }
.diagram-grid { display:grid; grid-template-columns:1fr 1fr; gap:28px; }
.diagram-grid b { font-size:27px; line-height:1.08; letter-spacing:-.8px; }
.diagram-grid p { font-size:11px; margin:10px 0; }
.diagram-grid span { display:inline-block; background:#BE3E3E; color:#fff; padding:7px 22px; font-size:10px; }
.photo-slot { border:1px solid #D7DAD4; display:flex; align-items:center; justify-content:center; text-align:center; font-size:12px; color:#636963; }
.examples { display:grid; grid-template-columns:1fr 1fr; gap:21px; align-items:start; }
figure { margin:0; }
.examples img { width:100%; height:300px; object-fit:contain; object-position:top center; display:block; }
figcaption { font-size:9px; color:#636963; margin:8px 0 0; }
.agent { background:#ECEEE9; border-top:2px solid #BE3E3E; padding:19px 21px; font-size:12.65px; line-height:1.58; }
.agent p:last-child { margin-bottom:0; }
.page[data-page="11"] td { padding-top:7px; padding-bottom:7px; }
.page[data-page="11"] li { margin-bottom:7px; }
.page[data-page="3"] h3 { padding-top:15px; }
@media screen { .page { margin:20px auto; box-shadow:0 5px 30px #0001; } }
'''
for subset, ranges in [('cyrillic','U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116'),('latin','U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD')]:
    for weight in [400,700,800]:
        font = uri(TMP / f'manrope-{subset}-{weight}.ttf', 'font/ttf')
        css += f'@font-face{{font-family:Manrope;src:url("{font}") format("truetype");font-weight:{weight};font-style:normal;font-display:block;unicode-range:{ranges};}}'

(HERE / 'BRAND_KNOWLEDGE.md').write_text('\n\n'.join(clean(s) for s in md)+'\n')
(HERE / 'AGENT_INSTRUCTIONS.txt').write_text(clean(agent_text))
(HERE / 'START_HERE.txt').write_text('''NEEDLE SHARK / ПЕРЕДАЧА ВИЗУАЛЬНОЙ БАЗЫ
Версия 1.0, 19 октября 2026

1. Прочитайте Needle-Shark-Brand-Guide.pdf.
2. Загрузите BRAND_KNOWLEDGE.md в базу знаний агента.
3. Вставьте AGENT_INSTRUCTIONS.txt в поле его инструкций.
4. Приложите assets/logo.svg, примеры из assets/ и ресурсы fonts/.
   Если система не принимает SVG/WOFF2, передайте эти ресурсы дизайнеру
   для финальной сборки; логотип не генерируйте заново.
5. Дайте конкретный бриф по разделу «Бриф и порядок работы».
6. Проверьте результат по списку в конце руководства.

PDF и Markdown содержат одни и те же правила. Для обучения через базу
знаний достаточно Markdown, а PDF нужен для визуальной сверки.
Другие документы проекта и доступ к репозиторию не требуются.
Не загружайте старую конфликтующую дизайн-концепцию как равноправный стандарт.
Согласованные образцы писем показывают композицию; поля в скобках в КП
заполняются перед отправкой. Не использовать их как готовый текст рекламы.
В комплекте нет фотографий изделий: исходники конкретного товара
нужно прикладывать к отдельному заданию.

Ресурсы
assets/logo.svg — исходный составной логотип.
assets/logo-email.png — PNG 513 × 174, непрозрачный фон #F6F7F4.
assets/email-received.png — согласованный образец письма.
assets/email-quote.jpg — согласованный образец КП с полями для заполнения.
fonts/manrope-cyrillic.woff2 и manrope-latin.woff2 — веб-шрифты.
fonts/OFL.txt — лицензия SIL OFL.

Раздавайте комплект целиком. При обновлении заменяйте и PDF, и текст,
повышайте версию; не смешивайте разные версии в активной базе агента.
''')
(TMP / 'guide.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Needle Shark — руководство по бренду</title><style>'+css+'</style><body>'+''.join(pages)+'</body></html>')
print(json.dumps({'pages':len(pages),'html':str(TMP/'guide.html'),'markdown':str(HERE/'BRAND_KNOWLEDGE.md')},ensure_ascii=False))
