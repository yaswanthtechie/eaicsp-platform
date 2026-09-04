
"""
Text preprocessing module for the Supplier Risk NLP pipeline.
"""

import string

# ------------------------------------------------------------------
# Translation table for removing punctuation
# ------------------------------------------------------------------

PUNCTUATION_TRANSLATOR = str.maketrans(
    string.punctuation,
    " " * len(string.punctuation),
)


def clean_text(text: str) -> str:
    """
    Clean the input text.

    Processing steps:
    - Convert to lowercase
    - Remove punctuation
    - Remove extra whitespace

    Args:
        text: Raw input text.

    Returns:
        Cleaned text.
    """

    if not isinstance(text, str):
        return ""

    cleaned_text = (
        text.lower()
        .translate(PUNCTUATION_TRANSLATOR)
        .replace("\n", " ")
        .replace("\t", " ")
    )

    return " ".join(cleaned_text.split())