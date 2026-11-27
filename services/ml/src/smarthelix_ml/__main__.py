"""Smoke check: load the profiles from the local database, preprocess them and build TF-IDF features.

    python -m smarthelix_ml            (from services/ml/src, stack running, seeds loaded)
"""

from pyspark.sql import functions as F

from .db import load_profiles_jdbc
from .features import DEFAULT_MIN_DF, build_features, idf_weights, vocabulary
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
    spark.stop()


if __name__ == "__main__":
    main()
