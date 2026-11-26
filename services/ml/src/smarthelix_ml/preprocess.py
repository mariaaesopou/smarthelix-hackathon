"""Greek and English text preprocessing, built-in Spark functions only.

No Python UDFs: every step runs in the JVM, which matters at 1M rows.

Steps (guide, Role 2, day 2-3):
1. join description + services + skills into one text,
2. lowercase and strip Greek accents (final sigma becomes σ),
3. tokenise on anything that is not a letter or digit,
4. drop tokens shorter than 2 characters and digit-only tokens,
5. drop the profile's own name tokens (the seed descriptions repeat the brand
   name, and names must never drive similarity or cluster labels),
6. remove English and Greek stopwords.

Repeated tokens are kept, so term frequency survives for TF-IDF.
"""

from collections.abc import Sequence

from pyspark.ml.feature import StopWordsRemover
from pyspark.sql import Column, DataFrame, functions as F

from . import stopwords

# Lowercase accented Greek -> plain. Applied after lower(), so capitals are covered.
_ACCENTED = "άέήίόύώϊϋΐΰς"
_PLAIN = "αεηιουωιυιυσ"

# Split on runs of anything that is not a Unicode letter or digit.
_SPLIT = r"[^\p{L}\p{N}]+"

DEFAULT_TEXT_COLUMNS = ("description", "services", "skills")


def normalize(col: Column | str) -> Column:
    """Lowercase and remove Greek accents."""
    c = F.col(col) if isinstance(col, str) else col
    return F.translate(F.lower(c), _ACCENTED, _PLAIN)


def _as_text(df: DataFrame, name: str) -> Column:
    """A string column as is; an array column joined with spaces. NULL -> ''."""
    if dict(df.dtypes)[name].startswith("array"):
        return F.coalesce(F.array_join(F.col(name), " "), F.lit(""))
    return F.coalesce(F.col(name), F.lit(""))


def _split(text: Column) -> Column:
    return F.filter(
        F.split(text, _SPLIT),
        lambda t: (F.length(t) >= 2) & ~t.rlike(r"^\d+$"),
    )


def add_tokens(
    df: DataFrame,
    text_columns: Sequence[str] = DEFAULT_TEXT_COLUMNS,
    output_col: str = "tokens",
    drop_name_tokens: bool = True,
) -> DataFrame:
    """Add `output_col`: the cleaned token array built from `text_columns`."""
    text = F.concat_ws(" ", *[_as_text(df, c) for c in text_columns])
    raw = _split(normalize(text))
    if drop_name_tokens:
        name_tokens = _split(normalize(F.coalesce(F.col("name"), F.lit(""))))
        raw = F.filter(raw, lambda t: ~F.array_contains(name_tokens, t))

    tmp = f"__{output_col}_raw"
    remover = StopWordsRemover(
        inputCol=tmp,
        outputCol=output_col,
        stopWords=stopwords.all_stopwords(),
        caseSensitive=True,  # tokens are already normalised
    )
    return remover.transform(df.withColumn(tmp, raw)).drop(tmp)


def preprocess(df: DataFrame) -> DataFrame:
    """Add `tokens`: the cleaned words of description + services + skills."""
    return add_tokens(df)
