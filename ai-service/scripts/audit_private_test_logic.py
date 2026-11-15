from __future__ import annotations

import html
import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether

ROOT = Path(__file__).resolve().parents[1]
from advertisement_lexicon import IDS, LEX, NAMES
NEG = re.compile(r"(?:не\s+(?:дела\w*|выполня\w*|оказыва\w*|занима\w*|предлага\w*|монтир\w*|устанавлива\w*|подключа\w*|укладыва\w*|кле\w*|крас\w*|штукатур\w*|ремонтир\w*)|не\s+наши|не\s+выполняем|кроме|за\s+исключением|отказ\w*\s+от)", re.I)
INJECTION = re.compile(r"игнорируй|если ты (?:языковая )?модель|для модели|верни\s*\[|выдай категори|повтори этот текст|короткий ответ запрещ|иначе проверка не пройдёт|добавь все возможные категори", re.I)

def clean(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()

def evidence_for(text: str, rx: re.Pattern) -> list[tuple[str, bool]]:
    out=[]
    for m in rx.finditer(text):
        before=text[max(0,m.start()-65):m.start()]
        neg=bool(NEG.search(before))
        out.append((text[max(0,m.start()-60):min(len(text),m.end()+65)],neg))
        if len(out)>=3: break
    return out

def category_analysis(text: str):
    hits={c:evidence_for(text,rx) for c,rx in LEX.items()}
    positive={c for c,vals in hits.items() if any(not neg for _,neg in vals)}
    negated={c for c,vals in hits.items() if vals and not any(not neg for _,neg in vals)}
    return hits,positive,negated

def build(csv_path: Path, prediction_path: Path, output_path: Path):
    df=pd.read_csv(csv_path).fillna({"description":""})
    pred=pd.read_csv(prediction_path).fillna({"predicted_categories":""})
    if len(df)!=len(pred): raise ValueError("Prediction rows do not match source CSV")
    font=Path(r"C:\Windows\Fonts\arial.ttf")
    bold=Path(r"C:\Windows\Fonts\arialbd.ttf")
    pdfmetrics.registerFont(TTFont("Arial",str(font)))
    pdfmetrics.registerFont(TTFont("Arial-Bold",str(bold)))
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleRu",parent=styles["Title"],fontName="Arial-Bold",fontSize=21,leading=26,textColor=colors.HexColor("#16324F"),alignment=TA_CENTER,spaceAfter=12))
    styles.add(ParagraphStyle(name="SubRu",parent=styles["Normal"],fontName="Arial",fontSize=10,leading=15,textColor=colors.HexColor("#3A4A5A"),alignment=TA_CENTER,spaceAfter=14))
    styles.add(ParagraphStyle(name="H1Ru",parent=styles["Heading1"],fontName="Arial-Bold",fontSize=15,leading=19,textColor=colors.HexColor("#16324F"),spaceBefore=9,spaceAfter=7))
    styles.add(ParagraphStyle(name="H2Ru",parent=styles["Heading2"],fontName="Arial-Bold",fontSize=11,leading=14,textColor=colors.HexColor("#205375"),spaceBefore=6,spaceAfter=4))
    styles.add(ParagraphStyle(name="BodyRu",parent=styles["BodyText"],fontName="Arial",fontSize=8.5,leading=11.5,spaceAfter=4))
    styles.add(ParagraphStyle(name="SmallRu",parent=styles["BodyText"],fontName="Arial",fontSize=7.4,leading=10,spaceAfter=3,textColor=colors.HexColor("#334155")))
    story=[]
    story += [Spacer(1,18*mm),Paragraph("Построчный логический аудит классификатора",styles["TitleRu"]),Paragraph("Private test dataset · 262 объявления · источник 101 → целевые категории 102–106",styles["SubRu"]),Spacer(1,8*mm)]
    story.append(Paragraph("Что проверено",styles["H1Ru"]))
    story.append(Paragraph("Каждое объявление сопоставлено с результатом текущего ансамбля (CPU char 55% + RuBERT 45%, порог 0,525). Для всех 262 записей оценены прямые смысловые признаки услуг, соответствие предсказанных меток тексту, возможные пропуски, отрицания и инструкции, пытающиеся повлиять на классификацию. Ниже приведён разбор каждой строки, включая объявления без предсказанных категорий.",styles["BodyRu"]))
    story.append(Paragraph("Ограничение интерпретации",styles["H1Ru"]))
    story.append(Paragraph("В private-test-dataset.csv нет эталонных меток. Поэтому это качественный аудит логики по тексту, а не измерение точности. Прямые ключевые слова дают сильное основание, но отсутствие такого слова не доказывает ошибку: услуга может быть описана косвенно. Формулировки «вероятный пропуск», «неподтверждённая метка» и «нужна ручная проверка» обозначают именно такие уровни уверенности.",styles["BodyRu"]))
    story.append(Paragraph("Сводка прогона",styles["H1Ru"]))
    pred_ids=[]; counts=Counter(); zero=0; multi=0; all5=0
    all_entries=[]
    for i,row in df.iterrows():
        pr=pred.iloc[i]
        raw=str(pr.predicted_categories).strip()
        assigned=set(int(x) for x in raw.split(";") if x and x!="nan")
        counts.update(assigned); zero+=not assigned; multi+=len(assigned)>1; all5+=len(assigned)==5
        text=clean(row.description); hits,positive,negated=category_analysis(text)
        injections=[m.group(0) for m in INJECTION.finditer(text)]
        missing=positive-assigned
        unsupported=assigned-positive
        if not assigned and positive: status="Вероятный пропуск явной услуги"
        elif missing and unsupported: status="Есть и вероятные пропуски, и неподтверждённые метки"
        elif missing: status="Есть вероятный пропуск услуги"
        elif unsupported: status="Есть метка без прямого словесного подтверждения"
        elif injections: status="Инструкция-вставка: проверить устойчивость"
        elif not positive and not assigned: status="Пустой ответ выглядит допустимым по явным признакам"
        else: status="Явные признаки в целом согласуются"
        all_entries.append((row,pr,assigned,text,hits,positive,negated,missing,unsupported,injections,status))
    story.append(Paragraph(f"Строк: {len(df)}; уникальных текстов: {df.description.nunique()}; с хотя бы одной категорией: {len(df)-zero}; без целевых категорий: {zero}; с несколькими: {multi}; сразу со всеми пятью: {all5}.",styles["BodyRu"]))
    story.append(Paragraph("Число назначений по категориям: "+"; ".join(f"{c} {NAMES[c]}: {counts[c]}" for c in IDS)+".",styles["BodyRu"]))
    counts_status=Counter(e[-1] for e in all_entries)
    story.append(Paragraph("Автоматически найденные логические сигналы (ориентир для чтения, не gold labels): "+"; ".join(f"{k}: {v}" for k,v in counts_status.items())+".",styles["BodyRu"]))
    story.append(Paragraph("Как читать карточки",styles["H1Ru"]))
    story.append(Paragraph("«Прямые основания» — фрагменты с явными названиями работ. «Вероятный пропуск» — работа явно упомянута, но модель её не назначила. «Не подтверждена напрямую» — модель назначила категорию, но прямой сигнал не найден; это может быть как лишняя метка, так и разумное смысловое обобщение. Инструкция-вставка сама по себе не является услугой и не должна менять предсказание.",styles["BodyRu"]))
    story.append(PageBreak())

    for idx,(row,pr,assigned,text,hits,positive,negated,missing,unsupported,injections,status) in enumerate(all_entries,1):
        case=html.escape(str(row.testcase))
        names=lambda cs: ", ".join(f"{c} {NAMES[c]}" for c in sorted(cs)) if cs else "нет"
        scoretxt="; ".join(f"{c}: {float(pr[f'score_{c}']):.3f}" for c in IDS)
        parts=[Paragraph(f"{idx:03d}. {case}",styles["H2Ru"]),
               Paragraph(f"<b>Результат модели:</b> {names(assigned)}. <b>Статус аудита:</b> {html.escape(status)}.",styles["BodyRu"]),
               Paragraph(f"<b>Оценки модели:</b> {scoretxt}.",styles["SmallRu"])]
        if positive:
            parts.append(Paragraph(f"<b>Прямо подтверждаются текстом:</b> {names(positive)}.",styles["BodyRu"]))
        if missing:
            parts.append(Paragraph(f"<font color='#A61B1B'><b>Вероятно пропущены:</b> {names(missing)}.</font>",styles["BodyRu"]))
        if unsupported:
            parts.append(Paragraph(f"<font color='#A05A00'><b>Назначены без прямого подтверждения:</b> {names(unsupported)}.</font>",styles["BodyRu"]))
        if negated:
            parts.append(Paragraph(f"<b>Есть лексика в отрицательном/ограничительном контексте:</b> {names(negated)}; проверить, не приняла ли модель упоминание за предложение услуги.",styles["BodyRu"]))
        ev=[]
        for c,vals in hits.items():
            for frag,neg in vals:
                ev.append(f"{c}{' (отрицание/ограничение)' if neg else ''}: «…{html.escape(clean(frag))}…»")
        if ev: parts.append(Paragraph("<b>Основания в тексте:</b> " + "<br/>".join(ev[:8]),styles["SmallRu"]))
        if injections:
            inj="; ".join(sorted(set(injections))[:5])
            parts.append(Paragraph(f"<font color='#6B3FA0'><b>Отвлекающая/инъекционная фраза:</b> {html.escape(inj)}.</font>",styles["SmallRu"]))
        # Include enough of every description for a human to review the logic.
        excerpt=text if len(text)<=850 else text[:820]+" … [текст сокращён; полная запись в исходном CSV]"
        parts.append(Paragraph("<b>Текст объявления:</b> "+html.escape(excerpt),styles["SmallRu"]))
        parts.append(Spacer(1,4))
        story.append(KeepTogether(parts))
    def footer(canvas,doc):
        canvas.saveState(); canvas.setFont("Arial",7); canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(16*mm,10*mm,"Логический аудит private-test · без эталонной разметки")
        canvas.drawRightString(A4[0]-16*mm,10*mm,f"Стр. {doc.page}")
        canvas.restoreState()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc=SimpleDocTemplate(str(output_path),pagesize=A4,rightMargin=15*mm,leftMargin=15*mm,topMargin=15*mm,bottomMargin=17*mm,title="Построчный логический аудит private test")
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    print(json.dumps({"pdf":str(output_path),"rows":len(df),"counts":dict(counts),"signals":dict(counts_status),"zero":zero,"positive":len(df)-zero},ensure_ascii=False,indent=2))

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description="Build a row-level logic audit from local CSV files")
    parser.add_argument("--private-csv",type=Path,required=True,help="Input CSV with testcase and description columns")
    parser.add_argument("--predictions-csv",type=Path,required=True,help="Prediction CSV with predicted_categories and score_* columns")
    parser.add_argument("--output",type=Path,required=True,help="Output PDF path")
    args=parser.parse_args()
    build(args.private_csv,args.predictions_csv,args.output)
