# standard library imports
import datetime as dt
import importlib.resources as ir
import pathlib

# 3rd party library imports
import netCDF4
import numpy as np
import yaml

# Local imports
from . import core


class MetadataWriter(core.MapCO2core):

    def __init__(
        self, ncfile,
        creator_name=None, creator_type=None, creator_email=None,
        creator_url=None, history=None, infoUrl=None, institution=None,
        keywords=None, license=None, references=None,
        standard_name_vocabulary=None, summary=None, title=None,
        contributors_citation=None, link_citation=None,
        verbosity=None, stationary_mobile=None,
        **kwargs
    ):
        """
        Parameters
        ----------
            ncfile : path
                Write attributes to this netCDF file.
            creator_name ... title : str
                ACDD attributes
        """
        self.ncfile = pathlib.Path(ncfile)
        super().__init__(
            src_dir=self.ncfile.parents[0], verbosity=verbosity,
            logger_name='metadata'
        )

        # attributes connected to a convention (usually ACDD?)
        self.acdd_attrs = {
            'creator_name': creator_name,
            'creator_type': creator_type,
            'creator_email': creator_email,
            'creator_url': creator_url,
            'history': history,
            'infoUrl': infoUrl,
            'institution': institution,
            'keywords': keywords,
            'license': license,
            'references': references,
            'standard_name_vocabulary': standard_name_vocabulary,
            'summary': summary,
            'title': title,
            'contributors_citation': contributors_citation,
            'link_citation': link_citation,
            'stationary_mobile': stationary_mobile
        }

    def run(self):
        self.logger.info('Starting to apply metadata conventions...')

        self.write_oceansites_conventions_attributes(self.ncfile)
        self.write_acdd_conventions_attributes(self.ncfile)

        self.logger.info('Finished applying metadata conventions...')

    def write_acdd_conventions_attributes(self, ncfile):

        self.write_acdd_attributes(self.ncfile)

    def write_oceansites_conventions_attributes(self, ncfile):
        """
        Write OceanSITES attributes.  These are also ACDD attributes.

        Parameters
        ----------
        ncfile : path or str
            Open netCDF file to write attributes.
        """
        # with ir.as_file(ir.files(core.data).joinpath('oceansites.yml')) as path:
        #     with path.open() as f:
        #         attrs = yaml.safe_load(f)
        attrs = {}

        with netCDF4.Dataset(ncfile, mode='r+') as nc:

            # fill in those attributes for which we only just now have enough
            # information

            # for the geospatial bounds (lat), only use values with good QC
            lat = nc['latitude'][:]
            lat_qc = nc['latitude_qc'][:]
            good_lats = lat[lat_qc == core.quality.GOOD]
            if len(good_lats) > 0:
                minval, maxval = np.nanmin(good_lats), np.nanmax(good_lats)
            else:
                minval, maxval = np.nan, np.nan
            attrs['geospatial_lat_min'] = minval
            attrs['geospatial_lat_max'] = maxval
            attrs['geospatial_lat_units'] = 'degree_north'

            # for the geospatial bounds (lon), only use values with good QC
            lon = nc['longitude'][:]
            lon_qc = nc['longitude_qc'][:]
            good_lons = lon[lon_qc == core.quality.GOOD]
            if len(good_lons) > 0:
                minval, maxval = np.nanmin(good_lons), np.nanmax(good_lons)
            else:
                minval, maxval = np.nan, np.nan
            attrs['geospatial_lon_min'] = minval
            attrs['geospatial_lon_max'] = maxval
            attrs['geospatial_lon_units'] = 'degree_east'

            format = '%Y-%m-%dT%H:%M:%SZ'
            start = nc[core.TIME][0].item()
            time_start = dt.datetime(2000, 1, 1) + dt.timedelta(seconds=start)
            attrs['time_coverage_start'] = time_start.strftime(format)

            time_end = nc[core.TIME][-1].item()
            time_end = dt.datetime(2000, 1, 1) + dt.timedelta(seconds=time_end)
            attrs['time_coverage_end'] = time_end.strftime(format)

            total_seconds = int((time_end - time_start).total_seconds())
            days = total_seconds // 86400
            total_seconds -= days * 86400
            hours = total_seconds // 3600
            total_seconds -= hours * 3600
            minutes = total_seconds // 60
            seconds = total_seconds - minutes * 60
            attrs['time_coverage_duration'] = f"P{days}DT{hours}H{minutes}M{seconds}S"  # noqa : E501

            attrs['netcdf_version'] = netCDF4.getlibversion().split()[0]

            # and finally, write the attributes to the netcdf file
            for key, value in attrs.items():
                setattr(nc, key, value)

    def write_acdd_attributes(self, ncfile):
        """
        Write ACDD attributes not covered by OceanSITES.

        Parameters
        ----------
        ncfile : path or str
            Open netCDF file to write attributes.
        """
        with ir.as_file(ir.files(core.data).joinpath('acdd.yml')) as path:
            with path.open() as f:
                attrs = yaml.safe_load(f)

        # date_modified and date_metadata_modified are only filled at this
        # very instant.
        now = dt.datetime.now()
        attrs['date_issued'] = now.strftime('%Y-%m-%d')
        attrs['date_metadata_modified'] = now.strftime('%Y-%m-%d')

        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            for key, value in attrs.items():
                setattr(nc, key, value)

            # These were passed in via command line arguments.
            for key, value in self.acdd_attrs.items():
                if value is not None:
                    setattr(nc, key, value)

            # "date_created" doesn't need to be supplied via command line
            nc.date_created = f"{dt.date.today()}"
