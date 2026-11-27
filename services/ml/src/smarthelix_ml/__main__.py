"""Smoke check: load the profiles from the local database, preprocess, build TF-IDF features,
compute similar profiles and print 5 profiles from 5 sectors for a hand check.

    python -m smarthelix_ml            (from services/ml/src, stack running, seeds loaded)
"""

import time

from pyspark.sql import Window, functions as F

from .db import load_profiles_jdbc
from .features import DEFAULT_MIN_DF, build_features, idf_weights, vocabulary
from .similarity import DEFAULT_K, top_k_similar
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

    feats, model = build_features(df)
    vocab, idf = vocabulary(model), idf_weights(model)
    vecs = feats.select("name", "features").collect()
    nonzero = [r.features.numNonzeros() for r in vecs]
    norms = [r.features.norm(2) for r in vecs if r.features.numNonzeros()]
    print(f"vocabulary: {len(vocab)} words (min_df={DEFAULT_MIN_DF})")
    print(f"words per vector: avg {sum(nonzero) / len(nonzero):.1f}, "
          f"max {max(nonzero)}, empty vectors {nonzero.count(0)}")
    print(f"vector length: min {min(norms):.6f}, max {max(norms):.6f}")
    by_idf = sorted(zip(idf, vocab))
    print("lowest IDF (common):", [(w, round(x, 2)) for x, w in by_idf[:6]])
    print("highest IDF (rare): ", [(w, round(x, 2)) for x, w in by_idf[-6:]])
    v = vecs[0].features
    top = sorted(zip(v.values, v.indices), reverse=True)[:6]
    print(f"top weighted words of {vecs[0].name!r}:", [(vocab[i], round(x, 2)) for x, i in top])

    # Similar profiles, plus the plan's hand check: 5 profiles from 5 different sectors.
    start = time.perf_counter()
    similar = top_k_similar(feats).cache()
    rows, per = similar.count(), similar.groupBy("profile_id").count()
    print(f"similar_profiles: {rows} rows in {time.perf_counter() - start:.1f}s, "
          f"profiles with a list: {per.count()}, with fewer than {DEFAULT_K}: "
          f"{per.where(F.col('count') < DEFAULT_K).count()}")
    info = df.select("id", "name", "type", "sector", "region")
    first_per_sector = Window.partitionBy("sector").orderBy("id")
    sample = (info.where(F.col("sector").isNotNull())
              .withColumn("n", F.row_number().over(first_per_sector)).where("n = 1")
              .orderBy("sector").limit(5).collect())
    for p in sample:
        print(f"\n{p.name} ({p.type}, {p.sector}, {p.region}) -> top 5:")
        (similar.where(F.col("profile_id") == p.id).where("rank <= 5")
         .join(info.withColumnRenamed("id", "similar_id"), "similar_id")
         .orderBy("rank").select("rank", F.round("score", 3).alias("score"), "name", "type", "sector", "region")
         .show(truncate=False))
    spark.stop()


if __name__ == "__main__":
    main()
