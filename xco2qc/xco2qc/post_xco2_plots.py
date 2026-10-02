""" """
# Standard library imports
import time

# 3rd party library imports
from IPython.display import display
import matplotlib.pyplot as plt
import seaborn as sns
import xarray as xr

# Local imports
from xco2qc import core
from xco2qc.qc import QCCore


class PostXCO2Plots(QCCore):
    """
    Create pre and post xco2 plots.

    Attributes
    ----------
    src_dir : pathlib paths
        Paths to the LICOR files.
    """
    def __init__(self, src_dir, use_colorblind=False, verbosity=None, **kwargs):
        super().__init__(
            src_dir,
            verbosity=verbosity,
            logger_name='post-xco2-plots',
            **kwargs
        )
        
        self.figsize = (8, 6)
        self.color_palette = None if not use_colorblind else "colorblind"

    def run(self):

        self.logger.info("Beginning Post xCO2 Plots...")

        if self._is_notebook:
            self.apoff_xco2_plot()
            self.epoff_xco2_plot()

    def apoff_xco2_plot(self):

        ncfile = self.src_dir / core.licor.APOFF_NCFILE

        self.xco2_wet_plot(ncfile)
        # plt.show()
        # time.sleep(0.2)
        
        self.xco2_dry_plot(ncfile)
        # plt.show()
        # time.sleep(0.2)

    def epoff_xco2_plot(self):

        ncfile = self.src_dir / core.licor.EPOFF_NCFILE

        self.xco2_wet_plot(ncfile)
        # time.sleep(0.2)
        
        self.xco2_dry_plot(ncfile)
        # time.sleep(0.2)

    def xco2_wet_plot(self, filename):
        """
        Plot the XCO2 wet against both v1 and v2 post xco2.

        Parameters
        ----------
        filename : str
            Basename of netCDF file, either APOFF_NCFILE or EPOFF_NCFILE.
        """

        fig, ax = plt.subplots(figsize=self.figsize)
        pal = sns.color_palette(palette=self.color_palette, n_colors=3)

        ncfile = self.src_dir / filename
        licor_label = core.mapco2core.file2label(ncfile)
        with xr.open_dataset(ncfile) as ds:

            ds['xco2_wet'].plot(ax=ax, label='xco2_wet', color=pal[0])

            try:
                licor_version = ds['post_xco2_wet'].licor_version
                title = (
                    f"{licor_label} Post XCO2 Wet : "
                    f"chosen version is {licor_version}"
                )
                ds['post_xco2_wet_v1'].plot(
                    ax=ax, label='post xco2 wet licor v1', color=pal[1]
                )
                ds['post_xco2_wet_v2'].plot(
                    ax=ax, label='post xco2 wet licor v2', color=pal[2]
                )
            except KeyError:
                title = f"{licor_label} XCO2 Wet"
                self.logger.warning(f"No post_xco2_wet' in {ncfile}.")

        ax.set_title(title)

        ax.legend()
        # time.sleep(0.2)
        display(fig)  # fig.canvas for responsive figures

    def xco2_dry_plot(self, filename):
        """
        Parameters
        ----------
        filename : str
            Basename of netCDF file, either APOFF_NCFILE or EPOFF_NCFILE.
        """

        fig, ax = plt.subplots(figsize=self.figsize)

        ncfile = self.src_dir / filename
        with xr.open_dataset(ncfile) as ds:

            ds['xco2_dry'].plot(ax=ax, label='xco2_dry')

            try:
                ds['post_xco2_dry'].plot(ax=ax, label='post_xco2_dry')
            except KeyError:
                self.logger.warning(f"No post_xco2_dry in {ncfile}.")

        ax.set_title(f"{core.mapco2core.file2label(ncfile)} Post XCO2 Dry")

        ax.legend()
        # time.sleep(0.2)
        display(fig)
