# standard library imports
import pathlib
import tempfile

# local imports
from xco2qc.external_data import ImportExternalData
from . import test_core


class TestSuite(test_core.TestSuite):

    def test_is_a_directory_error(self):
        """
        Scenario:  a directory is provided

        Expected result:  No errors.  Nothing in the output directory.
        """

        tdir = tempfile.mkdtemp()
        tpath = pathlib.Path(tdir)

        with ImportExternalData(tdir, dst_dir=tdir) as o:
            o.run()

        tpath = pathlib.Path(tdir)
        lst = list(tpath.glob('*.nc'))
        self.assertEqual(len(lst), 0)

    def test_is_a_path_error(self):
        """
        Scenario:  a directory path is provided

        Expected result:  No errors.  Nothing in the output directory.
        """

        tdir = tempfile.mkdtemp()
        tpath = pathlib.Path(tdir)

        with ImportExternalData(tpath, dst_dir=tdir) as o:
            o.run()

        lst = list(tpath.glob('*.nc'))
        self.assertEqual(len(lst), 0)
