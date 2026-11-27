"""SmartHelix ML functions (Role 2).

Every public function is DataFrame in -> DataFrame out, so Role 1's Spark runner
can call it without knowing how the data was loaded.
"""

from .schema import PROFILE_COLUMNS, PROFILE_SCHEMA, to_profile_frame
from .preprocess import add_tokens, normalize, preprocess
from .features import build_features, idf_weights, vocabulary
from .similarity import compute_similar, featurize, top_k_similar

__all__ = [
    "PROFILE_COLUMNS",
    "PROFILE_SCHEMA",
    "to_profile_frame",
    "add_tokens",
    "normalize",
    "preprocess",
    "build_features",
    "idf_weights",
    "vocabulary",
    "compute_similar",
    "featurize",
    "top_k_similar",
]
