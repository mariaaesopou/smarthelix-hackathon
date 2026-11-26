import pytest
from pyspark.sql import functions as F

from smarthelix_ml.db import jdbc_options
from smarthelix_ml.preprocess import add_tokens, normalize, preprocess
from smarthelix_ml.schema import PROFILE_COLUMNS, PROFILE_SCHEMA, to_profile_frame


def row(**kw):
    base = dict(id="p1", type="sme", name="Test Co", description="", sector=None, region=None,
                skills=[], services=[], needs=[], languages=[])
    base.update(kw)
    return tuple(base[c] for c in PROFILE_COLUMNS)


def tokens_of(spark, **kw):
    df = spark.createDataFrame([row(**kw)], PROFILE_SCHEMA)
    return preprocess(to_profile_frame(df)).first()


def test_normalize_strips_greek_accents_and_final_sigma(spark):
    df = spark.createDataFrame([("Ζαχαροπλαστική ΚΑΦΈΣ Ϊϋ ΐΰ",)], ["t"])
    assert df.select(normalize("t")).first()[0] == "ζαχαροπλαστικη καφεσ ιυ ιυ"


def test_tokens_join_description_services_and_skills(spark):
    r = tokens_of(spark, description="Fresh bread daily", services=["home delivery"],
                  skills=["ψήσιμο ψωμιού"])
    assert r.tokens == ["fresh", "bread", "daily", "home", "delivery", "ψησιμο", "ψωμιου"]


def test_stopwords_removed_in_both_languages(spark):
    r = tokens_of(spark, description="We are the best και η καλύτερη για εσάς στην πόλη")
    assert r.tokens == ["best", "καλυτερη", "πολη"]


def test_own_name_tokens_dropped_but_other_names_kept(spark):
    r = tokens_of(spark, name="Gaia Creative", description="Gaia Creative works with Hermes on branding")
    assert r.tokens == ["works", "hermes", "branding"]


def test_short_and_digit_tokens_dropped_and_repeats_kept(spark):
    r = tokens_of(spark, description="a 2026 web web 3d x")
    assert r.tokens == ["web", "web", "3d"]


def test_nulls_become_empty(spark):
    df = spark.createDataFrame(
        [("p1", "sme", "N", None, None, None, None, None, None, None)], PROFILE_SCHEMA)
    r = preprocess(to_profile_frame(df)).first()
    assert (r.description, r.tokens) == ("", [])


def test_missing_column_fails_loudly(spark):
    df = spark.createDataFrame([("p1", "sme")], ["id", "type"])
    with pytest.raises(ValueError, match="missing columns"):
        to_profile_frame(df)


def test_add_tokens_custom_column(spark):
    df = spark.createDataFrame([row(description="ignored", needs=["Web development"])], PROFILE_SCHEMA)
    out = add_tokens(df, ["needs"], "x", drop_name_tokens=False)
    assert out.select(F.col("x")).first()[0] == ["web", "development"]


def test_jdbc_options_parses_database_url():
    o = jdbc_options("postgres://u%40x:p%3Aw@db:6543/smart?sslmode=disable")
    assert o["url"] == "jdbc:postgresql://db:6543/smart"
    assert (o["user"], o["password"]) == ("u@x", "p:w")
    with pytest.raises(ValueError):
        jdbc_options("mysql://x@y/z")
