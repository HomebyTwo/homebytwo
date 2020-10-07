from pathlib import Path


def open_data(file, dir_path, binary=True):
    data_dir = Path("data")
    path = dir_path / data_dir / file

    if binary:
        return open(path, "rb")
    else:
        return open(path)


def read_data(file, dir_path=Path(__file__).resolve().parent, binary=False):
    return open_data(file, dir_path, binary).read()
