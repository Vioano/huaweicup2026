"""Original paper style. Fonts are loaded from the existing contest template."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt, font_manager as fm

PAPER=Path(__file__).resolve().parents[1]
FONTDIR=PAPER.parent/'template-2026'/'fonts'
for name in ('SimSun.ttf','Times.TTF','Timesbd.TTF','Timesi.TTF'):
    if (FONTDIR/name).exists(): fm.fontManager.addfont(FONTDIR/name)
C={'ink':'#243244','M':'#416A93','V':'#8877A8','in':'#2D918A','out':'#C9874D',
   'gray':'#A6ADB5','pale':'#E7EBEF','white':'#FFFFFF'}
PIPE={'PIPE_M':C['M'],'PIPE_V':C['V'],'PIPE_MTE2':C['in'],'PIPE_MTE3':C['out']}
plt.rcParams.update({'font.family':['Times New Roman','SimSun','DejaVu Serif'],
    'font.size':12,'axes.labelsize':12,'axes.titlesize':12,'xtick.labelsize':12,'ytick.labelsize':12,
    'legend.fontsize':12,'text.color':C['ink'],'axes.labelcolor':C['ink'],
    'axes.edgecolor':C['gray'],'xtick.color':C['ink'],'ytick.color':C['ink'],
    'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.6,
    'axes.unicode_minus':False,'pdf.fonttype':42,'ps.fonttype':42,
    'svg.fonttype':'none','savefig.facecolor':'white','figure.facecolor':'white',
    'mathtext.fontset':'stix','lines.linewidth':1.6,'grid.color':C['pale'],
    'grid.linewidth':.6,'legend.frameon':False})

def save(fig,name,outdir=None):
    outdir=outdir or PAPER/'figures';outdir.mkdir(parents=True,exist_ok=True)
    # Fixed physical canvas: never tight-crop and subsequently scale the font.
    for ext in ('pdf','svg','png'):
        kwargs={'dpi':180} if ext=='png' else {}
        if ext=='pdf': kwargs['metadata']={'Creator':'Deterministic paper figure script','Author':'','CreationDate':None}
        if ext=='svg': kwargs['metadata']={'Date':None}
        fig.savefig(outdir/(name+'.'+ext),**kwargs)
    plt.close(fig)

def clean(ax,xlabel=None,ylabel=None):
    ax.grid(axis='y',zorder=0)
    if xlabel: ax.set_xlabel(xlabel)
    if ylabel: ax.set_ylabel(ylabel)

