"""Render paired time budgets and representative actual routes from audited logs."""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from task3.experiments.summarize_optimization import read_runs


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',nargs='+',type=Path,required=True)
    parser.add_argument('--policy',default='candidate_049_joint_completion')
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    runs,_=read_runs(args.inputs)
    baseline='candidate_041_dynamic_open_route_deferred_cross_view'
    groups={}
    for (policy,seed,count),row in runs.items():
        groups.setdefault(policy,{})[(seed,count)]=row
    common=sorted(groups[baseline].keys() & groups[args.policy].keys())
    if not common:
        raise ValueError('no paired scenes')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    policies=[baseline]+[p for p in sorted(groups) if p!=baseline and groups[p].keys()==groups[baseline].keys()]
    components=['movement_s','measurement_s','switching_s','optical_s','laser_s']
    labels=['Movement','Radio detection','Switching','Optical attempts','Laser']
    colors=['#457b9d','#f4a261','#e76f51','#8ab17d','#48524b']
    fig,ax=plt.subplots(figsize=(9,5),layout='constrained')
    bottom=np.zeros(len(policies))
    for component,label,color in zip(components,labels,colors):
        values=np.array([sum(r['result']['time_breakdown'][component] for r in groups[p].values())/
                         sum(r['source_count'] for r in groups[p].values()) for p in policies])
        ax.bar(np.arange(len(policies)),values,bottom=bottom,label=label,color=color)
        bottom+=values
    for i,value in enumerate(bottom):
        ax.text(i,value+3,f'{value:.2f}',ha='center',fontsize=11)
    ax.axhline(220,color='#b42318',ls='--',lw=1.5,label='220 s/source target')
    ax.set_xticks(range(len(policies)),[p.split('_')[1] for p in policies])
    ax.set_xlabel('Policy candidate')
    ax.set_ylabel('Total virtual time / total sources (s)')
    ax.set_title(f'Q3: same {len(common)} scenes, all time components included')
    ax.set_ylim(0,float(max(bottom))+55)
    ax.legend(ncol=3,loc='upper center',frameon=False,fontsize=9)
    fig.savefig(args.output_dir/'paired_time_budget.png',dpi=180)
    plt.close(fig)
    delta={k:groups[baseline][k]['result']['virtual_time_s']-groups[args.policy][k]['result']['virtual_time_s'] for k in common}
    median=min(common,key=lambda k:abs(delta[k]-np.median(list(delta.values()))))
    least=min(common,key=lambda k:delta[k])
    fig,axes=plt.subplots(2,2,figsize=(11,11),layout='constrained')
    for row_index,(key,label) in enumerate([(median,'Median paired saving'),(least,'Least paired saving')]):
        for col,policy in enumerate([baseline,args.policy]):
            row=groups[policy][key]
            ax=axes[row_index,col]
            points=np.array([[0.,0.]]+[a['position'] for a in row['actions'] if 'position' in a])
            sources=np.array([s['position'] for s in row['sources']])
            ax.add_patch(plt.Circle((0,0),1800,fill=False,color='#555',lw=1))
            ax.plot(points[:,0],points[:,1],lw=1.1,color='#457b9d',alpha=.85,label='Actual executed route')
            ax.scatter(sources[:,0],sources[:,1],s=35,marker='x',color='#b42318',label='Sources (post-run truth)')
            ax.scatter([0],[0],s=55,marker='*',color='black',label='Start')
            for source in row['sources']:
                ax.annotate(str(source['channel']),source['position'],xytext=(4,4),textcoords='offset points',fontsize=7)
            ax.set(xlim=(-1950,1950),ylim=(-1950,1950),xlabel='x (m)',ylabel='y (m)',aspect='equal')
            ax.set_title(f"{label}: seed {key[0]}\n{policy.split('_')[1]} | {row['result']['virtual_time_s']/key[1]:.2f} s/source")
            ax.grid(alpha=.2)
            if row_index==0 and col==0:
                ax.legend(fontsize=7,loc='upper right')
    fig.savefig(args.output_dir/'paired_actual_routes.png',dpi=180)
    plt.close(fig)
    print(args.output_dir)


if __name__=='__main__':
    main()
