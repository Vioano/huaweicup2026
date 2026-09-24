"""Two-page strategy assessment; all scores are judgments, not experiment results.

Figure style adapted from ChenLiu-1996/figures4papers, CC BY-NC 4.0:
https://creativecommons.org/licenses/by-nc/4.0/
Changes: Chinese A4 report, annotated matrix, score and sensitivity panels.
Run with the repository's locked matplotlib/numpy environment.
"""
from pathlib import Path
import argparse, csv, hashlib, json, platform, subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/pdf'
RES = ROOT / 'results/selection'
FIG = ROOT / 'figures/selection'
for d in [OUT, RES, FIG]: d.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({'font.family': ['Arial Unicode MS', 'DejaVu Sans'], 'font.size': 9,
    'axes.spines.top': False, 'axes.spines.right': False, 'axes.linewidth': .65,
    'pdf.fonttype': 42, 'svg.fonttype': 'none', 'axes.unicode_minus': False})
BLUE='#0F4D92'; GREEN='#42949E'; INK='#202D3B'; GRAY='#687583'; LIGHT='#EAF0F5'; RED='#B64342'
weights=np.array([.30,.30,.15,.15,.10])
ids=['A','B','C','D','E','F']
names=['多核调度','燃料电池冷启动','脑电认知模型','无人机协同调度','多模态情感预测','大模型资源配置']
scores=np.array([[2.5,2,4,3,3.5],[1.5,2,2.5,2,3],[1.5,2,1.5,1.5,3.5],
                 [2,2,3.5,2.5,3.5],[2,2,3,2.5,2.5],[2,2,2.5,2.5,3]])
totals=25*scores@weights
# Judgment ranges; H is unknown for every problem and must not rank the center case.
low=np.array([[1.5,0,3,1.5,2.5],[.5,0,1.5,1,2],[.5,0,.5,.5,2],
              [1,0,2.5,1.5,2.5],[1,0,2,1.5,1.5],[1,0,1.5,1.5,2]])
high=np.array([[3,4,4,3.5,4],[2.5,4,3.5,3,4],[2.5,4,2.5,2.5,4],
               [3,4,4,3.5,4],[3,4,4,3.5,3.5],[3,4,3.5,3.5,4]])
reasons=[
 '提供问题1/2/3评估器及100个图；目标和反馈闭合。专业编译/运筹队同样可用这些工具。',
 '一维水热相变模型→五片电堆→优化控制。参数辨识与物理一致性构成串行瓶颈。',
 '去噪→视觉刺激机制→认知模型；仅F3/Fz/F4三路原始EEG。机理可识别性难于拟合。',
 '组批→多点运输→连续通信→固定方案分区。15服务区、80货箱；时空约束验证需自建。',
 '100条原视频特征、4850条预提取样本；局部缺失与解释须验证。通用模型优势较难独占。',
 '质量评价→标度律→约束优化→能力前沿。跨源映射、半合成Q与因果归因增加论证成本。']
with (RES/'scores.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['problem','name','A','H_placeholder','V','F','C','comparison_score','basis'])
 for i in range(6):w.writerow([ids[i],names[i],*scores[i],totals[i],reasons[i]])
with (RES/'score_ranges.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['problem','dimension','center','low','high','evidence'])
 for i in range(6):
  for j,d in enumerate(['A','H','V','F','C']):w.writerow([ids[i],d,scores[i,j],low[i,j],high[i,j],'U: center is placeholder' if d=='H' else 'H: judgment based on supplied materials; no solver validation'])

# Explicit stress tests, not assigned probabilities. Only A is stressed against D.
scenarios={'中心判断':scores.copy(),'A专业强队更集中':scores.copy(),
           'A的AI/集成优势落空':scores.copy(),'A验证与计算成本升高':scores.copy()}
scenarios['A专业强队更集中'][0,1]=.5
scenarios['A的AI/集成优势落空'][0,[0,3]]=[1.5,2]
scenarios['A验证与计算成本升高'][0,[2,3]]=[3,1.5]
scenarios['组合不利情景']=scenarios['A验证与计算成本升高'].copy()
scenarios['组合不利情景'][0,[0,1]]=[1.5,.5]
with (RES/'scenarios.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['scenario','problem','A','H','V','F','C','comparison_score'])
 for s,m in scenarios.items():
  for i in range(6):w.writerow([s,ids[i],*m[i],25*m[i]@weights])

# Enumerate vertices of the normalized +/- 5 percentage-point weight box.
import itertools
vertices=[]
for free in range(5):
 for bits in itertools.product([-1,1],repeat=4):
  v=weights.copy();fixed=[i for i in range(5) if i!=free]
  v[fixed]=weights[fixed]+.05*np.array(bits);v[free]=1-v[fixed].sum()
  if weights[free]-.05-1e-9<=v[free]<=weights[free]+.05+1e-9:vertices.append(v)
gaps={s:[float(min(25*(m[0]-m[3])@v for v in vertices)),float(max(25*(m[0]-m[3])@v for v in vertices))] for s,m in scenarios.items()}
(RES/'weight_sensitivity.json').write_text(json.dumps({'weight_box':'+/-0.05 absolute; sum=1','A_minus_D':gaps},ensure_ascii=False,indent=2))

def text(fig,x,y,s,size=10,color=INK,weight='normal',**kw):
 return fig.text(x,y,s,fontsize=size,color=color,fontweight=weight,va='top',**kw)
def line(fig,y):fig.add_artist(plt.Line2D([.065,.935],[y,y],transform=fig.transFigure,color='#D8E0E8',lw=.6))
def paragraph(fig,x,y,s,width=48,size=9.5,color=INK,leading=1.5):
 # Match Chinese and Latin widths without changing words in the stored input.
 result=[];buf='';units=0
 for ch in s:
  u=1 if ord(ch)>255 else .53
  if ch=='\n' or units+u>width:
   result.append(buf);buf='';units=0
   if ch=='\n':continue
  buf+=ch;units+=u
 if buf:result.append(buf)
 for k,sline in enumerate(result):text(fig,x,y-k*size*leading/841.89,sline,size,color)
 return y-len(result)*size*leading/841.89
def page(n,kicker,title):
 f=plt.figure(figsize=(8.2677,11.6929),facecolor='white')
 text(f,.065,.963,'HUAWEI CUP 2026  /  选题决策',8,GRAY)
 text(f,.935,.963,'2026.09.22',8,GRAY,ha='right')
 text(f,.065,.921,kicker,9,BLUE)
 text(f,.065,.893,title,23,BLUE,weight='bold')
 line(f,.054);text(f,.065,.038,'策略评估 · 基于所供材料 · 未运行求解实验 · 不代表入围概率',7,GRAY)
 text(f,.935,.038,f'{n} / 2',8,GRAY,ha='right')
 return f

f1=page(1,'决策 / 首选 A，备选 D','选 A：多核调度')
paragraph(f1,.065,.844,'通用神经网络处理器下的多核调度问题',width=48,size=13)
paragraph(f1,.065,.807,'按策略的“争取同题头部、提高数模之星入围机会”目标，A最值得优先投入。结论依赖本队能审查调度语义、整合算法的能力假设；当前未证明对专业强队的实际领先。',width=53,size=10)
line(f1,.741)
text(f1,.065,.719,'01  五维比较：A的优势集中在验证闭环与交付结构',12,INK,weight='bold')
text(f1,.065,.687,'0–4分，越高越有利；权重沿用策略§6.2。全部为材料支持的分析评分。',8.5,GRAY)

ax=f1.add_axes([.275,.398,.405,.235])
cmap=LinearSegmentedColormap.from_list('score',['#F3F6F9','#CCDDEE','#0F4D92'])
ax.imshow(scores,vmin=0,vmax=4,cmap=cmap,aspect='auto')
ax.set_xticks(range(5),['相对优势\n30%','头部竞争\n30%','可验证性\n15%','交付可行\n15%','差异化\n10%'],fontsize=8)
ax.xaxis.tick_top();ax.tick_params(axis='both',length=0,pad=9)
ax.set_yticks(range(6),[f'{a}  {b}' for a,b in zip(ids,names)],fontsize=9)
for sp in ax.spines.values():sp.set_visible(False)
for i in range(6):
 for j in range(5):
  if j==1:
   ax.add_patch(Rectangle((j-.5,i-.5),1,1,facecolor='#EFF1F3',edgecolor='#C8CDD2',hatch='///',lw=.5))
   ax.text(j,i,'未知',ha='center',va='center',fontsize=9,color=GRAY,bbox={'facecolor':'#EFF1F3','pad':1,'edgecolor':'none'})
  else:ax.text(j,i,f'{scores[i,j]:g}',ha='center',va='center',fontsize=10,color='white' if scores[i,j]>=3 else INK)
 ax.axhline(i+.5,color='white',lw=2)
for j in range(6):ax.axvline(j-.5,color='white',lw=2)
ax.add_patch(Rectangle((-.5,-.5),5,1,fill=False,edgecolor=BLUE,lw=1.8,clip_on=False))
ar=f1.add_axes([.727,.398,.191,.235])
ar.barh(range(6),totals,color=[BLUE,'#C7CFD7','#C7CFD7',GREEN,'#C7CFD7','#C7CFD7'],height=.61)
ar.set_ylim(5.5,-.5);ar.set_xlim(0,100);ar.set_yticks([]);ar.set_xticks([0,50,100]);ar.tick_params(axis='x',labelsize=7,length=2)
ar.set_title('比较分 / 100',fontsize=9,pad=31,color=INK)
for i,v in enumerate(totals):ar.text(v+2,i,f'{v:.1f}',va='center',fontsize=9,color=BLUE if i==0 else INK)
ar.spines['left'].set_visible(False)
paragraph(f1,.065,.360,'头部竞争H没有可靠人数或强队数据：各题统一以2分占位，可能范围0–4；不凭“冷门”加分。比较分 = 25 × Σ(权重 × 评分)。H每变动1分，总分改变7.5分。',width=56,size=8.5,color=GRAY)
text(f1,.065,.292,'02  为什么把A排在前面',12,INK,weight='bold')
items=[('统一反馈入口','题目提供三问评估器、固定配置及100个计算图，可围绕同一目标比较方案。[A]'),
 ('难点能落到工程模块','切图、分核、核内顺序、带宽与缓存彼此耦合；本队假定的数学审查与工程整合能力有明确作用点。'),
 ('有可检验的差异化','从通信感知切分到带宽/缓存感知联合调度，改进可用耗时、搬运量及消融论证；不是堆算法名称。')]
for y,(a,b) in zip([.255,.195,.135],items):
 text(f1,.065,y,a,10,BLUE,weight='bold');paragraph(f1,.285,y,b,width=42,size=9)

f2=page(2,'证据 / 边界 / 决策翻转','为何不是另外五题？')
text(f2,.065,.842,'各题都有研究空间；以下比较的是本队冲前列的主要障碍。',9.5,GRAY)
rows=[('D / 备选','最接近A的工程优化题。15服务区、80货箱，运输、电池与连续通信耦合；需自行建立统一验证器。[D]'),
 ('E / 次选','有预提取特征，降低计算门槛；但局部缺失鲁棒性、忠实解释和≤50MB交付均须兼顾，通用AI工具较难形成独占优势。[E]'),
 ('F / 次选','无需大规模训练；瓶颈在跨源质量映射、半合成数据边界及规模/技术贡献分离。能拟合不等于已解释因果。[F]'),
 ('B / 暂不选','一维水热相变→五片电堆→动态控制递进依赖。缺少已验证的电化学能力时，模型校准与物理审查不易靠代码生成压缩。[B]'),
 ('C / 暂不选','三路原始EEG须支撑去噪、刺激机制和认知模型。机理辨识与伪影保真验证更难；背景中的诊断应用不能当作已验证成果。[C]')]
for y,(a,b) in zip([.800,.742,.684,.626,.568],rows):
 text(f2,.065,y,a,10,GREEN if a.startswith('D') else INK,weight='bold')
 paragraph(f2,.205,y,b,width=46,size=8.8)
line(f2,.509)
text(f2,.065,.489,'03  何时应把首选改为D？',12,INK,weight='bold')
sa=f2.add_axes([.31,.309,.59,.135])
labels=list(scenarios)[:4]
for k,s in enumerate(labels):
 va=25*scenarios[s][0]@weights;vd=25*scenarios[s][3]@weights
 sa.plot([va,vd],[k,k],color='#B7C4CF',lw=2)
 sa.plot(va,k,'o',color=BLUE,ms=6);sa.plot(vd,k,'s',color=GREEN,ms=5)
 sa.text(va+(1.8 if va>vd else -1.8),k,f'{va:.1f}',ha='left' if va>vd else 'right',va='center',fontsize=8,color=BLUE)
 sa.text(vd+(-1.8 if va>vd else 1.8),k,f'{vd:.1f}',ha='right' if va>vd else 'left',va='center',fontsize=8,color=GREEN)
sa.set_yticks(range(4),labels,fontsize=8);sa.tick_params(axis='y',length=0,pad=10)
sa.set_xlim(0,100);sa.set_ylim(3.5,-.5);sa.set_xticks([0,25,50,75,100]);sa.tick_params(axis='x',labelsize=7)
sa.spines['left'].set_visible(False)
text(f2,.70,.474,'● A 首选    ■ D 备选',8,BLUE)
paragraph(f2,.065,.280,'压力情景仅改变A，D保持不变：依次令H=0.5；相对优势=1.5且交付=2；验证=3且交付=1.5。它们是可推翻推荐的假设，不是发生概率。',width=57,size=8,color=GRAY)
paragraph(f2,.065,.241,'明确翻转线：其余评分固定，若A的头部竞争评分比D低超过1分，D即领先。若A的优势无法转化为可审查改进，也应转D。各权重在原值±5个百分点且总和为1时，中心情景A仍领先6.3–8.8分；情景改变则会翻转。',width=56,size=8.7)
paragraph(f2,.065,.176,'落地取舍：A以可行切分/列表调度起步，再比较通信感知与带宽/缓存感知改进；D以单点可行组批起步，再做运输—中继分解协调。真正继续做题时，由队员独立核验模型、基线和全部硬约束。',width=56,size=8.4)
text(f2,.065,.122,'材料与范围',8,BLUE,weight='bold')
paragraph(f2,.065,.105,'策略§2.2、§6；[A]多核调度题面§1.3–1.5、问题1–3、附录B–D及附件README；[B–E]各题“问题/建模问题”与数据附录；[F]题面问题1–4及《数据说明》p.4、9–13。DOCX以章节定位。已读六题及附件结构，未跑求解、全量数据质量验证或团队能力测试；部分嵌入公式未逐式核验。图表为策略判断。',width=72,size=6.6)

pdf=OUT/'HuaweiCup_Selection_Report.pdf'
with PdfPages(pdf,metadata={'Title':'华为杯2026选题决策报告：首选A，备选D','Author':'团队内部策略评估','Subject':'材料评估；非求解实验；非获奖概率'}) as p:
 for i,f in enumerate([f1,f2],1):
  p.savefig(f)
  f.savefig(FIG/f'report-page-{i}.png',dpi=160)
  f.savefig(FIG/f'report-page-{i}.svg')
  plt.close(f)
parser=argparse.ArgumentParser();parser.add_argument('--source-root',type=Path);parser.add_argument('--strategy',type=Path);args=parser.parse_args()
manifest=[]
if args.source_root:
 for f in sorted(args.source_root.rglob('*')):
  if f.is_file() and not f.name.startswith('._') and (f.suffix=='.docx' or f.name=='数据说明.pdf' or f.name in ['README.md','config.txt'] and 'A题' in str(f)):
   manifest.append({'source':str(f.relative_to(args.source_root)),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
if args.strategy:manifest.append({'source':args.strategy.name,'sha256':hashlib.sha256(args.strategy.read_bytes()).hexdigest()})
(RES/'run.json').write_text(json.dumps({'date':'2026-09-22','kind':'judgment-based strategy assessment; no solver experiments','weights':weights.tolist(),'scores':totals.tolist(),'sources':manifest,'python':platform.python_version(),'matplotlib':matplotlib.__version__,'numpy':np.__version__,'git':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'style_credit':'ChenLiu-1996/figures4papers; CC BY-NC 4.0; adapted palette and typography; original layout'},ensure_ascii=False,indent=2))
print(json.dumps({'pdf':str(pdf),'scores':dict(zip(ids,totals)),'weight_gap':gaps},ensure_ascii=False))
