"""The ML input contract: the columns of `profiles` the ML functions read.

Mirrors db/migrations/20261125000002_core_tables.sql. Names, ids and type are
carried through for output and filtering only; they are never model features
(docs/architecture.md, item 19).
"""

from pyspark.sql import DataFrame, functions as F
from pyspark.sql.types import ArrayType, StringType, StructField, StructType

TEXT_ARRAY_COLUMNS = ["skills", "services", "needs", "languages"]

PROFILE_SCHEMA = StructType(
    [
        StructField("id", StringType(), False),
        StructField("type", StringType(), False),
        StructField("name", StringType(), False),
        StructField("description", StringType(), True),
        StructField("sector", StringType(), True),
        StructField("region", StringType(), True),
        *[StructField(c, ArrayType(StringType()), True) for c in TEXT_ARRAY_COLUMNS],
    ]
)

PROFILE_COLUMNS = [f.name for f in PROFILE_SCHEMA.fields]


def to_profile_frame(df: DataFrame) -> DataFrame:
    """Select the contract columns in order and replace NULLs with empty values.

    Raises ValueError naming any missing column, so a schema drift fails loudly
    instead of producing empty features.
    """
    missing = [c for c in PROFILE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"profile frame is missing columns: {missing}")

    empty = F.array().cast(ArrayType(StringType()))
    return df.select(
        F.col("id").cast("string").alias("id"),
        "type",
        "name",
        F.coalesce(F.col("description"), F.lit("")).alias("description"),
        "sector",
        "region",
        *[F.coalesce(F.col(c), empty).alias(c) for c in TEXT_ARRAY_COLUMNS],
    )
