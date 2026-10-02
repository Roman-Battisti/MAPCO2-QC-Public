=================
Updating MBL Data
=================

There is no need to do this if you instruct the processing to automatically retrieve the latest version of the data.  This can be done by setting the *retrieve_remote* option to be true in the *Determine MBL Adjustment section*.

1. Go to the `NOAA/ESRL Gas Marine Boundary Layer Reference website <https://www.esrl.noaa.gov/gmd/ccgg/mbl/>`_.
2. Click on the `Download` tab.
3. Choose the `Surface` Reference Type.
4. Click `Submit`
5. Scroll down and click `Download Data`.
6. Gzip the downloaded file (do not zip it) and rename to `Latest_MBL.txt.gz` 
7. Copy this gzipped file into place over the top of the existing file at `xco2qc/core/data/mbl/data/Latest_MBL.txt.gz`.
