import pytest

from smarthelix_ml.session import get_spark


@pytest.fixture(scope="session")
def spark():
    s = get_spark("smarthelix-ml-tests", master="local[1]", driver_memory="1g")
    s.sparkContext.setLogLevel("ERROR")
    yield s
    s.stop()
