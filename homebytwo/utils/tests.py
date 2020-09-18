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


def raise_connection_error(self, request, uri, headers):
    """
    raises a connection error to use as the body of the mock
    response in httpretty. Unfortunately httpretty outputs to stdout:
    cf. https://stackoverflow.com/questions/36491664/
    """
    raise ConnectionError("Connection error.")
