import yaml

def update_config_file(source_dir, aux_kwargs, qc_kwargs):
    config_path = source_dir / 'config.yml'
    if config_path.exists():
        with config_path.open() as f:
            config = yaml.safe_load(f)
    else:
        raise MissingFileException("No config.yml exists!")
    
    # update config from aux_kwargs
    for k, v in aux_kwargs.items():
        config["QC"][k] = v
    
    # update config from qc_kwargs
    for k, v in qc_kwargs.items():
        config["QC"][k] = v
    
    with config_path.open("w") as f:
        yaml.dump(config, f)


class MissingFileException(Exception):
    pass