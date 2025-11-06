#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
8gen — generátor osmisměrek (PDF, zelený vzhled)
- Slova se berou z PRVNÍHO zadaného souboru (TXT/CSV; 1/řádek nebo čárky/středníky).
- Pokud --words neuvedeš, použije se words.txt v aktuálním adresáři.
- Náhodně přijme jen TOLIK slov, kolik se podaří umístit do mřížky (greedy).
- Výchozí: česká abeceda s diakritikou, diagonály povolené, 10 stran.
- Každá strana = nově vygenerovaná mřížka (náhodně), seznam slov POD mřížkou.
- Žádná „témata“.

Instalace:
    pip install reportlab

Příklady:
    python 8gen.py --words slova.txt -o osmismerky.pdf
    python 8gen.py --pages 3 --cell 9 --size 16 -o tri_zelene.pdf
"""
import argparse
import os
import re
import random
import unicodedata
from datetime import datetime
from typing import List, Tuple, Set, Dict

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ---- Fonty (pro diakritiku) ----
TITLE_FONT = "UI-Bold"
TEXT_FONT = "UI"
MONO_FONT = "UI-Mono"
_fallback = False
BASE = os.path.dirname(__file__)
print(BASE)
try:
    pdfmetrics.registerFont(TTFont("UI", os.path.join(BASE, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("UI-Bold", os.path.join(BASE, "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("UI-Mono", os.path.join(BASE, "DejaVuSansMono.ttf")))
except Exception:
    # fallback na základní fonty (bez zaručené diakritiky)
    TITLE_FONT = "Helvetica-Bold"
    TEXT_FONT = "Helvetica"
    MONO_FONT = "Courier"
    _fallback = True

# ---- Barvy (zelené) ----
DARK_GREEN = colors.HexColor("#0F5132")    # tmavší zelená (písmo, čáry)
SOFT_GREEN = colors.HexColor("#E6F2EC")    # světle zelené pozadí stránky
GRID_FILL = colors.HexColor("#F0FBF6")     # světlé pozadí mřížky

ALPHABETS: Dict[str, str] = {
    "CZ (s diakritikou)": "AÁBCČDĎEÉĚFGHIÍJKLĽMNŇOÓPQRŘSŠTŤUÚŮVWXYÝZŽ",
    "A-Z (bez diakritiky)": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
}

DIRECTIONS: List[Tuple[int,int,str]] = [
    (1, 0, "E"), (0, 1, "S"), (1, 1, "SE"), (-1, 1, "SW"),
    (-1, 0, "W"), (0, -1, "N"), (-1, -1, "NW"), (1, -1, "NE"),
]

def remove_diacritics(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def pick_allowed(diagonals: bool=True, backwards: bool=True):
    forward = {"E", "S", "SE", "SW"}
    allowed = [d for d in DIRECTIONS if diagonals or d[0] == 0 or d[1] == 0]
    if backwards: return allowed
    return [d for d in allowed if d[2] in forward]

def make_empty(n: int):
    return [[None for _ in range(n)] for __ in range(n)]

def can_place(grid, x, y, dx, dy, word):
    n = len(grid)
    for i, ch in enumerate(word):
        cx, cy = x + dx*i, y + dy*i
        if cx < 0 or cy < 0 or cx >= n or cy >= n: return False
        cell = grid[cy][cx]
        if cell is not None and cell != ch: return False
    return True

def place_word(grid, x, y, dx, dy, word):
    coords = []
    for i, ch in enumerate(word):
        cx, cy = x + dx*i, y + dy*i
        grid[cy][cx] = ch
        coords.append((y + dy*i, x + dx*i))
    return coords

def fill_random(grid, alphabet: str):
    n = len(grid)
    for y in range(n):
        for x in range(n):
            if grid[y][x] is None:
                grid[y][x] = random.choice(alphabet)

def parse_words_from_text(text: str, strip: bool=False) -> List[str]:
    parts = re.split(r"[,\n;]+", text)
    words = []
    for w in parts:
        w = w.strip()
        if not w: continue
        w_up = w.upper()
        if strip: w_up = remove_diacritics(w_up)
        w_up = ' '.join(w_up.split()).replace(" ", "")
        words.append(w_up)
    # deduplikace
    words = sorted(set(words))
    return words

def read_words_file(path: str, strip: bool=False) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return parse_words_from_text(f.read(), strip=strip)

def greedy_place(words: List[str], n: int, diagonals: bool, backwards: bool, alphabet_key: str):
    """Z náhodně promíchaných slov zkusí postupně umístit co nejvíc.
       Vrací: grid a seznam slov, která se opravdu vešla (placed_words)."""
    grid = make_empty(n)
    allowed = pick_allowed(diagonals, backwards)
    # promíchej pořadí
    words_pool = words[:]
    random.shuffle(words_pool)
    # pro lepší šanci na delší slova občas preferujeme delší při promíchání
    words_pool.sort(key=len, reverse=True)
    random.shuffle(words_pool)

    placed = []
    for w in words_pool:
        if len(w) > n:
            continue
        success = False
        for _ in range(1000):
            dx, dy, _name = random.choice(allowed)
            max_x = n-1 if dx <= 0 else n - len(w)
            min_x = 0 if dx >= 0 else len(w)-1
            max_y = n-1 if dy <= 0 else n - len(w)
            min_y = 0 if dy >= 0 else len(w)-1
            x = random.randint(min_x, max_x)
            y = random.randint(min_y, max_y)
            if can_place(grid, x, y, dx, dy, w):
                place_word(grid, x, y, dx, dy, w)
                placed.append(w)
                success = True
                break
        # když to nejde, prostě přeskočíme
    # doplň písmena
    letters = ALPHABETS.get(alphabet_key, ALPHABETS["CZ (s diakritikou)"])
    letters_random = remove_diacritics(letters).upper()
    letters_random = ''.join(sorted(set([ch for ch in letters_random if 'A' <= ch <= 'Z'])))
    fill_random(grid, letters_random)
    return grid, placed

# ---- Vykreslení ----
def fill_page_background(c):
    W, H = A4
    c.setFillColor(SOFT_GREEN)
    c.rect(0, 0, W, H, stroke=0, fill=1)  # pozadí celé stránky
    c.setFillColor(DARK_GREEN)

def draw_grid(c, grid, origin_x, origin_y, cell_mm=8):
    n = len(grid)
    cell = cell_mm * mm
    # podklad mřížky
    c.setFillColor(GRID_FILL)
    c.rect(origin_x, origin_y, n*cell, n*cell, stroke=0, fill=1)
    c.setFillColor(DARK_GREEN)
    c.setStrokeColor(DARK_GREEN)
    c.setLineWidth(1)
    c.rect(origin_x, origin_y, n*cell, n*cell, stroke=1, fill=0)
    for y in range(n):
        for x in range(n):
            x0 = origin_x + x*cell
            y0 = origin_y + (n-1-y)*cell
            c.rect(x0, y0, cell, cell, stroke=1, fill=0)
            ch = grid[y][x]
            c.setFont(MONO_FONT, max(8, int(cell_mm*1.8)))
            tw = pdfmetrics.stringWidth(ch, MONO_FONT, max(8, int(cell_mm*1.8)))
            c.setFillColor(DARK_GREEN)
            c.drawString(x0 + (cell - tw)/2, y0 + cell*0.25, ch)

def draw_word_list_below(c, words: List[str], page_left, page_right, below_y, page_bottom=15, line_h_mm=6, cols=4, title="Seznam slov:"):
    c.setFont(TITLE_FONT, 12)
    c.setFillColor(DARK_GREEN)
    c.drawString(page_left, below_y, title)
    c.setFont(TEXT_FONT, 11)
    y = below_y - 5*mm

    # Available space (mm)
    avail_h_mm = (y/mm) - page_bottom
    if avail_h_mm < 10:
        avail_h_mm = 10

    # Auto-fit cols/line height
    ordered = sorted(words)
    col_gap_mm = 10

    # Try to fit with up to 8 columns and min line height 4mm
    best = None
    for try_cols in range(max(2, cols), 9):
        # maximum rows per column with current line height
        rows = max(1, int(avail_h_mm // line_h_mm))
        need_cols = (len(ordered) + rows - 1) // rows
        # expand columns if needed
        use_cols = max(try_cols, need_cols)
        if use_cols > 8:
            use_cols = 8
        # compute if fits horizontally
        max_width_mm = (page_right - page_left)/mm
        total_gap_mm = (use_cols - 1) * col_gap_mm
        col_width_mm = (max_width_mm - total_gap_mm) / use_cols
        if col_width_mm <= 0:
            continue
        # if rows too few, try smaller line height down to 4mm
        while rows * use_cols < len(ordered) and line_h_mm > 4:
            line_h_mm -= 1
            rows = max(1, int(avail_h_mm // line_h_mm))
            need_cols = (len(ordered) + rows - 1) // rows
            use_cols = max(use_cols, need_cols)
            if use_cols > 8:
                use_cols = 8
        if rows * use_cols >= len(ordered):
            best = (use_cols, line_h_mm, col_width_mm)
            break
    if best is None:
        # As a last resort, truncate and add ellipsis marker
        use_cols = 8
        col_width_mm = ( (page_right - page_left)/mm - (use_cols-1)*col_gap_mm ) / use_cols
        rows = max(1, int(avail_h_mm // line_h_mm))
        max_words = rows * use_cols
        ordered = ordered[:max_words-1] + ["…"] if len(ordered) > max_words else ordered
    else:
        use_cols, line_h_mm, col_width_mm = best

    # Build columns
    buckets = [[] for _ in range(use_cols)]
    for i, w in enumerate(ordered):
        buckets[i % use_cols].append(w)

    # Draw
    col_gap = col_gap_mm * mm
    col_width = col_width_mm * mm
    for ci, col in enumerate(buckets):
        x = page_left + ci * (col_width + col_gap)
        yy = y
        for w in col:
            c.drawString(x, yy, w)
            yy -= line_h_mm * mm

def page(c, title: str, subtitle: str, grid, placed_words: List[str], cell_mm: int, columns: int):
    W, H = A4
    page_left = 20*mm
    page_right = W - 20*mm
    top = H - 25*mm

    #fill_page_background(c)

    # hlavička
    c.setFillColor(DARK_GREEN)
    c.setFont(TITLE_FONT, 18)
    c.drawString(page_left, top, title)
    c.setFont(TEXT_FONT, 11)
    c.drawString(page_left, top - 6*mm, subtitle)

    # mřížka centrovaná vodorovně
    n = len(grid)
    cell = cell_mm * mm
    grid_w = n * cell
    origin_x = (W - grid_w) / 2.0
    origin_y = top - 20*mm - n*cell
    if origin_y < 40*mm: origin_y = 40*mm  # prostor pro seznam slov

    draw_grid(c, grid, origin_x, origin_y, cell_mm=cell_mm)

    # slova pod mřížkou (jen ta, která se VEŠLA)
    below_y = origin_y - 10*mm
    if below_y < 28*mm: below_y = 28*mm
    draw_word_list_below(c, placed_words, page_left, page_right, below_y, cols=columns)

    # patička
    c.setFont(TEXT_FONT, 9)
    c.setFillColor(DARK_GREEN)
    c.drawString(page_left, 12*mm, datetime.now().strftime("Kitsune, já Tě děsně miluju. Okami"))
    c.showPage()

def save_pdf_many(filename: str, title: str, subtitle: str, words: List[str], cell_mm: int, pages: int, size: int, diagonals: bool, backwards: bool, alphabet_key: str, columns: int):
    c = canvas.Canvas(filename, pagesize=A4)
    for _ in range(max(1, pages)):
        grid, placed_words = greedy_place(words, n=size, diagonals=diagonals, backwards=backwards, alphabet_key=alphabet_key)
        page(c, title, subtitle, grid, placed_words, cell_mm, columns)
    c.save()

def main():
    ap = argparse.ArgumentParser(description="8gen — generátor osmisměrek (PDF, zelený vzhled).")
    ap.add_argument("--words", help="Cesta k TXT/CSV se slovy. Když neuvedeš, použije se 'words.txt' v aktuálním adresáři.")
    ap.add_argument("-s","--size", type=int, default=15, help="Velikost mřížky (5..40).")
    ap.add_argument("-c","--cell", type=int, default=8, help="Velikost políčka [mm] (7–10 tisk).")
    ap.add_argument("--no-diagonals", action="store_true", help="Zakáže diagonály.")
    ap.add_argument("--no-backwards", action="store_true", help="Zakáže směry pozpátku.")
    ap.add_argument("--alphabet", default="CZ (s diakritikou)", choices=list(ALPHABETS.keys()), help="Volba abecedy (default CZ s diakritikou).")
    ap.add_argument("--strip", action="store_true", help="Odstranit diakritiku ze slov před vkládáním.")
    ap.add_argument("--title", default="Osmisměrka", help="Titulek PDF.")
    ap.add_argument("--subtitle", default="Najdi všechna slova.", help="Podtitulek PDF.")
    ap.add_argument("--pages", type=int, default=10, help="Počet stran (osmisměrek) v PDF. Default 10.")
    ap.add_argument("--columns", type=int, default=4, help="Počet sloupců seznamu slov pod mřížkou (auto-fit, min 2, max 8). Default 4.")
    ap.add_argument("-o","--output", default="osmismerky.pdf", help="Cílové PDF.")
    args = ap.parse_args()

    if args.size < 5 or args.size > 40:
        raise SystemExit("Velikost mřížky musí být 5..40.")

    # urči zdrojový soubor se slovy (uvnitř main — args je dostupný)
    if args.words:
        first_path = str(args.words).split(",")[0].strip()
    else:
        first_path = "words.txt"
    if not os.path.isfile(first_path):
        raise SystemExit(f"Soubor se slovy nebyl nalezen: {first_path}")

    # načti slova
    words = read_words_file(first_path, strip=args.strip)
    if not words:
        raise SystemExit("V souboru nejsou žádná použitelná slova.")

    diagonals = not args.no_diagonals
    backwards = not args.no_backwards

    # rychlá smoke-kontrola: zkus udělat jednu mřížku, aby se ověřilo, že parametry dávají smysl
    _grid, _placed = greedy_place(words, n=args.size, diagonals=diagonals, backwards=backwards, alphabet_key=args.alphabet)
    if not _placed:
        raise SystemExit("Nepodařilo se umístit žádné slovo. Zvaž větší mřížku, kratší slova, povol diagonály/pozpátku.")

    save_pdf_many(
        args.output, args.title, args.subtitle,
        words, cell_mm=args.cell, pages=args.pages, size=args.size,
        diagonals=diagonals, backwards=backwards, alphabet_key=args.alphabet,
        columns=args.columns
    )

    if _fallback:
        print("Upozornění: DejaVuSans není dostupný, použit fallback font (diakritika nemusí být 100%).")

    print(f"Hotovo -> {args.output} (slova ze souboru: {first_path})")

if __name__ == "__main__":
    main()
