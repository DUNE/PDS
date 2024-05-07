import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

df = pd.read_csv("scripts_fit.txt", sep="\t")
df['Vbd(Poly)'] = df['Vbd(Poly)'].fillna(0)

df_sorted = df.sort_values(by=['IP', 'CH'])
grouped = df_sorted.groupby('IP')

max_channels = grouped['CH'].max()
tot_channels = grouped['CH'].max().max()

num_ips = len(grouped)
subplot_width_ratios = max_channels/tot_channels

fig, axes = plt.subplots(ncols=num_ips, gridspec_kw={'width_ratios': subplot_width_ratios}, sharey=True)

for i, (ip, data) in enumerate(grouped):
    ax = axes[i]
    ax.step(data['CH'], data['Vbd(Poly)'])
    ax.set_title(ip,fontsize=10)
    ax.set_xlabel('Channel (CH)')
    if i == 0:
        ax.set_ylabel('Vbd (Poly Fit)')
    #else:
        #ax.set_yticks([])
        #ax.yaxis.set_visible(False)

    ax.grid(True)
    ax.set_xlim(0,max_channels[ip])

plt.subplots_adjust(wspace=0, hspace=0)
plt.savefig('vbd_ch.png')
plt.show()