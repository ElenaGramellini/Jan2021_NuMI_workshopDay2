# Jan2021_NuMI_workshopDay2
This is the repository that you'll need to download to follow the second day of the NuMI for beginners tutorial. 
We have three sessions: Systematics, effAndSmearing, ReferenceFrame
This is a brief description of the prerequisits for each section


#Systematics
For the systematics hands on tutorial we will use the NuMI_Workshop.C macro.
See slides in docdb:XXXX for details on what to change. 

Make sure you copy the file:
`/uboone/data/users/kmistry/work/MCC9/NuMI_Workshop_Jan2020/crosssec_run1.root`
to your local directory.

After you make your edits, to run the script you can do:

`root -l -b -q NuMI_Workshop.C`

this will make a folder called plots with all your saved histograms.

#EffAndSmearing
For the efficiency & smearing matrix tutorial we will use the `effAndSmearing.ipynb` jupyter notebook in conjunction with the `smear_plotter.py` plotting script. 

Run through the checklist on the last two slides in DocDB 33688 to properly set up the jupyter notebook before the tutorial. 

#ReferenceFrame
