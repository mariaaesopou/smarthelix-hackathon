"""Stopword lists. Spark's StopWordsRemover has no Greek list, so we keep one here.

Greek words are stored already normalised (lowercase, no accents, final sigma as σ)
because the remover runs after normalisation.
"""

from functools import lru_cache

from pyspark.ml.feature import StopWordsRemover

_GREEK_RAW = (
    {
        # articles
        "ο", "η", "το", "οι", "τα", "του", "της", "των", "τον", "την", "τη", "τις", "τους",
        "ενα", "ενας", "μια", "μιας", "ενος",
        # pronouns
        "εγω", "εσυ", "αυτος", "αυτη", "αυτο", "αυτοι", "αυτες", "αυτα", "αυτου", "αυτης",
        "αυτων", "εμεις", "εσεις", "μου", "σου", "μας", "σας", "τους", "μας", "εμας",
        "εαυτο", "εσας", "εμενα", "εσενα", "οποιος", "οποια", "οποιο", "οποιοι", "οποιες", "οποιων", "που", "ποιος",
        "ποια", "ποιο", "καθε", "ολοι", "ολες", "ολα", "ολο", "ολη", "αλλος", "αλλη", "αλλο",
        "αλλοι", "αλλες", "αλλα", "τοσο", "τετοιο", "τετοια",
        # prepositions and conjunctions
        "σε", "στο", "στη", "στην", "στον", "στα", "στις", "στους", "στου", "στης",
        "απο", "με", "για", "προς", "κατα", "μετα", "παρα", "χωρις", "μεχρι", "εως",
        "μεσα", "εξω", "πανω", "κατω", "διπλα", "μεταξυ", "αντι", "δια", "υπο", "περι",
        "και", "κι", "η", "ουτε", "ειτε", "αλλα", "ομως", "αν", "εαν", "οταν", "οπως",
        "ενω", "επειδη", "αφου", "ωστε", "οτι", "πως", "μη", "μην", "δε", "δεν", "να",
        "θα", "ας", "λοιπον", "επισης", "ακομα", "ακομη", "μονο", "ηδη", "πολυ", "πιο",
        "λιγο", "εδω", "εκει", "τωρα", "παντα", "ποτε", "σημερα", "ετσι",
        # common verbs
        "ειμαι", "εισαι", "ειναι", "ειμαστε", "ειστε", "ηταν", "εχω", "εχει", "εχουμε",
        "εχετε", "εχουν", "ειχε", "κανω", "κανει", "κανουμε", "κανουν", "μπορει",
        "μπορουμε", "πρεπει",
    }
)

# Same normalisation as preprocess.normalize: final sigma -> σ (the list has no accents).
GREEK = sorted({w.replace("ς", "σ") for w in _GREEK_RAW})

@lru_cache(maxsize=1)
def all_stopwords() -> list[str]:
    """Spark's English list + the Greek list. Needs an active SparkSession (JVM)."""
    english = StopWordsRemover.loadDefaultStopWords("english")
    return sorted(set(english) | set(GREEK))
