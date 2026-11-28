"""Potential partners (guide, Role 2, day 5-6): who offers what a profile needs.

Phrases, not words, are the terms: "website maintenance" is one term. Every point
of a score then comes from a need the partner really offers, so the score and the
reasons always agree, and a partner offering "website development" gets nothing
for a need "website maintenance" just because both contain "website".

Formula (documented for the report):

    phrases are normalised (lowercase, Greek accents stripped, spaces collapsed);
    a phrase counts only if at least min_df profiles offer it (typos are dropped:
    on the 2k seed typo phrases are offered by <= 3 profiles, real ones by >= 10)

    idf(p)   = log((n + 1) / (df(p) + 1))        n = profiles, df = profiles offering p
    w_A(p)   = idf(p) / ||idf over A's needs||   A's needs as a unit vector
    w_B(p)   = idf(p) / ||idf over B's offers||  B's offers (skills + services) as a unit vector
    base     = sum over p in needs(A) and offers(B) of w_A(p) * w_B(p)    (cosine, 0..1)
    raw      = base + region_boost * [same region] + type_boost * [different type]
    score    = raw / (1 + region_boost + type_boost)                       (0..1)

Dividing by the largest possible raw value keeps the score in 0..1, on the same
scale as similar-profile scores, so the UI can show either as a percentage. It
does not change the ranking: every raw score is divided by the same number.

B is a candidate for A only if B covers at least one of A's needs; reasons lists
those needs in A's own wording. Rare needs weigh more (idf). Dividing by the
length of B's offers favours focused providers over long, padded lists.

Chosen on the 2k seed, with the generator's labels used for inspection only: the
share of top-10 partners from an archetype A really needs is 95.8% for cosine,
93.9% for the hand-made SQL rule (db/seeds/003_dev_partners.sql) and 92.7% for
idf-weighted coverage. Boosts of 0.05 move same-region partners in the top 10
from 14% to 34% and different-type ones from 62% to 84%, keeping 94.4%.

Output matches potential_partners without run_id: (profile_id, partner_id, rank,
score, reasons) where reasons is the JSON text {"matched_needs": [...]}. The
runner's JDBC writer sends it with stringtype=unspecified, so Postgres casts it to
jsonb. k defaults to 20 (store 20, API shows 10).
"""

from pyspark.sql import Column, DataFrame, Window, functions as F

from .preprocess import normalize
from .schema import to_profile_frame

DEFAULT_K = 20
DEFAULT_MIN_DF = 4
REGION_BOOST = 0.05
TYPE_BOOST = 0.05


def phrase_key(col: Column | str) -> Column:
    """The form two phrases are compared in: trimmed, normalised, single spaces."""
    c = F.col(col) if isinstance(col, str) else col
    return F.regexp_replace(normalize(F.trim(c)), r"\s+", " ")


def compute_partners(
    profiles: DataFrame,
    k: int = DEFAULT_K,
    min_df: int = DEFAULT_MIN_DF,
    region_boost: float = REGION_BOOST,
    type_boost: float = TYPE_BOOST,
) -> DataFrame:
    """profiles (the agreed columns) -> (profile_id, partner_id, rank, score, reasons), top k each.

    Raises ValueError when no offered phrase reaches min_df (nothing can match).
    """
    if k < 1:
        raise ValueError("k must be at least 1")
    if region_boost < 0 or type_boost < 0:
        raise ValueError("boosts must be zero or positive, or scores could leave 0..1")
    p = to_profile_frame(profiles).cache()
    n = p.count()

    # A's needs, one row per distinct phrase, keeping A's own wording and order for reasons.
    needs = (
        p.select(F.col("id").alias("profile_id"), F.posexplode("needs").alias("pos", "need"))
        .withColumn("key", phrase_key("need"))
        .where(F.col("key") != "")
        .groupBy("profile_id", "key")
        .agg(F.min(F.struct("pos", "need")).alias("first"))
        .select("profile_id", "key", F.col("first.pos").alias("pos"), F.col("first.need").alias("need"))
    )
    offers = (
        p.select(F.col("id").alias("partner_id"), F.explode(F.concat("skills", "services")).alias("offer"))
        .select("partner_id", phrase_key("offer").alias("key"))
        .where(F.col("key") != "")
        .distinct()
    )

    vocab = (
        offers.groupBy("key").agg(F.count("*").alias("df"))
        .where(F.col("df") >= min_df)
        .select("key", F.log((F.lit(n) + 1) / (F.col("df") + 1)).alias("idf"))
    )
    if vocab.limit(1).count() == 0:
        raise ValueError(
            f"no offered phrase appears in at least min_df={min_df} profiles; "
            "load more profiles (e.g. seeds/002_profiles.sql) or lower min_df"
        )

    def unit(rows: DataFrame, id_col: str, weight: str) -> DataFrame:
        """idf of each phrase divided by the length of that profile's idf vector."""
        rows = rows.join(F.broadcast(vocab), "key")
        length = F.sqrt(F.sum(F.col("idf") ** 2).over(Window.partitionBy(id_col)))
        return rows.withColumn(weight, F.col("idf") / length).drop("idf")

    a = unit(needs, "profile_id", "wa")
    b = unit(offers, "partner_id", "wb")

    pairs = (
        a.join(b, "key")
        .where(F.col("profile_id") != F.col("partner_id"))
        .groupBy("profile_id", "partner_id")
        .agg(
            F.sum(F.col("wa") * F.col("wb")).alias("base"),
            F.array_sort(F.collect_list(F.struct("pos", "need"))).alias("matched"),
        )
    )

    who = p.select("id", "region", "type")
    pa = who.select(F.col("id").alias("profile_id"), F.col("region").alias("ra"), F.col("type").alias("ta"))
    pb = who.select(F.col("id").alias("partner_id"), F.col("region").alias("rb"), F.col("type").alias("tb"))
    same_region = F.coalesce(F.col("ra") == F.col("rb"), F.lit(False)).cast("double")  # unknown: no boost
    other_type = (F.col("ta") != F.col("tb")).cast("double")
    # least(): rounding can push a perfect cosine to 1.0000001
    raw = F.least(F.col("base"), F.lit(1.0)) + region_boost * same_region + type_boost * other_type
    score = raw / (1.0 + region_boost + type_boost)

    order = Window.partitionBy("profile_id").orderBy(F.desc("score"), F.asc("partner_id"))
    return (
        pairs.join(pa, "profile_id").join(pb, "partner_id")
        .withColumn("score", score)
        .withColumn("rank", F.row_number().over(order))
        .where(F.col("rank") <= k)
        .select(
            "profile_id",
            "partner_id",
            F.col("rank").cast("int"),
            F.col("score").cast("float"),
            F.to_json(F.struct(F.transform("matched", lambda m: m["need"]).alias("matched_needs"))).alias("reasons"),
        )
    )
