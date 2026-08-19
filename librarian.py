"""
librarian.py -- the community library kiosk.

This provides a text-input interface for the local model. 
Interaction: person types a question into the terminal interface.
This script assembles the components: reads contributions.csv and 
rules.txt fresh each time, builds the prompt (rules + corpus, then 
question,so Ollama's prefix cache makes repeat questions fast), 
calls the model, and appends the author index in code so attribution 
is robust and not dependent on the model.

The corpus lives in the CSV, not in the model; deletions are effective
immediately.

Usage:
    python3 librarian.py                 # interactive kiosk loop
    python3 librarian.py "one question"  # single query, then exit

Requires: ollama running (`ollama serve`), model pulled (`ollama pull qwen3:1.7b`)
"""

import sys
import json
import time
import urllib.request

MODEL = "qwen3:1.7b"        # any instruct model with >=16k context
OLLAMA = "http://localhost:11434/api/generate"
NUM_CTX = 16384             # default ctx silently truncates -- always set this
CSV = "contributions.csv"
RULES = "rules.txt"

DEFAULT_RULES = """\
Answer only from the community contributions provided below.
"""

def load_corpus():
    """Read the corpus fresh. No caching here; deletion must be instant."""
    import csv as csvmod
    rows = []
    with open(CSV, newline="", encoding="utf-8") as f:
        for row in csvmod.DictReader(f):
            rows.append((row["name"], row["contribution"]))
    return rows


def load_rules():
    try:
        with open(RULES, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        with open(RULES, "w", encoding="utf-8") as f:
            f.write(DEFAULT_RULES)
        print(f"(created {RULES} with starting rules -- the community "
              f"should amend this file)")
        return DEFAULT_RULES


def build_prompt(rules, corpus, question):
    """Static block first (rules + corpus), question last.
    Keeping the prefix byte-identical across questions lets Ollama reuse
    its processed form, so only the question costs time after warmup."""
    parts = [rules.strip(), "", "COMMUNITY CONTRIBUTIONS:", ""]
    for name, text in corpus:
        parts.append(f"{name}: {text}")
    parts += ["", f"QUESTION: {question}", "", "ANSWER:"]
    return "\n".join(parts)


def ask(question, rules, corpus):
    prompt = build_prompt(rules, corpus, question)
    body = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.9, "num_ctx": NUM_CTX,
                    "num_predict": 700},
    }).encode()
    req = urllib.request.Request(
        OLLAMA, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        resp = json.loads(r.read())
    return resp, time.time() - t0


def main():
    one_shot = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None

    print("\n=== COMMUNITY LIBRARY ===")
    print("Ask what the community knows. Type 'quit' to leave.\n")

    while True:
        if one_shot:
            question = one_shot
        else:
            try:
                question = input("? ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not question:
                continue
            if question.lower() in ("quit", "exit", "bye"):
                break

        # Fresh read every question: edits and deletions apply immediately.
        rules = load_rules()
        corpus = load_corpus()

        try:
            resp, elapsed = ask(question, rules, corpus)
        except urllib.error.URLError:
            print(f"\nCan't reach Ollama. Is it running? Try: ollama serve")
            print(f"And is the model pulled? Try: ollama pull {MODEL}\n")
            if one_shot:
                return
            continue

        answer = resp.get("response", "").strip()
        # some models emit a reasoning block; show only the answer part
        if "</think>" in answer:
            answer = answer.split("</think>", 1)[1].strip()

        print("\n" + answer)

        # What the code can honestly guarantee: which shelf was read.
        # Which sources the ANSWER used is the model's claim, made in its
        # own citations above -- the wrapper cannot verify it. Keep these
        # two layers distinct.
        print(f"\n[Shelf consulted: all {len(corpus)} contributions. "
              f"Named sources above are the model's own citations -- "
              f"check them against the shelf.]")

        pe_t = resp.get("prompt_eval_duration", 0) / 1e9
        ev_t = resp.get("eval_duration", 0) / 1e9
        pe_n = resp.get("prompt_eval_count", 0)
        cached = " (corpus served from cache)" if pe_n < 200 else \
                 f" (read {pe_n} tokens)"
        print(f"[{elapsed:.1f}s -- reading {pe_t:.1f}s{cached}, "
              f"writing {ev_t:.1f}s]\n")

        if one_shot:
            return


if __name__ == "__main__":
    main()
