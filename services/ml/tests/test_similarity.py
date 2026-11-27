import random

import numpy as np
import pytest
from pyspark.sql.types import ArrayType, StringType, StructField, StructType

from smarthelix_ml.features import build_features
from smarthelix_ml.schema import PROFILE_COLUMNS, PROFILE_SCHEMA
from smarthelix_ml.similarity import compute_similar, top_k_similar

TOKENS = StructType([StructField("id", StringType()), StructField("tokens", ArrayType(StringType()))])


def features(spark, rows):
    df, _ = build_features(spark.createDataFrame(rows, TOKENS), min_df=1)
    return df


def result(df):
    return [(r.profile_id, r.similar_id, r.rank, r.score) for r in
            df.orderBy("profile_id", "rank").collect()]


def test_matches_brute_force_cosine(spark):
    rng = random.Random(7)
    words = [f"w{i}" for i in range(12)]
    rows = [(f"p{i:02d}", rng.choices(words, k=rng.randint(1, 6))) for i in range(30)]
    df = features(spark, rows)
    got = {(r.profile_id, r.similar_id): (r.rank, r.score) for r in top_k_similar(df, k=5).collect()}

    vecs = {r.id: r.features.toArray() for r in df.collect()}
    for pid, v in vecs.items():
        others = sorted(((-float(v @ w), oid) for oid, w in vecs.items() if oid != pid and v @ w > 0))
        for rank, (neg, oid) in enumerate(others[:5], start=1):
            assert got[(pid, oid)][0] == rank
            assert got[(pid, oid)][1] == pytest.approx(-neg, abs=1e-6)
        assert sum(1 for (p, _) in got if p == pid) == min(5, len(others))


def test_never_lists_itself_and_identical_profiles_score_one(spark):
    df = features(spark, [("a", ["web", "react"]), ("b", ["web", "react"]), ("c", ["web"])])
    rows = result(top_k_similar(df))
    assert all(p != s for p, s, _, _ in rows)
    assert rows[0][:3] == ("a", "b", 1) and rows[0][3] == pytest.approx(1.0)


def test_profiles_sharing_no_word_are_not_listed(spark):
    df = features(spark, [("a", ["web"]), ("b", ["web"]), ("c", ["bread"])])
    assert [(p, s) for p, s, _, _ in result(top_k_similar(df))] == [("a", "b"), ("b", "a")]


def test_k_limits_rows_and_ranks_are_1_to_k_by_score(spark):
    df = features(spark, [("a", ["web", "react", "css"]), ("b", ["web", "react", "css"]),
                          ("c", ["web", "react"]), ("d", ["web"]), ("e", ["web", "bread"]),
                          ("f", ["bread"])])  # f: "web" must not be in every profile, or its IDF is 0
    a = [r for r in result(top_k_similar(df, k=3)) if r[0] == "a"]
    assert [r[2] for r in a] == [1, 2, 3]
    assert [r[1] for r in a] == ["b", "c", "d"]
    assert a[0][3] >= a[1][3] >= a[2][3]


def test_ties_are_broken_by_similar_id(spark):
    df = features(spark, [("a", ["web"]), ("z", ["web"]), ("m", ["web"]), ("b", ["web"]),
                          ("x", ["bread"])])  # x keeps "web" from being in every profile (IDF 0)
    a = [r[1] for r in result(top_k_similar(df)) if r[0] == "a"]
    assert a == ["b", "m", "z"]


def test_scores_are_symmetric(spark):
    df = features(spark, [("a", ["web", "react"]), ("b", ["web", "css"]), ("c", ["react", "css", "web"])])
    s = {(p, q): sc for p, q, _, sc in result(top_k_similar(df))}
    for (p, q), sc in s.items():
        assert s[(q, p)] == pytest.approx(sc)


def test_output_columns_match_the_table(spark):
    out = top_k_similar(features(spark, [("a", ["web"]), ("b", ["web"])]))
    assert out.columns == ["profile_id", "similar_id", "rank", "score"]
    assert dict(out.dtypes) == {"profile_id": "string", "similar_id": "string",
                                "rank": "int", "score": "float"}


def test_k_must_be_positive(spark):
    with pytest.raises(ValueError):
        top_k_similar(features(spark, [("a", ["web"])]), k=0)


def test_compute_similar_runs_from_raw_profiles(spark):
    base = dict(type="sme", description="", sector=None, region=None, services=[], needs=[], languages=[])
    profiles = [dict(base, id=f"p{i}", name=f"Shop {i}",
                     skills=["web development", "react"] if i < 4 else ["baking", "pastry"])
                for i in range(8)]
    df = spark.createDataFrame([tuple(p[c] for c in PROFILE_COLUMNS) for p in profiles], PROFILE_SCHEMA)
    rows = result(compute_similar(df))
    web = {f"p{i}" for i in range(4)}
    assert rows and all((p in web) == (s in web) for p, s, _, _ in rows)  # web shops match web shops
    assert np.isclose(rows[0][3], 1.0)
