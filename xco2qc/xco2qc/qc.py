""" """
# Standard library imports

# 3rd party library imports
import netCDF4
import numpy as np
import xarray as xr

# Local imports
from . import core
from .Outlier_Detector import (
    OutlierDetector, InterquartileVarianceAlgorithm, byFrameGeneratorFactory
)
from xco2qc.utilities import get_qc_mask_varname


# These are optional parameters that may be supplied.  If they are not
# supplied, they are retrieved from the configuration file.
KEYWORDS = [
    'initial_span_cal',
    'air_diff_range_lower',
    'air_diff_range_higher',
    'equil_diff_range_lower',
    'equil_diff_range_higher',
    'max_air_xco2_std',
    'max_equil_xco2_std',
    'max_pressoff_diff',
    'max_rh_std',
    'max_rh_temp_std',
    'num_points_eachside',
    'ppm_below_span_cal',
    'ppm_above_span_cal',
    'ppm_below_zero',
    'ppm_above_zero',
    'span_diff_range_lower',
    'span_diff_range_higher',
    'xco2_trend_std',
]


class QCCore(core.MapCO2core):
    """
    Superclass for QC checker and QC plots.
    """
    def __init__(self, src_dir, logger_name=None, verbosity=None, **kwargs):
        super().__init__(
            src_dir=src_dir, verbosity=verbosity, logger_name=logger_name
        )
        
        try:
            self.spike_detection = kwargs['spike_detection']
        except KeyError:
            # spike detection wasn't specified
            self.spike_detection = False

        # handle remaining command line parameters, they should all correspond
        # to configuration file items
        qc = self.config['QC']
        for item in KEYWORDS:
            if item in kwargs and kwargs[item] is not None:
                setattr(self, item, kwargs[item])
            else:
                # It wasn't specified, so use the default value in our own
                # configuration file.
                setattr(self, item, qc[item])

        if self.air_diff_range_lower > self.air_diff_range_higher:
            msg = (
                f"The air-diff-range "
                f"[{self.air_diff_range_lower}, {self.air_diff_range_higher}]"
                f"must be monotonically increasing."
            )
            raise RuntimeError(msg)

        if self.equil_diff_range_lower > self.equil_diff_range_higher:
            msg = (
                f"The equil-diff-range "
                f"[{self.equil_diff_range_lower}, "
                f"{self.equil_diff_range_higher}]"
                f"must be monotonically increasing."
            )
            raise RuntimeError(msg)

        if self.span_diff_range_lower > self.span_diff_range_higher:
            msg = (
                f"The span-diff-range "
                f"[{self.span_diff_range_lower}, "
                f"{self.span_diff_range_higher}]"
                f"must be monotonically increasing."
            )
            raise RuntimeError(msg)

        if self.ppm_below_zero <= 0 or self.ppm_above_zero <= 0:
            msg = (
                f"The values for PPM below/above zero "
                f"[{self.ppm_below_zero}, {self.ppm_above_zero}]"
                f"must both be positive."
            )
            raise RuntimeError(msg)

        if self.ppm_below_span_cal <= 0 or self.ppm_above_span_cal <= 0:
            msg = (
                f"The values for the spread around the initial span "
                f"calibration value (below and above) "
                f"[{self.ppm_below_span_cal}, {self.ppm_above_span_cal}]"
                f"must both be positive."
            )
            raise RuntimeError(msg)


class QCChecker(QCCore):
    """
    Runs QC checks on LICOR files.

    Attributes
    ----------
    src_dir : pathlib paths
        Paths to the LICOR files.
    spike_detection : bool
        True if spike detection is turned on.
    """
    def __init__(self, src_dir, verbosity=None, **kwargs):
        super().__init__(
            src_dir, verbosity=verbosity, logger_name='qc', **kwargs
        )

    def run(self):
        """
        Run QC checks.
        """
        self.logger.info("Beginning QC checks...")

        # These QC checks are in the QC VBA module.
        self.check_loss_of_span()
        self.check_zpoff_xco2_range()
        self.check_zpostcal_xco2_range()
        self.check_spoff_spostcal_xco2_in_span_range()
        self.check_epoff_xco2_stddev()
        self.check_apoff_xco2_stddev()
        self.check_apoff_spoff_epoff_pressure_differences()
        self.check_epoff_epon_pressure_differences()
        self.check_apoff_apon_pressure_differences()
        self.check_spoff_spon_pressure_differences()
        self.check_rh_stddev()
        self.check_rh_temp_stddev()
        self.check_external_sami()
        self.check_aanderaa_o2()

        # This QC check is not in the QC VBA module.
        self.check_valid_range()
        self.check_spike_detection()

        self.logger.info("Finished with  QC checks...")

    def check_aanderaa_o2(self):
        """
        When using Aandera O2 data, BAD_SSTC will need to be recorded for o2
        when there is missing salinity.
        """
        sbe16_ncfile = self.src_dir / core.SBE16_NCFILE
        met_ncfile = self.src_dir / core.MET_NCFILE
        if not sbe16_ncfile.exists() or not met_ncfile.exists():
            # if no sbe16 file, there is nothing to do
            return

        with xr.open_dataset(met_ncfile) as ds:
            df = ds.to_dataframe()

        with netCDF4.Dataset(sbe16_ncfile, mode='r+') as nc:
            if 'o2_qc' not in nc.variables:
                return

            qc = nc['o2_qc'][:]
            qc = np.where(
                df['SSS_qc'] != core.quality.GOOD,
                np.bitwise_or(
                    self.clear_flag(qc, core.quality.GOOD),
                    core.quality.BAD_SSTC,
                ),
                qc
            )
            qc = np.where(
                df['SST_qc'] != core.quality.GOOD,
                np.bitwise_or(
                    self.clear_flag(qc, core.quality.GOOD),
                    core.quality.BAD_SSTC,
                ),
                qc
            )
            nc['o2_qc'][:] = qc

    def check_external_sami(self):
        """
        If there is external sami, then there is a flag column.  It needs to be
        converted from the raw values into the QC bitmask.
        """
        ncfile = self.src_dir / core.EXTERNAL_SAMI_NCFILE
        if not ncfile.exists():
            # if no external sami file, there is nothing to do
            return

        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            qc = nc['ph_qc'][:]
            flag = nc['external_flag'][:]

            # were there outliers?
            qc = np.where(
                np.logical_and(flag, core.external_sami_quality.OUTLIER),
                np.bitwise_or(qc, core.quality.EXTERNAL_SAMI_OUTLIER),
                qc
            )

            # was there a pump issue?
            qc = np.where(
                np.logical_and(flag, core.external_sami_quality.PUMP),
                np.bitwise_or(qc, core.quality.EXTERNAL_SAMI_PUMP),
                qc
            )

            # was there a saturation issue?
            qc = np.where(
                np.logical_and(flag, core.external_sami_quality.SATURATION),
                np.bitwise_or(qc, core.quality.EXTERNAL_SAMI_SATURATION),
                qc
            )

            # was there a blank issue?
            qc = np.where(
                np.logical_and(flag, core.external_sami_quality.BLANK),
                np.bitwise_or(qc, core.quality.EXTERNAL_SAMI_BLANK),
                qc
            )

            nc['ph_qc'][:] = qc

    def check_rh_temp_stddev(self):
        """
        Original comments in VBA:

            l) Compare Relative Humidity Temperature standard deviation
            for Air Pump Off, Span Pump Off, Equil Pump Off with Max RH
            Temp Std Dev defined in Date sheet.

            Look at RHTemp Std dev
        """
        valid_range = np.array([0, self.max_rh_temp_std], dtype=np.float64)

        for label, stem in zip(
            ("APOFF", "SPOFF", "EPOFF"),
            (
                core.licor.APOFF_NCFILE,
                core.licor.SPOFF_NCFILE,
                core.licor.EPOFF_NCFILE
            )
        ):
            ncfile = self.src_dir / stem

            self.logger.info(f"Checking RH TEMP STDDEV in {ncfile}...")

            self.clear_qc(
                ncfile, 'rh_temp_qc', core.quality.EXCESS_RH_TEMP_STDDEV
            )

            with netCDF4.Dataset(ncfile, mode='r+') as nc:
                # the valid range is not yet set so set it here
                nc['rh_temp_stddev'].valid_range = valid_range

            with netCDF4.Dataset(ncfile, mode='r+') as nc:

                data = nc['rh_temp_stddev'][:]

                if np.isscalar(data.mask) and not data.mask:
                    # If there is no masked data, then "mask" is not a full
                    # boolean array.  numpy doesn't like us using np.nonzero
                    # on this.  Grrr...
                    break

                # This finds values outside of the valid range.  The mask will
                # tell us this, but it also gives us "too much".  We don't want
                # to consider the fill value here.
                qc = nc['rh_temp_qc'][:]
                qc = np.where(
                    np.logical_and(data.mask, data.data != data.fill_value),
                    np.bitwise_or(
                        self.clear_flag(qc, core.quality.GOOD),
                        core.quality.EXCESS_RH_TEMP_STDDEV),
                    qc
                )

                # how many bad values?
                bad_idx = np.nonzero(
                    np.bitwise_and(qc, core.quality.EXCESS_RH_TEMP_STDDEV)
                )
                bad_idx = bad_idx[0]

                # log the bad values
                if len(bad_idx) > 0:
                    msg = (
                        f"{label} RH TEMP STDDEV is greater than threshold "
                        f"value {self.max_rh_temp_std:.2f} "
                        f" a total of {len(bad_idx)} times"
                    )
                    self.logger.warning(msg)

                # And finally, write the QC back.
                nc['rh_temp_qc'][:] = qc

        # Set the valid range to be the same for the pump - "on" files as well.
        for stem in [
            core.licor.APON_NCFILE,
            core.licor.SPON_NCFILE,
            core.licor.EPON_NCFILE
        ]:
            with netCDF4.Dataset(ncfile, mode='r+') as nc:
                ncfile = self.src_dir / stem
                nc['rh_temp_stddev'].valid_range = valid_range

    def check_rh_stddev(self):
        """
        Original comments in VBA:

            Look at RH Std dev
            k) Compare Relative Humidity standard deviation for Air Pump Off,
            Span Pump Off, Equil Pump Off with Max RH Std Dev defined in
            Date sheet.
        """
        valid_range = np.array([0, self.max_rh_std], dtype=np.float64)

        for label, stem in zip(
            ("APOFF", "SPOFF", "EPOFF"),
            (
                core.licor.APOFF_NCFILE,
                core.licor.SPOFF_NCFILE,
                core.licor.EPOFF_NCFILE
            )
        ):
            ncfile = self.src_dir / stem

            self.logger.info(f"Checking RH STDDEV in {ncfile}...")

            self.clear_qc(ncfile, 'rh_qc', core.quality.EXCESS_RH_STDDEV)

            with netCDF4.Dataset(ncfile, mode='r+') as nc:
                # Set the valid range here.
                nc['rh_stddev'].valid_range = valid_range

            with netCDF4.Dataset(ncfile, mode='r+') as nc:

                data = nc['rh_stddev'][:]
                if np.isscalar(data.mask) and not data.mask:
                    # If there is no masked data, then "mask" is not a full
                    # boolean array.  numpy doesn't like us using np.nonzero
                    # on this.  Grrr...
                    break

                qc = nc['rh_qc'][:]

                # This finds values outside of the valid range or equal to the
                # fill value.  We don't want to consider the fill value here.
                # Be sure to clear out any GOOD flags there.
                qc = np.where(
                    np.logical_and(data.mask, data.data != data.fill_value),
                    np.bitwise_or(
                        self.clear_flag(qc, core.quality.GOOD),
                        core.quality.EXCESS_RH_STDDEV
                    ),
                    qc
                )

                # how many bad values?
                bad_idx = np.nonzero(
                    np.bitwise_and(qc, core.quality.EXCESS_RH_STDDEV)
                )
                bad_idx = bad_idx[0]

                # log the bad values
                if len(bad_idx) > 0:
                    msg = (
                        f"{label} RH STDDEV is greater than threshold "
                        f"value {self.max_rh_std:.2f} "
                        f" a total of {len(bad_idx)} times"
                    )
                    self.logger.warning(msg)

                # Write the QC back.
                nc['rh_qc'][:] = qc

        # Set the valid range to be the same for the pump - "on" files as well.
        for stem in [
            core.licor.APON_NCFILE,
            core.licor.SPON_NCFILE,
            core.licor.EPON_NCFILE
        ]:
            with netCDF4.Dataset(ncfile, mode='r+') as nc:
                ncfile = self.src_dir / stem
                nc['rh_stddev'].valid_range = valid_range

    def check_spike_detection(self):
        """
        Check each variable for spikes.

        The netCDF4 package employs masked arrays to represent variable data,
        which has implicit support for the valid_range attribute (any value
        outside of the valid range is "masked").  But other netCDF clients
        do not necessarily have this support, so we record violations of the
        valid range in the ancillary QC variable.
        """
        if not self.spike_detection:
            return

        for ncfile in self.src_dir.glob('*.nc'):

            if core.CYCLE_HEADER_NCFILE in ncfile.name:
                # Don't bother with spike detection with the latitude/longitude
                # data.
                continue

            self.logger.info(f"Checking for spikes in {ncfile}...")

            with netCDF4.Dataset(ncfile, 'r+') as nc:
                for varname in nc.variables:

                    qc_varname = get_qc_mask_varname(nc, varname)
                    if qc_varname is None:
                        # If a QC variable is not defined, then we have nothing
                        # to do.
                        continue

                    data = nc[varname][:]
                    qc = nc[qc_varname][:]

                    od = OutlierDetector(byFrameGeneratorFactory(),
                                         InterquartileVarianceAlgorithm())
                    outliers = od.outliers(data.data.copy())
                    outliers = outliers.reshape((len(outliers),))

                    qc = np.where(
                        outliers,
                        np.bitwise_or(qc, core.quality.SPIKE_DETECTED),
                        qc
                    )

                    nc[qc_varname][:] = qc

    def check_apoff_apon_pressure_differences(self):
        """
        Original comments in VBA:

            'j) Test whether pressure difference between Air Pump Off
            and Air Pump On are within range defined in Air Pres Diff
            Range defined Date sheet.
        """
        self.logger.info('Checking APON/APOFF pressure differences...')

        valid_range = [
            self.air_diff_range_lower, self.air_diff_range_higher
        ]

        ncfile1 = self.src_dir / core.licor.APOFF_NCFILE
        ncfile2 = self.src_dir / core.licor.APON_NCFILE

        label = "APOFF/APON"

        self._check_pressure_differences(
            ncfile1, ncfile2, valid_range, label,
            core.quality.AIR_PUMP_PRESSURE_DIFFERENCE
        )

    def _check_pressure_differences(
        self, ncfile1, ncfile2, valid_range, label, pressure_flag
    ):
        """
        Perform the pressure difference check.  Set the QC flags accordingly

        Parameters
        ----------
        ncfile1, ncfile2 : str or path
            The two netCDF files containing the pressure variable.
        valid_range : 2-tuple or 2-element list
            The valid range for the pressure difference.
        pressure_flag : int
            If the pressure difference is out of the valid range, set this
            bit in the qc flag mask.
        """
        # clear any existing flags first
        self.clear_qc(ncfile1, 'pressure_qc', pressure_flag)
        self.clear_qc(ncfile2, 'pressure_qc', pressure_flag)

        with netCDF4.Dataset(ncfile1) as nc:
            press1 = nc['pressure'][:]
            qc1 = nc['pressure_qc'][:]

        with netCDF4.Dataset(ncfile2) as nc:
            press2 = nc['pressure'][:]
            qc2 = nc['pressure_qc'][:]

        # Log any differences that are out of range.
        bad_idx = np.nonzero(
            np.logical_or(
                np.abs(press1 - press2) < valid_range[0],
                np.abs(press1 - press2) > valid_range[1]
            )
        )
        if len(bad_idx[0]) > 0:
            msg = (
                f"{label} pressure difference was out of range "
                f"{valid_range} a total of {len(bad_idx[0])} time(s)."
            )
            self.logger.warning(msg)

        # Be sure to zero out any good QC where we found bad data.
        qc1[bad_idx] = np.bitwise_or(
            self.clear_flag(qc1[bad_idx], core.quality.GOOD),
            pressure_flag
        )
        qc2[bad_idx] = np.bitwise_or(
            self.clear_flag(qc2[bad_idx], core.quality.GOOD),
            pressure_flag
        )

        # Write the QC back
        with netCDF4.Dataset(ncfile1, mode='r+') as nc:
            nc['pressure_qc'][:] = qc1
        with netCDF4.Dataset(ncfile2, mode='r+') as nc:
            nc['pressure_qc'][:] = qc2

    def check_spoff_spon_pressure_differences(self):
        """
        Original comments in VBA:

            h) Test whether pressure difference between Span Pump Off
            and Span Pump On are within range defined in Span Press Diff
            Range defined Date sheet.

            Look at pressure differences (skip zero pump on cycle)
        """
        self.logger.info('Checking SPON/SPOFF pressure differences...')

        valid_range = [
            self.span_diff_range_lower, self.span_diff_range_higher,
        ]

        ncfile1 = self.src_dir / core.licor.SPOFF_NCFILE
        ncfile2 = self.src_dir / core.licor.SPON_NCFILE

        label = "SPOFF/SPON"

        self._check_pressure_differences(
            ncfile1, ncfile2, valid_range, label,
            core.quality.SPAN_PUMP_PRESSURE_DIFFERENCE
        )

    def check_epoff_epon_pressure_differences(self):
        """
        Original comments in VBA:

            i) Test whether pressure difference between Equil Pump Off and
            Equil Pump On are within range defined in Equil Pres Diff Range
            defined Date sheet.
        """
        self.logger.info('Checking EPON/EPOFF pressure differences...')
        valid_range = [
            self.equil_diff_range_lower, self.equil_diff_range_higher,
        ]

        ncfile1 = self.src_dir / core.licor.EPOFF_NCFILE
        ncfile2 = self.src_dir / core.licor.EPON_NCFILE

        label = "EPOFF/EPON"

        self._check_pressure_differences(
            ncfile1, ncfile2, valid_range, label,
            core.quality.EQUILIBRATOR_PUMP_PRESSURE_DIFFERENCE
        )

    def check_apoff_spoff_epoff_pressure_differences(self):
        """
        Original comments in VBA:

            g) Compare pressures differences between Air Pump Off, Span
            Pump Off, Equil Pump Off (SPOFF _ APOFF, APOFF _ EPOFF,
            and EPOFF _ SPOFF). Pressures differences are compared to
            max_pressoff_diff set in Date sheet.  Compare Pressures of
            Air Pump off, Span Pump Off and Equil Pump Off
        """

        nc_apoff = self.src_dir / core.licor.APOFF_NCFILE
        nc_epoff = self.src_dir / core.licor.EPOFF_NCFILE
        nc_spoff = self.src_dir / core.licor.SPOFF_NCFILE

        self._check_pressure_off_difference(nc_apoff, nc_epoff)
        self._check_pressure_off_difference(nc_apoff, nc_spoff)
        self._check_pressure_off_difference(nc_epoff, nc_spoff)

    def _check_pressure_off_difference(self, ncfile1, ncfile2):
        """
        ncfile1, ncfile2 : path or str
            These two netCDF files are any two of the set APOFF, EPOFF, SPOFF
        """
        self.__check_pressure_off_differences(ncfile1, ncfile2)
        self.__check_pressure_off_differences(ncfile2, ncfile1)

    def __check_pressure_off_differences(self, ncfile, ncfile_ref):

        label = core.mapco2core.file2label(ncfile)
        label_ref = core.mapco2core.file2label(ncfile_ref)

        label = f"{label}/{label_ref}"

        self.logger.info(f"Checking {label} pressure differences...")

        with xr.open_dataset(ncfile) as ds:
            press = ds['pressure'].to_pandas()
            qc = ds['pressure_qc'].to_pandas().astype(np.uint32)

        with xr.open_dataset(ncfile_ref) as ds:
            press_ref = ds['pressure'].to_pandas()
            qc_ref = ds['pressure_qc'].to_pandas()

            press_ref = press_ref.reindex(press.index, method='nearest')
            qc_ref = qc_ref.reindex(qc.index, method='nearest').astype(np.uint32)  # noqa : E501

        # Log any differences that exceed the threshold.
        bad_idx = np.abs(press - press_ref) > self.max_pressoff_diff
        num_bad = sum(bad_idx)
        if num_bad > 0:
            msg = (
                f"{label} pressure difference exceeded threshold "
                f"{self.max_pressoff_diff} {num_bad} time(s)"
            )
            self.logger.warning(msg)

        if num_bad == 0:
            return

        qc[bad_idx] = np.bitwise_or(core.quality.EXCESS_PRESSURE_OFF_DIFFERENCE, qc[bad_idx])  # noqa : E501

        # Write the QC back
        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            nc['pressure_qc'][:] = qc

    def check_apoff_xco2_stddev(self):
        """
        Original comments in VBA:

            e) xCO2 trend analysis in Air Pump Off.  Described in
            check_epoff_xco2_stddev.
        """
        ncfile = self.src_dir / core.licor.APOFF_NCFILE
        max_xco2_stddev = self.max_air_xco2_std
        self._check_xco2_stddev(ncfile, max_xco2_stddev)

    def _check_xco2_stddev(self, ncfile, max_xco2_stddev):
        """
        Parameters
        ----------
        ncfile: path or str
            Either APOFF or EPOFF netCDF file
        max_xco2_stddev: float
            Largest allowed standard deviation (APOFF and EPOFF can be
            different.
        """

        self.logger.info(f"Checking xCO2 standard deviation in {ncfile}...")

        # Clear any existing flags first.
        self.clear_qc(
            ncfile,
            'xco2_wet_qc',
            core.quality.TREND_STDDEV_OUT_OF_RANGE
        )
        self.clear_qc(
            ncfile,
            'xco2_wet_qc',
            core.quality.RAW_STDDEV_OUT_OF_RANGE
        )

        # The window is centered, so the total size is "num_points_eachside"
        # each way, plus the center point.
        n = int(self.num_points_eachside)
        window_size = 2 * n + 1

        # Compute "trend" or rolling mean and stddevs.
        with xr.open_dataset(ncfile) as ds:
            ds.load()

            xco2 = ds['xco2_wet'].to_series()
            xco2_stddev = ds['xco2_wet_stddev'].to_series()
            qc = ds['xco2_wet_qc'].to_series().astype(np.uint32)

            # Compute the population standard deviation, apparently, not
            # sample standard deviation.
            #
            # xarray may issue a warning here if there are nans in the data.
            # seems harmless though.
            xco2_std_range = xco2.rolling(window_size, center=True).std(ddof=0)  # noqa : E501
            xco2_ave_range = xco2.rolling(window_size, center=True).mean()

            # Fill in the leading and lagging half windows.  Just assume that
            # it's the first/last non-nan value.  This is equivalent to
            # ffill/backfill in those half windows.
            xco2_std_range[:n] = xco2_std_range.iloc[n]
            xco2_ave_range[:n] = xco2_ave_range.iloc[n]
            xco2_std_range[-n - 1:] = xco2_std_range.iloc[-n - 1]
            xco2_ave_range[-n - 1:] = xco2_ave_range.iloc[-n - 1]

            std_thresh = self.xco2_trend_std * xco2_std_range
            absdiff = np.abs(xco2 - xco2_ave_range)

            qc = np.where(
                absdiff > std_thresh,
                np.bitwise_or(
                    self.clear_flag(qc, core.quality.GOOD),
                    core.quality.TREND_STDDEV_OUT_OF_RANGE,
                ),
                qc
            )

            qc = np.where(
                xco2_stddev > max_xco2_stddev,
                np.bitwise_or(
                    self.clear_flag(qc, core.quality.GOOD),
                    core.quality.RAW_STDDEV_OUT_OF_RANGE,
                ),
                qc
            )

        label = core.mapco2core.file2label(ncfile)

        # Log any bad values.
        idx_bad = np.argwhere(
            np.bitwise_and(qc, core.quality.TREND_STDDEV_OUT_OF_RANGE)
        )
        if len(idx_bad) > 0:
            msg = (
                f"{label}:xCO2_wet trend exceeded local thresholds "
                f"a total of {len(idx_bad)} time(s)"
            )
            self.logger.warning(msg)

        idx_bad = np.argwhere(
            np.bitwise_and(qc, core.quality.RAW_STDDEV_OUT_OF_RANGE)
        )
        if len(idx_bad) > 0:
            msg = (
                f"{label}:xCO2_wet raw std exceeds threshold value "
                f"{max_xco2_stddev} a total of {len(idx_bad)} "
                "times."
            )
            self.logger.warning(msg)

        # and finally, write the new QC values back to file
        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            nc['xco2_wet_qc'][:] = qc

    def check_epoff_xco2_stddev(self):
        """
        Original comments in VBA:

            e) xCO2 trend analysis in Equil Pump Off. Computes average
            xCO2 and standard deviation in a range around each value
            (number of points on each side of point is set in Date
            sheet). These values are compared to measured xCO2 and
            standard deviation of Equil Pump Off cycle to the computed
            mean and standard deviation of the range around the point.
            Possible errors are Trend and Standard Deviation are off,
            Trend is off, and Standard Deviation is off.

            Checks std dev of Equil Pump Off cycle and also look at
            trends in xCO2 values
        """
        ncfile = self.src_dir / core.licor.EPOFF_NCFILE
        max_xco2_stddev = self.max_equil_xco2_std
        self._check_xco2_stddev(ncfile, max_xco2_stddev)

    def check_zpostcal_xco2_range(self):
        """
        Original comments in VBA:

        b) Check xCO2 in Zero Pump Off in the range Zero Value Range defined
        in Date sheet.

        Check the "Zero Post Cal" value to see if it is within
        Num_ppm_below_zero of zero
        """
        ncfile = self.src_dir / core.licor.ZPOSTCAL_NCFILE
        self._check_xco2_range(ncfile)

    def check_zpoff_xco2_range(self):
        """
        Original comments in VBA:

        b) Check xCO2 in Zero Pump Off in the range Zero Value Range defined
        in Date sheet.

        Check the "Zero Pump Off" value to see if it is within
        Num_ppm_below_zero of zero
        """
        ncfile = self.src_dir / core.licor.ZPOFF_NCFILE
        self._check_xco2_range(ncfile)

    def _check_xco2_range(self, ncfile):

        self.logger.info(f"Checking for xCO2 valid range in {ncfile}...")

        self.clear_qc(ncfile, 'xco2_wet_qc', core.quality.OUT_OF_RANGE)

        with netCDF4.Dataset(ncfile, mode='r+') as nc:

            v = nc['xco2_wet']

            # Set the valid range here, as it is different than in other
            # xco2_wet datasets.
            v.valid_range = [-self.ppm_below_zero, self.ppm_above_zero]

            data = nc['xco2_wet'][:]
            valid_range = nc['xco2_wet'].valid_range
            qc = nc['xco2_wet_qc'][:]

            qc = np.where(
                # We are looking for where the data is outside of the valid
                # range, but NOT where the data is equal to the fill value
                # (which is outside of the valid range).
                np.logical_and(
                    data.data != data.fill_value,
                    np.logical_or(
                        data.data < valid_range[0],
                        data.data > valid_range[1]
                    ),
                ),
                # where this condition was satisfied, set the OUT_OF_RANGE
                # flag
                np.bitwise_or(core.quality.OUT_OF_RANGE, qc),
                # otherwise take the existing QC
                qc
            )

            nc['xco2_wet_qc'][:] = qc

        # Log any bad values.
        for idx in np.argwhere(np.bitwise_and(qc, core.quality.OUT_OF_RANGE)):

            label = core.mapco2core.file2label(ncfile)
            msg = (
                f"{label}:xCO2_wet[{idx}] = {data[idx].item():.2f} "
                f"not in range {valid_range}"
            )
            self.logger.warning(msg)

    def check_loss_of_span(self):
        """
        Original comments:

            Check the span flag and zero flag in Zero Pump On. If point
            is recalculated, this test is skipped no matter whether
            short circuit is on or off.

            Currently we skip processing a point that has a flag value and the
            deployment has be recalculated

            This was check (a) in the QC VBA module.
        """
        ncfile = self.src_dir / core.CYCLE_HEADER_NCFILE

        self.logger.info(f"Checking for loss of span in {ncfile}...")

        with netCDF4.Dataset(ncfile) as nc:
            span_flag = nc['span_flag'][:]
            zero_flag = nc['zero_flag'][:]

            idx = np.argwhere(np.logical_or(span_flag, zero_flag))
            if len(idx) > 0:

                self.logger.warning(
                    f"ZPON: {len(idx)} non-zero values of span_flag, zero_flag"
                )

    def check_spoff_spostcal_xco2_in_span_range(self):
        """
        Check that xCO2 in Span Post Cal, Span OFF is in the range of
        [span_value - zero_value, span_value + zero_value] as defined in the
        configuration YAML file.

        This was check (d) in the QC VBA module.
        """
        span_range = [
            self.initial_span_cal - self.ppm_below_span_cal,
            self.initial_span_cal + self.ppm_above_span_cal,
        ]

        for label, stem in zip(
            ["SPOSTCAL", "SPOFF"],
            [core.licor.SPOFF_NCFILE, core.licor.SPOSTCAL_NCFILE]
        ):

            ncfile = self.src_dir / stem

            self.clear_qc(
                ncfile, 'xco2_wet_qc', core.quality.OUT_OF_SPAN_RANGE
            )

            self.logger.info(f"Checking for xCO2 in span range in {ncfile}...")

            with netCDF4.Dataset(ncfile, mode='r+') as nc:
                data = nc['xco2_wet'][:]
                qc = nc['xco2_wet_qc'][:]

                # Flip the qc flag where data is outside of the span range,
                # but not where the data is already equal to the fill value.
                qc = np.where(
                    np.logical_and(
                        ~data.mask,
                        np.logical_or(
                            data < span_range[0],
                            data > span_range[1]
                        )
                    ),
                    # and clear any good flags at such data points
                    np.bitwise_or(
                        self.clear_flag(qc, core.quality.GOOD),
                        core.quality.OUT_OF_SPAN_RANGE
                    ),
                    qc
                )

                nc['xco2_wet_qc'][:] = qc

            # Log any out of range values.
            idx = np.argwhere(
                np.bitwise_and(qc, core.quality.OUT_OF_SPAN_RANGE)
            )
            if len(idx) > 0:

                self.logger.warning(
                    f"{len(idx)} values of {label}:xCO2 not in range "
                    f"[{span_range[0]:.1f}, {span_range[1]:.1f}]"
                )

    def check_valid_range(self):
        """
        Check each variable for its valid range if it has a valid range
        attribute defined.

        The netCDF4 package employs masked arrays to represent variable data,
        which has implicit support for the valid_range attribute (any value
        outside of the valid range is "masked").  But other netCDF clients
        do not necessarily have this support, so we record violations of the
        valid range in the ancillary QC variable.
        """
        for ncfile in self.src_dir.glob('*.nc'):

            with xr.open_dataset(ncfile) as ds:

                # don't process certain netCDF files
                if ds.data_source in ['validation']:
                    continue

            with netCDF4.Dataset(ncfile, 'r+') as nc:

                for varname in nc.variables:

                    qc_varname = get_qc_mask_varname(nc, varname)
                    if qc_varname is None:
                        # If a QC variable is not defined, then we have nothing
                        # to do.
                        continue

                    self.clear_qc(
                        nc, qc_varname, core.quality.OUT_OF_RANGE
                    )

                    data = nc[varname][:]

                    qc = nc[qc_varname][:]

                    # Any NaNs are out of range
                    qc = np.where(
                        np.isnan(data),
                        np.bitwise_or(qc, core.quality.OUT_OF_RANGE),
                        qc
                    )

                    # If the data is masked, then it is out of range.
                    # Be sure to clear the GOOD flag.
                    if hasattr(data, 'mask'):
                        qc = np.where(
                            data.mask,
                            np.bitwise_or(
                                np.bitwise_and(qc, (~core.quality.GOOD) & 0xFFFFFFFF),
                                core.quality.OUT_OF_RANGE
                            ),
                            qc
                        )

                    # And finally, look at the valid_range attribute,
                    # if it exists.
                    if hasattr(nc[varname], 'valid_range'):
                        valid_min, valid_max = nc[varname].valid_range

                        qc = np.where(
                            (data < valid_min) | (data > valid_max),
                            np.bitwise_or(qc, core.quality.OUT_OF_RANGE),
                            qc
                        )

                    nc[qc_varname][:] = qc
