import sys
from scipy.stats import norm
from matplotlib.colors import LogNorm

import importlib
import uproot
import numpy as np
import math
import matplotlib.pyplot as plt

import pandas as pd

import awkward

plt.rc('xtick', labelsize=14) 
plt.rc('ytick', labelsize=14) 



# --------------------------------------------------------------------------- # 
# calculate track PID score
def track_PID_score(file, df): 
    trk_llr_pid_v = file.array('trk_llr_pid_score_v')
    trk_id = file.array('trk_id')-1
    trk_llr_pid_v_sel = awkward.fromiter([pidv[tid] if tid<len(pidv) else 9999. for pidv,tid in zip(trk_llr_pid_v,trk_id)])
    df['trkpid'] = trk_llr_pid_v_sel
    
    return df
# --------------------------------------------------------------------------- # 
# plot detector resolution 
def plot_det_res(det_res, mu, sigma):
    
    fig = plt.figure(figsize=(8, 5))
    out = plt.hist(det_res, 12, histtype='step', color='orange', range=[-1, 1])

    xmin, xmax = plt.xlim()
    x = np.linspace(xmin, xmax, 100)
    p = norm.pdf(x, mu, sigma)
    area = np.sum(np.diff(out[1])*out[0])

    plt.xticks(fontsize=14)
    plt.yticks(fontsize=14)
    plt.xlabel('(true - reco) / true', fontsize=14)
    plt.ylabel('counts', fontsize=14)

    plt.plot(x, p*area, 'k', linewidth=2, color='red')

    title = "mu = %.2f,  std = %.2f" % (mu, sigma)
    plt.title(title, fontsize=15)

    plt.show()
# --------------------------------------------------------------------------- #    
# plot efficiency overlaid on selected signal events 
def plot_signal_and_eff(selected, df, signal, bins): 
    
    # generated true signal events per bin 
    gen = plt.hist(df.query(signal)['elec_e'], bins, color='orange')
    plt.close()
    
    # plot selected signal events 
    fig, ax1 = plt.subplots(figsize=(8, 5))
    
    sel = ax1.hist(selected.query(signal)['elec_e'], bins, color='orange')
    ax1.set_ylabel('selected signal events', fontsize=15)
    ax1.set_xlabel('true electron energy [GeV]', fontsize=15)

    # compute efficiency 
    eff = [ a/b for a, b in zip(sel[0], gen[0]) ]
    eff_err = []
    for i in range(len(eff)): 
        eff_err.append(math.sqrt( (eff[i]*(1-eff[i]))/gen[0][i] ) )
        
    # compute bin centers 
    bc = 0.5*(sel[1][1:]+sel[1][:-1])
    x_err = []
    for i in range(len(sel[1])-1): 
        x_err.append((sel[1][i+1]-sel[1][i])/2)

    # plot efficiency 
    ax2 = ax1.twinx()
    ax2.errorbar(bc, eff, xerr=x_err, yerr=eff_err, fmt='o', color='seagreen', ecolor='seagreen', markersize=3) 
    ax2.set_ylim(0, 0.5)
    ax2.set_ylabel('Efficiency', fontsize=15)

    plt.show()
# --------------------------------------------------------------------------- #  
# plot the smearing matrix 
def plot_smearing(selected, signal, true, reco, bins, norm=False): 
    fig = plt.figure(figsize=(10, 6))

    smear = plt.hist2d(selected.query(signal)[true],selected.query(signal)[reco],
                   bins, cmin=0.000000001, cmap='OrRd')

    for i in range(len(bins)-1): # reco bins i (y axis) rows
        for j in range(len(bins)-1): # true bins j (x axis) cols
            if smear[0].T[i,j] > 0: 
                if smear[0].T[i,j]>80: 
                    col='white'
                else: 
                    col='black'
                    
                binx_centers = smear[1][j]+(smear[1][j+1]-smear[1][j])/2
                biny_centers = smear[2][i]+(smear[2][i+1]-smear[2][i])/2
                        
                plt.text(binx_centers, biny_centers, round(smear[0].T[i,j], 1), 
                    color=col, ha="center", va="center", fontsize=12)

    cbar = plt.colorbar()
    cbar.set_label('selected signal events', fontsize=15)
    
    if norm: 
        plt.close()
        
        norm_array = smear[0].T
    
        # for each truth bin (column): 
        for j in range(len(bins)-1): 
        
            reco_events_in_column = [ norm_array[i][j] for i in range(len(bins)-1) ]
            tot_reco_events = np.nansum(reco_events_in_column)
        
            # replace with normalized value 
            for i in range(len(bins)-1): 
                norm_array[i][j] =  norm_array[i][j] / tot_reco_events
            
        # now plot
        fig = plt.figure(figsize=(10, 6))
        plt.pcolor(bins, bins, norm_array, cmap='OrRd', vmax=1)
    
        # Loop over data dimensions and create text annotations.
        for i in range(len(bins)-1): # reco bins (rows)
            for j in range(len(bins)-1): # truth bins (cols)
                if norm_array[i][j]>0: 
                
                    if norm_array[i][j]>0.7: 
                        col = 'white'
                    else: 
                        col = 'black'
                    
                    binx_centers = smear[1][j]+(smear[1][j+1]-smear[1][j])/2
                    biny_centers = smear[2][i]+(smear[2][i+1]-smear[2][i])/2
                
                    plt.text(binx_centers, biny_centers, round(norm_array[i][j], 2), 
                         ha="center", va="center", color=col, fontsize=12)
      
        cbar = plt.colorbar()
        cbar.set_label('fraction of reco events in true bin', fontsize=15)

    plt.xlabel('true electron energy [GeV]', fontsize=15)
    plt.ylabel('reco shower energy [GeV]', fontsize=15)

    plt.show()
# --------------------------------------------------------------------------- #  