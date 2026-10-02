###############
Getting Started
###############

*************************
Getting Set Up with Conda
*************************
The MAPCO2-QC package is built and tested on the Anaconda version 3.9
of python.  If you do not already have Anaconda on your system, please go
to https://www.anaconda.com/distribution/#download-section and download
the version appropriate to your computer.

Consult the documentation at
https://docs.anaconda.com/anaconda/user-guide/getting-started/
if you need help getting started.

From this point forward, it is assumed that you are working in a terminal
window on either mac or linux, or in an Anaconda Prompt window on Windows.

Once you are confident with using Anaconda, it's time to use git to clone
the MAPCO2-QC repo from github.  A linux distribution often already
has git installed, but if you don't have it, then install it from the
command line. ::

  $ conda install git

Clone the MAPCO2-QC repo with ::

  $ git clone git@github.com:git@github.com:NOAA-PMEL/MAPCO2-QC.git

Change folders into MAPCO2-QC/xco2qc.

As the Anaconda installer doesn't quite get all the packages required
to run MAPCO2-QC, we recommend using the ``environment.yml`` file in
the current directory to create a suitable anaconda environment. ::

  $ conda env create -f xco2qc/core/data/environment.yml
  $ conda activate xco2qc

Updated packages have been known to cause problems with the MAPCO2-QC
package in the past, so in addition to the generic environment file,
three additional enviroment files are provided that pin the packages
to versions that are known to work.  A linux, a mac, and a windows-specific
environment file are provided in xco2qc/core/data.

If you wish to install the command line executables, you should do so with ::

  $ pip install -e .

