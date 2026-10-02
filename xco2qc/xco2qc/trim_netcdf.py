"""
Trim off the ends of the netCDF file if necessary.  Data may have come in both
before the deployment officially started and after the deployment officially
ended.
"""

# standard library imports
import datetime as dt
import shutil

# 3rd party library imports
import dateutil.parser
import xarray as xr

# local imports
from xco2qc import core


class TrimXCO2netCDF(core.MapCO2core):
    """
    Attributes
    ----------
    src_dir : path
        Path to input netCDF files to be trimmed.
    dst_dir : path
        Path to the output netCDF files.
    start, stop : datetime.datetime
        The netCDF file will be trimmed to contain dates only between these
        two points in time.
    """

    def __init__(
        self, src_dir, dst_dir, verbosity=None, start=None, stop=None
    ):
        """
        Parameters
        ----------
        src_dir : path or str
            Path to input netCDF files to be trimmed.
        dst_dir : path or str
            Path to the output trimmed netCDF files.
        start, stop : datetime.datetime or None
            The netCDF file will be trimmed to contain dates only between these
            two points in time.  If a value of None is given, then an
            appropriate default is chosen.  For example, if start is None, then
            the first time point in the input netCDF file is chosen.
        """
        super().__init__(
            src_dir=src_dir, dst_dir=dst_dir, verbosity=verbosity,
            logger_name='trimming'
        )

        self.start = start
        self.stop = stop

    def adjust_parameters(self):

        # Determine the earliest cycle time and latest cycle time.  Have to
        # look at all the data streams coming from mapco2.  Exclude any
        # historical or external sources.
        beginning = []
        end = []
        for name in [
            core.CYCLE_HEADER_NCFILE,
            core.SBE16_NCFILE,
            core.MET_NCFILE,
            core.SAMI_NCFILE,
            core.licor.APOFF_NCFILE,
            core.licor.APON_NCFILE,
            core.licor.EPOFF_NCFILE,
            core.licor.EPON_NCFILE,
            core.licor.ZPOFF_NCFILE,
            core.licor.ZPON_NCFILE,
            core.licor.ZPOSTCAL_NCFILE,
            core.licor.SPOFF_NCFILE,
            core.licor.SPON_NCFILE,
            core.licor.SPOSTCAL_NCFILE,
        ]:
            ncfile = self.src_dir / name
            if ncfile.exists():
                with xr.open_dataset(ncfile) as ds:
                    ts = ds['time'].to_series()
                    beginning.append(ts.iloc[0])
                    end.append(ts.iloc[-1])

        ncfile = self.src_dir / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(ncfile) as ds:
            cycle_header_ts = ds['time'].to_series()

        if self.start is None:
            # interpret the intention here as to wanting the starting point
            # of the time series
            self.start = min(beginning)
        else:
            self.start = dateutil.parser.parse(self.start)

        if self.stop is None:
            # interpret the intention here as to wanting the ending point
            # of the time series.  This is not the last point in the cycle
            # header netCDF file because that time series is based on the
            # START of each cycle.  So make it one timestep further.
            self.stop = max(end)
        else:
            self.stop = dateutil.parser.parse(self.stop)
            # again, compare against the cycle header times.  Use the very
            # end of the cycle.
            following_cycles = cycle_header_ts[cycle_header_ts > self.stop]
            if len(following_cycles) == 0:
                # special case where we are trimming against the end of the
                # time series
                self.stop = max(end)
            else:
                # the first of the following cycles is the first cycle that
                # we do not want to use.  so make the end point one minute
                # before that.
                self.stop = following_cycles.iloc[0] - dt.timedelta(minutes=1)

    def run(self):
        self.adjust_parameters()
        self.trim_netcdf_files()

    def trim_netcdf_files(self):
        self.logger.info(f"Start time set to {self.start}")
        self.logger.info(f"Stop time set to {self.stop}")

        # Make sure that the output path can be reached.
        if not self.dst_dir.exists():
            self.dst_dir.mkdir(parents=True)

        for input_ncfile in self.src_dir.glob('*.nc'):

            output_ncfile = self.dst_dir / input_ncfile.name

            # the historical file (if it exists) is an exception to this
            # process.  if it exists, just copy it as is.
            with xr.open_dataset(input_ncfile) as ds:
                data_source = ds.data_source
            if data_source == 'historical':
                shutil.copyfile(input_ncfile, output_ncfile)
                continue

            # This code fragment only works well if the time series is strictly
            # monotonic increasing.
            with xr.open_dataset(input_ncfile) as ds:
                trimmed_ds = ds.sel(time=slice(self.start, self.stop))

            if len(trimmed_ds.time) == 0:
                msg = (
                    f"The start and stop dates of ({self.start}, "
                    f"{self.stop}) result in a time series of zero length.  "
                    f"You may need to choose a different time extent."
                )
                self.logger.error(msg)
                raise RuntimeError(msg)

            trimmed_ds.to_netcdf(output_ncfile)

            msg = f"{input_ncfile} trimmed to {output_ncfile}"
            self.logger.info(msg)
