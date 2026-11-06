"""Lightweight retrieval normalization and passage scoring; never generates facts."""
import re

STOP = set("apa yang di dan atau untuk dari dalam ada saja aja sebutkan jelaskan tolong bagaimana tentang berapa saya aku minta menurut nomor tahun kalau kalo punya dengan sebesar tersebut berupa paling pertanyaan terbaru belum pakai jelasin dong eh gimana masih tetap perlu nggak gak kena sama sekali siapa".split())

def normalize_legal_query(text):
    """Normalize document notation, not legal facts or user parameters."""
    kinds = r'pergub|perda|kepgub|pp|undang[ -]undang'
    text = re.sub(r'\b('+kinds+r')\s+(?:no\.?|nomor)?\s*(\d+)\s*[/]\s*(\d{4})\b',
                  lambda m: f'{m[1]} {m[2]} tahun {m[3]}', text, flags=re.I)
    first = re.search(r'\b('+kinds+r')\s+(?:nomor\s+)?\d+\s+(?:tahun\s+)?\d{4}\b', text, re.I)
    if first:
        # In comparisons the second document often omits its kind.
        text = re.sub(r'\b(dan|sama|dengan|vs)\s+(\d+)\s*/\s*(\d{4})\b',
                      lambda m: f'{m[1]} {first[1]} {m[2]} tahun {m[3]}', text, flags=re.I)
    return text


def normalized_terms(text):
    text = normalize_legal_query(text).casefold()
    text = re.sub(r'\b(?:(?:nggak|gak|tidak) (?:kena|dikenai|dikenakan)|dikecualikan|pengecualian|kecuali)\b', 'pengecualian', text)
    text = re.sub(r'\b(?:nggak|gak|tidak)\s+(?:perlu\s+)?bayar\s+(?:pokok\s+)?pbb\s+sama sekali\b', 'pembebasan penuh pbb', text)
    text = re.sub(r'\b(?:siapa (?:aja |saja )?yang|berhak)\b', 'syarat', text)
    if re.search(r'\b(?:bebas|pembebasan)\b', text) and 'penuh' in text:
        text += ' 100'
    text = re.sub(r"\bpersentase\b", "persen", text)
    text = re.sub(r"\b(?:bebas|pembebasan|dibebaskan)\b", "pembebasan", text)
    text = re.sub(r"\b(?:syarat|persyaratan|kriteria)\b", "syarat", text)
    text = re.sub(r"\b(?:dua|2(?=\s+(?:rumah|objek))|lebih dari (?:1|satu))\b", "multiobjek", text)
    return set(t for t in re.findall(r"[^\W_]+", text) if len(t)>1 and t not in STOP)

def document_matches(query, title):
    kinds = r"pergub|perda|kepgub|pp|undang[ -]undang"
    expected = re.findall(r"\b("+kinds+r")\s+(?:nomor\s+)?(\d+)\s+(?:tahun\s+)?(\d{4})\b", normalize_legal_query(query).casefold())
    if not expected:
        return True
    actual = re.findall(r"\b("+kinds+r")\s+(?:nomor\s+)?(\d+)\s+(?:tahun\s+)?(\d{4})\b", title.casefold())
    return any(item in actual for item in expected)

def passage_body(text):
    lines = [line for line in text.splitlines() if not line.startswith(('[SUMBER', '#', '>'))]
    body = '\n'.join(lines).strip()
    if 'atribut regulasi' in body.casefold() or 'tanggal ditetapkan' in body.casefold() and '| **' in body:
        return ''
    return body

def passage_score(query, text, title):
    body = passage_body(text)
    if not re.search(r'[^\W\d_]{2,}', body) or not document_matches(query, title):
        return -1.0
    q = normalized_terms(query)
    # Document identifiers and year are filters, not useful evidence repeated in each title.
    q -= normalized_terms(title)
    q -= {'pergub','perda','kepgub','pbb','p2','njop'} if len(q)>3 else set()
    words = normalized_terms(body)
    score = float(len(q & words))
    # Rank the requested benefit, not a negative mention in a different scheme.
    full = '100' in normalized_terms(query) or 'penuh' in normalized_terms(query)
    if full and 'pembebasan' in normalized_terms(query):
        if re.search(r'tidak memenuhi[^.\n]{0,120}(?:100\s*%|seratus persen)', body, re.I):
            score -= 7
        if re.search(r'(?:kriteria|syarat|hunian|orang pribadi|NIK)', body, re.I) and re.search(r'100\s*%|seratus persen', body, re.I):
            score += 5
        if re.search(r'pengurangan pokok|pembebasan sebagian', body, re.I):
            score -= 3
    if 'bangunan' in normalized_terms(query) and re.search(r'termasuk dalam pengertian bangunan|kolam renang', body, re.I):
        score += 5
    if ('persen' in normalized_terms(query)) and re.search(r"\d+(?:[.,]\d+)?\s*%|\bpersen\b", body.casefold()):
        score += 3
    if 'syarat' in normalized_terms(query) and 'a.' in body and 'b.' in body:
        score += 3
    if 'pengecualian' in normalized_terms(query) and re.search(r'\b(?:tidak dikenakan|dikecualikan)\b', body.casefold()):
        score += 3
    if 'multiobjek' in normalized_terms(query) and 'multiobjek' in words:
        score += 5
    if '\nPertanyaan terbaru: ' in query:
        latest = query.rsplit('\nPertanyaan terbaru: ', 1)[1]
        recent = normalized_terms(latest) - normalized_terms(title)
        score += 4 * len(recent & words)
    return score


def document_title_pattern(query):
    matches = re.findall(r"\b(pergub|perda|kepgub|pp)\s+(?:nomor\s+)?(\d+)\s+(?:tahun\s+)?(\d{4})\b", normalize_legal_query(query).casefold())
    if not matches:
        return None
    kind, number, year = matches[-1]
    return f"%{kind}%{number}%{year}%"


LEGAL_ID = r"\b(pergub|perda|kepgub|pp)\s+(?:nomor\s+)?(\d+)\s+(?:tahun\s+)?(\d{4})\b"

def legal_queries(query):
    """Split explicit comparisons, retaining topic and identity for each document."""
    targets = list(dict.fromkeys(re.findall(LEGAL_ID, normalize_legal_query(query).casefold())))
    if not 2 <= len(targets) <= 4:
        return []
    topic = re.sub(LEGAL_ID, '', normalize_legal_query(query), flags=re.I)
    return [f'{kind} {number} tahun {year} {topic}' for kind, number, year in targets]

def lexical_expansions(query):
    concepts = normalized_terms(query)
    aliases = {'persen': ['persen', 'persentase'], 'pembebasan': ['pembebasan', 'bebas'],
               'syarat': ['syarat', 'kriteria'], 'multiobjek': ['lebih'],
               'pengecualian': ['pengecualian', 'dikecualikan', 'dikenakan']}
    terms = [word for concept, words in aliases.items() if concept in concepts for word in words]
    if '100' in concepts:
        terms.append('100')
    return list(dict.fromkeys(terms))
