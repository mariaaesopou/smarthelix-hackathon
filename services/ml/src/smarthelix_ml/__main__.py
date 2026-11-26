"""Smoke check: load the profiles from the local database and preprocess them.

    python -m smarthelix_ml            (from services/ml/src, stack running, seeds loaded)
"""

from pyspark.sql import functions as F

from .db import load_profiles_jdbc
from .preprocess import preprocess
from .session import get_spark


def main() -> None:
    spark = get_spark(jdbc=True)
    spark.sparkContext.setLogLevel("WARN")
    df = preprocess(load_profiles_jdbc(spark)).cache()

    df.printSchema()
    print("profiles:", df.count())
    df.groupBy("type").count().orderBy("type").show()
    df.select(
        F.avg(F.size("tokens")).alias("avg_tokens"),
        F.sum((F.size("tokens") == 0).cast("int")).alias("empty_tokens"),
    ).show()
    df.select("name", F.slice("tokens", 1, 10).alias("first_tokens")).show(5, truncate=False)
    spark.stop()


if __name__ == "__main__":
    main()
