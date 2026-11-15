"""Build the Russian report for the latest conflict-resolved ensemble."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable,
)

REPO = Path(__file__).resolve().parents[2]
OUTPUT = REPO / "output/pdf/avito_last_model_analysis_ru.pdf"

NAVY = HexColor("#172B4D")
BLUE = HexColor("#176B87")
TEAL = HexColor("#19A4A2")
PALE = HexColor("#EEF5F8")
LIGHT = HexColor("#F5F7FA")
MID = HexColor("#576779")
GREEN = HexColor("#24745E")

pdfmetrics.registerFont(TTFont("Arial", r"C:\Windows\Fonts\arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", r"C:\Windows\Fonts\arialbd.ttf"))

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleRU", fontName="Arial-Bold", fontSize=25, leading=31, textColor=NAVY, spaceAfter=8))
styles.add(ParagraphStyle(name="SubtitleRU", fontName="Arial", fontSize=11, leading=16, textColor=MID, spaceAfter=12))
styles.add(ParagraphStyle(name="H1RU", fontName="Arial-Bold", fontSize=17, leading=22, textColor=NAVY, spaceBefore=4, spaceAfter=9, keepWithNext=True))
styles.add(ParagraphStyle(name="H2RU", fontName="Arial-Bold", fontSize=11.5, leading=15, textColor=BLUE, spaceBefore=7, spaceAfter=5, keepWithNext=True))
styles.add(ParagraphStyle(name="BodyRU", fontName="Arial", fontSize=9.3, leading=13.5, textColor=HexColor("#263442"), spaceAfter=6))
styles.add(ParagraphStyle(name="SmallRU", fontName="Arial", fontSize=7.6, leading=10.4, textColor=MID, spaceAfter=3))
styles.add(ParagraphStyle(name="CellRU", fontName="Arial", fontSize=8, leading=10.5, textColor=HexColor("#263442")))
styles.add(ParagraphStyle(name="CellBoldRU", fontName="Arial-Bold", fontSize=8, leading=10.5, textColor=HexColor("#263442")))
styles.add(ParagraphStyle(name="CellHeaderRU", fontName="Arial-Bold", fontSize=8, leading=10.5, textColor=colors.white))
styles.add(ParagraphStyle(name="CalloutRU", fontName="Arial-Bold", fontSize=10, leading=14, textColor=NAVY))
styles.add(ParagraphStyle(name="LabelRU", fontName="Arial-Bold", fontSize=7.6, leading=9, textColor=TEAL, spaceAfter=3))


def P(text, style="BodyRU"):
    return Paragraph(text, styles[style])


def cell(text, bold=False):
    return P(text, "CellBoldRU" if bold else "CellRU")


def make_table(data, widths, header=True):
    if header:
        data = [[P(v.getPlainText() if isinstance(v, Paragraph) else str(v), "CellHeaderRU") for v in data[0]]] + data[1:]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), .35, HexColor("#D7E0E8")),
    ]
    if header:
        commands.append(("BACKGROUND", (0, 0), (-1, 0), NAVY))
    if len(data) > 1:
        commands.append(("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, LIGHT]))
    t.setStyle(TableStyle(commands))
    return t


def on_page(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 7 * mm, width, 7 * mm, stroke=0, fill=1)
    canvas.setFont("Arial", 7.5)
    canvas.setFillColor(MID)
    canvas.drawString(17 * mm, 10 * mm, "Разбор локального ансамбля Avito | 15 ноября 2026")
    canvas.drawRightString(width - 17 * mm, 10 * mm, str(doc.page))
    canvas.restoreState()


def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frame = Frame(16 * mm, 17 * mm, A4[0] - 32 * mm, A4[1] - 31 * mm,
                  id="normal", leftPadding=0, rightPadding=0, topPadding=8 * mm, bottomPadding=0)
    doc = BaseDocTemplate(str(OUTPUT), pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm,
                          topMargin=15 * mm, bottomMargin=17 * mm,
                          title="Разбор последней версии классификатора Avito", author="OpenAI Codex")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=on_page)])
    story = []

    # Page 1: executive summary and comparable independent results.
    story += [Spacer(1, 8 * mm), P("ТЕХНИЧЕСКИЙ ОТЧЁТ · ВЕРСИЯ 15.11.2026", "LabelRU"),
              P("Классификатор объявлений Avito", "TitleRU"),
              P("Разбор последней обученной версии: conflict-resolved adaptive ensemble", "SubtitleRU"),
              HRFlowable(width="100%", thickness=1.1, color=TEAL, spaceAfter=10)]
    hero = Table([[P("Кандидат обучен и проверен на доступных независимых данных. Его оценка на секретной проверке неизвестна. Предыдущая отправка с результатом 89% сохранена как ориентир.", "CalloutRU")]], colWidths=[doc.width])
    hero.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PALE), ("BOX", (0, 0), (-1, -1), .7, TEAL),
                              ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                              ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    story += [hero, Spacer(1, 5 * mm), P("Короткий вывод", "H1RU"),
              P("Новая версия не улучшила micro-F1 на доступной ручной проверке относительно варианта, набравшего 89%: обе версии получили 0.9091 на 19 независимых ручных объявлениях. На 800 авторских OOD-текстах новый кандидат допустил одно ложное срабатывание вместо двух. Это умеренно положительный сигнал по отказу от мусора, но он не доказывает рост закрытого балла.")]
    metrics = [
        [cell("Проверка", True), cell("Последняя модель", True), cell("Версия 89%", True)],
        [cell("Ручная выборка, micro-F1"), cell("0.9091"), cell("0.9091")],
        [cell("Precision / recall"), cell("0.8333 / 1.0000"), cell("0.8333 / 1.0000")],
        [cell("Exact match"), cell("0.7368"), cell("0.7368")],
        [cell("OOD: ложные срабатывания"), cell("1 / 800 (0.125%)"), cell("2 / 800 (0.250%)")],
    ]
    story += [make_table(metrics, [76 * mm, 51 * mm, 51 * mm]), Spacer(1, 4 * mm),
              P("Статус секретного результата", "H2RU"),
              P("Новая submission ещё не получила балл от платформы. В отчёте не приводится прогноз закрытого score: локально известны только тексты и предсказания, но нет эталонных меток."),
              P("Сравнение с первой отправкой на 86%", "H2RU"),
              P("На тех же 19 ручных примерах первая фиксированная смесь дала micro-F1 0.8657 и exact match 0.6316; adaptive-версия и новый кандидат дали 0.9091 и 0.7368. Это сравнение на малой локальной выборке, не на закрытой проверке."), PageBreak()]

    # Page 2: data.
    story += [P("1. Данные и разрешение конфликтов", "H1RU"),
              P("Использованы слабые исходные метки, предыдущие курируемые контрасты и новые ручные дополнения. Исходный файл сохранён отдельно; обучающий вариант сформирован как новая копия.")]
    data_rows = [
        [cell("Этап", True), cell("Объём", True), cell("Что сделано", True)],
        [cell("Исходная обучающая копия"), cell("11 109 строк"), cell("Дедупликация по нормализованному тексту: оставлено 5 963 уникальных описания; схлопнуто 5 146 точных повторов.")],
        [cell("Похожие строки с разными метками"), cell("18 конфликтных групп"), cell("13 групп разрешены по тексту: исправлены 27 пропусков меток при явно перечисленной услуге. 5 групп оставлены: в них действительно различается перечень работ.")],
        [cell("Новые ручные файлы"), cell("51 строка -> 50 уникальных"), cell("26 строк из XLSX и 25 из CSV проверены по текущей услуге, контексту и отрицаниям. Один дословный дубль удалён. Семь добавочных фрагментов после разделителя CSV включены в описания.")],
        [cell("Итоговая база"), cell("6 013 уникальных текстов"), cell("5 963 очищенных исходных описания + 50 новых ручных примеров.")],
    ]
    story += [make_table(data_rows, [39 * mm, 37 * mm, 102 * mm]), Spacer(1, 4 * mm),
              P("Правило ручной сверки", "H2RU"),
              P("Положительной считается услуга, которую автор объявления предлагает сейчас. Слова в старом портфолио, упоминание работ другого подрядчика, отказ от услуги и только проектирование/подбор материалов не превращаются автоматически в целевой класс. Для неполных, общих объявлений используется пустой набор категорий, если конкретные работы не заявлены."),
              P("Распределение обучающих предъявлений CPU-модели", "H2RU")]
    train_rows = [
        [cell("Источник", True), cell("Уникальных примеров", True), cell("Повторы", True), cell("Предъявлений", True)],
        [cell("Исправленная исходная база"), cell("5 963"), cell("1"), cell("5 963")],
        [cell("Human-style ловушки"), cell("60"), cell("8"), cell("480")],
        [cell("Контрасты намерения"), cell("160"), cell("4"), cell("640")],
        [cell("Контрасты offer/scope"), cell("225"), cell("4"), cell("900")],
        [cell("Новые ручные примеры"), cell("50"), cell("8"), cell("400")],
        [cell("Всего для CPU fit"), cell("6 458 уникальных источников"), cell(""), cell("8 383")],
    ]
    story += [make_table(train_rows, [51 * mm, 40 * mm, 34 * mm, 53 * mm]), Spacer(1, 3 * mm),
              P("Для независимой оценки использованы 19 ручных объявлений, не попавших в исходную или новую обучающую выборку, и отдельный OOD набор из 800 текстов, где ожидаются нулевые дополнительные категории. Новые 50 ручных примеров использованы для обучения и не считаются тестом.", "SmallRU"), PageBreak()]

    # Page 3: architecture and runtime.
    story += [P("2. Архитектура и путь одного объявления", "H1RU"),
              P("Источник задачи - объявление категории 101 (ремонт под ключ). Ансамбль независимо оценивает пять дополнительных категорий:")]
    classes = [[cell("ID", True), cell("Категория", True), cell("Примеры смысла", True)],
               [cell("102"), cell("Штукатурные работы"), cell("Оштукатуривание, выравнивание стен")],
               [cell("103"), cell("Плиточные работы"), cell("Кафель, плитка, керамогранит")],
               [cell("104"), cell("Сантехнические работы"), cell("Трубы, смесители, сантехническое подключение")],
               [cell("105"), cell("Электромонтажные работы"), cell("Проводка, кабель, розетки, светильники")],
               [cell("106"), cell("Обои и малярные работы"), cell("Поклейка обоев, шпаклёвка, покраска")]]
    story += [make_table(classes, [20 * mm, 56 * mm, 102 * mm]), Spacer(1, 4 * mm),
              P("CPU модель", "H2RU"),
              P("Символьный TF-IDF char_wb, n-граммы длины 3-5, min_df=2, до 350 000 признаков, sublinear_tf=True. Головы классов - One-vs-Rest Logistic Regression с C=200 и балансировкой классов. CPU получает полный нормализованный текст."),
              P("RuBERT модель и длинный контекст", "H2RU"),
              P("DeepPavlov/rubert-base-cased с пятью sigmoid-выходами. Инференс разбивает объявление на окна до 512 токенов с перекрытием 128 токенов. По каждому классу берётся максимальная вероятность среди окон. Поэтому конец длинного текста тоже участвует в классификации, хотя при дообучении новой модели использовались первые 512 токенов каждого учебного экземпляра."),
              P("Адаптивная смесь и порог", "H2RU")]
    blend = [[cell("Размер по RuBERT tokenizer", True), cell("CPU", True), cell("RuBERT", True)],
             [cell("512 токенов или меньше"), cell("45%"), cell("55%")],
             [cell("Больше 512 токенов"), cell("55%"), cell("45%")]]
    story += [make_table(blend, [82 * mm, 45 * mm, 51 * mm]), Spacer(1, 3 * mm),
              P("Порог класса - 0.525. После порогового решения применяется детерминированная проверка явного отрицания, чтобы, например, фраза «электрику не выполняем» не выдавала электромонтажный класс только из-за слова «электрика». Если ни один класс 102-106 не проходит порог, возвращается пустой список."),
              P("На RTX 3050 в CUDA-режиме (100 объявлений, тёплый путь): p50 15.35 мс, p95 62.34 мс, среднее 36.26 мс на объявление. Загрузка CPU и RuBERT весов заняла около 8.31 с. Замер включает нормализацию, модели, смесь, порог и отрицания; исключает HTTP, сетевые задержки и генерацию текста."), PageBreak()]

    # Page 4: fit, costs, limitations.
    story += [P("3. Переобучение, стоимость и эксплуатация", "H1RU"),
              P("CPU-кандидат обучен на всех 8 383 предъявлениях, указанных выше. RuBERT дообучен от предыдущего checkpoint rubert_intent_context на 27 исправленных слабых метках и 50 новых ручных примерах, каждый повторён 8 раз: 616 предъявлений. Одна эпоха, batch size 4, gradient accumulation 2, AdamW, learning rate 1e-6; средний train loss 0.1438. Loss не является независимой метрикой качества."),
              P("Стоимость", "H2RU"),
              P("Классификация полностью локальная; платные API вызовы классификатора не выполняются, поэтому API cost составляет $0. Электропотребление не измерялось. Генерация заголовка или текста через DeepSeek является отдельным API этапом и в скорость и стоимость классификатора не входит."),
              P("Что говорят результаты", "H2RU"),
              P("Новый кандидат сохранил метрики adaptive-версии на 19 независимых ручных примерах и улучшил OOD false positives на одно объявление. Проверка подтверждает отсутствие явной регрессии на доступных наборах, но размер ручной выборки мал, а OOD набор составлен авторами проекта. Из этих результатов нельзя надёжно вывести закрытый балл."),
              P("Дальше нужно сравнить фактический score после отправки. Если он выше 89%, это подтвердит пользу изменений; если ниже, по одному агрегатному score нельзя определить ошибочные строки. Нужны дополнительные независимые ручные метки на спорные классы."),
              P("Конфигурация уже загружена в develop, commit b7a4507. Настройки: LOCAL_CLASSIFIER_BACKEND=ensemble, CPU/RuBERT веса cpu_char_conflict_resolved.joblib и rubert_conflict_resolved/, адаптивное смешивание и порог 0.525. В Git находятся конфигурация и код, веса распространяются отдельно из-за размера."),
              P("Файлы для воспроизведения", "H2RU"),
              P("В репозитории: ai-service/data/user-updated-train-conflict-resolved.jsonl, новые ручные примеры, три контрастных набора, OOD набор, скрипты подготовки/обучения/оценки, инструкция MODEL_CONFIGURATION_RU.md и этот PDF. Закрытый private-test-dataset.csv и построчные предсказания в публичный Git не включаются.")]
    callout = Table([[P("Итог: кандидат выглядит не хуже версии на 89% по независимой ручной проверке и немного лучше отказывает на авторском OOD наборе. Доказательств, что секретный score превысит 89%, пока нет.", "CalloutRU")]], colWidths=[doc.width])
    callout.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), HexColor("#EAF4EF")), ("BOX", (0, 0), (-1, -1), .8, GREEN),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                                 ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    story += [Spacer(1, 2 * mm), callout]
    doc.build(story)
    print(OUTPUT)


if __name__ == "__main__":
    build()
