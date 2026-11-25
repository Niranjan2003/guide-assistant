import json

from guide import Guide, lookup, MIN_COVERAGE

guide = Guide(open("guide.md", encoding="utf-8").read())
data = json.load(open("eval_questions.json", encoding="utf-8"))

first = 0
top3 = 0
wrongly_refused = 0
print("in scope")
for item in data["in_scope"]:
    hits = guide.search(item["q"])
    titles = [h["title"] for h in hits]
    ok = titles[:1] == [item["section"]]
    first += ok
    top3 += item["section"] in titles
    refused = not lookup(guide, item["q"])["found"]
    wrongly_refused += refused
    if not ok or refused:
        print("  miss:", item["q"], "| got:", titles[0] if titles else "-", "| refused:", refused)

refused_ok = 0
print("out of scope")
for q in data["out_of_scope"]:
    refused = not lookup(guide, q)["found"]
    refused_ok += refused
    if not refused:
        print("  answered by mistake:", q)

n = len(data["in_scope"])
m = len(data["out_of_scope"])
print()
print(f"right section first: {first}/{n}")
print(f"right section in top 3: {top3}/{n}")
print(f"in scope refused by mistake: {wrongly_refused}/{n}")
print(f"out of scope refused: {refused_ok}/{m}")
print(f"(min coverage is {MIN_COVERAGE}, chosen with these same questions so it looks better than it is)")
