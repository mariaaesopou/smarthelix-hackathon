"""Load live profiles from Postgres into a DataFrame with the agreed columns."""

import os
from urllib.parse import unquote, urlparse

from pyspark.sql import DataFrame, SparkSession

from .schema import to_profile_frame

# Local default = the docker-compose dev database (see docker-compose.yml).
LOCAL_DATABASE_URL = "postgres://smarthelix:smarthelix_dev@127.0.0.1:5432/smarthelix"

# Live profiles only: not deleted, not merged into another profile.
# The generated `search` tsvector is left out: Spark's JDBC reader cannot map it.
PROFILES_QUERY = """
SELECT id::text AS id, type, name, description, sector, region,
       skills, services, needs, languages
FROM profiles
WHERE deleted_at IS NULL AND merged_into IS NULL
"""


def jdbc_options(database_url: str) -> dict[str, str]:
    """postgres://user:pass@host:port/db?... -> Spark JDBC options."""
    u = urlparse(database_url)
    if u.scheme not in ("postgres", "postgresql"):
        raise ValueError("DATABASE_URL must start with postgres:// or postgresql://")
    return {
        "url": f"jdbc:postgresql://{u.hostname}:{u.port or 5432}{u.path}",
        "user": unquote(u.username or ""),
        "password": unquote(u.password or ""),
        "driver": "org.postgresql.Driver",
    }


def load_profiles_jdbc(spark: SparkSession, database_url: str | None = None) -> DataFrame:
    """Read live profiles. Needs a session built with get_spark(jdbc=True)."""
    url = database_url or os.environ.get("ML_DATABASE_URL") or LOCAL_DATABASE_URL
    df = (
        spark.read.format("jdbc")
        .options(**jdbc_options(url))
        .option("query", PROFILES_QUERY)
        .option("fetchsize", "5000")
        .load()
    )
    return to_profile_frame(df)
