"""
Support for manual QC.  This can be run either from within a Jupyter notebook
or from the python command line.
"""
# standard library imports
from contextlib import ExitStack
import os
import pathlib
import pickle
import time

# 3rd party library imports
from matplotlib.path import Path
import matplotlib.pyplot as plt
from matplotlib.widgets import PolygonSelector
import netCDF4
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.cluster import KMeans
import statsmodels.formula.api as smf
import xarray as xr

# local imports
from xco2qc import core
from xco2qc.netcdf import NetCDFWriter

# Limit KMeans to one thread so it doesn't lock
os.environ["OMP_NUM_THREADS"] = "1"


class ManualRegressionQC(core.MapCO2core):
    """
    Use native matplotlib functionality to select data points to mask out of
    the regression calculation.

    This modifies two netCDF files.  The SPAN_COEFFICIENT_QC in the cycle
    header file is modified to manually flag any points selected by the user.
    The UPDATED_SPAN_COEFFICIENTS and QC are written back to the SPOFF file.

    Attributes
    ----------
    ncfile : path
        Path to netCDF file
    fig, ax :
        matplotlib figure and associated axis
    models : dict
        Maps a regression model to a cluster of (span coefficient, temperature,
        time) data points
    models_file : path or None
        path to binary file where regression and cluster model information will
        be stored, but only if the models_file is not None
    ts, qc : pandas.Series
        time series for xCO2 data and QC
    poly : matplotlib.widgets.PolygonSelector
        Select a polygon region of an axes.
    palette : seaborn color palette
    """

    def __init__(
        self, reduced_path, models_file=None, n_clusters=1, use_colorblind=False, verbosity=None
    ):

        super().__init__(
            src_dir=reduced_path, verbosity=verbosity,
            logger_name='manual-regression'
        )

        reduced_path = pathlib.Path(reduced_path)
        self.models_file = models_file

        self.cycle_header_ncfile = reduced_path / core.CYCLE_HEADER_NCFILE
        self.spoff_ncfile = reduced_path / core.licor.SPOFF_NCFILE
        self.zpon_ncfile = reduced_path / core.licor.ZPON_NCFILE
        self.reduced_path = reduced_path

        self.n_clusters = n_clusters

        self.fig, self.ax = plt.subplots()
        # self.fig_update, self.ax_update = plt.subplots(nrows=2)  # for finalized span-temperature values (using clustering and LR results)
        self.color_palette = None if not use_colorblind else "colorblind"
        self.palette = sns.color_palette(palette=self.color_palette, n_colors=5)

    def reload(self):
        """
        Read the datasets back in, but if this is a 2nd or 3rd time, then
        quality flags should be updated, and we should have fewer data points
        upon which to plot and run the regression calculation.
        """

        self.logger.info('Reloading...')

        with xr.open_dataset(
            self.cycle_header_ncfile, mask_and_scale=False
        ) as ds:
            sc = ds['span_coefficient'].to_series()
            sc_qc = ds['span_coefficient_qc'].to_series().astype(np.uint32)
            span_flag = ds['span_flag'].to_series().astype(np.uint8)
            zc = ds['zero_coefficient'].to_series()

        with xr.open_dataset(self.zpon_ncfile) as ds:
            df = ds.load().to_dataframe()
            df = df[~df.index.duplicated(keep='first')]
            df = df.reindex(index=sc.index, method='nearest')
            temp = df['temperature']
            temp_qc = df['temperature_qc']

        with xr.open_dataset(self.spoff_ncfile) as ds:
            df = ds.load().to_dataframe()
            df = df[~df.index.duplicated(keep='first')]
            df = df.reindex(index=sc.index, method='nearest')
            try:
                usc_qc = df['updated_span_coefficient_qc']
            except KeyError:
                # If this is the first time thru, then this variable doesn't
                # exist yet.  Make it all good quality because we don't know
                # any differently right now.
                usc_qc = pd.Series(
                    np.zeros(len(sc)), dtype=np.uint32, index=sc.index
                )

        # construct a dataframe to use as the basis for plotting and regression
        mapper = {
            'span_flag': span_flag,
            'temperature': temp.values,
            'temp_qc': temp_qc.values,
            'sc': sc.values,
            'sc_qc': sc_qc.values,
            'zc': zc.values,
            'updated_sc_qc': usc_qc.values,
            'label': np.nan,
        }
        self.df = pd.DataFrame(mapper, index=sc.index)
        self.logger.debug(f"Loaded dataframe with {len(self.df)} values")

        # We need to include time as part of the regression.  Do this by adding
        # another column for the unix timestamp.
        self.df['timestamp'] = self.df.index.view('int64')

    def run(self):

        self.logger.info('Running temperature / span coefficient regression')

        self.reload()
        self.run_kmeans()
        self.run_regression_on_kmeans_clusters()
        self.update_span_coefficients()
        self.write_span_coefficients_back_to_file()
        self.save_cluster_and_regression_models()
        
        self.plot()

    def save_cluster_and_regression_models(self):
        """
        Save the cluster and regression models to file.
        """
        if self.models_file is None:
            return

        with open(self.models_file, mode='wb') as f:
            pickle.dump([self.models, self.km], f)

    def update_span_coefficients(self):
        """
        Use the linear regression relationship(s) uncovered via k-means to
        adjust the span coefficients in the netCDF file.
        """
        self.logger.info('Updating span coefficients in SPOFF.')

        # Start by initializing the updated span coefficient predictions to be
        # all NaN because if any points are not predicted (filled in), we can
        # detect that later on.
        self.df['predict'] = np.nan

        # loop through the clusters and update the prediction
        for cluster_label in range(self.n_clusters):

            self.logger.debug(f"Regressing on cluster label {cluster_label}")
            
            # for good sc data, use original values
            # idx = (self.df['label'] == cluster_label) & (self.df['sc_qc'] == core.quality.GOOD)
            # self.df.loc[idx, 'predict'] = self.df.loc[idx, 'sc']
            
            # for bad/flagged sc, predict using LR
            idx = self.df['label'] == cluster_label
                  # & (self.df['sc_qc'] != core.quality.GOOD) | (self.df['span_flag'] == 255)

            model = self.models[cluster_label]
            X = self.df.loc[idx, 'temperature']
            self.df.loc[idx, 'predict'] = model.predict(X)

        # replace any NaNs in the predictions with the fill value so that it
        # is suitable to be written to the netCDF file
        metadata = core.vardefs.data_dict['licor']['updated_span_coefficient']
        idx = pd.isnull(self.df['predict'])
        self.df.loc[idx, 'predict'] = metadata['fill_value']

    def write_span_coefficients_back_to_file(self):

        # the quality for the updated span coefficients derives from
        # the original span coefficients quality.  In addition, if the
        # temperature is not good, we make note of that as well.
        #
        # Be sure to zero out the GOOD flag appropriately.
        qc = self.df['sc_qc']
        qc = np.where(
            self.df['temp_qc'] != core.quality.GOOD,
            np.bitwise_or(
                np.bitwise_xor(qc, core.quality.GOOD),
                core.quality.BAD_TEMPERATURE
            ),
            qc
        )

        # turn qc back into a time series so that it can be reindexed
        qc = pd.Series(qc, index=self.df.index)

        # must reindex the data back to SPOFF before writing
        with xr.open_dataset(self.spoff_ncfile) as ds:
            rh = ds['rh'].to_pandas()

            updated_sc = self.df['predict'].reindex(rh.index, method='nearest')
            qc = qc.reindex(rh.index, method='nearest')

        # write the predictions back out to file
        with RegressionNetCDFWriter(src_ncfile=self.spoff_ncfile) as p:

            with ExitStack() as cm:

                # Safely acquire netCDF resources
                p.dst_nc = cm.enter_context(
                    netCDF4.Dataset(self.spoff_ncfile, mode='r+')
                )

                p.define_netcdf_variable('updated_span_coefficient')
                p.write_netcdf_variable(
                    'updated_span_coefficient',
                    updated_sc,
                    qc=qc
                )

    def run_kmeans(self):
        """
        Run the KMeans algorithm with the specified number of clusters.
        """

        self.logger.info(f'Running KMeans with {self.n_clusters} clusters')

        self.km = KMeans(n_clusters=self.n_clusters)

        # We can only run kmeans where we have good data so where is good data?
        idx = (
            (self.df['temp_qc'] == core.quality.GOOD)
            & (self.df['sc_qc'] == core.quality.GOOD)
            & (self.df['span_flag'] != 255)
        )
        
        # predict on good temperature, sc, and timestamp
        _df = self.df[['temperature', 'sc', 'timestamp']][idx]
        sc_good_mean = np.nanmean(_df['sc'])  # use to get the 'approximate' value of bad span coefficients to label properly
        self.logger.debug(f"Running kmeans on {len(_df)} points...")
        self.km.fit(_df)
        
        # select any good temp to perform predict
        idx = (self.df['temp_qc'] == core.quality.GOOD)
        _df = self.df[['temperature', 'sc', 'timestamp', 'sc_qc', 'span_flag']][idx].copy()
        
        # replace any bad/flagged sc with the good mean for prediction (the spans could be so far off as to affect their predicted cluster)
        idx_bad_sc = (_df['sc_qc'] != core.quality.GOOD) | (_df['span_flag'] == 255)
        _df.loc[idx_bad_sc, 'sc'] = sc_good_mean
        _df = _df[['temperature', 'sc', 'timestamp']]
        
        # predict
        self.df.loc[idx, 'label'] = self.km.predict(_df).astype(np.float64)

    def run_regression_on_kmeans_clusters(self):
        """
        Run regression on each kmeans cluster and save the regression model
        results.
        """
        self.logger.info('running linear regression on each cluster')

        self.models = {}
        for cluster_label in range(self.n_clusters):

            # restrict the regression model to where temperature and span
            # coefficients both have good quality, where the span flag is not
            # 255, and where the data belongs to the current cluster
            idx = (
                (self.df['temp_qc'] == core.quality.GOOD)
                & (self.df['sc_qc'] == core.quality.GOOD)
                & (self.df['span_flag'] != 255)
                & (self.df['label'] == cluster_label)
            )
            _df = self.df[idx]

            model = smf.ols('sc ~ temperature', data=_df).fit()
            self.models[cluster_label] = model

            self.log_cluster_information(cluster_label)

    def log_cluster_information(self, cluster_label):
        """
        There should be a record of this information somehow.  It doesn't
        really fit well as netCDF attributes.
        """

        msg = (
            f"Cluster {cluster_label}:  "
            f"center is {self.km.cluster_centers_[cluster_label]}"
        )
        self.logger.info(msg)

        msg = (
            f"Regression equation:  SC = "
            f"{self.models[cluster_label].params['temperature']} * T "
            f"+ {self.models[cluster_label].params['Intercept']}"
        )
        self.logger.info(msg)

        msg = (
            f"Regression R**2:  {self.models[cluster_label].rsquared}"
        )
        self.logger.info(msg)

    def plot(self):
        self.plot_regression_of_temperature_vs_span_coefficient()
        # self.plot_updated_span_coefficient()
        self.plot_zero_coeff_vs_span_coefficient()

    def plot_zero_coeff_vs_span_coefficient(self):
        fig, ax = plt.subplots()

        idx = (self.df['temp_qc'] == core.quality.GOOD)
        _df = self.df[idx]

        sns.scatterplot(
            x='temperature', y='zc', hue='label', data=_df, alpha=0.3,
            palette=self.color_palette, ax=ax
        )

        # Set the labels and title
        ax.set_xlabel('LICOR Temperature')
        ax.set_ylabel('Zero Coefficient')

        # No need for a legend here, so cover up the one that seaborn created.
        plt.legend([], [], frameon=False)

        ax.set_title('Licor Temperature vs. Zero Coefficient')

        fig.tight_layout()
        
        if self._is_notebook:
            plt.show()

    def plot_regression_of_temperature_vs_span_coefficient(self):
        """
        Create a scatter plot of the good data points and the linear
        regressions
        """
        self.logger.debug('Plot')

        self.ax.cla()

        # Restrict the scatter plot to where QC is has not been manually
        # flagged.  That way the user can selectively refine the regression.
        idx = (
            (self.df['temp_qc'] == core.quality.GOOD)
            & (self.df['sc_qc'] == core.quality.GOOD)
            & (self.df['span_flag'] != 255)
        )
        df = self.df[idx]

        # plot the regressions, but also specifically set the zorder to 1
        # so that it plots on top of everything else that follows.
        # We don't need a specific label value, we just have to supply it here.
        labels = self.df['label'].unique()
        labels.sort()
        for idx, label in enumerate(labels):
            scatter_kws = {
                'zorder': 1,
                'color': self.palette[idx],
                'edgecolor': 'w'
            }
            sns.regplot(
                x='temperature', y='sc', data=df.query('label == @label'),
                ax=self.ax, label=str(label),
                scatter_kws=scatter_kws
            )
        self.ax.legend()

        # plot the data that has been flagged.  plot it under the good data,
        # give it a low alpha level to distinguish it.  but only if there is
        # actually data that has been flagged (otherwise an annoying warning
        # appears).
        idx = (
            (self.df['temp_qc'] == core.quality.GOOD)
            & (self.df['sc_qc'] != core.quality.GOOD)
            & (self.df['span_flag'] != 255)
        )
        df = self.df[idx]
        if len(df) > 0:
            sns.scatterplot(
                x='temperature', y='sc', hue='label', data=df, palette=self.color_palette,
                ax=self.ax, zorder=0, alpha=0.1
            )

        # store the xlimits computed by sns.scatterplot, because they seems to
        # get lost somewhere along the line after this method finishes.
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()

        # plot the temperature values where span was lost
        # plot on the bottom of the y-axis
        loss_of_span_df = self.df.query('span_flag == 255')
        if len(loss_of_span_df) > 0:
            x = loss_of_span_df['temperature']
            delta = ylim[1] - ylim[0]
            y = np.full((len(x),), ylim[0] + delta / 100)
            self.ax.plot(
                x, y, label='', marker='*', color='k', linestyle='none'
            )

            # if loss of span temperatures go past the current xlims, we need
            # to then extend the xlims
            xlim = [min(xlim[0], x.min()), max(xlim[1], x.max())]

        handles, _ = self.ax.get_legend_handles_labels()

        # rework the labels to provide a bit more information
        labels = []
        for cluster_label in sorted(self.models.keys()):
            slope = self.models[cluster_label].params['temperature']
            label = (
                f"$m$ = {slope:.4f} "
                f"$R^2$ = {self.models[cluster_label].rsquared:.2f}"
            )
            labels.append(label)

        self.ax.legend(handles, labels)

        # Add a title to give some indication of how much loss of span happened
        percentage = len(loss_of_span_df) / len(self.df) * 100
        title = (
            f"Loss of span: "
            f"{len(loss_of_span_df)} out of {len(self.df)} measurements, "
            f"{percentage:.1f}%"
        )
        self.ax.set_title(title)

        # Set the labels and title
        self.ax.set_xlabel('LICOR Temperature')
        self.ax.set_ylabel('Span Coefficient')

        # Attach our polygon selector so that we can de-select temperature /
        # span coefficient points if we wish.
        self.poly = PolygonSelector(self.ax, self.onselect)

        # And finally, restore the xy limits to what we know should look ok
        self.ax.set_xlim(xlim)
        self.ax.set_ylim(ylim)

        self.fig.tight_layout()
        
        if self._is_notebook:
            plt.show()
            # time.sleep(0.2)

    def plot_updated_span_coefficient(self):
        
        self.ax_update[0].cla()
        self.ax_update[1].cla()
        with xr.open_dataset(self.spoff_ncfile) as ds:
            _df = ds[['updated_span_coefficient']].to_pandas().reindex(self.df.index, method='nearest')
            _df['temperature'] = self.df['temperature']
            _df['label'] = self.df['label']
        
        labels = self.df['label'].unique()
        labels.sort()
        for idx, label in enumerate(labels):
            scatter_kws = {
                'zorder': 1,
                'color': self.palette[idx],
                'edgecolor': 'w'
            }
            idx_good = (
                (self.df['label'] == label)
                & (self.df['temp_qc'] == core.quality.GOOD)
                & (self.df['sc_qc'] == core.quality.GOOD)
                & (self.df['span_flag'] != 255)
                )
            
            # plot good data
            sns.scatterplot(
                x='temperature', y='updated_span_coefficient', data=_df[idx_good],
                label=str(label), ax=self.ax_update[0], **scatter_kws
            )
            
            idx_flagged = (
                (self.df['label'] == label)
                & (self.df['temp_qc'] == core.quality.GOOD)
                & ((self.df['sc_qc'] != core.quality.GOOD)
                | (self.df['span_flag'] == 255))
                )
            
            # plot recalculated data
            sns.scatterplot(
                x='temperature', y='updated_span_coefficient', data=_df[idx_flagged],
                ax=self.ax_update[0], marker='$\star$', s=75, zorder=1, color=self.palette[idx],
                edgecolor='k', linewidth=0.5
            )
            
            _idx = (
                (self.df['label'] == label)
                & (self.df['temp_qc'] == core.quality.GOOD)
                )
            
            # Plot updated_span_coefficients time series
            sns.scatterplot(
                x=_df[idx_good].index, y='updated_span_coefficient', data=_df[idx_good],
                ax=self.ax_update[1], **scatter_kws
            )
            sns.scatterplot(
                x=_df[idx_flagged].index, y='updated_span_coefficient', data=_df[idx_flagged],
                ax=self.ax_update[1], marker='$\star$', s=75, zorder=1, color=self.palette[idx],
                edgecolor='k', linewidth=0.5
            )
        self.ax_update[0].legend([], [], frameon=False)
        self.ax_update[1].legend([], [], frameon=False)
        
        # Set the labels and title
        self.ax_update[0].set_xlabel('LICOR Temperature')
        self.ax_update[0].set_ylabel('Updated Span Coefficient')
        self.ax_update[1].set_ylabel('Updated Span Coefficient')

        self.ax_update[0].set_title('Licor Temperature vs. Updated Span Coefficient')
        plt.tight_layout()
        
        if self._is_notebook:
            plt.show()
    
    def onselect(self, verts):
        """
        All points within the selected polygon are to be manually flagged.  We
        do this by flipping the MANUALLY_FLAGGED bit on the span coefficient
        qc variable.

        Parameters
        ----------
        verts : list
            list of (xdata, ydata) tuples.
        """
        self.logger.info(f"onselect called with {len(verts)} vertices")
        path = Path(verts)

        data = np.array(list(zip(
            self.df['temperature'].values, self.df['sc'].values)
        ))

        # find the points that fall within the polygon and toggle the QC flag
        idx = np.nonzero(path.contains_points(data))[0]
        self.logger.info(f"Flagging {len(idx)} points...")
        self.logger.debug(f"Flagging locations {idx}...")

        with netCDF4.Dataset(self.cycle_header_ncfile, mode='r+') as nc:
            qc = nc['span_coefficient_qc'][:]
            qc[idx] = np.bitwise_xor(
                np.bitwise_xor(qc[idx], core.quality.GOOD),
                core.quality.MANUALLY_FLAGGED
            )
            
            nc['span_coefficient_qc'][:] = qc

        # Go again.
        self.run()


class RegressionNetCDFWriter(NetCDFWriter):
    """
    This makes it easier to write back to the ZPON file.

    Attributes
    ----------
    time : xarray
    """
    def __init__(self, src_ncfile):
        super().__init__(src_ncfile=src_ncfile)

        self.nc_variable_defs = core.vardefs.data_dict['licor']
