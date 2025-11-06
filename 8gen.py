#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
8gen — generátor osmisměrek (PDF, bílý podklad stránky, zelený styl mřížky)
- Slova ze souboru (--words), jinak 'words.txt' v aktuálním adresáři.
- Volitelně tajenka z --tajenky nebo automaticky 'tajenky.csv'.
- Výchozí: CZ abeceda s diakritikou, diagonály povolené, 10 stran, 4 sloupce pod mřížkou.
"""
import argparse, os, re, random, unicodedata
from datetime import datetime
from typing import List, Tuple, Dict

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ---- Fonty ----
TITLE_FONT = "DejaVuSans-Bold"
TEXT_FONT  = "DejaVuSans"
MONO_FONT  = "DejaVuSansMono"
_fallback  = False
def _try_register_triplet(regular, bold, mono):
    pdfmetrics.registerFont(TTFont(TEXT_FONT,  regular))
    pdfmetrics.registerFont(TTFont(TITLE_FONT, bold))
    pdfmetrics.registerFont(TTFont(MONO_FONT,  mono))
def _register_fonts():
    global TITLE_FONT, TEXT_FONT, MONO_FONT, _fallback
    BASE = os.path.dirname(__file__)
    candidates = [
        (os.path.join(BASE, "DejaVuSans.ttf"),
         os.path.join(BASE, "DejaVuSans-Bold.ttf"),
         os.path.join(BASE, "DejaVuSansMono.ttf")),
        (r"C:\Windows\Fonts\arial.ttf",
         r"C:\Windows\Fonts\arialbd.ttf",
         r"C:\Windows\Fonts\consola.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
    ]
    for reg, bold, mono in candidates:
        try:
            if os.path.isfile(reg) and os.path.isfile(bold) and os.path.isfile(mono):
                _try_register_triplet(reg, bold, mono)
                return
        except Exception:
            pass
    TITLE_FONT, TEXT_FONT, MONO_FONT = "Helvetica-Bold", "Helvetica", "Courier"
    _fallback = True
_register_fonts()

# ---- Barvy ----
DARK_GREEN = colors.HexColor("#0F5132")
GRID_FILL  = colors.HexColor("#F0FBF6")

ALPHABETS: Dict[str,str] = {
    "CZ (s diakritikou)": "AÁBCČDĎEÉĚFGHIÍJKLĽMNŇOÓPQRŘSŠTŤUÚŮVWXYÝZŽ",
    "A-Z (bez diakritiky)": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
}
DIRECTIONS: List[Tuple[int,int,str]] = [
    (1,0,"E"), (0,1,"S"), (1,1,"SE"), (-1,1,"SW"),
    (-1,0,"W"), (0,-1,"N"), (-1,-1,"NW"), (1,-1,"NE"),
]
def remove_diacritics(s:str)->str:
    return ''.join(c for c in unicodedata.normalize("NFD",s) if unicodedata.category(c)!="Mn")

def pick_allowed(diagonals=True, backwards=True):
    forward={"E","S","SE","SW"}
    allowed=[d for d in DIRECTIONS if diagonals or d[0]==0 or d[1]==0]
    return allowed if backwards else [d for d in allowed if d[2] in forward]

def make_empty(n): return [[None for _ in range(n)] for __ in range(n)]
def can_place(grid,x,y,dx,dy,word):
    n=len(grid)
    for i,ch in enumerate(word):
        cx,cy=x+dx*i,y+dy*i
        if cx<0 or cy<0 or cx>=n or cy>=n: return False
        cell=grid[cy][cx]
        if cell is not None and cell!=ch: return False
    return True
def place_word(grid,x,y,dx,dy,word):
    for i,ch in enumerate(word): grid[y+dy*i][x+dx*i]=ch
def fill_random(grid,alphabet:str):
    n=len(grid)
    for y in range(n):
        for x in range(n):
            if grid[y][x] is None: grid[y][x]=random.choice(alphabet)
def parse_words_from_text(text,strip=False)->List[str]:
    parts=re.split(r"[,\n;]+",text); words=[]
    for w in parts:
        w=w.strip()
        if not w: continue
        w_up=w.upper()
        if strip: w_up=remove_diacritics(w_up)
        w_up=''.join(w_up.split())
        words.append(w_up)
    return sorted(set(words))
def read_words_file(path,strip=False)->List[str]:
    with open(path,"r",encoding="utf-8") as f: return parse_words_from_text(f.read(),strip=strip)
def read_tajenky_file(path:str)->List[str]:
    with open(path,"r",encoding="utf-8") as f: txt=f.read()
    parts=re.split(r"[,\n;]+",txt)
    return [p.strip() for p in parts if p.strip()]
def normalize_tajenka(s:str)->str:
    return ''.join(ch for ch in s.strip().upper() if not ch.isspace())
def fill_with_tajenka(grid,alphabet:str,tajenka:str):
    letters_random=''.join(sorted(set([ch for ch in remove_diacritics(alphabet).upper() if 'A'<=ch<='Z'])))
    empties=[(y,x) for y,row in enumerate(grid) for x,val in enumerate(row) if val is None]
    for i,(y,x) in enumerate(empties):
        grid[y][x]=tajenka[i] if i<len(tajenka) else random.choice(letters_random)
def greedy_place(words:List[str],n:int,diagonals:bool,backwards:bool,alphabet_key:str,tajenka_len:int=0):
    grid=make_empty(n); allowed=pick_allowed(diagonals,backwards)
    words_pool=words[:]; words_pool.sort(key=len,reverse=True); random.shuffle(words_pool)
    placed=[];
    for w in words_pool:
        if len(w)>n: continue
        for _ in range(1000):
            dx,dy,_=random.choice(allowed)
            max_x=n-1 if dx<=0 else n-len(w); min_x=0 if dx>=0 else len(w)-1
            max_y=n-1 if dy<=0 else n-len(w); min_y=0 if dy>=0 else len(w)-1
            x,y=random.randint(min_x,max_x),random.randint(min_y,max_y)
            if can_place(grid,x,y,dx,dy,w):
                new_cells=sum(1 for i in range(len(w)) if grid[y+dy*i][x+dx*i] is None)
                empties=sum(1 for row in grid for cell in row if cell is None)
                if tajenka_len and (empties-new_cells)<tajenka_len: continue
                place_word(grid,x,y,dx,dy,w); placed.append(w); break
    return grid,placed

# ---- Vykreslení ----
def draw_grid(c,grid,origin_x,origin_y,cell_mm=8):
    n=len(grid); cell=cell_mm*mm
    c.setFillColor(GRID_FILL)
    c.rect(origin_x,origin_y,n*cell,n*cell,stroke=0,fill=1)
    c.setFillColor(DARK_GREEN); c.setStrokeColor(DARK_GREEN); c.setLineWidth(1)
    c.rect(origin_x,origin_y,n*cell,n*cell,stroke=1,fill=0)
    for y in range(n):
        for x in range(n):
            x0=origin_x+x*cell; y0=origin_y+(n-1-y)*cell
            c.rect(x0,y0,cell,cell,stroke=1,fill=0)
            ch=grid[y][x]; c.setFont(MONO_FONT,max(8,int(cell_mm*1.8)))
            tw=pdfmetrics.stringWidth(ch,MONO_FONT,max(8,int(cell_mm*1.8)))
            c.setFillColor(DARK_GREEN); c.drawString(x0+(cell-tw)/2,y0+cell*0.25,ch)
def draw_word_list_below(c,words:List[str],page_left,page_right,below_y,cols=4,title="Seznam slov:"):
    c.setFont(TITLE_FONT,12); c.setFillColor(DARK_GREEN); c.drawString(page_left,below_y,title)
    c.setFont(TEXT_FONT,11); y=below_y-5*mm
    ordered=sorted(words); col_gap=10*mm; max_width=page_right-page_left
    col_width=(max_width-(cols-1)*col_gap)/cols; buckets=[[] for _ in range(cols)]
    for i,w in enumerate(ordered): buckets[i%cols].append(w)
    for ci,col in enumerate(buckets):
        x=page_left+ci*(col_width+col_gap); yy=y
        for w in col: c.drawString(x,yy,w); yy-=6*mm
def page(c,title,subtitle,grid,placed,cell_mm,columns,tajenka=None,show_tajenka=False):
    W,H=A4; left=20*mm; right=W-20*mm; top=H-25*mm
    c.setFillColor(DARK_GREEN); c.setFont(TITLE_FONT,18); c.drawString(left,top,title)
    sub=subtitle+ (f" | Tajenka: {tajenka}" if show_tajenka and tajenka else "")
    c.setFont(TEXT_FONT,11); c.drawString(left,top-6*mm,sub)
    n=len(grid); cell=cell_mm*mm; grid_w=n*cell; ox=(W-grid_w)/2; oy=top-20*mm-n*cell
    if oy<40*mm: oy=40*mm
    draw_grid(c,grid,ox,oy,cell_mm); below_y=oy-10*mm;
    if below_y<28*mm: below_y=28*mm
    draw_word_list_below(c,placed,left,right,below_y,cols=columns)
    c.setFont(TEXT_FONT,9); c.setFillColor(DARK_GREEN)
    c.drawString(left,12*mm,datetime.now().strftime("Miluju Tě. Okami :cxx!")); c.showPage()
def save_pdf(filename,title,subtitle,words,cell_mm,pages,size,diagonals,backwards,alphabet_key,columns,tajenka=None,show_tajenka=False):
    c=canvas.Canvas(filename,pagesize=A4)
    for _ in range(max(1,pages)):
        taj_len=len(tajenka) if tajenka else 0
        grid,placed=greedy_place(words,size,diagonals,backwards,alphabet_key,tajenka_len=taj_len)
        letters=ALPHABETS.get(alphabet_key,ALPHABETS["CZ (s diakritikou)"])
        if taj_len: fill_with_tajenka(grid,letters,tajenka)
        else:
            letters_random=''.join(sorted(set([ch for ch in remove_diacritics(letters).upper() if 'A'<=ch<='Z'])))
            fill_random(grid,letters_random)
        page(c,title,subtitle,grid,placed,cell_mm,columns,tajenka,show_tajenka)
    c.save()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--words",help="Soubor se slovy (default words.txt).")
    ap.add_argument("-s","--size",type=int,default=15)
    ap.add_argument("-c","--cell",type=int,default=8)
    ap.add_argument("--no-diagonals",action="store_true")
    ap.add_argument("--no-backwards",action="store_true")
    ap.add_argument("--alphabet",default="CZ (s diakritikou)",choices=list(ALPHABETS.keys()))
    ap.add_argument("--strip",action="store_true")
    ap.add_argument("--title",default="Osmisměrka")
    ap.add_argument("--subtitle",default="Najdi všechna slova.")
    ap.add_argument("--pages",type=int,default=10)
    ap.add_argument("--columns",type=int,default=4)
    ap.add_argument("--tajenky",help="Soubor s tajenkami (default tajenky.csv pokud existuje).")
    ap.add_argument("--tajenka-index",type=int)
    ap.add_argument("--show-tajenka",action="store_true")
    ap.add_argument("-o","--output",default="osmismerky.pdf")
    args=ap.parse_args()
    if args.words: word_file=args.words.split(",")[0].strip()
    else: word_file="words.txt"
    if not os.path.isfile(word_file): raise SystemExit(f"Soubor {word_file} nenalezen.")
    words=read_words_file(word_file,strip=args.strip)
    diagonals=not args.no_diagonals; backwards=not args.no_backwards
    tajenka=None; taj_file=args.tajenky if args.tajenky else ("tajenky.csv" if os.path.isfile("tajenky.csv") else None)
    if taj_file and os.path.isfile(taj_file):
        phrases=read_tajenky_file(taj_file)
        if phrases:
            idx=args.tajenka_index if args.tajenka_index is not None else random.randrange(len(phrases))
            idx=max(0,min(idx,len(phrases)-1))
            tajenka=normalize_tajenka(phrases[idx])
    save_pdf(args.output,args.title,args.subtitle,words,args.cell,args.pages,args.size,diagonals,backwards,args.alphabet,args.columns,tajenka,args.show_tajenka)
    if _fallback: print("Upozornění: fallback fonty (diakritika nemusí být 100%).")
    print(f"Hotovo -> {args.output} (slova: {word_file}"+(f", tajenka: {tajenka}" if tajenka else "")+")")

if __name__=="__main__": main()
