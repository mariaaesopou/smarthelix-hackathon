"""A local SparkSession for development, tests and the benchmark.

Role 1's runner builds its own session for spark-submit; this one is for working
on the ML functions on a laptop.
"""

import os
import sys
import urllib.request
from pathlib import Path

from pyspark.sql import SparkSession

POSTGRES_VERSION = "42.7.4"
POSTGRES_DRIVER = f"org.postgresql:postgresql:{POSTGRES_VERSION}"
_CACHE = Path.home() / ".cache" / "smarthelix-ml"


def get_spark(
    app_name: str = "smarthelix-ml",
    master: str = "local[*]",
    driver_memory: str = "2g",
    jdbc: bool = False,
) -> SparkSession:
    # Workers must use the same interpreter as the driver (matters on Windows).
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)

    builder = (
        SparkSession.builder.appName(app_name)
        .master(master)
        .config("spark.driver.memory", driver_memory)
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.ui.enabled", "false")
    )
    if jdbc:
        if os.name == "nt" and master.startswith("local"):
            # spark.jars.packages needs Hadoop's winutils.exe on Windows. In local mode
            # driver and executors share one JVM, so the jar on the driver classpath is enough.
            builder = builder.config("spark.driver.extraClassPath", str(_postgres_jar()))
        else:
            builder = builder.config("spark.jars.packages", POSTGRES_DRIVER)
    return builder.getOrCreate()


def _postgres_jar() -> Path:
    """The Postgres JDBC jar: Ivy's cache if present, else downloaded once from Maven Central."""
    name = f"org.postgresql_postgresql-{POSTGRES_VERSION}.jar"
    for candidate in (Path.home() / ".ivy2" / "jars" / name, _CACHE / name):
        if candidate.is_file():
            return candidate
    _CACHE.mkdir(parents=True, exist_ok=True)
    target = _CACHE / name
    url = (f"https://repo1.maven.org/maven2/org/postgresql/postgresql/"
           f"{POSTGRES_VERSION}/postgresql-{POSTGRES_VERSION}.jar")
    urllib.request.urlretrieve(url, target)
    return target
