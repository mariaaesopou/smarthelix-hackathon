"""Similar profiles (guide, Role 2, day 4-5): TF-IDF + cosine, top k per profile.

Vectors from build_features have length 1, so cosine(a, b) = a . b. The dot
products are computed as a sparse join: explode each vector into
(profile, word, weight) rows, join two copies on the word, and sum
weight_a * weight_b per profile pair. Built-in Spark operations only, exact, and
pairs that share no word (cosine 0) are never generated.

The cost grows with the square of each word's document frequency (a word in 636
profiles makes 636^2 pairs). That is fine for the live data; the 1M-vector
benchmark uses LSH instead.

Output matches the similar_profiles table without run_id, which the runner adds:
(profile_id, similar_id, rank, score). k defaults to 20 because the API stores
20 and shows 10 (docs/architecture.md, items 15 and 21).
"""

from pyspark.ml.functions import vector_to_array
from pyspark.sql import DataFrame, Window, functions as F

from .features import build_features
from .preprocess import preprocess
from .schema import to_profile_frame

DEFAULT_K = 20


def featurize(profiles: DataFrame):
    """profiles -> (DataFrame with `tokens` and `features`, fitted feature model)."""
    return build_features(preprocess(to_profile_frame(profiles)))


def top_k_similar(
    df: DataFrame,
    k: int = DEFAULT_K,
    id_col: str = "id",
    features_col: str = "features",
) -> DataFrame:
    """Top k most similar other profiles for each profile, by cosine of `features_col`.

    Ties are broken by similar_id so results are stable between runs. A profile
    with an all-zero vector, or sharing no word with anyone, gets no rows.
    """
    if k < 1:
        raise ValueError("k must be at least 1")

    entries = (
        df.select(F.col(id_col).alias("pid"), F.posexplode(vector_to_array(features_col)))
        .where(F.col("col") != 0)
        .select("pid", F.col("pos").alias("term"), F.col("col").alias("weight"))
    )
    a = entries.select(F.col("pid").alias("profile_id"), "term", F.col("weight").alias("wa"))
    b = entries.select(F.col("pid").alias("similar_id"), "term", F.col("weight").alias("wb"))

    scores = (
        a.join(b, "term")
        .where(F.col("profile_id") != F.col("similar_id"))
        .groupBy("profile_id", "similar_id")
        # least(): rounding can give 1.0000001 for identical vectors
        .agg(F.least(F.sum(F.col("wa") * F.col("wb")), F.lit(1.0)).alias("score"))
    )
    order = Window.partitionBy("profile_id").orderBy(F.desc("score"), F.asc("similar_id"))
    return (
        scores.withColumn("rank", F.row_number().over(order))
        .where(F.col("rank") <= k)
        .select("profile_id", "similar_id", F.col("rank").cast("int"), F.col("score").cast("float"))
    )


def compute_similar(profiles: DataFrame, k: int = DEFAULT_K) -> DataFrame:
    """profiles (the agreed columns) -> (profile_id, similar_id, rank, score), top k each."""
    features, _ = featurize(profiles)
    return top_k_similar(features, k)
