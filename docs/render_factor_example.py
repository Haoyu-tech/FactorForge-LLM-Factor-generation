"""Render a saved factor result: python render_factor_example.py INPUT_JSON.

Input requires factor.factor_name, id, split and result (saved split analytics).
Only the rendered image is published; local research records remain private.
"""
import json
import sys
from pathlib import Path
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from matplotlib.patches import FancyBboxPatch

d = json.loads(Path(sys.argv[1]).read_text())
r = d['result']
m = r['metrics']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                     'axes.spines.right':False,'axes.edgecolor':'#d3e1df','text.color':'#132f38',
                     'axes.labelcolor':'#536d77','xtick.color':'#536d77','ytick.color':'#536d77'})
fig = plt.figure(figsize=(16,10),facecolor='#f3f8f6')
fig.text(.05,.947,'FactorForge',size=24,weight='bold')
fig.text(.95,.951,'FACTOR RESEARCH  /  SAVED RESULTS',size=10,ha='right',color='#0f766e')
fig.text(.05,.895,'Cash Flow Quality & Growth Stability',size=23,weight='bold')
fig.text(.05,.858,f"US equities / S&P 500   |   {d['split'].upper()} SET: {r['startDate']} to {r['endDate']}   |   Monthly rebalancing",size=11,color='#536d77')

cards=[('RANK IC',f"{m['Rank IC']:.4f}"),('RANK ICIR',f"{m['Rank ICIR']:.4f}"),
       ('LONG-SHORT NET RETURN / YR',f"{m['month.long_short.annualized_net_return']:.2%}"),
       ('LONG-SHORT SHARPE',f"{m['month.long_short.sharpe_ratio']:.2f}")]
for i,(label,value) in enumerate(cards):
 x=.05+i*.228
 fig.add_artist(FancyBboxPatch((x,.735),.213,.089,boxstyle='round,pad=0.008',transform=fig.transFigure,
                              facecolor='white',edgecolor='#dce7e4',zorder=0))
 fig.text(x+.012,.794,label,size=9,color='#536d77')
 fig.text(x+.012,.756,value,size=21,weight='bold',color='#0f766e')

colors=['#b66c57','#cf8b57','#d6ad56','#9caf62','#74aa7c','#48a695','#249ca6','#2786b5','#546fc2','#7757b9']
ax=fig.add_axes([.075,.32,.87,.33],facecolor='white')
for i in range(1,11):
 rows=r['decileCurves']['month'][f'group_{i}']
 ax.plot([datetime.fromisoformat(p['date']) for p in rows],[p['value'] for p in rows],
         color=colors[i-1],lw=1.5 if i not in (1,10) else 2.1,label=f'D{i}')
ax.set_title('Decile cumulative returns',loc='left',pad=17,weight='bold',fontsize=14)
ax.yaxis.set_major_formatter(PercentFormatter(1))
ax.grid(alpha=.17)
ax.set_axisbelow(True)
ax.legend(ncol=10,loc='upper center',bbox_to_anchor=(.5,-.11),frameon=False,fontsize=9)

bar=fig.add_axes([.075,.095,.52,.13],facecolor='white')
bar.bar(range(1,11),[m[f'month.group_{i}.annualized_net_return'] for i in range(1,11)],color=colors,width=.65)
bar.set_xticks(range(1,11),[f'D{i}' for i in range(1,11)])
bar.yaxis.set_major_formatter(PercentFormatter(1,decimals=0))
bar.set_title('Annualized net return by decile',loc='left',fontsize=12,weight='bold',pad=12)
bar.grid(axis='y',alpha=.17)
bar.set_axisbelow(True)
fig.text(.655,.225,'PORTFOLIO DIAGNOSTICS',size=10,weight='bold',color='#0f766e')
for j,(label,value) in enumerate([
 ('Long-short maximum drawdown',f"{m['month.long_short.max_drawdown']:.2%}"),
 ('Decile monotonicity',f"{m['month.decile_monotonicity']:.3f}"),
 ('Monthly rebalance count',f"{m['month.long.rebalance_count']:.0f}")]):
 y=.187-j*.037
 fig.text(.655,y,label,size=10,color='#536d77')
 fig.text(.95,y,value,size=12,weight='bold',ha='right')
fig.text(.05,.035,f"Saved factor: {d['factor']['factor_name']}  |  ID: {d['id']}",size=8,color='#536d77')
fig.text(.05,.016,'Illustrative saved research result, not a live performance record. Curves use the stored sampled points; metrics use the saved evaluation.',size=8,color='#536d77')
out=Path(__file__).parent/'assets'/'factor-results-example.png'
fig.savefig(out,dpi=180,facecolor=fig.get_facecolor())
print(out)
