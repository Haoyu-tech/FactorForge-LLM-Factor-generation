"""Render explanation and saved risk diagnostics for the README example."""
import json
import sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

d=json.loads(Path(sys.argv[1]).read_text())
m=d['result']['metrics']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'text.color':'#132f38',
 'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#d3e1df',
 'xtick.color':'#536d77','ytick.color':'#536d77'})
fig=plt.figure(figsize=(16,11),facecolor='#f3f8f6')
fig.text(.05,.95,'FactorForge | Signal interpretation',fontsize=24,weight='bold')
fig.text(.05,.91,'Saved US equity example  /  Test set: 2015–2025  /  Monthly rebalancing',color='#536d77')
sections=[
 ('01  WHAT THE FORMULA MEASURES',
  'Cross-sectional rank of the 252-observation mean of Sales / Assets, divided by its\n'
  '252-observation standard deviation. Higher values favor stable, high asset turnover.\n'
  'The Assets / Assets term equals 1 only where assets are finite and nonzero.'),
 ('02  ECONOMIC INTERPRETATION',
  'A possible operating-efficiency signal: firms producing relatively steady revenue\n'
  'per unit of assets may rank higher. This is a hypothesis, not evidence of causality.\n'
  'The formula does not explicitly measure operating cash flow or sales growth.'),
 ('03  HOW TO READ THE RESULTS',
  'RankIC is positive but small (0.0079). Decile monotonicity is 0.794; the long-short\n'
  'net return is 1.65% per year with a Sharpe of 0.46. Long-only returns also include\n'
  'market exposure and should not be interpreted as pure factor alpha.'),
]
for i,(title,body) in enumerate(sections):
 y=.70-i*.17
 fig.add_artist(FancyBboxPatch((.05,y),.90,.135,boxstyle='round,pad=0.012',
   transform=fig.transFigure,facecolor='white',edgecolor='#dce7e4',zorder=0))
 fig.text(.067,y+.099,title,color='#0f766e',fontsize=11,weight='bold')
 fig.text(.067,y+.021,body,fontsize=11,linespacing=1.6)

ax=fig.add_axes([.085,.12,.40,.16],facecolor='white')
keys=['mktrf','smb','hml','rmw','cma']
betas=[m[f'month.asset_pricing.ff5.beta_{k}'] for k in keys]
ax.barh(['Market','Size (SMB)','Value (HML)','Profitability (RMW)','Investment (CMA)'],betas,color=['#0f766e' if b>=0 else '#b66c57' for b in betas])
ax.axvline(0,color='#9cadaa',lw=1)
ax.set_title('Saved FF5 regression loadings',loc='left',fontsize=12,weight='bold',pad=12)
ax.set_xlabel('Regression coefficient (long-short portfolio)',fontsize=9)
ax.tick_params(axis='y',labelsize=9)
ax.grid(axis='x',alpha=.15)
fig.text(.57,.29,'ALPHA & INTERPRETATION CHECK',color='#0f766e',weight='bold')
fig.text(.57,.25,f"FF5 annualized alpha: {m['month.asset_pricing.ff5.alpha_annualized']:.2%}",fontsize=13)
fig.text(.57,.215,f"t-statistic: {m['month.asset_pricing.ff5.alpha_t_stat']:.2f}   |   p-value: {m['month.asset_pricing.ff5.alpha_p_value']:.3f}")
fig.text(.57,.18,'Not significant at the conventional 5% level.',fontsize=10,color='#936346')
fig.text(.57,.125,'Audit note: the saved name / LLM description refers to\ncash flow and growth; the expression does not.\nInterpretation above follows the stored expression.',fontsize=10,linespacing=1.5)
fig.text(.05,.035,'Saved research diagnostics; not live trading performance. Verify point-in-time fundamentals and return assumptions before use.',fontsize=9,color='#536d77')
out=Path(__file__).parent/'assets'/'factor-interpretation-example.png'
fig.savefig(out,dpi=180,facecolor=fig.get_facecolor())
print(out)
