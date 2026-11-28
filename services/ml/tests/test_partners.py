import json
import math

import pytest

from smarthelix_ml.partners import compute_partners
from smarthelix_ml.schema import PROFILE_COLUMNS, PROFILE_SCHEMA


def profile(pid, needs=(), skills=(), services=(), region=None, type="sme"):
    p = dict(id=pid, type=type, name=f"Name {pid}", description="", sector=None, region=region,
             skills=list(skills), services=list(services), needs=list(needs), languages=[])
    return tuple(p[c] for c in PROFILE_COLUMNS)


def partners(spark, rows, **kw):
    kw.setdefault("min_df", 1)  # tests state the rule they check, not the seed's default
    df = compute_partners(spark.createDataFrame(rows, PROFILE_SCHEMA), **kw)
    out = {}
    for r in df.orderBy("profile_id", "rank").collect():
        out.setdefault(r.profile_id, []).append(
            (r.partner_id, r.rank, r.score, json.loads(r.reasons)["matched_needs"]))
    return out


def test_partner_offers_what_a_needs_and_reasons_name_it(spark):
    out = partners(spark, [profile("a", needs=["web development"]),
                           profile("b", services=["web development"]),
                           profile("c", services=["fresh bread"])])
    assert [(p, rank, needs) for p, rank, _, needs in out["a"]] == [("b", 1, ["web development"])]


def test_reasons_keep_the_needers_own_wording(spark):
    out = partners(spark, [profile("a", needs=["  Κατασκευή   Ιστοσελίδων "]),
                           profile("b", skills=["κατασκευη ιστοσελιδων"])])
    assert out["a"][0][3] == ["  Κατασκευή   Ιστοσελίδων "]


def test_whole_phrases_only_no_credit_for_a_shared_word(spark):
    out = partners(spark, [profile("a", needs=["website maintenance"]),
                           profile("b", services=["website development"])])
    assert "a" not in out


def test_not_symmetric_self_excluded_and_no_needs_no_rows(spark):
    out = partners(spark, [profile("a", needs=["seo"], services=["seo"]),
                           profile("b", services=["seo"])])
    assert [p for p, *_ in out["a"]] == ["b"]   # a never lists itself
    assert "b" not in out                        # b needs nothing


def test_a_focused_partner_beats_a_long_padded_list(spark):
    out = partners(spark, [profile("a", needs=["seo"]),
                           profile("focused", services=["seo"]),
                           profile("padded", services=["seo", "baking", "pastry", "tours"]),
                           profile("x", services=["baking", "pastry", "tours"])])
    assert [p for p, *_ in out["a"]] == ["focused", "padded"]


def test_a_rare_need_weighs_more_than_a_common_one(spark):
    rows = [profile("a", needs=["hotel photography", "api integration"]),
            profile("rare", services=["hotel photography"]),
            profile("common", services=["api integration"])]
    rows += [profile(f"o{i}", services=["api integration"]) for i in range(5)]
    assert out_first(partners(spark, rows)["a"]) == "rare"


def out_first(rows):
    return rows[0][0]


def test_score_is_cosine_plus_the_documented_boosts(spark):
    rows = [profile("a", needs=["seo"], region="Attica", type="sme"),
            profile("near_other", services=["seo"], region="Attica", type="freelancer"),
            profile("near_same", services=["seo"], region="Attica", type="sme"),
            profile("far_other", services=["seo"], region="Crete", type="freelancer"),
            profile("unknown", services=["seo"], region=None, type="sme")]
    s = {p: score for p, _, score, _ in partners(spark, rows)["a"]}
    # each partner offers exactly a's one need, so the cosine is 1 for all of them
    assert s["near_other"] == pytest.approx(1.10)
    assert s["near_same"] == pytest.approx(1.05)
    assert s["far_other"] == pytest.approx(1.05)
    assert s["unknown"] == pytest.approx(1.00)   # an unknown region gets no boost


def test_partial_cover_matches_the_formula(spark):
    rows = [profile("a", needs=["seo", "logo design"]), profile("b", services=["seo", "tours"]),
            profile("c", services=["logo design"]), profile("d", services=["tours"])]
    out = partners(spark, rows, region_boost=0, type_boost=0)
    n = 4
    idf = {"seo": math.log(5 / 2), "logo design": math.log(5 / 2), "tours": math.log(5 / 3)}
    na = math.hypot(idf["seo"], idf["logo design"])
    nb = math.hypot(idf["seo"], idf["tours"])
    b = next(r for r in out["a"] if r[0] == "b")
    assert n == len(rows) and b[2] == pytest.approx(idf["seo"] ** 2 / (na * nb), rel=1e-5)
    assert b[3] == ["seo"]


def test_phrases_offered_by_too_few_are_ignored(spark):
    rows = [profile("a", needs=["seo", "photorgaphy"]), profile("b", services=["photorgaphy"]),
            profile("c", services=["seo"]), profile("d", services=["seo"])]
    out = partners(spark, rows, min_df=2)
    assert [p for p, *_ in out["a"]] == ["c", "d"]   # the typo is offered by 1 < 2 profiles


def test_k_limits_rows_ranks_run_1_to_k_and_ties_go_by_partner_id(spark):
    rows = [profile("a", needs=["seo"])] + [profile(p, services=["seo"]) for p in ("z", "m", "b", "q")]
    a = partners(spark, rows, k=3)["a"]
    assert [(p, rank) for p, rank, *_ in a] == [("b", 1), ("m", 2), ("q", 3)]


def test_output_columns_types_and_reasons_json(spark):
    df = compute_partners(spark.createDataFrame(
        [profile("a", needs=["seo"]), profile("b", services=["seo"])], PROFILE_SCHEMA), min_df=1)
    assert df.columns == ["profile_id", "partner_id", "rank", "score", "reasons"]
    assert dict(df.dtypes) == {"profile_id": "string", "partner_id": "string", "rank": "int",
                               "score": "float", "reasons": "string"}
    assert json.loads(df.first().reasons) == {"matched_needs": ["seo"]}


def test_nothing_offered_often_enough_is_a_clear_error(spark):
    with pytest.raises(ValueError, match="min_df"):
        compute_partners(spark.createDataFrame(
            [profile("a", needs=["seo"]), profile("b", services=["seo"])], PROFILE_SCHEMA))


def test_k_must_be_positive(spark):
    with pytest.raises(ValueError):
        compute_partners(spark.createDataFrame([profile("a")], PROFILE_SCHEMA), k=0)
