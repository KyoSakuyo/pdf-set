"""Conservative multilingual sentence boundaries for translation preparation.

Length is deliberately absent here: a short target must never turn an
abbreviation, editorial marker or embedded note into a sentence ending.
Parentheses are context, not opaque spans; long parenthetical prose can split.
"""
import re

SUP_RE = re.compile(r'<sup>.*?</sup>', re.I | re.S)
WORD_RE = re.compile(r'[^\W\d_]+', re.UNICODE)
PUNCTUATION = set('.?!。？！')
CLOSERS = set(')）]】»›”’\"')
OPENERS = set('(（[【«‹“‘\"')

# Medial abbreviations; matched as whole tokens, with Unicode case folding.
MEDIAL = set('''m mme mmes mlle mlles mm dr drs pr prof mr mrs ms st ste
th ch chr fr sigm alf alfr allr wilh joh ph phil aug alex rob ern edw
cf ex ibid ib op cit vol chap fig pag pp éd éds trad liv sect nr nos
intern internat int neurolog zentralbl zbl zeitschr wschr jb jh arch
psychoanal psychopath psicol psychol päd angew contrib cand stud priv
extraord oct janv févr avr sept nov déc'''.split())
REFERENCE = {'p', 't', 'n', 'v', 's', 'bd'}
CONTEXTUAL = {'etc', 'sq', 'ff', 'fl', 'cour', 'kr', 'med', 'pcs', 'ics', 'pc'}
SENTENCE_STARTERS = set('''je il elle ils elles on nous vous tu ce cette cet ces
cela ceci cependant mais pourtant donc ainsi alors ensuite enfin certes
naturellement maintenant désormais lorsque quand comme pour dans après avant
sans avec par sous sur bien en or et un une le la les si au aux à a de des
du the this that these those it he she they we i however then when der die
das er sie wir ich aber nun'''.split())
MULTI_RE = re.compile(
    r'\b(?:c\s*\.\s*[-–]?\s*à\s*[-–]\s*d\s*\.'
    r'|(?:par\s*\.?\s*|p\s*\.\s*)ex\s*\.'
    r'|[ie]\s*\.\s*[eg]\s*\.'
    r'|(?:l|op)\s*\.\s*(?:c|cit)\s*\.'
    r'|(?:[A-ZÀ-ÖØ-Þ]\s*\.\s*[-–]?\s*){2,}'
    r'|OCF\s*\.\s*P\.?)', re.I)
MARKER_RE = re.compile(r'[\[(（【]\s*[!?？！]+\s*[\])）】]')
MARKUP_RE = re.compile(
    r'!?\[[^\]\n]*\]\((?:[^()\n]|\([^()\n]*\))*\)'
    r'|`+[^`\n]*`+|https?://[^\s<>]+|<[^>]+>')


def token_before(text, index):
    start = index
    while start and text[start - 1].isalpha():
        start -= 1
    return text[start:index]


def skip_space(text, index):
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def endpoint(text, index):
    """Include closing punctuation and attached notes, but not new clauses."""
    end = index + 1
    while True:
        pos = skip_space(text, end)
        if pos < len(text) and text[pos] in CLOSERS | PUNCTUATION:
            end = pos + 1
            continue
        note = SUP_RE.match(text, pos)
        if note:
            end = note.end()
            continue
        if pos < len(text) and text[pos] == '【':
            depth = 1
            close = pos + 1
            while close < len(text) and depth:
                depth += (text[close] == '【') - (text[close] == '】')
                close += 1
            if depth == 0:
                end = close
                continue
        return skip_space(text, end)


def next_word(text, start):
    start = skip_space(text, start)
    while start < len(text) and text[start] in OPENERS:
        start = skip_space(text, start + 1)
    match = WORD_RE.match(text, start)
    return match.group(0) if match else ''


def protected_mask(text, protect_sup=True):
    mask = bytearray(len(text))
    patterns = [MARKUP_RE, MARKER_RE, MULTI_RE]
    if protect_sup:
        patterns.append(SUP_RE)
    for pattern in patterns:
        for match in pattern.finditer(text):
            mask[match.start():match.end()] = b'\1' * (match.end() - match.start())
    return mask


def abbreviation_dot(text, i, end):
    token = token_before(text, i)
    lower = token.casefold()
    word = next_word(text, end)
    if lower in MEDIAL:
        return True
    if lower in REFERENCE and token == token.lower():
        return True
    # German journal abbreviations and abbreviated von, including anonymous names.
    if lower in {'f', 'd'} and token.islower():
        return True
    if len(token) == 1 and token.isupper():
        # Initial chains/surnames, including accented capitals. Genuine sentence
        # starts such as "Anna O. Elle..." remain possible.
        if word and word[0].isupper() and word.casefold() not in SENTENCE_STARTERS:
            return True
        if end < len(text) and text[end] in '(&[【':
            return True
    if lower in CONTEXTUAL:
        if end < len(text) and text[end].isdigit():
            return True
        if word and (word[0].islower() or word.casefold() not in SENTENCE_STARTERS):
            return True
    return False


def safe_cuts(text, protect_sup=True):
    """Return character offsets after safe sentence endings (not just dots).

    Calculate once for the whole paragraph so later length grouping cannot lose
    the context preceding an initial, a list marker or an opening bracket.
    """
    mask = protected_mask(text, protect_sup)
    cuts = set()
    for i, ch in enumerate(text):
        if ch not in PUNCTUATION or mask[i]:
            continue
        if ch == '.':
            if (i and text[i-1] == '.') or (i+1 < len(text) and text[i+1] == '.'):
                continue
            # Decimal/date/URL/acronym interiors and OCR no-space continuations.
            if i+1 < len(text) and text[i+1].isalnum():
                continue
            number = re.search(r'(\d+)$', text[max(0, i-30):i])
            if number:
                start = i - len(number.group(0))
                prefix = text[max(0, start-50):start].rstrip()
                if not prefix or prefix.endswith((':', ';', '.')) or re.search(r'\b(?:et|and|und)$', prefix):
                    continue
            token = token_before(text, i)
            if len(token) == 1 and token.islower():
                prefix = text[:i-1].rstrip()
                if not prefix or prefix[-1] in '(（[【)）]】':
                    continue
        # Never cut before an attached footnote: keep the note with its anchor.
        direct = skip_space(text, i + 1)
        end = endpoint(text, i)
        if end >= len(text):
            continue
        right = text[end:]
        if right[0] in ',;:，；：&-–—' or right[0].islower():
            continue
        word = next_word(text, end)
        if right[0] in OPENERS and word and word[0].islower():
            continue
        # A comma/etc after closers is continuation even when the closer belongs
        # to a quotation or a long parenthesis, not just a short aside.
        if ch == '.' and abbreviation_dot(text, i, end):
            continue
        if direct < len(text) and text[direct] == '<' and not SUP_RE.match(text, direct):
            continue
        cuts.add(end)
    return sorted(cuts)
