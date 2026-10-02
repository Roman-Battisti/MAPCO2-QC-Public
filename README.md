# MAPCO2-QC-Public
Mooring group MAPCO2 QC software, specific to xCO2

# If you are updating from a previous release of XCO2-QC...
You need to remove the existing environment. Run the following only if you have previously created the xco2qc environment and need to update it.

1.  Go to the start menu and launch the Anaconda Prompt.  
2.  Remove the xco2qc environment by typing `conda env remove -n xco2qc`
3.  Follow the installation and setup instructions below.

# Installation Instructions
1.  On the GitHub MAPCO2-QC home page, go to Releases (on the right hand side) and click on the "tags".
2.  On the subsequent page, choose the most recent release (choose zip), which should start the download process.
3.  You may unpack the zip file anywhere you wish, but it will be assumed in these instructions that it is unpacked into your Documents folder.  After that is done, there should be a directory structure that looks like `Documents\MAPCO2-QC-version-number\setup.py`.

You must have Anaconda installed before you can proceed any further.  Please
refer to https://docs.anaconda.com/anaconda/install/ for details on how to do that.

## Windows Setup Instructions
This process can take quite some time to complete, specifically step 2. We suggest running this process in the background while performing other tasks.
1.  Go to the start menu and launch the Anaconda Prompt.
2.  From within the prompt run (copy the following line, paste into Anaconda Prompt, then press enter):

conda create -n xco2qc -c conda-forge autograd build cftime coverage erddapy flake8 future git gsw ipympl ipywidgets jupyter lxml matplotlib netcdf4 numpy openpyxl pandas pip plotly pynco pyqt pytables pytest pytest-cov pytest-xdist python python-dateutil python-docx pyyaml requests scikit-learn scipy seaborn sphinx statsmodels tornado xarray xlrd

4.  Activate the environment with `conda activate xco2qc`
5.  Run:
   
   pip install pyco2sys
   
6.  From within the prompt, type `cd Documents\MAPCO2-QC-release-number\MAPCO2-QC-release-number\xco2qc`. The path after cd is the directory where the unpacked QC program exists.
7.  Start your jupyter notebook with `jupyter notebook`
8.  From within the jupyter notebook, open `ocean_CO2_QC.ipynb` and follow the instructions contained in the notebook.

## Other Platforms

### OpenSUSE Tumbleweed
A working installation with system packages only, i.e. no Anaconda, was
verified on OpenSUSE Tumbleweed on the 20200829 snapshot.  The jupyter
notebook was tested on Firefox.

The only additional step needed was to install the
`python3-matplotlib-qt5` RPM, which has no corresponding package in the
Anaconda ecosysem.

### Others

Installing of Anaconda on the Mac and on other versions of linux such as Fedora has also worked.

Ubuntu 20.04 does not work due to having too old of a version of `ipywidgets`.

Fedora 32 does not work due to having too old of a version of `python3-dateutil`.

#### Legal Disclaimer
*This repository is a software product and is not official communication
of the National Oceanic and Atmospheric Administration (NOAA), or the
United States Department of Commerce (DOC). All NOAA GitHub project
code is provided on an 'as is' basis and the user assumes responsibility
for its use. Any claims against the DOC or DOC bureaus stemming from
the use of this GitHub project will be governed by all applicable Federal
law. Any reference to specific commercial products, processes, or services
by service mark, trademark, manufacturer, or otherwise, does not constitute
or imply their endorsement, recommendation, or favoring by the DOC.
The DOC seal and logo, or the seal and logo of a DOC bureau, shall not
be used in any manner to imply endorsement of any commercial product
or activity by the DOC or the United States Government.*
