# standard library tests
import os
import pathlib
import shutil
import tempfile
import unittest

# 3rd party library imports
import numpy as np
import xarray as xr
import yaml

# local imports
from xco2qc.core import MERGE_NCFILE, MODELS_FILE
import xco2qc.aux_sensor_gui
from xco2qc.load_project import load_project, MissingSubDirectoryException, MissingFileException
import xco2qc.core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from . import test_core


# check os.rename to rename tempfile directories. This may be a bad idea...
# make sure to use shutil.rmtree(root) to get rid of folder structure at end.
# May want to check that folder doesn't exist at the end and use try...finally to make sure rmtree is called.


# from test_config.py
class TestSuiteExpectingException(unittest.TestCase):
    """
    Tests for proper errors when various paths/files are missing.
    """
    
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.required_sub_dirs = {'reduced': None, 'trimmed': None, 'merge': None}
        self.generator = directory_generator(self.root, list(self.required_sub_dirs.keys()))
    
    def _run_load_expecting_failure(
        self, expected_exception
    ):
    
        with self.assertRaises(expected_exception):
            load_project(self.root)
    
    def test__missing_components(self):
        
        # no config file should exist in the raw directory
        self._run_load_expecting_failure(MissingFileException)
        
        # create config file to test next error
        temp_config = tempfile.NamedTemporaryFile(suffix='.yml', dir=self.root, delete=False).name
        config_path = os.path.join(self.root, 'config.yml')
        os.rename(temp_config, config_path)
        config_contents = {'test': 'success'}
        # write something to the config file
        with open(config_path, 'w') as f:
            yaml.dump(config_contents, f)
        self._run_load_expecting_failure(MissingSubDirectoryException)
        
        # build various directories then test for expected next error
        for i, d, e in zip(
                    list(self.required_sub_dirs.keys()),
                    self.generator,
                    [MissingSubDirectoryException,
                     MissingSubDirectoryException,
                     MissingFileException]
                           ):
            self.required_sub_dirs[i] = d
            self._run_load_expecting_failure(e)
        
        # build final files
        temp_pkl = tempfile.NamedTemporaryFile(suffix='.pkl', dir=self.required_sub_dirs['reduced'], delete=False).name
        pkl_path = os.path.join(self.required_sub_dirs['reduced'], MODELS_FILE)
        os.rename(temp_pkl, pkl_path)
        self._run_load_expecting_failure(MissingFileException)
        
        temp_merge_nc = tempfile.NamedTemporaryFile(suffix='.nc', dir=self.required_sub_dirs['merge'], delete=False).name
        merge_nc_path = os.path.join(self.required_sub_dirs['merge'], MERGE_NCFILE)
        os.rename(temp_merge_nc, merge_nc_path)
        
        # everything required should now exist, test that the load outputs the expected paths
        trimmed_dir, merge_dir, models_file, merge_ncfile, config = load_project(self.root)
        self.assertEqual(str(trimmed_dir), str(self.required_sub_dirs['trimmed']))
        self.assertEqual(str(merge_dir), str(self.required_sub_dirs['merge']))
        self.assertEqual(str(models_file), str(pkl_path))
        self.assertEqual(str(merge_ncfile), str(merge_nc_path))
        self.assertDictEqual(config, config_contents)
    
    def tearDown(self):
        shutil.rmtree(self.root)


def directory_generator(root_dir, new_sub_dirs: list):
    for d in new_sub_dirs:
        temp_dir = tempfile.mkdtemp(dir=root_dir)
        new_dir = os.path.join(root_dir, d)
        os.rename(temp_dir, new_dir)
        yield new_dir