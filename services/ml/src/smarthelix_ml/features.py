"""TF-IDF features (guide, Role 2, day 3-4).

tokens -> CountVectorizer (term counts) -> IDF (down-weight common words)
       -> Normalizer (L2, every vector has length 1)

Why these choices:
- CountVectorizer, not HashingTF: it keeps a vocabulary, so a vector position
  maps back to its word. Cluster labels (top TF-IDF words) and match reasons
  need that; HashingTF cannot map back and can merge two words into one slot.
- min_df=4: a word in only one profile can never be shared, so it adds nothing
  to cosine similarity but still lengthens its vector. A typo shared by two or
  three profiles is worse: rarity gives it the highest IDF, so it would link
  unrelated profiles. On the 2k seed every word in 1-3 profiles is a typo (387
  words), no word is in 4 or 5, and every real word is in 6 or more; 4 is the
  smallest cut in that gap, so niche real skills are kept. A count suits a
  corpus of this size; for a much larger one pass a fraction (< 1) instead.
- L2 normalisation: with |a| = |b| = 1, cosine(a, b) = a . b, a cheap sparse dot
  product. It also makes Euclidean distance rank like cosine
  (|a - b|^2 = 2 - 2 cos), which the LSH benchmark relies on.
"""

from pyspark.ml import PipelineModel
from pyspark.ml.feature import IDF, CountVectorizer, Normalizer
from pyspark.sql import DataFrame

DEFAULT_MIN_DF = 4
DEFAULT_VOCAB_SIZE = 1 << 18  # upper bound only; the seed has about 430 words


def build_features(
    df: DataFrame,
    input_col: str = "tokens",
    output_col: str = "features",
    min_df: float = DEFAULT_MIN_DF,
    vocab_size: int = DEFAULT_VOCAB_SIZE,
) -> tuple[DataFrame, PipelineModel]:
    """Fit TF-IDF on `df` and add `output_col`, an L2-normalised sparse vector.

    Returns the DataFrame and the fitted model; `vocabulary(model)` gives the word
    at each vector position. A profile with no kept words gets an all-zero vector.
    `min_df` >= 1 is a count of profiles, below 1 a fraction of them (Spark's rule).
    """
    tf, tfidf = f"__{output_col}_tf", f"__{output_col}_tfidf"
    counter = CountVectorizer(inputCol=input_col, outputCol=tf, minDF=min_df, vocabSize=vocab_size)
    counts = counter.fit(df)
    if not counts.vocabulary:  # Spark would fail later with only "requirement failed"
        raise ValueError(
            f"no word appears in at least min_df={min_df} profiles, so the vocabulary is "
            "empty; load more profiles (e.g. seeds/002_profiles.sql) or lower min_df"
        )
    weighted = IDF(inputCol=tf, outputCol=tfidf).fit(counts.transform(df))
    model = PipelineModel(
        stages=[counts, weighted, Normalizer(inputCol=tfidf, outputCol=output_col, p=2.0)]
    )
    return model.transform(df).drop(tf, tfidf), model


def vocabulary(model: PipelineModel) -> list[str]:
    """The word at each vector position of a model from build_features."""
    return list(model.stages[0].vocabulary)


def idf_weights(model: PipelineModel) -> list[float]:
    """IDF weight per vector position: log((n + 1) / (df + 1)), 0 for a word in every profile."""
    return model.stages[1].idf.toArray().tolist()
