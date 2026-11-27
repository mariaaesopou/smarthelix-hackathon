import math

import pytest
from pyspark.sql.types import ArrayType, StringType, StructField, StructType

from smarthelix_ml.features import build_features, idf_weights, vocabulary

SCHEMA = StructType([StructField("id", StringType()), StructField("tokens", ArrayType(StringType()))])


def featurize(spark, rows, **kw):
    kw.setdefault("min_df", 1)  # each test states the rule it checks, not the default
    df, model = build_features(spark.createDataFrame(rows, SCHEMA), **kw)
    return {r.id: r.features for r in df.collect()}, model


def test_vectors_have_length_one(spark):
    vecs, _ = featurize(spark, [("a", ["web", "react", "web"]), ("b", ["web", "design"]),
                                ("c", ["react", "design"])])
    for v in vecs.values():
        assert math.isclose(v.norm(2), 1.0, rel_tol=1e-9)


def test_dot_product_is_cosine(spark):
    vecs, _ = featurize(spark, [("a", ["web", "react"]), ("a2", ["web", "react"]),
                                ("b", ["bread", "pastry"]), ("b2", ["bread", "pastry"])])
    assert vecs["a"].dot(vecs["a2"]) == pytest.approx(1.0)  # same words -> cosine 1
    assert vecs["a"].dot(vecs["b"]) == pytest.approx(0.0)   # no shared words -> cosine 0


def test_min_df_drops_words_in_too_few_profiles(spark):
    rows = [("a", ["web", "typoo"]), ("b", ["web", "typoo"]), ("c", ["web"]), ("d", ["web"])]
    _, model = featurize(spark, rows, min_df=3)
    assert vocabulary(model) == ["web"]  # "typoo" is in 2 profiles, below 3


def test_default_min_df_drops_typos_shared_by_up_to_three_profiles(spark):
    rows = [(f"p{i}", ["web"] + (["typoo"] if i < 3 else [])) for i in range(5)]
    df, model = build_features(spark.createDataFrame(rows, SCHEMA))
    assert vocabulary(model) == ["web"]


def test_min_df_as_fraction(spark):
    rows = [(f"p{i}", ["web"] + (["rare"] if i == 0 else [])) for i in range(10)]
    _, model = featurize(spark, rows, min_df=0.2)  # at least 20% of 10 profiles
    assert vocabulary(model) == ["web"]


def test_common_words_weigh_less_than_rare_ones(spark):
    rows = [("a", ["services", "pastry"]), ("b", ["services", "pastry"]),
            ("c", ["services", "react"]), ("d", ["services", "react"])]
    _, model = featurize(spark, rows)
    idf = dict(zip(vocabulary(model), idf_weights(model)))
    assert idf["services"] == pytest.approx(0.0)  # in every profile: log(5/5) = 0
    assert idf["pastry"] > 0


def test_profile_without_kept_words_gets_zero_vector(spark):
    vecs, _ = featurize(spark, [("a", ["web"]), ("b", ["web"]), ("empty", []), ("rare", ["once"])],
                        min_df=2)
    for pid in ("empty", "rare"):
        assert vecs[pid].numNonzeros() == 0
        assert not any(math.isnan(x) for x in vecs[pid].toArray())


def test_keeps_input_columns_and_drops_intermediates(spark):
    df, _ = build_features(spark.createDataFrame([("a", ["web"]), ("b", ["web"])], SCHEMA), min_df=1)
    assert df.columns == ["id", "tokens", "features"]


def test_empty_vocabulary_gives_a_clear_error(spark):
    df = spark.createDataFrame([("a", ["web"]), ("b", ["web"])], SCHEMA)  # "web" in 2 < 4 profiles
    with pytest.raises(ValueError, match="vocabulary is empty"):
        build_features(df)
