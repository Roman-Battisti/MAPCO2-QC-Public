# standard library imports
import logging


class XCO2SetupLogFile(object):

    def __init__(self, logfile):

        logger = logging.getLogger('xco2qc')
        logger.setLevel(logging.INFO)

        format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        formatter = logging.Formatter(format)

        fh = logging.FileHandler(logfile)
        fh.setLevel(logging.INFO)
        fh.setFormatter(formatter)

        logger.addHandler(fh)

    def run(self):
        pass
