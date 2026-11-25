import math
import re
from collections import Counter

STOP_WORDS = set("""a an the and or but if of to in on at by for with from as is are was were be been
i me my we our you your it its this that these those there here what which who when where why how
can could should would will may might must have has had not no so than then very much many
about into out up down over again also just any all some more most only own same do does did
get got take want need know tell please allowed""".split())

# how much of the question's words the best section has to contain, picked by trying eval.py
MIN_COVERAGE = 0.5


def words(text):
    found = re.findall(r"[a-zåäö0-9]+", text.lower())
    # cut to 4 letters so thesis/theses and enrol/enrolment match. crude
    return [w[:4] for w in found if w not in STOP_WORDS]


def split_guide(text):
    sections = []
    title = None
    lines = []
    for line in text.splitlines():
        if line.startswith("## "):
            if title:
                sections.append({"title": title, "text": " ".join(lines)})
            title = line[3:].strip()
            lines = []
        elif title and line.strip():
            lines.append(line.strip())
    if title:
        sections.append({"title": title, "text": " ".join(lines)})
    return sections


class Guide:
    def __init__(self, text):
        self.sections = split_guide(text)
        self.counts = []
        for s in self.sections:
            # title twice so the heading helps a bit
            self.counts.append(Counter(words(s["title"]) * 2 + words(s["text"])))

        doc_freq = Counter()
        for c in self.counts:
            doc_freq.update(c.keys())
        n = len(self.sections)
        self.idf = {w: math.log(1 + n / doc_freq[w]) for w in doc_freq}
        self.max_idf = max(self.idf.values()) if self.idf else 1

    def search(self, question, how_many=3):
        q = set(words(question))
        if not q:
            return []
        # words the guide never uses still count in the total, otherwise nonsense questions look fine
        total = sum(self.idf.get(w, self.max_idf) for w in q)

        results = []
        for section, counts in zip(self.sections, self.counts):
            score = 0
            matched = 0
            for w in q:
                if w in counts:
                    score += self.idf[w] * (1 + math.log(counts[w]))
                    matched += self.idf[w]
            results.append({
                "title": section["title"],
                "text": section["text"],
                "score": round(score, 2),
                "coverage": round(matched / total, 2),
            })
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:how_many]


def best_sentences(text, question, n=2):
    q = set(words(question))
    sentences = re.split(r"(?<=[.!?])\s+", text)
    ranked = sorted(range(len(sentences)), key=lambda i: -len(q & set(words(sentences[i]))))
    keep = sorted(ranked[:n])
    return " ".join(sentences[i] for i in keep)


def lookup(guide, question):
    hits = guide.search(question)
    if not hits or hits[0]["coverage"] < MIN_COVERAGE:
        return {"found": False, "hits": hits[:1], "text": None}

    top = hits[0]
    close = [h for h in hits if h["score"] >= 0.6 * top["score"]]
    return {"found": True, "hits": close, "text": best_sentences(top["text"], question)}
