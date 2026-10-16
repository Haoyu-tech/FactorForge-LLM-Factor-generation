"""Render the English FactorForge README overview (Pillow, no market data)."""
from pathlib import Path
import os
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / 'assets' / 'factorforge-overview.png'
S = 2
im = Image.new('RGB', (1800*S, 1170*S), '#071b24')
d = ImageDraw.Draw(im)
fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
def font(size, bold=False):
    name = fonts / ('segoeuib.ttf' if bold else 'segoeui.ttf')
    fallback = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    return ImageFont.truetype(str(name) if name.exists() else fallback, size*S)
def box(rect, fill, outline=None, radius=18):
    d.rounded_rectangle(tuple(int(v*S) for v in rect), radius=radius*S, fill=fill, outline=outline, width=S)
def text(x,y,value,size=22,color='#bfd0d5',bold=False):
    d.text((x*S,y*S),value,font=font(size,bold),fill=color)
def line(coords,fill='#29414a',width=1):
    d.line([int(v*S) for v in coords],fill=fill,width=width*S)

for x in range(0,1800,60): line((x,0,x,1170),'#0b222b')
for y in range(0,1170,60): line((0,y,1800,y),'#0b222b')

box((64,52,116,104),'#a7f3d0',radius=14)
text(79,54,'F',34,'#071b24',True)
text(132,52,'FactorForge',34,'#f0f7f5',True)
text(135,94,'QUANTITATIVE RESEARCH WORKSPACE',13,'#8ba9ac',True)
box((1354,60,1736,101),'#102f37','#29474e',radius=20)
text(1378,69,'LLM-POWERED  /  MULTI-MARKET',16,'#a7f3d0',True)

text(64,151,'Turn market intuition',66,'#f0f7f5',True)
text(64,230,'into testable factors.',66,'#a7f3d0',True)
text(68,325,'One workflow for hypothesis generation, factor evaluation and out-of-sample backtesting.',24)

markets=[('01','US EQUITIES','Historical S&P 500','WRDS / CRSP / Compustat','GICS + Fama–French'),
         ('02','CHINA A-SHARES','CSI 300 / CSI 500 / SME Composite','Daily prices + financial statements','Shenwan + Barra-style diagnostics'),
         ('03','CRYPTO PERPETUALS','Binance USDT-margined contracts','Daily market + trading-activity data','Funding + liquidity diagnostics')]
for i,(num,title,universe,data,diag) in enumerate(markets):
    x=64+i*564
    box((x,397,x+544,593),'#0f2932','#29434a')
    text(x+24,416,num,17,'#5f8e8e',True)
    text(x+65,414,title,21,'#a7f3d0',True)
    text(x+24,458,universe,23,'#f0f7f5',True)
    text(x+24,507,data,18)
    text(x+24,542,diag,18,'#8fb0b4')

box((64,629,1736,1100),'#f2f6f3',radius=24)
text(96,655,'FROM IDEA TO EVIDENCE',16,'#0f766e',True)
text(96,686,'A connected research lifecycle',32,'#102a32',True)
text(1295,693,'Research • Library • Backtest',18,'#597179')

stages=[('1','Hypothesize','Describe a research goal','Generate factor expressions'),
        ('2','Evaluate','Calculate factor signals','Review validation evidence'),
        ('3','Curate','Save factors and explanations','Filter correlated signals'),
        ('4','Backtest','Fit expanding-window models','Evaluate out-of-sample results')]
for i,(n,title,a,b) in enumerate(stages):
    x=96+i*409
    box((x,751,x+381,906),'#ffffff','#d9e4df',14)
    box((x+20,773,x+51,804),'#e3f2eb',radius=9)
    text(x+29,775,n,18,'#0f766e',True)
    text(x+65,772,title,24,'#102a32',True)
    text(x+20,822,a,18,'#597179')
    text(x+20,853,b,18,'#597179')
    if i<3:
        line((x+387,826,x+403,826),'#0f766e',2)
        line((x+397,820,x+403,826,x+397,832),'#0f766e',2)

line((96,937,1704,937),'#d5e1dc')
for x,title,body in [(96,'MODELS','LightGBM · PLS5 · Lasso'),
                     (650,'EVALUATION','RankIC · Portfolios · Exposures'),
                     (1204,'WORKSPACE','Chinese / English · Saved analytics')]:
    text(x,960,title,14,'#0f766e',True)
    text(x,990,body,21,'#102a32',True)
text(96,1048,'Train → Validate → Test   |   Validation-guided selection. Independent test-set reporting.',18,'#597179')
text(64,1124,'FACTORFORGE  /  OPEN RESEARCH TOOLING',14,'#8ba9ac',True)
text(1210,1124,'Platform overview • No performance results shown',15,'#8ba9ac')
OUT.parent.mkdir(parents=True,exist_ok=True)
im.save(OUT, optimize=True)
print(OUT)
