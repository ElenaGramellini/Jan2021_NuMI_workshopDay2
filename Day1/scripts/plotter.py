#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""@package plotter
Plotter for searchingfornues TTree

This module produces plot from the TTree produced by the
searchingfornues framework (https://github.com/ubneutrinos/searchingfornues)

Example:
    my_plotter = plotter.Plotter(samples, weights)
    fig, ax1, ax2 = my_plotter.plot_variable(
        "reco_e",
        query="selected == 1"
        kind="event_category",
        title="$E_{deposited}$ [GeV]",
        bins=20,
        range=(0, 2)
    )

Attributes:
    category_labels (dict): Description of event categories
    pdg_labels (dict): Labels for PDG codes
    category_colors (dict): Color scheme for event categories
    pdg_colors (dict): Colors scheme for PDG codes
"""

import math
import warnings
import bisect

from collections import defaultdict
from collections.abc import Iterable
import scipy.stats
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import gridspec


category_labels = {
    1: r"$\nu_e$ Other",
    10: r"$\nu_e$ CC0$\pi$0p",
    12: r"$\bar\nu_e$ CC0$\pi$Np",
    13: r"$\bar\nu_e$ CC0$\pi$0p",
    11: r"$\nu_e$ CC0$\pi$Np",
    111: r"MiniBooNE LEE",
    2: r"$\nu_{\mu}$ CC",
    21: r"$\nu_{\mu}$ CC $\pi^{0}$",
    22: r"$\nu_{\mu}$ CC 0p$^+$",
    23: r"$\nu_{\mu}$ CC 1p$^+$",
    24: r"$\nu_{\mu}$ CC 2p$^+$",
    25: r"$\nu_{\mu}$ CC Np$^+$",
    3: r"$\nu$ NC",
    31: r"$\nu$ NC $\pi^{0}$",
    4: r"Cosmic",
    5: r"Out. fid. vol.",
    # eta categories start with 80XX
    801: r"$\eta \rightarrow$ other",
    802: r"$\nu_{\mu} \eta \rightarrow \gamma\gamma$",
    803: r'1 $\pi^0$',
    804: r'2 $\pi^0$',
    805: r'$\nu$ other',
    806: r'out of FV',
    6: r"other",
    0: r"No slice"
}


flux_labels = {
    1: r"$\pi$",
    10: r"K",
    111: r"MiniBooNE LEE",
    0: r"backgrounds"
}

flux_colors = {
    0: "xkcd:cerulean",
    111: "xkcd:goldenrod",
    10: "xkcd:light red",
    1: "xkcd:purple",
}


pdg_labels = {
    2212: r"$p$",
    13: r"$\mu$",
    11: r"$e$",
    111: r"$\pi^0$",
    -13: r"$\mu$",
    -11: r"$e$",
    211: r"$\pi^{\pm}$",
    -211: r"$\pi$",
    2112: r"$n$",
    22: r"$\gamma$",
    321: r"$K$",
    -321: r"$K$",
    0: "Cosmic"
}

int_labels = {
    0: "QE",
    1: "Resonant",
    2: "DIS",
    3: "Coherent",
    4: "Coherent Elastic",
    5: "Electron scatt.",
    6: "IMDAnnihilation",
    7: r"Inverse $\beta$ decay",
    8: "Glashow resonance",
    9: "AMNuGamma",
    10: "MEC",
    11: "Diffractive",
    12: "EM",
    13: "Weak Mix"
}


int_colors = {
    0: "bisque",
    1: "darkorange",
    2: "goldenrod",
    3: "lightcoral",
    4: "forestgreen",
    5: "turquoise",
    6: "teal",
    7: "deepskyblue",
    80: "steelblue",
    81: "steelblue",
    82: "steelblue",
    9: "royalblue",
    10: "crimson",
    11: "mediumorchid",
    12: "magenta",
    13: "pink",
    111: "black"
}

category_colors = {
    4: "xkcd:light red",
    5: "xkcd:brick",
    8: "xkcd:cerulean",
    2: "xkcd:cyan",
    21: "xkcd:cerulean",
    22: "xkcd:lightblue",
    23: "xkcd:cyan",
    24: "steelblue",
    25: "blue",
    3: "xkcd:cobalt",
    31: "xkcd:sky blue",
    1: "xkcd:moss green",
    10: "xkcd:mint green",
    12: "xkcd:green",
    13: "xkcd:forest green",
    11: "xkcd:lime green",
    111: "xkcd:goldenrod",
    6: "xkcd:grey",
    0: "xkcd:black",
    # eta categories
    803: "xkcd:cerulean",
    804: "xkcd:blue",
    801: "xkcd:purple",
    802: "xkcd:lavender",
    806: "xkcd:crimson",
    805: "xkcd:cyan",
}

pdg_colors = {
    2212: "#a6cee3",
    22: "#1f78b4",
    13: "#b2df8a",
    211: "#33a02c",
    111: "#137e6d",
    0: "#e31a1c",
    11: "#ff7f00",
    321: "#fdbf6f",
    2112: "#cab2d6",
}

class Plotter:
    """Main plotter class

    Args:
        samples (dict): Dictionary of pandas dataframes.
            mc`, `nue`, `data`, and `ext` are required. `lee` and `dirt` are optional.
        weights (dict): Dictionary of global dataframes weights.
            One for each entry in the samples dict.
        pot (int): Number of protons-on-target. Defaults is 4.5e19.

    Attributes:
       samples (dict): Dictionary of pandas dataframes.
       weights (dict): Dictionary of global dataframes weights.
       pot (int): Number of protons-on-target.
    """

    def __init__(self, samples, weights, pot=4.5e19):
        self.weights = weights
        self.samples = samples
        self.pot = pot
        self.significance = 0
        self.significance_likelihood = 0
        self.chisqdatamc = 0
        self.sigma_shapeonly = 0
        self.detsys = None
        self.stats = {}
        self.cov = None # covariance matrix from systematics
        self.cov_mc_stat = None
        self.cov_data_stat = None
        self.cov_full = None
        self._ratio_vals = None
        self._ratio_errs = None
        self.data = None # data binned events

        self.nu_pdg = nu_pdg = "~(abs(nu_pdg) == 12 & ccnc == 0)" # query to avoid double-counting events in MC sample with other MC samples

        if ("ccpi0" in self.samples):
            self.nu_pdg = self.nu_pdg+" & ~(mcf_pass_ccpi0==1)"
        if ("ncpi0" in self.samples):
            self.nu_pdg = self.nu_pdg+" & ~(mcf_np0==1 & mcf_nmp==0 & mcf_nmm==0 & mcf_nem==0 & mcf_nep==0)" #note: mcf_pass_ccpi0 is wrong (includes 'mcf_actvol' while sample is in all cryostat)
        if ("ccnopi" in self.samples):
            self.nu_pdg = self.nu_pdg+" & ~(mcf_pass_ccnopi==1 & (nslice==0 | (slnunhits/slnhits)>0.1))"
        if ("cccpi" in self.samples):
            self.nu_pdg = self.nu_pdg+" & ~(mcf_pass_cccpi==1 & (nslice==0 | (slnunhits/slnhits)>0.1))"
        if ("nccpi" in self.samples):
            self.nu_pdg = self.nu_pdg+" & ~(mcf_pass_nccpi==1 & (nslice==0 | (slnunhits/slnhits)>0.1))"
        if ("ncnopi" in self.samples):
            self.nu_pdg = self.nu_pdg+" & ~(mcf_pass_ncnopi==1 & (nslice==0 | (slnunhits/slnhits)>0.1))"


        if "dirt" not in samples:
            warnings.warn("Missing dirt sample")

        necessary = ["category"]#, "selected",  # "trk_pfp_id", "shr_pfp_id_v",
                     #"backtracked_pdg", "nu_pdg", "ccnc", "trk_bkt_pdg", "shr_bkt_pdg"]

        missing = np.setdiff1d(necessary, samples["mc"].columns)

        if missing.size > 0:
            raise ValueError(
                "Missing necessary columns in the DataFrame: %s" % missing)

    @staticmethod
    def _chisquare(data, mc, err_mc):
        num = (data - mc)**2
        den = data+err_mc**2
        if np.count_nonzero(data):
            return sum(num / den) / len(data)
        return np.inf


    @staticmethod
    def _chisq_pearson(data, mc):
        return (data-mc)**2 / mc

    @staticmethod
    def _chisq_neyman(data, mc):
        return (data-mc)**2 / data

    def _chisq_CNP(self,data, mc):
        return np.sum((1/3.) * (self._chisq_neyman(data,mc) + 2 * self._chisq_pearson(data,mc)))/len(data)

    @staticmethod
    def _sigma_calc_likelihood(sig, bkg, err_bkg, scale_factor=1):
        """It calculates the significance with the profile likelihood ratio
        assuming an uncertainity on the background entries.
        Taken from http://www.pp.rhul.ac.uk/~cowan/stat/medsig/medsigNote.pdf
        """
        b = bkg * scale_factor
        if not isinstance(err_bkg, Iterable):
            e = np.array([err_bkg]) * scale_factor
        else:
            e = err_bkg * scale_factor

        s = sig * scale_factor

        p1 = (s+b)*np.log((s+b)*(b+e**2)/(b**2+(s+b)*e**2))

        p2 = -s
        if sum(e) > 0:
            p2 = -b**2/(e**2)*np.log(1+e**2*s/(b*(b+e**2)))
        z = 2*(p1+p2)

        return math.sqrt(sum(z))

    @staticmethod
    def _sigma_calc_matrix(signal, background, scale_factor=1, cov=None):
        """It calculates the significance as the square root of the Δχ2 score

        Args:
            signal (np.array): array of signal histogram
            background (np.array): array of background histogram
            scale_factor (float, optional): signal and background scaling factor.
                Default is 1

        Returns:
            Square root of S•B^(-1)•S^T
        """

        bkg_array = background * scale_factor
        empty_elements = np.where(bkg_array == 0)[0]
        sig_array = signal * scale_factor
        cov = cov * scale_factor * scale_factor
        sig_array = np.delete(sig_array, empty_elements)
        bkg_array = np.delete(bkg_array, empty_elements)
        cov[np.diag_indices_from(cov)] += bkg_array
        emtxinv = np.linalg.inv(cov)
        chisq = float(sig_array.dot(emtxinv).dot(sig_array.T))

        return np.sqrt(chisq)


    def deltachisqfakedata(self, BinMin, BinMax, LEE_v, SM_v, nsample):

        deltachisq_v = []
        deltachisq_SM_v  = []
        deltachisq_LEE_v = []

        #print ('deltachisqfakedata!!!!!!')
        
        for n in range(1000):

            SM_obs, LEE_obs = self.genfakedata(BinMin, BinMax, LEE_v, SM_v, nsample)

            #chisq = self._chisq_CNP(SM_obs,LEE_obs)           
            #print ('LEE obs : ',LEE_obs)
            #print ('SM obs : ',SM_obs)
            
            chisq_SM_SM  = self._chisq_CNP(SM_v,SM_obs)
            chisq_LEE_SM = self._chisq_CNP(LEE_v,SM_obs)
            
            chisq_SM_LEE  = self._chisq_CNP(SM_v,LEE_obs)
            chisq_LEE_LEE = self._chisq_CNP(LEE_v,LEE_obs)
            
            deltachisq_SM  = (chisq_SM_SM-chisq_LEE_SM)
            deltachisq_LEE = (chisq_SM_LEE-chisq_LEE_LEE)

            #if (np.isnan(chisq)):
            #    continue

            #deltachisq_v.append(chisq)
            
            if (np.isnan(deltachisq_SM ) or np.isnan(deltachisq_LEE) ):
                continue

            deltachisq_SM_v.append(deltachisq_SM)
            deltachisq_LEE_v.append(deltachisq_LEE)

        #median = np.median(deltachisq_v)
        #dof = len(LEE_v)

        #return median/float(dof)

        #print ('delta SM  : ',deltachisq_SM_v)
        #print ('delta LEE : ',deltachisq_LEE_v)

        deltachisq_SM_v  = np.array(deltachisq_SM_v)
        deltachisq_LEE_v = np.array(deltachisq_LEE_v)

        if (len(deltachisq_SM_v) == 0):
            return 999.
        
        # find median of LEE distribution
        med_LEE = np.median(deltachisq_LEE_v)
        #print ('median LEE is ',med_LEE)
        # how many values in SM are above this value?
        nabove = len( np.where(deltachisq_SM_v > med_LEE)[0] )
        #print ('n above is ',nabove)
        frac = float(nabove) / len(deltachisq_SM_v)

        #print ('deltachisqfakedata!!!!!!')
        
        return math.sqrt(2)*scipy.special.erfinv(1-frac*2)
        
        #return frac

            
    def genfakedata(self, BinMin, BinMax, LEE_v, SM_v, nsample):

        p_LEE = LEE_v / np.sum(LEE_v)
        p_SM  = SM_v / np.sum(SM_v)

        #print ('PDF for LEE : ',p_LEE)
        #print ('PDF for SM  : ',p_SM)

        obs_LEE = np.zeros(len(LEE_v))
        obs_SM  = np.zeros(len(SM_v))

        max_LEE = np.max(p_LEE)
        max_SM  = np.max(p_SM)

        #print ('max of LEE : ',max_LEE)
        #print ('max of SM  : ',max_SM)

        n_sampled_LEE = 0
        n_sampled_SM  = 0

        while (n_sampled_LEE < nsample):

            value = BinMin + (BinMax-BinMin) * np.random.random()

            BinNumber = int((value-BinMin)/(BinMax-BinMin) * len(LEE_v))
            
            prob = np.random.random() * max_LEE
            if (prob < p_LEE[BinNumber]):
                #print ('LEE simulation: prob of %.02f vs. bin prob of %.02f leads to selecting event at bin %i'%(prob,p_LEE[BinNumber],BinNumber))
                obs_LEE[BinNumber] += 1
                n_sampled_LEE += 1

        while (n_sampled_SM < nsample):

            value = BinMin + (BinMax-BinMin) * np.random.random()

            BinNumber = int((value-BinMin)/(BinMax-BinMin) * len(SM_v))
            
            prob = np.random.random() * max_SM
            if (prob < p_SM[BinNumber]):
                obs_SM[BinNumber] += 1
                n_sampled_SM += 1

        return obs_SM, obs_LEE
            
            

    def _chisq_full_covariance(self,data, mc,CNP=True,STATONLY=False):

        np.set_printoptions(precision=3)

        dof = len(data)
        
        COV = self.cov + self.cov_mc_stat + self.cov_mc_detsys
            
        # remove rows/columns with zero data and MC
        remove_indices_v = []
        for i,d in enumerate(data):
            idx = len(data)-i-1
            if ((data[idx]==0) and (mc[idx] == 0)):
                remove_indices_v.append(idx)

        for idx in remove_indices_v:
            COV = np.delete(COV,idx,0)
            COV = np.delete(COV,idx,1)
            data = np.delete(data,idx,0)
            mc   = np.delete(mc,idx,0)


        COV_STAT = np.zeros([len(data), len(data)])


        ERR_STAT = 3. / ( 1./data + 2./mc )
        
        for i,d in enumerate(data):
            
            if (d == 0):
                ERR_STAT[i] = mc[i]/2.
            if (mc[i] == 0):
                ERR_STAT[i] = d

        if (CNP == False):
            ERR_STAT = data + mc
        

        COV_STAT[np.diag_indices_from(COV_STAT)] = ERR_STAT

        COV += COV_STAT

        if (STATONLY == True):
            COV = COV_STAT

        #print("COV matrix : ",COV)
                
        diff = (data-mc)
        emtxinv = np.linalg.inv(COV)
        chisq = float(diff.dot(emtxinv).dot(diff.T))
        
        covdiag = np.diag(COV)
        chisqsum = 0.
        for i,d in enumerate(diff):
            #print ('bin %i has COV value %.02f'%(i,covdiag[i]))
            chisqsum += ( (d**2) /covdiag[i])

        return chisq, chisqsum, dof

    @staticmethod
    def _data_err(data,doAsym=False):
        obs = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]
        low = [0.00,0.17,0.71,1.37,2.09,2.84,3.62,4.42,5.23,6.06,6.89,7.73,8.58,9.44,10.30,11.17,12.04,12.92,13.80,14.68,15.56]
#        hig = [0.38,3.30,4.64,5.92,7.16,8.38,9.58,10.77,11.95,13.11,14.27,15.42,16.56,17.70,18.83,19.96,21.08,22.20,23.32,24.44,25.55]
        hig = [1.15,3.30,4.64,5.92,7.16,8.38,9.58,10.77,11.95,13.11,14.27,15.42,16.56,17.70,18.83,19.96,21.08,22.20,23.32,24.44,25.55]
        if doAsym:
            lb = [i-low[i] if i<=20 else (np.sqrt(i)) for i in data]
            hb = [hig[i]-i if i<=20 else (np.sqrt(i)) for i in data]
            return (lb,hb)
        else: return (np.sqrt(data),np.sqrt(data))


    @staticmethod
    def _ratio_err(num, den, num_err, den_err):
        n, d, n_e, d_e = num, den, num_err, den_err
        n[n == 0] = 0.00001
        #d[d == 0] = 0.00001
        return np.array([
            #n[i] / d[i] * math.sqrt((n_e[i] / n[i])**2 + (d_e[i] / d[i])**2) <= this does not work if n[i]==0
            math.sqrt( ( n_e[i] / d[i] )**2 + ( n[i] * d_e[i] / (d[i]*d[i]) )**2) if d[i]>0 else 0
            for i, k in enumerate(num)
        ])

    @staticmethod
    def _is_fiducial(x, y, z):
        try:
            x_1 = x[:, 0] > 10
            x_2 = x[:, 1] > 10
            y_1 = y[:, 0] > 15
            y_2 = y[:, 1] > 15
            z_1 = z[:, 0] > 10
            z_2 = z[:, 1] > 50

            return x_1 & x_2 & y_1 & y_2 & z_1 & z_2
        except IndexError:
            return True

    def print_stats(self):
        print ('print stats...')
        for key,val in self.stats.items():
            print ('%s : %.02f'%(key,val))


    def _select_showers(self, variable, variable_name, sample, query="selected==1", score=0.5, extra_cut=None):
        variable = variable.ravel()

        if variable.size > 0:
            if isinstance(variable[0], np.ndarray):
                variable = np.hstack(variable)
                if "shr" in variable_name and variable_name != "shr_score_v":
                    shr_score = np.hstack(self._selection(
                        "shr_score_v", sample, query=query, extra_cut=extra_cut))
                    shr_score_id = shr_score < score
                    variable = variable[shr_score_id]
                elif "trk" in variable_name and variable_name != "trk_score_v":
                    trk_score = np.hstack(self._selection(
                        "trk_score_v", sample, query=query, extra_cut=extra_cut))
                    trk_score_id = trk_score >= score
                    variable = variable[trk_score_id]

        return variable


    def _apply_track_cuts(self,df,variable,track_cuts,mask):
        '''
        df is dataframe of the sample of interest
        variable is what values will be in the output
        track_cuts are list of tuples defining track_cuts
        input mask to be built upon

        returns
            Series of values of variable that pass all track_cuts
            boolean mask that represents union of input mask and new cut mask
        '''
        #need to do this fancy business with the apply function to make masks
        #this is because unflattened DataFrames are used
        for (var,op,val) in track_cuts:
            if type(op) == list:
                #this means treat two conditions in an 'or' fashion
                or_mask1 = df[var].apply(lambda x: eval("x{}{}".format(op[0],val[0])))#or condition 1
                or_mask2 = df[var].apply(lambda x: eval("x{}{}".format(op[1],val[1])))#or condition 2
                mask *= (or_mask1 + or_mask2) #just add the booleans for "or"
            else:
                mask *= df[var].apply(lambda x: eval("x{}{}".format(op,val))) #layer on each cut mask
        vars = (df[variable]*mask).apply(lambda x: x[x != False]) #apply mask
        vars = vars[vars.apply(lambda x: len(x) > 0)] #clean up empty slices
        #fix list comprehension issue for non '_v' variables
        if variable[-2:] != "_v":
            vars = vars.apply(lambda x: x[0])
        elif "_v" not in variable:
            print("_v not found in variable, assuming event-level")
            print("not fixing list comprehension bug for this variable")

        return vars, mask

    def _select_longest(self,df, variable, mask):
        '''
        df: dataframe for sample
        variable: Series of values that pass cuts defined by mask
        mask: mask used to find variable

        returns
            list of values of variable corresponding to longest track in each slices
            boolean mask for longest tracks in df
        '''

        #print("selecting longest...")
        #print("mask", mask)
        trk_lens = (df['trk_len_v']*mask).apply(lambda x: x[x != False])#apply mask to track lengths
        trk_lens = trk_lens[trk_lens.apply(lambda x: len(x) > 0)]#clean up slices
        variable = variable.apply(lambda x: x[~np.isnan(x)])#clean up nan vals
        variable = variable[variable.apply(lambda x: len(x) > 0)] #clean up empty slices
        nan_mask = variable.apply(lambda x: np.nan in x or "nan" in x)
        longest_mask = trk_lens.apply(lambda x: x == x[list(x).index(max(x))])#identify longest
        variable = (variable*longest_mask).apply(lambda x: x[x!=False])#apply mask
        if len(variable.iloc[0]) == 1:
            variable = variable.apply(lambda x: x[0] if len(x)>0 else -999)#expect values, not lists, for each event
        else:
            if len(variable.iloc[0]) == 0:
                raise ValueError(
                    "There is no longest track per slice")
            elif len(variable.iloc[0]) > 1:
                #this happens with the reco_nu_e_range_v with unreconstructed values
                print("there are more than one longest slice")
                print(variable.iloc[0])
                try:
                    variable = variable.apply(lambda x: x[0])
                except:
                    raise ValueError(
                        "There is more than one longest track per slice in \n var {} lens {}".format(variable,trk_lens))

        return variable, longest_mask

    def _selection(self, variable, sample, query="selected==1", extra_cut=None, track_cuts=None, select_longest=True):
        '''
        variable,  must be specified
        select_longest, True by default, keeps from multiple tracks of same event making it through
        query must be a string defining event-level cuts
        track_cuts is a list of cuts of which each entry looks like
            (variable_tobe_cut_on, '>'or'<'or'=='etc, cut value )
            or
            (variable, [operator1, operator2], [cutval1, cutval2]) to do an 'or' cut
        track_
        returns an Series of values that pass all track_cuts
        '''
        sel_query = query
        if extra_cut is not None:
            sel_query += "& %s" % extra_cut
        '''
        if ( (track_cuts == None) or (select_longest == False) ):
            return sample.query(sel_query).eval(variable).ravel()
        '''


        '''
        df = sample.query(sel_query)
        #print (df.isna().sum())
        dfna = df.isna()
        for (colname,colvals) in dfna.iteritems():
            if (colvals.sum() != 0):
                print ('name : ',colname)
                print ('nan entries : ',colvals.sum())
        '''
        df = sample.query(sel_query)
        #if (track_cuts != None):
        #    df = sample.query(sel_query).dropna().copy() #don't want to eliminate anything from memory

        #df = sample.query(sel_query).dropna().copy() #don't want to eliminate anything from memory

        track_cuts_mask = None #df['trk_score_v'].apply(lambda x: x == x) #all-True mask, assuming trk_score_v is available
        if track_cuts is not None:
            vars, track_cuts_mask = self._apply_track_cuts(df,variable,track_cuts,track_cuts_mask)
        else:
            vars = df[variable]
        #vars is now a Series object that passes all the cuts

        #select longest of the cut passing tracks
        #assuming all track-level variables end in _v
        if variable[-2:] == "_v" and select_longest:
            vars, longest_mask = self._select_longest(df, vars, track_cuts_mask)
        elif "_v_" in variable:
            print("Variable is being interpretted as event-level, not track_level, despite having _v in name")
            print("the longest track is NOT being selected")
        return vars.ravel()

    def _categorize_entries_pdg(self, sample, variable, query="selected==1", extra_cut=None, track_cuts=None, select_longest=True):

        if "trk" in variable:
            pfp_id_variable = "trk_pfp_id"
            score_v = self._selection("trk_score_v", sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest)
        else:
            pfp_id_variable = "shr_pfp_id_v"
            score_v = self._selection("shr_score_v", sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest)


        pfp_id = self._selection(
            pfp_id_variable, sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest)
        plotted_variable = self._selection(
            variable, sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest)
        pfp_id = np.subtract(pfp_id, 1)
        backtracked_pdg = np.abs(self._selection(
            "backtracked_pdg", sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest))

        plotted_variable = self._select_showers(
            plotted_variable, variable, sample, query=query, extra_cut=extra_cut)

        if "trk" in variable:
            pfp_id = np.array([pf_id[score > 0.5] for pf_id, score in zip(pfp_id, score_v)])
        else:
            pfp_id = np.array([pf_id[score <= 0.5] for pf_id, score in zip(pfp_id, score_v)])

        pfp_pdg = np.array([pdg[pf_id]
                            for pdg, pf_id in zip(backtracked_pdg, pfp_id)])
        pfp_pdg = np.hstack(pfp_pdg)
        pfp_pdg = abs(pfp_pdg)

        return pfp_pdg, plotted_variable

    def _categorize_entries_single_pdg(self, sample, variable, query="selection==1", extra_cut=None, track_cuts=None, select_longest=True):
        if "trk" in variable:
            bkt_variable = "trk_bkt_pdg"
        else:
            bkt_variable = "shr_bkt_pdg"

        backtracked_pdg = np.abs(self._selection(
            bkt_variable, sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest))
        plotted_variable = self._selection(
            variable, sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest)

        return backtracked_pdg, plotted_variable

    def _categorize_entries(self, sample, variable, query="selected==1", extra_cut=None, track_cuts=None, select_longest=True):
        category = self._selection(
            "category", sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest)
        plotted_variable = self._selection(
            variable, sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest)

        if plotted_variable.size > 0:
            if isinstance(plotted_variable[0], np.ndarray):
                if "trk" in variable or select_longest:
                    score = self._selection(
                        "trk_score_v", sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest)
                    category = np.array([
                        np.array([c] * len(v[s > 0.5])) for c, v, s in zip(category, plotted_variable, score)
                    ])
                else:
                    score = self._selection(
                        "shr_score_v", sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest)
                    category = np.array([
                        np.array([c] * len(v[s < 0.5])) for c, v, s in zip(category, plotted_variable, score)
                    ])
                category = np.hstack(category)

            plotted_variable = self._select_showers(
                plotted_variable, variable, sample, query=query, extra_cut=extra_cut)

        return category, plotted_variable

    def _categorize_entries_int(self, sample, variable, query="selected==1", extra_cut=None, track_cuts=None, select_longest=True):
        category = self._selection(
            "interaction", sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest)
        plotted_variable = self._selection(
            variable, sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest)


    def _categorize_entries_flux(self, sample, variable, query="selected==1", extra_cut=None, track_cuts=None, select_longest=True):
        category = self._selection(
            "flux", sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest)
        plotted_variable = self._selection(
            variable, sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest)


        if plotted_variable.size > 0:
            if isinstance(plotted_variable[0], np.ndarray):
                if "trk" in variable or select_longest:
                    score = self._selection(
                        "trk_score_v", sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest)
                    category = np.array([
                        np.array([c] * len(v[s > 0.5])) for c, v, s in zip(category, plotted_variable, score)
                    ])
                else:
                    score = self._selection(
                        "shr_score_v", sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest)
                    category = np.array([
                        np.array([c] * len(v[s < 0.5])) for c, v, s in zip(category, plotted_variable, score)
                    ])
                category = np.hstack(category)

            plotted_variable = self._select_showers(
                plotted_variable, variable, sample, query=query, extra_cut=extra_cut)

        return category, plotted_variable



    @staticmethod
    def _variable_bin_scaling(bins, bin_width, variable):
        idx = bisect.bisect_left(bins, variable)
        if len(bins) > idx:
            return bin_width/(bins[idx]-bins[idx-1])
        return 0

    def _get_genie_weight(self, sample, variable, query="selected==1", extra_cut=None, track_cuts=None,\
                          select_longest=True, weightvar="weightSplineTimesTuneTimesPPFX",weightsignal=None):

        plotted_variable = self._selection(
            variable, sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest)
        genie_weights = self._selection(
            weightvar, sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest)
        if (weightsignal != None):
            genie_weights *= self._selection(
            weightsignal, sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest)
        if plotted_variable.size > 0:
            if isinstance(plotted_variable[0], np.ndarray):
                if "trk" in variable or select_longest:
                    score = self._selection(
                        "trk_score_v", sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest)
                else:
                    score = self._selection(
                        "shr_score_v", sample, query=query, extra_cut=extra_cut, track_cuts=track_cuts, select_longest=select_longest)
                genie_weights = np.array([
                    np.array([c] * len(v[s > 0.5])) for c, v, s in zip(genie_weights, plotted_variable, score)
                ])
                genie_weights = np.hstack(genie_weights)
        return genie_weights

    def _get_variable(self, variable, query, track_cuts=None):

        '''
        nu_pdg = "~(abs(nu_pdg) == 12 & ccnc == 0)"
        if ("ccpi0" in self.samples):
            nu_pdg = nu_pdg+" & ~(mcf_pass_ccpi0==1)"
        if ("ncpi0" in self.samples):
            nu_pdg = nu_pdg+" & ~(mcf_np0==1 & mcf_nmp==0 & mcf_nmm==0 & mcf_nem==0 & mcf_nep==0)" #note: mcf_pass_ccpi0 is wrong (includes 'mcf_actvol' while sample is in all cryostat)
        if ("ccnopi" in self.samples):
            nu_pdg = nu_pdg+" & ~(mcf_pass_ccnopi==1 & (nslice==0 | (slnunhits/slnhits)>0.1))"
        if ("cccpi" in self.samples):
            nu_pdg = nu_pdg+" & ~(mcf_pass_cccpi==1 & (nslice==0 | (slnunhits/slnhits)>0.1))"
        if ("nccpi" in self.samples):
            nu_pdg = nu_pdg+" & ~(mcf_pass_nccpi==1 & (nslice==0 | (slnunhits/slnhits)>0.1))"
        if ("ncnopi" in self.samples):
            nu_pdg = nu_pdg+" & ~(mcf_pass_ncnopi==1 & (nslice==0 | (slnunhits/slnhits)>0.1))"
        '''

        # if plot_options["range"][0] >= 0 and plot_options["range"][1] >= 0 and variable[-2:] != "_v":
        #     query += "& %s <= %g & %s >= %g" % (
        #         variable, plot_options["range"][1], variable, plot_options["range"][0])

        mc_plotted_variable = self._selection(
            variable, self.samples["mc"], query=query, extra_cut=self.nu_pdg, track_cuts=track_cuts)
        mc_plotted_variable = self._select_showers(
            mc_plotted_variable, variable, self.samples["mc"], query=query, extra_cut=self.nu_pdg)
        mc_weight = [self.weights["mc"]] * len(mc_plotted_variable)

        nue_plotted_variable = self._selection(
            variable, self.samples["nue"], query=query, track_cuts=track_cuts)
        nue_plotted_variable = self._select_showers(
            nue_plotted_variable, variable, self.samples["nue"], query=query)
        nue_weight = [self.weights["nue"]] * len(nue_plotted_variable)

        ext_plotted_variable = self._selection(
            variable, self.samples["ext"], query=query, track_cuts=track_cuts)
        ext_plotted_variable = self._select_showers(
            ext_plotted_variable, variable, self.samples["ext"], query=query)
        ext_weight = [self.weights["ext"]] * len(ext_plotted_variable)

        dirt_weight = []
        dirt_plotted_variable = []
        if "dirt" in self.samples:
            dirt_plotted_variable = self._selection(
                variable, self.samples["dirt"], query=query, track_cuts=track_cuts)
            dirt_plotted_variable = self._select_showers(
                dirt_plotted_variable, variable, self.samples["dirt"], query=query)
            dirt_weight = [self.weights["dirt"]] * len(dirt_plotted_variable)

        ncpi0_weight = []
        ncpi0_plotted_variable = []
        if "ncpi0" in self.samples:
            ncpi0_plotted_variable = self._selection(
                variable, self.samples["ncpi0"], query=query, track_cuts=track_cuts)
            ncpi0_plotted_variable = self._select_showers(
                ncpi0_plotted_variable, variable, self.samples["ncpi0"], query=query)
            ncpi0_weight = [self.weights["ncpi0"]] * len(ncpi0_plotted_variable)

        ccpi0_weight = []
        ccpi0_plotted_variable = []
        if "ccpi0" in self.samples:
            ccpi0_plotted_variable = self._selection(
                variable, self.samples["ccpi0"], query=query, track_cuts=track_cuts)
            ccpi0_plotted_variable = self._select_showers(
                ccpi0_plotted_variable, variable, self.samples["ccpi0"], query=query)
            ccpi0_weight = [self.weights["ccpi0"]] * len(ccpi0_plotted_variable)

        ccnopi_weight = []
        ccnopi_plotted_variable = []
        if "ccnopi" in self.samples:
            ccnopi_plotted_variable = self._selection(
                variable, self.samples["ccnopi"], query=query, track_cuts=track_cuts)
            ccnopi_plotted_variable = self._select_showers(
                ccnopi_plotted_variable, variable, self.samples["ccnopi"], query=query)
            ccnopi_weight = [self.weights["ccnopi"]] * len(ccnopi_plotted_variable)

        cccpi_weight = []
        cccpi_plotted_variable = []
        if "cccpi" in self.samples:
            cccpi_plotted_variable = self._selection(
                variable, self.samples["cccpi"], query=query, track_cuts=track_cuts)
            cccpi_plotted_variable = self._select_showers(
                cccpi_plotted_variable, variable, self.samples["cccpi"], query=query)
            cccpi_weight = [self.weights["cccpi"]] * len(cccpi_plotted_variable)

        nccpi_weight = []
        nccpi_plotted_variable = []
        if "nccpi" in self.samples:
            nccpi_plotted_variable = self._selection(
                variable, self.samples["nccpi"], query=query, track_cuts=track_cuts)
            nccpi_plotted_variable = self._select_showers(
                nccpi_plotted_variable, variable, self.samples["nccpi"], query=query)
            nccpi_weight = [self.weights["nccpi"]] * len(nccpi_plotted_variable)

        ncnopi_weight = []
        ncnopi_plotted_variable = []
        if "ncnopi" in self.samples:
            ncnopi_plotted_variable = self._selection(
                variable, self.samples["ncnopi"], query=query, track_cuts=track_cuts)
            ncnopi_plotted_variable = self._select_showers(
                ncnopi_plotted_variable, variable, self.samples["ncnopi"], query=query)
            ncnopi_weight = [self.weights["ncnopi"]] * len(ncnopi_plotted_variable)

        lee_weight = []
        lee_plotted_variable = []
        if "lee" in self.samples:
            lee_plotted_variable = self._selection(
                variable, self.samples["lee"], query=query, track_cuts=track_cuts)
            lee_plotted_variable = self._select_showers(
                lee_plotted_variable, variable, self.samples["lee"], query=query)
            lee_weight = self.samples["lee"].query(
                query)["leeweight"] * self.weights["lee"]

        total_weight = np.concatenate((mc_weight, nue_weight, ext_weight, dirt_weight, ncpi0_weight, ccpi0_weight, ccnopi_weight, cccpi_weight, nccpi_weight, ncnopi_weight, lee_weight))
        total_variable = np.concatenate((mc_plotted_variable, nue_plotted_variable, ext_plotted_variable, dirt_plotted_variable, ncpi0_plotted_variable, ccpi0_plotted_variable, ccnopi_plotted_variable, cccpi_plotted_variable, nccpi_plotted_variable, ncnopi_plotted_variable, lee_plotted_variable))
        return total_variable, total_weight


    def plot_2d(self, variable1_name, variable2_name, query="selected==1", track_cuts=None, **plot_options):
        variable1, weight1 = self._get_variable(variable1_name, query, track_cuts=track_cuts)
        variable2, weight2 = self._get_variable(variable2_name, query, track_cuts=track_cuts)

        heatmap, xedges, yedges = np.histogram2d(variable1, variable2,
                                                 range=[[plot_options["range_x"][0], plot_options["range_x"][1]], [plot_options["range_y"][0], plot_options["range_y"][1]]],
                                                 bins=[plot_options["bins_x"], plot_options["bins_y"]],
                                                 weights=weight1)

        extent = [xedges[0], xedges[-1], yedges[0], yedges[-1]]
        fig, axes  = plt.subplots(1,3, figsize=(15,5))

        axes[0].imshow(heatmap.T, extent=extent, origin='lower', aspect="auto")

        data_variable1 = self._selection(variable1_name, self.samples["data"], query=query, track_cuts=track_cuts)
        data_variable1 = self._select_showers(data_variable1, variable1_name, self.samples["data"], query=query)

        data_variable2 = self._selection(
            variable2_name, self.samples["data"], query=query, track_cuts=track_cuts)
        data_variable2 = self._select_showers(
            data_variable2, variable2_name, self.samples["data"], query=query)

        heatmap_data, xedges, yedges = np.histogram2d(data_variable1, data_variable2, range=[[plot_options["range_x"][0], plot_options["range_x"][1]], [
                                                      plot_options["range_y"][0], plot_options["range_y"][1]]],
                                                      bins=[plot_options["bins_x"],
                                                      plot_options["bins_y"]])

        axes[1].imshow(heatmap_data.T, extent=extent, origin='lower', aspect="auto")

        ratio = heatmap_data/heatmap
        im_ratio = axes[2].imshow(ratio.T, extent=extent, origin='lower', aspect='auto', vmin=0, vmax=2, cmap="coolwarm")
        fig.colorbar(im_ratio)

        axes[0].title.set_text('MC+EXT')
        axes[1].title.set_text('Data')
        axes[2].title.set_text('Data/(MC+EXT)')
        if "title" in plot_options:
            axes[0].set_xlabel(plot_options["title"].split(";")[0])
            axes[0].set_ylabel(plot_options["title"].split(";")[1])
            axes[1].set_xlabel(plot_options["title"].split(";")[0])
            axes[2].set_xlabel(plot_options["title"].split(";")[0])
        else:
            axes[0].set_xlabel(variable1_name)
            axes[0].set_ylabel(variable2_name)
            axes[1].set_xlabel(variable1_name)
            axes[2].set_xlabel(variable1_name)

        return fig, axes

    def plot_2d_oneplot(self, variable1_name, variable2_name, query="selected==1", track_cuts=None, **plot_options):
        variable1, weight1 = self._get_variable(variable1_name, query, track_cuts=track_cuts)
        variable2, weight2 = self._get_variable(variable2_name, query, track_cuts=track_cuts)

        heatmap, xedges, yedges = np.histogram2d(variable1, variable2,
                                                 range=[[plot_options["range_x"][0], plot_options["range_x"][1]], [plot_options["range_y"][0], plot_options["range_y"][1]]],
                                                 bins=[plot_options["bins_x"], plot_options["bins_y"]],
                                                 weights=weight1)

        extent = [xedges[0], xedges[-1], yedges[0], yedges[-1]]

        #if figure is passed, use that to build plot
        if "figure" in plot_options:
            fig = plot_options["figure"]
        else:
            fig = plt.figure(figsize=(6,6))
        if "axis" in plot_options:
            axis = plot_options["axis"]
        else:
            axis = plt.gca()

        if 'range_z' in plot_options:
            image = axis.imshow(heatmap.T, extent=extent, origin='lower', aspect="auto",
                vmin=plot_options['range_z'][0], vmax=plot_options['range_z'][1])
        else:
            image = axis.imshow(heatmap.T, extent=extent, origin='lower', aspect="auto")

        return fig, axis, image


    def load_detsys_errors(self,var,path,binedges):

        detsys_frac = np.zeros(len(binedges)-1)

        DETSAMPLES = ["X", "YZ", 'aYZ', "aXZ","dEdX","SCE","LYD","LYR","LYA"]

        if os.path.isdir(path) == False:
            #print ('DETSYS. path %s is not valid'%path)
            return detsys_frac

        for varsample in DETSAMPLES:

            filename = var + "_" + varsample + ".txt"

            if (os.path.isfile(path+filename) == False):
                #print ('file-name %s is not valid'%filename)
                continue

            f = open(path+filename,'r')

            for binnumber in range(len(detsys_frac)):

                binmin = binedges[binnumber]
                binmax = binedges[binnumber+1]

                bincenter = 0.5*(binmin+binmax)

                # find uncertainty associated to this bin in the text-file

                f.seek(0,0)
                
                for line in f:

                    words = line.split(",")
                    binrange_v = words[0].split("-")
                    bincenter = 0.5*(float(binrange_v[0])+float(binrange_v[1]))

                    if ( (bincenter > binmin) and (bincenter <= binmax) ):
                    
                        fracerror = float(words[1].split()[0])
                        detsys_frac[binnumber] += fracerror * fracerror

                        break

        detsys_frac = np.sqrt(np.array(detsys_frac))
        print ('detsys diag error terms are ', detsys_frac)

        return detsys_frac


    def add_detsys_error(self,sample,mc_entries_v,weight):
        detsys_v  = np.zeros(len(mc_entries_v))
        entries_v = np.zeros(len(mc_entries_v))
        if (self.detsys == None): return detsys_v
        if sample in self.detsys:
            if (len(self.detsys[sample]) == len(mc_entries_v)):
                for i,n in enumerate(mc_entries_v):
                    detsys_v[i] = (self.detsys[sample][i] * n * weight)#**2
                    entries_v[i] = n * weight
            else:
                print ('NO MATCH! len detsys : %i. Len plotting : %i'%(len(self.detsys[sample]),len(mc_entries_v) ))

        return detsys_v



    def plot_variable(self, variable, query="selected==1", title="", kind="event_category", draw_geoSys=False,
                      draw_sys=False, stacksort=0, track_cuts=None, select_longest=False,
                      detsys=None,ratio=True,chisq=False,draw_data=True,asymErrs=False,genieweight="weightSplineTimesTuneTimesPPFX",
                      ncol=2,
                      COVMATRIX='', # path to covariance matrix file
                      DETSYSPATH="", # path where to find detector systematics files
                      **plot_options):
        """It plots the variable from the TTree, after applying an eventual query

        Args:
            variable (str): name of the variable.
            query (str): pandas query. Default is ``selected``.
            title (str, optional): title of the plot. Default is ``variable``.
            kind (str, optional): Categorization of the plot.
                Accepted values are ``event_category``, ``particle_pdg``, and ``sample``
                Default is ``event_category``.
            track_cuts (list of tuples (var, operation, cut val), optional):
                List of cuts ot be made on track-level variables ("_v" in variable name)
                These get applied one at a time in self._selection
            select_longest (bool): if variable is a track-level variable
                setting to True will take the longest track of each slice
                    after QUERY and track_cuts have been applied
                select_longest = False might have some bugs...
            **plot_options: Additional options for matplotlib plot (e.g. range and bins).

        Returns:
            Figure, top subplot, and bottom subplot (ratio)

        """
        #if (detsys != None):
        self.detsys = detsys

        if not title:
            title = variable
        if not query:
            query = "nslice==1"

        # pandas bug https://github.com/pandas-dev/pandas/issues/16363
        if plot_options["range"][0] >= 0 and plot_options["range"][1] >= 0 and variable[-2:] != "_v":
            query += "& %s <= %g & %s >= %g" % (
                variable, plot_options["range"][1], variable, plot_options["range"][0])

        #eventually used to subdivide monte-carlo sample
        if kind == "event_category":
            categorization = self._categorize_entries
            cat_labels = category_labels
        elif kind == "particle_pdg":
            var = self.samples["mc"].query(query).eval(variable)
            if var.dtype == np.float32:
                categorization = self._categorize_entries_single_pdg
            else:
                categorization = self._categorize_entries_pdg
            cat_labels = pdg_labels
        elif kind == "interaction":
            categorization = self._categorize_entries_int
            cat_labels = int_labels
        elif kind == "flux":
            categorization = self._categorize_entries_flux
            cat_labels = flux_labels
        elif kind == "sample":
            return self._plot_variable_samples(variable, query, title, asymErrs, **plot_options)
        else:
            raise ValueError(
                "Unrecognized categorization, valid options are 'sample', 'event_category', and 'particle_pdg'")


        nu_pdg = "~(abs(nu_pdg) == 12 & ccnc == 0)"
        if ("ccpi0" in self.samples):
            nu_pdg = nu_pdg+" & ~(mcf_pass_ccpi0==1)"
        if ("ncpi0" in self.samples):
            nu_pdg = nu_pdg+" & ~(mcf_np0==1 & mcf_nmp==0 & mcf_nmm==0 & mcf_nem==0 & mcf_nep==0)" #note: mcf_pass_ccpi0 is wrong (includes 'mcf_actvol' while sample is in all cryostat)
        if ("ccnopi" in self.samples):
            nu_pdg = nu_pdg+" & ~(mcf_pass_ccnopi==1 & (nslice==0 | (slnunhits/slnhits)>0.1))"
        if ("cccpi" in self.samples):
            nu_pdg = nu_pdg+" & ~(mcf_pass_cccpi==1 & (nslice==0 | (slnunhits/slnhits)>0.1))"
        if ("nccpi" in self.samples):
            nu_pdg = nu_pdg+" & ~(mcf_pass_nccpi==1 & (nslice==0 | (slnunhits/slnhits)>0.1))"
        if ("ncnopi" in self.samples):
            nu_pdg = nu_pdg+" & ~(mcf_pass_ncnopi==1 & (nslice==0 | (slnunhits/slnhits)>0.1))"


        category, mc_plotted_variable = categorization(
            self.samples["mc"], variable, query=query, extra_cut=self.nu_pdg, track_cuts=track_cuts, select_longest=select_longest)


        var_dict = defaultdict(list)
        weight_dict = defaultdict(list)
        mc_genie_weights = self._get_genie_weight(
            self.samples["mc"], variable, query=query, extra_cut=self.nu_pdg, track_cuts=track_cuts,select_longest=select_longest, weightvar=genieweight)

        for c, v, w in zip(category, mc_plotted_variable, mc_genie_weights):
            var_dict[c].append(v)
            weight_dict[c].append(self.weights["mc"] * w)

        nue_genie_weights = self._get_genie_weight(
            self.samples["nue"], variable, query=query, track_cuts=track_cuts, select_longest=select_longest, weightvar=genieweight)

        category, nue_plotted_variable = categorization(
            self.samples["nue"], variable, query=query, track_cuts=track_cuts, select_longest=select_longest)

        for c, v, w in zip(category, nue_plotted_variable, nue_genie_weights):
            var_dict[c].append(v)
            weight_dict[c].append(self.weights["nue"] * w)

        if "ncpi0" in self.samples:
            ncpi0_genie_weights = self._get_genie_weight(
                    self.samples["ncpi0"], variable, query=query, track_cuts=track_cuts, select_longest=select_longest, weightvar=genieweight)
            category, ncpi0_plotted_variable = categorization(
                self.samples["ncpi0"], variable, query=query, track_cuts=track_cuts, select_longest=select_longest)

            for c, v, w in zip(category, ncpi0_plotted_variable, ncpi0_genie_weights):
                var_dict[c].append(v)
                weight_dict[c].append(self.weights["ncpi0"] * w)

        if "ccpi0" in self.samples:
            ccpi0_genie_weights = self._get_genie_weight(
                    self.samples["ccpi0"], variable, query=query, track_cuts=track_cuts, select_longest=select_longest, weightvar=genieweight)
            category, ccpi0_plotted_variable = categorization(
                self.samples["ccpi0"], variable, query=query, track_cuts=track_cuts, select_longest=select_longest)

            for c, v, w in zip(category, ccpi0_plotted_variable, ccpi0_genie_weights):
                var_dict[c].append(v)
                weight_dict[c].append(self.weights["ccpi0"] * w)

        if "ccnopi" in self.samples:
            ccnopi_genie_weights = self._get_genie_weight(
                    self.samples["ccnopi"], variable, query=query, track_cuts=track_cuts, select_longest=select_longest, weightvar=genieweight)
            category, ccnopi_plotted_variable = categorization(
                self.samples["ccnopi"], variable, query=query, track_cuts=track_cuts, select_longest=select_longest)

            for c, v, w in zip(category, ccnopi_plotted_variable, ccnopi_genie_weights):
                var_dict[c].append(v)
                weight_dict[c].append(self.weights["ccnopi"] * w)

        if "cccpi" in self.samples:
            cccpi_genie_weights = self._get_genie_weight(
                    self.samples["cccpi"], variable, query=query, track_cuts=track_cuts, select_longest=select_longest, weightvar=genieweight)
            category, cccpi_plotted_variable = categorization(
                self.samples["cccpi"], variable, query=query, track_cuts=track_cuts, select_longest=select_longest)

            for c, v, w in zip(category, cccpi_plotted_variable, cccpi_genie_weights):
                var_dict[c].append(v)
                weight_dict[c].append(self.weights["cccpi"] * w)

        if "nccpi" in self.samples:
            nccpi_genie_weights = self._get_genie_weight(
                    self.samples["nccpi"], variable, query=query, track_cuts=track_cuts, select_longest=select_longest, weightvar=genieweight)
            category, nccpi_plotted_variable = categorization(
                self.samples["nccpi"], variable, query=query, track_cuts=track_cuts, select_longest=select_longest)

            for c, v, w in zip(category, nccpi_plotted_variable, nccpi_genie_weights):
                var_dict[c].append(v)
                weight_dict[c].append(self.weights["nccpi"] * w)

        if "ncnopi" in self.samples:
            ncnopi_genie_weights = self._get_genie_weight(
                    self.samples["ncnopi"], variable, query=query, track_cuts=track_cuts, select_longest=select_longest, weightvar=genieweight)
            category, ncnopi_plotted_variable = categorization(
                self.samples["ncnopi"], variable, query=query, track_cuts=track_cuts, select_longest=select_longest)

            for c, v, w in zip(category, ncnopi_plotted_variable, ncnopi_genie_weights):
                var_dict[c].append(v)
                weight_dict[c].append(self.weights["ncnopi"] * w)

        if "dirt" in self.samples:
            dirt_genie_weights = self._get_genie_weight(
                self.samples["dirt"], variable, query=query, track_cuts=track_cuts, select_longest=select_longest, weightvar=genieweight)
            category, dirt_plotted_variable = categorization(
                self.samples["dirt"], variable, query=query, track_cuts=track_cuts, select_longest=select_longest)

            for c, v, w in zip(category, dirt_plotted_variable, dirt_genie_weights):
                var_dict[c].append(v)
                weight_dict[c].append(self.weights["dirt"] * w)

        if "lee" in self.samples:
            category, lee_plotted_variable = categorization(
                self.samples["lee"], variable, query=query, track_cuts=track_cuts, select_longest=select_longest)
            #print ('weight 1 : ',len(self.samples["lee"].query(query)["leeweight"]))
            #print ('weight 2 : ',len(self._selection("weightSplineTimesTuneTimesPPFX", self.samples["lee"], query=query, track_cuts=track_cuts, select_longest=select_longest)))
            #print ('track cuts : ',track_cuts)
            #print ('select_longest : ',select_longest)
            leeweight = self._get_genie_weight(
                self.samples["lee"], variable, query=query, track_cuts=track_cuts, select_longest=select_longest,weightsignal="leeweight", weightvar=genieweight)
            #self.samples["lee"].query(query)["leeweight"] * self._selection("weightSplineTimesTuneTimesPPFX", self.samples["lee"], query=query, track_cuts=track_cuts, select_longest=select_longest)

            for c, v, w in zip(category, lee_plotted_variable, leeweight):
                var_dict[c].append(v)
                weight_dict[c].append(self.weights["lee"] * w)

            lee_hist, lee_bins = np.histogram(
                var_dict[111],
                bins=plot_options["bins"],
                range=plot_options["range"],
                weights=weight_dict[111])

        if draw_data:
            ext_plotted_variable = self._selection(
                variable, self.samples["ext"], query=query, track_cuts=track_cuts, select_longest=select_longest)
            ext_plotted_variable = self._select_showers(
            ext_plotted_variable, variable, self.samples["ext"], query=query)
            data_plotted_variable = self._selection(
            variable, self.samples["data"], query=query, track_cuts=track_cuts, select_longest=select_longest)
            data_plotted_variable = self._select_showers(data_plotted_variable, variable,
                                                     self.samples["data"], query=query)


        if ratio:
            fig = plt.figure(figsize=(8, 7))
            gs = gridspec.GridSpec(2, 1, height_ratios=[2, 1])
            ax1 = plt.subplot(gs[0])
            ax2 = plt.subplot(gs[1])
        else:
            fig = plt.figure(figsize=(7, 5))
            gs = gridspec.GridSpec(1, 1)#, height_ratios=[2, 1])
            ax1 = plt.subplot(gs[0])



        # order stacked distributions
        order_dict = {}
        order_var_dict    = {}
        order_weight_dict = {}
        if (stacksort >= 1 and stacksort <= 3):
            # figure out ordering based on total yield.
            # Options are to have no exceptions (stacksort=1),
            # put eLEE on top (stacksort=2), or put nue+eLEE on top (stacksort=3)
            # put numu on top (stacksort >= 4)
            has1   = False
            has10  = False
            has11  = False
            has111 = False
            has12  = False
            for c in var_dict.keys():
                if stacksort >= 2:
                    if int(c)==111:
                        has111 = True
                        continue
                if stacksort == 3:
                    if int(c)==1:
                        has1 = True
                        continue
                    if int(c)==12:
                        has12 = True
                        continue

                    if int(c)==10:
                        has10 = True
                        continue
                    if int(c)==11:
                        has11 = True
                        continue
                order_dict[c] = sum(weight_dict[c])
                order_dict = {k: v for k, v in sorted(order_dict.items(), key=lambda item: item[1])}
            if has1:
                order_dict[1] = sum(weight_dict[1])
            if has1:
                order_dict[12] = sum(weight_dict[12])
            if has10:
                order_dict[10] = sum(weight_dict[10])
            if has11:
                order_dict[11] = sum(weight_dict[11])
            if has111:
                order_dict[111] = sum(weight_dict[111])
            # now that the order has been sorted out, fill the actual dicts
            for c in order_dict.keys():
                order_var_dict[c] = var_dict[c]
            for c in order_dict.keys():
                order_weight_dict[c] = weight_dict[c]
        elif stacksort == 4:
            #put the numu stuff on top
            hasprotons = 23 in var_dict.keys()
            keys = list(var_dict.keys())
            if hasprotons:
                keys.remove(22)#take them out
                keys.remove(23)
                keys.remove(24)
                keys.remove(25)
                keys.append(22)#and put at end
                keys.append(23)
                keys.append(24)
                keys.append(25)

            for c in keys:
                order_var_dict[c] = var_dict[c]
                order_weight_dict[c] = weight_dict[c]
        else:
            for c in var_dict.keys():
                order_var_dict[c] = var_dict[c]
            for c in weight_dict.keys():
                order_weight_dict[c] = weight_dict[c]


        total = sum(sum(order_weight_dict[c]) for c in order_var_dict)
        if draw_data:
            total += sum([self.weights["ext"]] * len(ext_plotted_variable))
        labels = [
            "%s: %.1f" % (cat_labels[c], sum(order_weight_dict[c])) \
            if sum(order_weight_dict[c]) else ""
            for c in order_var_dict.keys()
        ]


        if kind == "event_category":
            plot_options["color"] = [category_colors[c]
                                     for c in order_var_dict.keys()]
        elif kind == "particle_pdg":
            plot_options["color"] = [pdg_colors[c]
                                     for c in order_var_dict.keys()]
        elif kind == "flux":
            plot_options["color"] = [flux_colors[c]
                                     for c in order_var_dict.keys()]
        else:
            plot_options["color"] = [int_colors[c]
                                     for c in order_var_dict.keys()]

        #for key in order_var_dict:
        #    print ('key ',key)
        #    print ('val ',order_var_dict[key])
        #for key in order_weight_dict:
        #    print ('key ',key)
        #    print ('val ',order_weight_dict[key])

        stacked = ax1.hist(
            order_var_dict.values(),
            weights=list(order_weight_dict.values()),
            stacked=True,
            label=labels,
            **plot_options)

        total_array = np.concatenate(list(order_var_dict.values()))
        total_weight = np.concatenate(list(order_weight_dict.values()))

        #print(stacked)
        #print(labels)

        plot_options.pop('color', None)

        total_hist, total_bins = np.histogram(
            total_array, weights=total_weight,  **plot_options)

        if draw_data:
            ext_weight = [self.weights["ext"]] * len(ext_plotted_variable)
            n_ext, ext_bins, patches = ax1.hist(
            ext_plotted_variable,
            weights=ext_weight,
            bottom=total_hist,
            label="EXT: %.1f" % sum(ext_weight) if sum(ext_weight) else "",
            hatch="//",
            color="white",
            **plot_options)

            total_array = np.concatenate([total_array, ext_plotted_variable])
            total_weight = np.concatenate([total_weight, ext_weight])

        n_tot, bin_edges, patches = ax1.hist(
        total_array,
        weights=total_weight,
        histtype="step",
        edgecolor="black",
        **plot_options)

        bincenters = 0.5 * (bin_edges[1:] + bin_edges[:-1])
        mc_uncertainties, bins = np.histogram(
            mc_plotted_variable, **plot_options)
        err_mc = np.array(
            [n * self.weights["mc"] * self.weights["mc"] for n in mc_uncertainties])
        #if ("mc" in self.detsys.keys()):
        #    self.detsys["mc"] = self.load_detsys_errors(variable,DETSYSPATH,bin_edges)
        sys_mc = self.add_detsys_error("mc",mc_uncertainties,self.weights["mc"])

        nue_uncertainties, bins = np.histogram(
            nue_plotted_variable, **plot_options)
        err_nue = np.array(
            [n * self.weights["nue"] * self.weights["nue"] for n in nue_uncertainties])
        #if ("nue" in self.detsys.keys()):
        #    self.detsys["nue"] = self.load_detsys_errors(variable,DETSYSPATH,bin_edges)
        sys_nue = self.add_detsys_error("nue",nue_uncertainties,self.weights["nue"])

        err_dirt = np.array([0 for n in mc_uncertainties])
        if "dirt" in self.samples:
            dirt_uncertainties, bins = np.histogram(
                dirt_plotted_variable, **plot_options)
            err_dirt = np.array(
                [n * self.weights["dirt"] * self.weights["dirt"] for n in dirt_uncertainties])
        #if ("dirt" in self.detsys.keys()):
        #    self.detsys["dirt"] = self.load_detsys_errors(variable,DETSYSPATH,bin_edges)
            sys_dirt = self.add_detsys_error("dirt",dirt_uncertainties,self.weights["dirt"])

        err_lee = np.array([0 for n in mc_uncertainties])
        if "lee" in self.samples:
            if isinstance(plot_options["bins"], Iterable):
                lee_bins = plot_options["bins"]
            else:
                bin_size = (plot_options["range"][1] - plot_options["range"][0])/plot_options["bins"]
                lee_bins = [plot_options["range"][0]+n*bin_size for n in range(plot_options["bins"]+1)]

            if variable[-2:] != "_v":
                binned_lee = pd.cut(self.samples["lee"].query(query).eval(variable), lee_bins)
                err_lee = self.samples["lee"].query(query).groupby(binned_lee)['leeweight'].agg(
                    "sum").values * self.weights["lee"] * self.weights["lee"]

        err_ncpi0 = np.array([0 for n in mc_uncertainties])
        sys_ncpi0 = np.array([0 for n in mc_uncertainties])
        if "ncpi0" in self.samples:
            ncpi0_uncertainties, bins = np.histogram(
                ncpi0_plotted_variable, **plot_options)
            err_ncpi0 = np.array(
                [n * self.weights["ncpi0"] * self.weights["ncpi0"] for n in ncpi0_uncertainties])
            if ("ncpi0" in self.detsys.keys()):
                self.detsys["ncpi0"] = self.load_detsys_errors(variable,DETSYSPATH,bin_edges)
            sys_ncpi0 = self.add_detsys_error("ncpi0",ncpi0_uncertainties,self.weights["ncpi0"])

        err_ccpi0 = np.array([0 for n in mc_uncertainties])
        sys_ccpi0 = np.array([0 for n in mc_uncertainties])
        if "ccpi0" in self.samples:
            ccpi0_uncertainties, bins = np.histogram(
                ccpi0_plotted_variable, **plot_options)
            err_ccpi0 = np.array(
                [n * self.weights["ccpi0"] * self.weights["ccpi0"] for n in ccpi0_uncertainties])
            if ("ccpi0" in self.detsys.keys()):
                self.detsys["ccpi0"] = self.load_detsys_errors(variable,DETSYSPATH,bin_edges)
            sys_ccpi0 = self.add_detsys_error("ccpi0",ccpi0_uncertainties,self.weights["ccpi0"])

        err_ccnopi = np.array([0 for n in mc_uncertainties])
        sys_ccnopi = np.array([0 for n in mc_uncertainties])
        if "ccnopi" in self.samples:
            ccnopi_uncertainties, bins = np.histogram(
                ccnopi_plotted_variable, **plot_options)
            err_ccnopi = np.array(
                [n * self.weights["ccnopi"] * self.weights["ccnopi"] for n in ccnopi_uncertainties])
            if ("ccnopi" in self.detsys.keys()):
                self.detsys["ccnopi"] = self.load_detsys_errors(variable,DETSYSPATH,bin_edges)
            sys_ccnopi = self.add_detsys_error("ccnopi",ccnopi_uncertainties,self.weights["ccnopi"])

        err_cccpi = np.array([0 for n in mc_uncertainties])
        sys_cccpi = np.array([0 for n in mc_uncertainties])
        if "cccpi" in self.samples:
            cccpi_uncertainties, bins = np.histogram(
                cccpi_plotted_variable, **plot_options)
            err_cccpi = np.array(
                [n * self.weights["cccpi"] * self.weights["cccpi"] for n in cccpi_uncertainties])
            if ("cccpi" in self.detsys.keys()):
                self.detsys["cccpi"] = self.load_detsys_errors(variable,DETSYSPATH,bin_edges)
            sys_cccpi = self.add_detsys_error("cccpi",cccpi_uncertainties,self.weights["cccpi"])

        err_nccpi = np.array([0 for n in mc_uncertainties])
        sys_nccpi = np.array([0 for n in mc_uncertainties])
        if "nccpi" in self.samples:
            nccpi_uncertainties, bins = np.histogram(
                nccpi_plotted_variable, **plot_options)
            err_nccpi = np.array(
                [n * self.weights["nccpi"] * self.weights["nccpi"] for n in nccpi_uncertainties])
            if ("nccpi" in self.detsys.keys()):
                self.detsys["nccpi"] = self.load_detsys_errors(variable,DETSYSPATH,bin_edges)
            sys_nccpi = self.add_detsys_error("nccpi",nccpi_uncertainties,self.weights["nccpi"])

        err_ncnopi = np.array([0 for n in mc_uncertainties])
        sys_ncnopi = np.array([0 for n in mc_uncertainties])
        if "ncnopi" in self.samples:
            ncnopi_uncertainties, bins = np.histogram(
                ncnopi_plotted_variable, **plot_options)
            err_ncnopi = np.array(
                [n * self.weights["ncnopi"] * self.weights["ncnopi"] for n in ncnopi_uncertainties])
            if ("ncnopi" in self.detsys.keys()):
                self.detsys["ncnopi"] = self.load_detsys_errors(variable,DETSYSPATH,bin_edges)
            sys_ncnopi = self.add_detsys_error("ncnopi",ncnopi_uncertainties,self.weights["ncnopi"])

        if draw_data:
            err_ext = np.array(
                [n * self.weights["ext"] * self.weights["ext"] for n in n_ext])
        else:
            err_ext = np.zeros(len(err_mc))

        exp_err    = np.sqrt(err_mc + err_ext + err_nue + err_dirt + err_ncpi0 + err_ccpi0 + err_ccnopi + err_cccpi + err_nccpi + err_ncnopi)
        #print("counting_err: {}".format(exp_err))
        if "dirt" in self.samples:
            detsys_err = sys_mc + sys_nue + sys_dirt + sys_ncpi0 + sys_ccpi0 + sys_ccnopi + sys_cccpi + sys_nccpi + sys_ncnopi
        else:
            detsys_err = sys_mc + sys_nue + sys_ncpi0 + sys_ccpi0 + sys_ccnopi + sys_cccpi + sys_nccpi + sys_ncnopi
        #print("detsys_err: {}".format(detsys_err))
        exp_err = np.sqrt(exp_err**2 + detsys_err**2)
        #print ('total exp_err : ', exp_err)

        bin_size = [(bin_edges[i + 1] - bin_edges[i]) / 2
                    for i in range(len(bin_edges) - 1)]

        self.cov           = np.zeros([len(exp_err), len(exp_err)])
        self.cov_mc_stat   = np.zeros([len(exp_err), len(exp_err)])
        self.cov_mc_detsys = np.zeros([len(exp_err), len(exp_err)])
        self.cov_data_stat = np.zeros([len(exp_err), len(exp_err)])

        self.cov_mc_stat[np.diag_indices_from(self.cov_mc_stat)]     = (err_mc + err_ext + err_nue + err_dirt + err_ncpi0 + err_ccpi0 + err_ccnopi + err_cccpi + err_nccpi + err_ncnopi)
        if "dirt" in self.samples:
            self.cov_mc_detsys[np.diag_indices_from(self.cov_mc_detsys)] = (sys_mc + sys_nue + sys_dirt + sys_ncpi0 + sys_ccpi0 + sys_ccnopi + sys_cccpi + sys_nccpi + sys_ncnopi)**2
        else:
            self.cov_mc_detsys[np.diag_indices_from(self.cov_mc_detsys)] = (sys_mc + sys_nue + sys_ncpi0 + sys_ccpi0 + sys_ccnopi + sys_cccpi + sys_nccpi + sys_ncnopi)**2

        if draw_sys:
            if (COVMATRIX == ""):
                print("IN COVMATRIX_XS_PPFX")
                self.cov = (self.sys_err("weightsPPFX",variable,query,plot_options["range"],plot_options["bins"],genieweight)+
                            self.sys_err("weightsGenie",variable,query,plot_options["range"],plot_options["bins"],genieweight)+
                            self.sys_err("weightsReint",variable,query, plot_options["range"],plot_options["bins"],genieweight))
                if draw_geoSys :
                    print("Add Drawing Geo Sys")
                    self.cov += self.sys_err_NuMIGeo("weightsNuMIGeo",variable,query,plot_options["range"],plot_options["bins"],genieweight)

                #self.cov = (self.sys_err("weightsReint",variable,query,plot_options["range"],plot_options["bins"],genieweight))

            else:
                self.cov = self.get_SBNFit_cov_matrix(COVMATRIX,len(bin_edges)-1)
            exp_err = np.sqrt( np.diag((self.cov + self.cov_mc_stat + self.cov_mc_detsys))) # + exp_err*exp_err)

            np.set_printoptions(formatter={'float': lambda x: "{0:0.3f}".format(x)})
            print("draw Sys")
            
            #cov = self.sys_err("weightsFlux", variable, query, plot_options["range"], plot_options["bins"], "weightSplineTimesTuneTimesPPFX")


        if "lee" in self.samples:
            if kind == "event_category":
                try:
                    self.significance = self._sigma_calc_matrix(
                        lee_hist, n_tot-lee_hist, scale_factor=1.01e21/self.pot, cov=(self.cov+self.cov_mc_stat))
                    self.significance_likelihood = self._sigma_calc_likelihood(
                        lee_hist, n_tot-lee_hist, np.sqrt(err_mc + err_ext + err_nue + err_dirt + err_ncpi0 + err_ccpi0 + err_ccnopi + err_cccpi + err_nccpi + err_ncnopi), scale_factor=1.01e21/self.pot)
                    # area normalized version
                    #normLEE = 68. / np.sum(n_tot)
                    #normSM  = 68. / np.sum(n_tot-lee_hist)
                    #self.significance_likelihood = self._sigma_calc_likelihood(
                    #    lee_hist * normLEE, (n_tot-lee_hist) * normSM, np.sqrt(normSM) * np.sqrt(err_mc + err_ext + err_nue + err_dirt + err_ncpi0 + err_ccpi0 + err_ccnopi + err_cccpi + err_nccpi + err_ncnopi), scale_factor=1.0)
                except (np.linalg.LinAlgError, ValueError) as err:
                    print("Error calculating the significance", err)
                    self.significance = -1
                    self.significance_likelihood = -1
        # old error-bar plotting
        #ax1.bar(bincenters, n_tot, facecolor='none',
        #       edgecolor='none', width=0, yerr=exp_err)
        ax1.bar(bincenters, exp_err*2,width=[n*2 for n in bin_size],facecolor='tab:blue',alpha=0.2,bottom=(n_tot-exp_err))
        #ax1.errorbar(bincenters,n_tot,yerr=exp_err,fmt='k.',lw=35,alpha=0.2)
        '''
        ax1.fill_between(
            bincenters+(bincenters[1]-bincenters[0])/2.,
            n_tot-exp_err,
            n_tot+exp_err,
            step="pre",
            color="grey",
            alpha=0.5)
        '''

        if draw_data:
            n_data, bins = np.histogram(data_plotted_variable, **plot_options)
            self.data = n_data
            data_err = self._data_err(n_data,asymErrs)

            self.cov_data_stat[np.diag_indices_from(self.cov_data_stat)] = n_data

        #self.cov_data_stat[np.diag_indices_from(self.cov_data_stat)] = n_data
        # This is a hacky workaround -- I should be ashamed of myself, EG
        else:
            n_data = np.zeros(len(bin_size))

        if sum(n_data) > 0:
            ax1.errorbar(
                bincenters,
                n_data,
                xerr=bin_size,
                yerr=data_err,
                fmt='ko',
                label="NuMI: %i" % len(data_plotted_variable) if len(data_plotted_variable) else "")

        #frac = self.deltachisqfakedata(plot_options["range"][0], plot_options["range"][-1], np.array([1,1,1,5,5,5]), np.array([1,1,1,5,5,5]), 70)
        if "lee" in self.samples:
            self.sigma_shapeonly = self.deltachisqfakedata(plot_options["range"][0], plot_options["range"][-1], n_tot, (n_tot-lee_hist), 70)


        chistatonly, aab, aac = self._chisq_full_covariance(n_data,n_tot,CNP=True,STATONLY=True)
        self.stats['pvaluestatonly'] = (1 - scipy.stats.chi2.cdf(chistatonly,aac))
        
        if (draw_sys):

            #chisq = self._chisquare(n_data, n_tot, exp_err)
            #self.stats['chisq'] = chisq
            chisqCNP = self._chisq_CNP(n_data,n_tot)
            #self.stats['chisqCNP'] = chisqCNP
            #print ('chisq for data/mc agreement with diagonal terms only : %.02f'%(chisq))
            #print ('chisq for data/mc agreement with diagonal terms only : %.02f'%(self._chisquare(n_data, n_tot, np.sqrt(np.diag(cov)))))
        
            #chiarea, aab, aac = self._chisq_full_covariance(n_tot-lee_hist,n_tot,CNP=True,STATONLY=True,AREANORMED=True)
            chicov, chinocov,dof = self._chisq_full_covariance(n_data,n_tot,CNP=True)#,USEFULLCOV=True)
            if "lee" in self.samples:
                chilee, chileenocov,dof = self._chisq_full_covariance(n_tot-lee_hist,n_tot,CNP=True)
            #self.stats['chisq full covariance'] = chicov
            #self.stats['chisq full covariance (diagonal only)'] = chinocov
            self.stats['dof']            = dof
            self.stats['chisqstatonly']  = chistatonly
            #self.stats['chiarea']  = chiarea
            self.stats['pvaluediag']     = (1 - scipy.stats.chi2.cdf(chinocov,dof))
            self.stats['chisqdiag']     = chinocov

            #self.stats['parea']          = (1 - scipy.stats.chi2.cdf(chiarea,dof))
            self.stats['chisq']          = chicov
            #self.stats['chilee']          = chilee
            self.stats['pvalue']         = (1 - scipy.stats.chi2.cdf(chicov,dof))
            if "lee" in self.samples:
                self.stats['pvaluelee']         = (1 - scipy.stats.chi2.cdf(chilee,dof))
            #print ('chisq for data/mc agreement with full covariance is : %.02f. without cov : %.02f'%(chicov,chinocov))

            #self.print_stats()
        if (ncol > 3):
            leg = ax1.legend(
                frameon=False, ncol=4, title=r'MicroBooNE Preliminary %g POT' % self.pot,
                prop={'size': fig.get_figwidth()})
        else:
            leg = ax1.legend(
                frameon=False, ncol=2, title=r'MicroBooNE Preliminary %g POT' % self.pot)
        leg._legend_box.align = "left"
        plt.setp(leg.get_title(), fontweight='bold')

        unit = title[title.find("[") +
                     1:title.find("]")] if "[" and "]" in title else ""
        x_range = plot_options["range"][1] - plot_options["range"][0]
        if isinstance(plot_options["bins"], Iterable):
            ax1.set_ylabel("N. Entries",fontsize=16)
        else:
            ax1.set_ylabel(
                "N. Entries / %.2g %s" % (round(x_range / plot_options["bins"],2), unit),fontsize=16)

        if (ratio==True):
            ax1.set_xticks([])

        ax1.set_xlim(plot_options["range"][0], plot_options["range"][1])

        '''
        ax1.fill_between(
            bincenters+(bincenters[1]-bincenters[0])/2.,
            n_tot - exp_err,
            n_tot + exp_err,
            step="pre",
            color="grey",
            alpha=0.5)
        '''

        if (ratio==True):
            if draw_data == False:
                n_data = np.zeros(len(n_tot))
                data_err = (np.zeros(len(n_tot)),np.zeros(len(n_tot)))
            else:
                self.chisqdatamc = self._chisquare(n_data, n_tot, exp_err)
            self._draw_ratio(ax2, bins, n_tot, n_data, exp_err, data_err)

        if ( (chisq==True) and (ratio==True)):
            if sum(n_data) > 0:
                ax2.text(
                    0.725,
                    0.9,
                    r'$\chi^2 /$n.d.f. = %.2f' % (self.stats['chisq']/self.stats['dof']) +
                             #'K.S. prob. = %.2f' % scipy.stats.ks_2samp(n_data, n_tot)[1],
                             ', p = %.2f' % (1 - scipy.stats.chi2.cdf(self.stats['chisq'],self.stats['dof'])) +
                             ', O/P = %.2f' % (sum(n_data)/sum(n_tot)) +
                             ' $\pm$ %.2f' % (self._data_err([sum(n_data)],asymErrs)[0]/sum(n_tot)),
                    va='center',
                    ha='center',
                    ma='right',
                    fontsize=12,
                    transform=ax2.transAxes)

        if (ratio==True):
            ax2.set_xlabel(title,fontsize=18)
            ax2.set_xlim(plot_options["range"][0], plot_options["range"][1])
        else:
            ax1.set_xlabel(title,fontsize=18)

        fig.tight_layout()
        if title == variable:
            ax1.set_title(query)
        #     fig.suptitle(query)
        # fig.savefig("plots/%s_cat.pdf" % variable.replace("/", "_"))

        if ratio and draw_data:
            return fig, ax1, ax2, stacked, labels, n_ext
        elif ratio:
            return fig, ax1, ax2, stacked, labels
        elif draw_data:
            return fig, ax1, stacked, labels, n_ext
        else:
            return fig, ax1, stacked, labels

    def _plot_variable_samples(self, variable, query, title, asymErrs, **plot_options):

        '''
        nu_pdg = "~(abs(nu_pdg) == 12 & ccnc == 0)"
        if ("ccpi0" in self.samples):
            nu_pdg = nu_pdg+" & ~(mcf_pass_ccpi0==1)"
        if ("ncpi0" in self.samples):
            nu_pdg = nu_pdg+" & ~(mcf_np0==1 & mcf_nmp==0 & mcf_nmm==0 & mcf_nem==0 & mcf_nep==0)" #note: mcf_pass_ccpi0 is wrong (includes 'mcf_actvol' while sample is in all cryostat)
        if ("ccnopi" in self.samples):
            nu_pdg = nu_pdg+" & ~(mcf_pass_ccnopi==1 & (nslice==0 | (slnunhits/slnhits)>0.1))"
        if ("cccpi" in self.samples):
            nu_pdg = nu_pdg+" & ~(mcf_pass_cccpi==1 & (nslice==0 | (slnunhits/slnhits)>0.1))"
        if ("nccpi" in self.samples):
            nu_pdg = nu_pdg+" & ~(mcf_pass_nccpi==1 & (nslice==0 | (slnunhits/slnhits)>0.1))"
        if ("ncnopi" in self.samples):
            nu_pdg = nu_pdg+" & ~(mcf_pass_ncnopi==1 & (nslice==0 | (slnunhits/slnhits)>0.1))"
        '''

        if plot_options["range"][0] >= 0 and plot_options["range"][1] >= 0 and variable[-2:] != "_v":
            query += "& %s <= %g & %s >= %g" % (
                variable, plot_options["range"][1], variable, plot_options["range"][0])

        mc_plotted_variable = self._selection(
            variable, self.samples["mc"], query=query, extra_cut=self.nu_pdg)
        mc_plotted_variable = self._select_showers(
            mc_plotted_variable, variable, self.samples["mc"], query=query, extra_cut=self.nu_pdg)
        mc_weight = [self.weights["mc"]] * len(mc_plotted_variable)

        nue_plotted_variable = self._selection(
            variable, self.samples["nue"], query=query)
        nue_plotted_variable = self._select_showers(
            nue_plotted_variable, variable, self.samples["nue"], query=query)
        nue_weight = [self.weights["nue"]] * len(nue_plotted_variable)

        ext_plotted_variable = self._selection(
            variable, self.samples["ext"], query=query)
        ext_plotted_variable = self._select_showers(
            ext_plotted_variable, variable, self.samples["ext"], query=query)
        ext_weight = [self.weights["ext"]] * len(ext_plotted_variable)

        if "dirt" in self.samples:
            dirt_plotted_variable = self._selection(
                variable, self.samples["dirt"], query=query)
            dirt_plotted_variable = self._select_showers(
                dirt_plotted_variable, variable, self.samples["dirt"], query=query)
            dirt_weight = [self.weights["dirt"]] * len(dirt_plotted_variable)

        if "ncpi0" in self.samples:
            ncpi0_plotted_variable = self._selection(
                variable, self.samples["ncpi0"], query=query)
            ncpi0_plotted_variable = self._select_showers(
                ncpi0_plotted_variable, variable, self.samples["ncpi0"], query=query)
            ncpi0_weight = [self.weights["ncpi0"]] * len(ncpi0_plotted_variable)

        if "ccpi0" in self.samples:
            ccpi0_plotted_variable = self._selection(
                variable, self.samples["ccpi0"], query=query)
            ccpi0_plotted_variable = self._select_showers(
                ccpi0_plotted_variable, variable, self.samples["ccpi0"], query=query)
            ccpi0_weight = [self.weights["ccpi0"]] * len(ccpi0_plotted_variable)

        if "ccnopi" in self.samples:
            ccnopi_plotted_variable = self._selection(
                variable, self.samples["ccnopi"], query=query)
            ccnopi_plotted_variable = self._select_showers(
                ccnopi_plotted_variable, variable, self.samples["ccnopi"], query=query)
            ccnopi_weight = [self.weights["ccnopi"]] * len(ccnopi_plotted_variable)

        if "cccpi" in self.samples:
            cccpi_plotted_variable = self._selection(
                variable, self.samples["cccpi"], query=query)
            cccpi_plotted_variable = self._select_showers(
                cccpi_plotted_variable, variable, self.samples["cccpi"], query=query)
            cccpi_weight = [self.weights["cccpi"]] * len(cccpi_plotted_variable)

        if "nccpi" in self.samples:
            nccpi_plotted_variable = self._selection(
                variable, self.samples["nccpi"], query=query)
            nccpi_plotted_variable = self._select_showers(
                nccpi_plotted_variable, variable, self.samples["nccpi"], query=query)
            nccpi_weight = [self.weights["nccpi"]] * len(nccpi_plotted_variable)

        if "ncnopi" in self.samples:
            ncnopi_plotted_variable = self._selection(
                variable, self.samples["ncnopi"], query=query)
            ncnopi_plotted_variable = self._select_showers(
                ncnopi_plotted_variable, variable, self.samples["ncnopi"], query=query)
            ncnopi_weight = [self.weights["ncnopi"]] * len(ncnopi_plotted_variable)

        if "lee" in self.samples:
            lee_plotted_variable = self._selection(
                variable, self.samples["lee"], query=query)
            lee_plotted_variable = self._select_showers(
                lee_plotted_variable, variable, self.samples["lee"], query=query)
            lee_weight = self.samples["lee"].query(query)["leeweight"] * self.weights["lee"]


        data_plotted_variable = self._selection(
            variable, self.samples["data"], query=query)
        data_plotted_variable = self._select_showers(
            data_plotted_variable,
            variable,
            self.samples["data"],
            query=query)

        if "dirt" in self.samples:
            total_variable = np.concatenate(
                [mc_plotted_variable,
                 nue_plotted_variable,
                 ext_plotted_variable,
                 dirt_plotted_variable])
            total_weight = np.concatenate(
                [mc_weight, nue_weight, ext_weight, dirt_weight])
        else:
            total_variable = np.concatenate(
                [mc_plotted_variable, nue_plotted_variable, ext_plotted_variable])
            total_weight = np.concatenate(
                [mc_weight, nue_weight, ext_weight])

        if "lee" in self.samples:
            total_variable = np.concatenate(
                [total_variable,
                 lee_plotted_variable])
            total_weight = np.concatenate(
                [total_weight, lee_weight])

        if "ncpi0" in self.samples:
            total_variable = np.concatenate(
                [total_variable,
                 ncpi0_plotted_variable])
            total_weight = np.concatenate(
                [total_weight, ncpi0_weight])

        if "ccpi0" in self.samples:
            total_variable = np.concatenate(
                [total_variable,
                 ccpi0_plotted_variable])
            total_weight = np.concatenate(
                [total_weight, ccpi0_weight])

        if "ccnopi" in self.samples:
            total_variable = np.concatenate(
                [total_variable,
                 ccnopi_plotted_variable])
            total_weight = np.concatenate(
                [total_weight, ccnopi_weight])

        if "cccpi" in self.samples:
            total_variable = np.concatenate(
                [total_variable,
                 cccpi_plotted_variable])
            total_weight = np.concatenate(
                [total_weight, cccpi_weight])

        if "nccpi" in self.samples:
            total_variable = np.concatenate(
                [total_variable,
                 nccpi_plotted_variable])
            total_weight = np.concatenate(
                [total_weight, nccpi_weight])

        if "ncnopi" in self.samples:
            total_variable = np.concatenate(
                [total_variable,
                 ncnopi_plotted_variable])
            total_weight = np.concatenate(
                [total_weight, ncnopi_weight])


        fig = plt.figure(figsize=(7, 7))
        #fig = plt.figure(figsize=(8, 7))
        gs = gridspec.GridSpec(1, 1)#, height_ratios=[2, 1])
        #gs = gridspec.GridSpec(2, 1, height_ratios=[2, 1])
        print (gs[0])

        ax1 = plt.subplot(gs[0])
        #ax2 = plt.subplot(gs[1])

        n_mc, mc_bins, patches = ax1.hist(
            mc_plotted_variable,
            weights=mc_weight,
            label="NuMI overlay: %.1f entries" % sum(mc_weight),
            **plot_options)

        n_nue, nue_bins, patches = ax1.hist(
            nue_plotted_variable,
            bottom=n_mc,
            weights=nue_weight,
            label=r"$\nu_{e}$ overlay: %.1f entries" % sum(nue_weight),
            **plot_options)

        n_dirt = 0
        if "dirt" in self.samples:
            n_dirt, dirt_bins, patches = ax1.hist(
                dirt_plotted_variable,
                bottom=n_mc + n_nue,
                weights=dirt_weight,
                label=r"Dirt: %.1f entries" % sum(dirt_weight),
                **plot_options)

        n_ncpi0 = 0
        if "ncpi0" in self.samples:
            n_ncpi0, ncpi0_bins, patches = ax1.hist(
                ncpi0_plotted_variable,
                bottom=n_mc + n_nue + n_dirt,
                weights=ncpi0_weight,
                label=r"NC$\pi^0$: %.1f entries" % sum(ncpi0_weight),
                **plot_options)

        n_ccpi0 = 0
        if "ccpi0" in self.samples:
            n_ccpi0, ccpi0_bins, patches = ax1.hist(
                ccpi0_plotted_variable,
                bottom=n_mc + n_nue + n_dirt + n_ncpi0,
                weights=ccpi0_weight,
                label=r"CC$\pi^0$: %.1f entries" % sum(ccpi0_weight),
                **plot_options)

        n_ccnopi = 0
        if "ccnopi" in self.samples:
            n_ccnopi, ccnopi_bins, patches = ax1.hist(
                ccnopi_plotted_variable,
                bottom=n_mc + n_nue + n_dirt + n_ncpi0 + n_ccpi0,
                weights=ccnopi_weight,
                label=r"CCNoPi: %.1f entries" % sum(ccnopi_weight),
                **plot_options)

        n_cccpi = 0
        if "cccpi" in self.samples:
            n_cccpi, cccpi_bins, patches = ax1.hist(
                cccpi_plotted_variable,
                bottom=n_mc + n_nue + n_dirt + n_ncpi0 + n_ccpi0 + n_ccnopi,
                weights=cccpi_weight,
                label=r"CCPi+: %.1f entries" % sum(cccpi_weight),
                **plot_options)

        n_nccpi = 0
        if "nccpi" in self.samples:
            n_nccpi, nccpi_bins, patches = ax1.hist(
                nccpi_plotted_variable,
                bottom=n_mc + n_nue + n_dirt + n_ncpi0 + n_ccpi0 + n_ccnopi + n_cccpi,
                weights=nccpi_weight,
                label=r"NCcPi: %.1f entries" % sum(nccpi_weight),
                **plot_options)

        n_ncnopi = 0
        if "ncnopi" in self.samples:
            n_ncnopi, ncnopi_bins, patches = ax1.hist(
                ncnopi_plotted_variable,
                bottom=n_mc + n_nue + n_dirt + n_ncpi0 + n_ccpi0 + n_ccnopi + n_cccpi + n_nccpi,
                weights=ncnopi_weight,
                label=r"Ncnopi: %.1f entries" % sum(ncnopi_weight),
                **plot_options)

        n_lee = 0
        if "lee" in self.samples:
            n_lee, lee_bins, patches = ax1.hist(
                lee_plotted_variable,
                bottom=n_mc + n_nue + n_dirt + n_ncpi0 + n_ccpi0 + n_ccnopi + n_cccpi + n_nccpi + n_ncnopi,
                weights=lee_weight,
                label=r"MiniBooNE LEE: %.1f entries" % sum(lee_weight),
                **plot_options)

        n_ext, ext_bins, patches = ax1.hist(
            ext_plotted_variable,
            bottom=n_mc + n_nue + n_dirt + n_lee + n_ncpi0 + n_ccpi0 + n_ccnopi + n_cccpi + n_nccpi + n_ncnopi,
            weights=ext_weight,
            label="EXT: %.1f entries" % sum(ext_weight),
            hatch="//",
            color="white",
            **plot_options)

        n_tot, tot_bins, patches = ax1.hist(
            total_variable,
            weights=total_weight,
            histtype="step",
            edgecolor="black",
            **plot_options)

        mc_uncertainties, bins = np.histogram(
            mc_plotted_variable, **plot_options)
        nue_uncertainties, bins = np.histogram(
            nue_plotted_variable, **plot_options)
        ext_uncertainties, bins = np.histogram(
            ext_plotted_variable, **plot_options)
        err_mc = np.array([n * self.weights["mc"] * self.weights["mc"] for n in mc_uncertainties])
        err_nue = np.array(
            [n * self.weights["nue"] * self.weights["nue"] for n in nue_uncertainties])
        err_ext = np.array(
            [n * self.weights["ext"] * self.weights["ext"] for n in ext_uncertainties])
        err_dirt = np.array([0 for n in n_mc])
        err_lee = np.array([0 for n in n_mc])
            
        if "dirt" in self.samples:
            dirt_uncertainties, bins = np.histogram(dirt_plotted_variable, **plot_options)
            err_dirt = np.array(
                [n * self.weights["dirt"] * self.weights["dirt"] for n in dirt_uncertainties])

        err_ncpi0 = np.array([0 for n in n_mc])
        if "ncpi0" in self.samples:
            ncpi0_uncertainties, bins = np.histogram(ncpi0_plotted_variable, **plot_options)
            err_ncpi0 = np.array(
                [n * self.weights["ncpi0"] * self.weights["ncpi0"] for n in ncpi0_uncertainties])

        err_ccpi0 = np.array([0 for n in n_mc])
        if "ccpi0" in self.samples:
            ccpi0_uncertainties, bins = np.histogram(ccpi0_plotted_variable, **plot_options)
            err_ccpi0 = np.array(
                [n * self.weights["ccpi0"] * self.weights["ccpi0"] for n in ccpi0_uncertainties])

        err_ccnopi = np.array([0 for n in n_mc])
        if "ccnopi" in self.samples:
            ccnopi_uncertainties, bins = np.histogram(ccnopi_plotted_variable, **plot_options)
            err_ccnopi = np.array(
                [n * self.weights["ccnopi"] * self.weights["ccnopi"] for n in ccnopi_uncertainties])

        err_cccpi = np.array([0 for n in n_mc])
        if "cccpi" in self.samples:
            cccpi_uncertainties, bins = np.histogram(cccpi_plotted_variable, **plot_options)
            err_cccpi = np.array(
                [n * self.weights["cccpi"] * self.weights["cccpi"] for n in cccpi_uncertainties])

        err_nccpi = np.array([0 for n in n_mc])
        if "nccpi" in self.samples:
            nccpi_uncertainties, bins = np.histogram(nccpi_plotted_variable, **plot_options)
            err_nccpi = np.array(
                [n * self.weights["nccpi"] * self.weights["nccpi"] for n in nccpi_uncertainties])

        err_ncnopi = np.array([0 for n in n_mc])
        if "ncnopi" in self.samples:
            ncnopi_uncertainties, bins = np.histogram(ncnopi_plotted_variable, **plot_options)
            err_ncnopi = np.array(
                [n * self.weights["ncnopi"] * self.weights["ncnopi"] for n in ncnopi_uncertainties])

        if "lee" in self.samples:
            if isinstance(plot_options["bins"], Iterable):
                lee_bins = plot_options["bins"]
            else:
                bin_size = (
                    plot_options["range"][1] - plot_options["range"][0])/plot_options["bins"]
                lee_bins = [plot_options["range"][0]+n *
                            bin_size for n in range(plot_options["bins"]+1)]

            binned_lee = pd.cut(self.samples["lee"].query(
                query).eval(variable), lee_bins)
            err_lee = self.samples["lee"].query(query).groupby(binned_lee)['leeweight'].agg(
                "sum").values * self.weights["lee"] * self.weights["lee"]

        exp_err = np.sqrt(err_mc + err_ext + err_nue + err_dirt + err_lee + err_ncpi0 + err_ccpi0 + err_ccnopi + err_cccpi + err_nccpi + err_ncnopi)

        bincenters = 0.5 * (tot_bins[1:] + tot_bins[:-1])
        bin_size = [(tot_bins[i + 1] - tot_bins[i]) / 2
                    for i in range(len(tot_bins) - 1)]
        ax1.bar(bincenters, n_tot, width=0, yerr=exp_err)

        n_data, bins = np.histogram(data_plotted_variable, **plot_options)
        data_err = self._data_err(n_data,asymErrs)
        ax1.errorbar(
            bincenters,
            n_data,
            xerr=bin_size,
            yerr=data_err,
            fmt='ko',
            label="NuMI: %i events" % len(data_plotted_variable))

        leg = ax1.legend(
            frameon=False, title=r'MicroBooNE Preliminary %g POT' % self.pot)
        leg._legend_box.align = "left"
        plt.setp(leg.get_title(), fontweight='bold')

        unit = title[title.find("[") + 1:title.find("]")
                     ] if "[" and "]" in title else ""
        xrange = plot_options["range"][1] - plot_options["range"][0]
        if isinstance(bins, Iterable):
            ax1.set_ylabel("N. Entries")
        else:
            ax1.set_ylabel(
                "N. Entries / %g %s" % (xrange / plot_options["bins"], unit))
        #ax1.set_xticks([])
        ax1.set_xlim(plot_options["range"][0], plot_options["range"][1])

        #self._draw_ratio(ax2, bins, n_tot, n_data, exp_err, data_err)

        #ax2.set_xlabel(title)
        ax1.set_xlabel(title)
        #ax2.set_xlim(plot_options["range"][0], plot_options["range"][1])
        fig.tight_layout()
        # fig.savefig("plots/%s_samples.pdf" % variable)
        return fig, ax1#, ax2

    def _draw_ratio(self, ax, bins, n_tot, n_data, tot_err, data_err, draw_data=True):
        bincenters = 0.5 * (bins[1:] + bins[:-1])
        bin_size = [(bins[i + 1] - bins[i]) / 2 for i in range(len(bins) - 1)]
        if draw_data:
            data_err_low = self._ratio_err(n_data, n_tot, data_err[0], np.zeros(len(data_err[0])))
            data_err_high = self._ratio_err(n_data, n_tot, data_err[1], np.zeros(len(data_err[1])))
            ratio_error = (data_err_low,data_err_high)
            ax.errorbar(bincenters, n_data / n_tot,
                    xerr=bin_size, yerr=ratio_error, fmt="ko")

            ratio_error_mc = self._ratio_err(n_tot, n_tot, tot_err, np.zeros(len(n_tot)))
            ratio_error_mc = np.insert(ratio_error_mc, 0, ratio_error_mc[0])
            bins = np.array(bins)
            ratio_error_mc = np.array(ratio_error_mc)
        self._ratio_vals = n_data / n_tot
        self._ratio_errs = ratio_error
        ax.fill_between(
            bins,
            1.0 - ratio_error_mc,
            ratio_error_mc + 1,
            step="pre",
            color="tab:blue",
            alpha=0.5)

        ax.set_ylim(0, 2)
        ax.set_ylabel("NuMI / (MC+EXT)")
        ax.axhline(1, linestyle="--", color="k")

    # NuMI needs to add PPFX workaround for dirt
    def sys_err(self, name, var_name, query, x_range, n_bins, weightVar):
        # how many universes?
        Nuniverse = 500 #100 #len(df)
        print("Universes",Nuniverse)

        n_tot = np.empty([Nuniverse, n_bins])
        n_cv_tot = np.empty(n_bins)
        n_tot.fill(0)
        n_cv_tot.fill(0)

        for t in self.samples:
            if t in ["ext", "data", "lee", "data_7e18", "data_1e20","dirt"]: 
                continue

            # for pi0 fit only
            #if ((t in ["ncpi0","ccpi0"]) and (name == "weightsGenie") ):
            #    continue

            tree = self.samples[t]


            extra_query = ""
            if t == "mc":
                extra_query = "& " + self.nu_pdg # "& ~(abs(nu_pdg) == 12 & ccnc == 0) & ~(npi0 == 1 & category != 5)"

            queried_tree = tree.query(query+extra_query)
            variable = queried_tree[var_name]
            syst_weights = queried_tree[name]
            #print ('N universes is :',len(syst_weights))
            spline_fix_cv  = queried_tree[weightVar] * self.weights[t]
            spline_fix_var = queried_tree[weightVar] * self.weights[t]
            if (name == "weightsGenie"):
                spline_fix_var = queried_tree["weightSpline"] * self.weights[t]

            s = syst_weights
            df = pd.DataFrame(s.values.tolist())
            #print (df)
            #continue

            if var_name[-2:] == "_v":
                #this will break for vector, "_v", entries
                variable = variable.apply(lambda x: x[0])

            n_cv, bins = np.histogram(
                variable,
                range=x_range,
                bins=n_bins,
                weights=spline_fix_cv)
            n_cv_tot += n_cv

            if not df.empty:
                for i in range(Nuniverse):
                    weight = df[i].values / 1000.
                    weight[np.isnan(weight)] = 1
                    weight[weight > 100] = 1
                    weight[weight < 0] = 1
                    weight[weight == np.inf] = 1

                    n, bins = np.histogram(
                        variable, weights=weight*spline_fix_var, range=x_range, bins=n_bins)
                    n_tot[i] += n

        cov = np.empty([len(n_cv), len(n_cv)])
        cov.fill(0)

        for n in n_tot:
            for i in range(len(n_cv)):
                for j in range(len(n_cv)):
                    cov[i][j] += (n[i] - n_cv_tot[i]) * (n[j] - n_cv_tot[j])

        cov /= Nuniverse

        return cov

    def sys_err_NuMIGeoMultiverse(self, name, var_name, query, x_range, n_bins, weightVar):
        # how many universes?
        Nuniverse = 20 #100 #len(df)
        print("Universes Geo Multiverses",Nuniverse)

        n_tot = np.empty([Nuniverse, n_bins])
        n_cv_tot = np.empty(n_bins)
        n_tot.fill(0)
        n_cv_tot.fill(0)

        for t in self.samples:
            if t in ["ext", "data", "lee", "data_7e18", "data_1e20","dirt"]: 
                continue

            # for pi0 fit only
            #if ((t in ["ncpi0","ccpi0"]) and (name == "weightsGenie") ):
            #    continue

            tree = self.samples[t]


            extra_query = ""
            if t == "mc":
                extra_query = "& " + self.nu_pdg # "& ~(abs(nu_pdg) == 12 & ccnc == 0) & ~(npi0 == 1 & category != 5)"

            queried_tree = tree.query(query+extra_query)
            variable = queried_tree[var_name]
            syst_weights = queried_tree[name]
            #print ('N universes is :',len(syst_weights))
            spline_fix_cv  = queried_tree[weightVar] * self.weights[t]
            spline_fix_var = queried_tree[weightVar] * self.weights[t]
            if (name != "weightsNuMIGeo"):                     
                    sys.exit(1) 

            s = syst_weights
            df = pd.DataFrame(s.values.tolist())
            #print (df)
            #continue

            if var_name[-2:] == "_v":
                #this will break for vector, "_v", entries
                variable = variable.apply(lambda x: x[0])

            n_cv, bins = np.histogram(
                variable,
                range=x_range,
                bins=n_bins,
                weights=spline_fix_cv)
            n_cv_tot += n_cv

            if not df.empty:
                for i in range(Nuniverse):
                    weight = df[i].values 
                    weight[np.isnan(weight)] = 1
                    weight[weight > 100] = 1
                    weight[weight < 0] = 1
                    weight[weight == np.inf] = 1

                    n, bins = np.histogram(
                        variable, weights=weight*spline_fix_var, range=x_range, bins=n_bins)
                    n_tot[i] += n

        cov = np.empty([len(n_cv), len(n_cv)])
        cov.fill(0)

        for n in n_tot:
            for i in range(len(n_cv)):
                for j in range(len(n_cv)):
                    cov[i][j] += (n[i] - n_cv_tot[i]) * (n[j] - n_cv_tot[j])

        cov /= Nuniverse

        return cov
    
    def sys_err_NuMIGeo(self, name, var_name, query, x_range, n_bins, weightVar):
      # how many universes?
        print("Number of variations Universes",10)
        for variationNumber in [x*2 for x in range(10)]:
            n_tot = np.empty([2, n_bins])
            n_cv_tot = np.empty(n_bins)
            n_tot.fill(0)
            n_cv_tot.fill(0)########

            for t in self.samples:
                if t in ["ext", "data", "lee", "data_7e18", "data_1e20","dirt"]: 
                    continue
               
                tree = self.samples[t]
                extra_query = ""
                if t == "mc":
                    extra_query = "& " + self.nu_pdg # "& ~(abs(nu_pdg) == 12 & ccnc == 0) & ~(npi0 == 1 & category != 5)"

                queried_tree = tree.query(query+extra_query)
                variable = queried_tree[var_name]
                syst_weights = queried_tree[name]
                spline_fix_cv  = queried_tree[weightVar] * self.weights[t]
                spline_fix_var = queried_tree[weightVar] * self.weights[t]
                if (name != "weightsNuMIGeo"):                     
                    sys.exit(1) 
    
                s = syst_weights
                df = pd.DataFrame(s.values.tolist())

                if var_name[-2:] == "_v":
                    #this will break for vector, "_v", entries
                    variable = variable.apply(lambda x: x[0])

                n_cv, bins = np.histogram(
                    variable,
                    range=x_range,
                    bins=n_bins,
                    weights=spline_fix_cv)
                n_cv_tot += n_cv

                if not df.empty:
                    for i in range(2):
                        #print(df.shape)
                        weight = df[i+variationNumber].values
                        weight[np.isnan(weight)] = 1
                        weight[weight > 100] = 1
                        weight[weight < 0] = 1
                        weight[weight == np.inf] = 1

                        n, bins = np.histogram(
                            variable, weights=weight*spline_fix_var, range=x_range, bins=n_bins)
                        n_tot[i] += n

            tempCov = np.empty([len(n_cv), len(n_cv)])
            tempCov.fill(0)
            for n in n_tot:
                for i in range(len(n_cv)):
                    for j in range(len(n_cv)):
                        tempCov[i][j] += (n[i] - n_cv_tot[i]) * (n[j] - n_cv_tot[j])

            tempCov /= 2
            if variationNumber == 0:
                cov = tempCov
            else:
                cov += tempCov

            
        return cov

    def get_SBNFit_cov_matrix(self,COVMATRIX,NBINS):

        covmatrix = np.zeros([NBINS,NBINS])
        
        if (os.path.isfile("COV/"+COVMATRIX) == False):
            print ('ERROR : file-path for covariance matrix not valid!')
            return covmatrix

        covmatrixfile = open("COV/"+COVMATRIX,"r")

        NLINES = len(covmatrixfile.readlines())

        print ('file has %i lines and histo has %i bins'%(NLINES,NBINS))

        if NLINES != NBINS:
            print ('ERROR : number of lines in text-file does not match number of bins!')
            return covmatrix

        LINECTR = 0

        covmatrixfile.seek(0,0)
        for line in covmatrixfile:

            words = line.split(",")

            WORDCTR = 0

            if len(words) != NBINS:
                print ('ERROR : number of words in line does not match number of bins!')
                break
                
            for word in words:

                val = float(word)

                covmatrix[LINECTR][WORDCTR] = val

                WORDCTR += 1

            LINECTR += 1

        return covmatrix
    
