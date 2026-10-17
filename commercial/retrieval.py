"""Deterministic lexical ranking over the caller's authorized snapshot only."""
from collections import Counter
import math
import re
import unicodedata


def tokens(text):
    text = unicodedata.normalize('NFKC', str(text or '')).casefold()
    text = text.translate(str.maketrans('يكى۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', 'یکی01234567890123456789'))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return re.findall(r'[^\W_]+', text.replace('\u200c', ' '), re.UNICODE)


def ranked_indices(query, documents):
    """AND across tokens; BM25 ranking, stable source order on ties. No shared cache."""
    terms = set(tokens(query))
    if not terms:
        return [] if str(query).strip() else list(range(len(documents)))
    counts = [Counter(tokens(doc)) for doc in documents]
    lengths = [sum(c.values()) for c in counts]
    average = sum(lengths) / max(1, len(counts)) or 1
    frequencies = {term: sum(term in c for c in counts) for term in terms}
    ranked = []
    for index, (count, length) in enumerate(zip(counts, lengths)):
        if not terms.issubset(count):
            continue
        score = sum(math.log(1 + (len(counts) - frequencies[t] + .5) / (frequencies[t] + .5))
                    * count[t] * 2.2 / (count[t] + 1.2 * (.25 + .75 * length / average))
                    for t in sorted(terms))
        ranked.append((index, score))
    return [index for index, _ in sorted(ranked, key=lambda item: (-item[1], item[0]))]
