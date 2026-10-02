# standard library imports
import yaml

# local imports
from .core import MERGE_NCFILE, MODELS_FILE


def load_project(output_root):
    """
    Load folder, file paths and appropriate config parameters for a previously started project.
    Checks for existence of each folder/file.
    
    :param output_root: (str or PathLike) top level directory of a xco2qc file structure
    
    :output trimmed_dir: (PathLike) path to trimmed directory
    :output merge_dir: (PathLike) path to merge directory
    :output models_file: (PathLike) path to models file
    :output merge_ncfile: (PathLike) path to merge NetCDF file
    :output config: (dict) dictonary of quality control parameters.
    """
    
    # check for config file existance
    config_path = output_root / 'config.yml'
    if not config_path.exists():
        raise MissingFileException("config.yml file does not exist!")
    
    # check for existing reduced, trimmed, and merge subfolders
    reduced_dir = output_root / "reduced"
    trimmed_dir = output_root / "trimmed"
    merge_dir = output_root / "merge"
    if not reduced_dir.exists():
        raise MissingSubDirectoryException("reduced sub-directory does not exist!")
    if not trimmed_dir.exists():
        raise MissingSubDirectoryException("trimmed sub-directory does not exist!")
    if not merge_dir.exists():
        raise MissingSubDirectoryException("merge sub-directory does not exist!")
    
    # check for existing MODELS_FILE, MERGE_NCFILE
    models_file = reduced_dir / MODELS_FILE
    merge_ncfile = merge_dir / MERGE_NCFILE
    if not models_file.exists():
        raise MissingFileException(f"{MODELS_FILE} does not exist!")
    if not merge_ncfile.exists():
        raise MissingFileException(f"{MERGE_NCFILE} does not exist!")
    
    # since all directories and files exist, now load config.
    with config_path.open() as f:
        config = yaml.safe_load(f)
    
    return trimmed_dir, merge_dir, models_file, merge_ncfile, config


class MissingSubDirectoryException(Exception):
    pass


class MissingFileException(Exception):
    pass