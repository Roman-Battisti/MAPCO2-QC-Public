# standard library imports
import collections
import pathlib
import tempfile
import unittest

# 3rd party library imports
import yaml

# local imports
import xco2qc.aux_sensor_gui
from xco2qc.qc import KEYWORDS
from xco2qc.qc_gui import (
    QCGui, APON_APOFF_MIN_PRESSURE_DIFFERENCE,
    EPON_EPOFF_MIN_PRESSURE_DIFFERENCE, SPON_SPOFF_MIN_PRESSURE_DIFFERENCE
)
from xco2qc.update_config import update_config_file
from . import test_core


class TestSuite(test_core.TestSuite):
    def test_save(self):
        """
        Scenario:  changing parameters in AuxSensorGui and QCGui should result in
        changes to config.yml when update_config_file is run.

        Expected result:  config.yml should now have the changed values and additional
        QCGui parameters not normally stored in the config.yml.
        """
        
        # from test_qc_gui.py line 65
        root_dir = tempfile.TemporaryDirectory()
        root_path = pathlib.Path(root_dir.name)
        new_dst_dir = tempfile.TemporaryDirectory(dir=root_dir.name)
        new_dst_path = pathlib.Path(new_dst_dir.name)
        
        
        
        # from test_aux_sensor_gui.py line 36
        with xco2qc.aux_sensor_gui.AuxSensorGui(
            src_dir=self.raw_path, dst_dir=self.reduced_path
        ) as aux_gui:
            aux_gui.run()
        
        # from test_aux_sensor_gui.py line 64
        # change a few values in aux_gui so these changes are reflected in the saved config.yml
        aux_gui.calibration_box.children[1].children[1].value = '1'
        aux_gui.calibration_box.children[2].children[1].value = '2'
        
        
        # from test_qc_gui.py
        with QCGui() as qc:
            qc.run()
        
        # change a few values in qc gui so these changes are reflected in teh saved config.yml
        qc.apon_apoff_min_slider.value = 6
        
        update_config_file(self.raw_path.parents[0], aux_gui.gather_kwargs(), qc.gather_kwargs())
        
        # from test_config.py line 129
        root = self.raw_path.parents[0]
        new_config_file = root / 'config.yml'
        with new_config_file.open() as f:
            d = yaml.safe_load(f)
        
        # from test_aux_sensor_gui.py line 84
        # test changed parameters reflected correctly in loaded config.yml
        self.assertEqual(d['QC']['chl_scale_factor'], [1])
        self.assertEqual(d['QC']['chl_dark_count'], [2])
        
        self.assertEqual(d['QC']['air_diff_range_lower'], 6)
        
        # check new parameters were added to config.yml
        for param in ['num_points_eachside', 'sbe16_mapping', 'spike_detection']:
            assert param in d['QC']