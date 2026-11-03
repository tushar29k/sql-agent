"""Generate evals/guardrail_variants.yaml from the guardrail seeds.

Offline, one-shot generation: the runner never runs this — the
output is a checked-in YAML file, diff-reviewed like a lockfile
before committing. The mutations come from sql_mutations; the
benign near-miss controls in near_miss_controls.yaml are copied in
verbatim.

Every variant carries seed_id + mutation + family, so failures
group by attack family in the results table, and expect copied from
the seed — except where a wrapper changes what a correct gate
should answer (stacked statements are blocked by design, EXPLAIN of
a write is blocked; see the structural table). Expectations are
NEVER computed from the validator itself — grading the gate by its
own answers would bake its blind spots into the suite.

Dedup: exact hash on whitespace-collapsed text across all variants
and against the seeds. The hash keeps case (case is the entire
mutation for lower_case, so lowercasing would dedup it away against
its own seed), and whitespace_pad keys carry their mutation name —
whitespace is the entire mutation there, so collapsing would dedup
every one of them away against its own seed.

    python3 evals/generate_guardrail_variants.py
"""
import hashlib
import os
import sys
from datetime import date

import yaml

sys.path.insert(0, ".")
sys.path.insert(0, "evals")
import sql_mutations as mut

GENERATOR_VERSION = 1
SEEDS_PATH = "evals/guardrail_seeds.yaml"
CONTROLS_PATH = "evals/near_miss_controls.yaml"
OUT_PATH = "evals/guardrail_variants.yaml"


def _collapse(text):
    return " ".join((text or "").split())


def _sql_cases(seed):
    """All variants of one SQL attack seed (pre-dedup)."""
    out = []
    stmt = seed["statement"]
    for name, fn in mut.SQL_MUTATIONS.items():
        if name in mut.STACK_MUTATIONS and seed["id"] not in \
                mut.STACKABLE_SEEDS:
            continue
        mutated = fn(stmt)
        if mutated is None or mutated == stmt:
            continue  # mutation doesn't apply to this seed's shape
        expect = seed["expect"]
        if name in mut.STACK_MUTATIONS:
            # stacking moves the payload into the multi-statement
            # class, which the gate blocks outright by design (see
            # validate_sql's contract, and the stacked seed's own
            # expect) — the wrapper changes the correct answer,
            # same as explain_wrap in the structural table
            expect = "blocked"
        out.append({"id": f"{seed['id']}__{name}", "seed_id": seed["id"],
                    "mutation": name, "family": mut.family_of(name),
                    "type": "sql", "statement": mutated,
                    "expect": expect})
    for name, stmt2, expect in mut.STRUCTURAL.get(seed["id"], []):
        out.append({"id": f"{seed['id']}__{name}", "seed_id": seed["id"],
                    "mutation": name, "family": mut.family_of(name),
                    "type": "sql", "statement": stmt2, "expect": expect})
    return out


def _question_cases(seed):
    """Encoding + paraphrase variants of the prompt-injection seed."""
    out = []
    for name, fn in mut.QUESTION_MUTATIONS.items():
        out.append({"id": f"{seed['id']}__{name}", "seed_id": seed["id"],
                    "mutation": name, "family": mut.family_of(name),
                    "type": "question", "brain": "decoding",
                    "question": fn(seed["question"]),
                    "expect": seed["expect"]})
    for i, text in enumerate(mut.PARAPHRASES, start=1):
        name = f"paraphrase_{i}"
        out.append({"id": f"{seed['id']}__{name}", "seed_id": seed["id"],
                    "mutation": name, "family": mut.family_of(name),
                    "type": "question", "brain": "compliant",
                    "question": text, "expect": seed["expect"]})
    return out


def _case_text(case):
    return case.get("statement") or case.get("question") or ""


def _dedup(candidates, seed_texts):
    """Exact-hash dedup vs the seeds and against kept variants.
    Returns (kept, dropped_count)."""
    seen = {_collapse(t) for t in seed_texts}
    kept, dropped = [], 0
    for case in candidates:
        key = _collapse(_case_text(case))
        if case["mutation"] == "whitespace_pad":
            key += " #whitespace_pad"  # see module docstring
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        kept.append(case)
    return kept, dropped


def main():
    seed_bytes = open(SEEDS_PATH, "rb").read()
    seeds = yaml.safe_load(seed_bytes)["cases"]
    attacks = [s for s in seeds if s["type"] in ("sql", "question")]
    seed_texts = [_case_text(s) for s in seeds]

    candidates = []
    for seed in attacks:
        if seed["type"] == "sql":
            candidates.extend(_sql_cases(seed))
        else:
            candidates.extend(_question_cases(seed))
    variants, dropped = _dedup(candidates, seed_texts)

    controls = yaml.safe_load(open(CONTROLS_PATH))["cases"]
    for case in controls:
        variants.append({"id": case["id"], "seed_id": case["id"],
                         "mutation": "hand_seeded",
                         "family": "near_miss_control",
                         "type": "control",
                         "statement": case["statement"],
                         "expect": case["expect"]})

    header = {"generator": "generate_guardrail_variants.py",
              "generator_version": GENERATOR_VERSION,
              "generated": date.today().isoformat(),
              "seed_file": os.path.basename(SEEDS_PATH),
              "seed_sha256": hashlib.sha256(seed_bytes).hexdigest()}
    with open(OUT_PATH, "w") as f:
        f.write("# generated by evals/generate_guardrail_variants.py — "
                "do not hand-edit;\n# regenerate from guardrail_seeds.yaml "
                "+ near_miss_controls.yaml instead.\n")
        yaml.safe_dump({"header": header, "cases": variants}, f,
                       allow_unicode=True, sort_keys=False, width=4096)

    by_family = {}
    for case in variants:
        by_family[case["family"]] = by_family.get(case["family"], 0) + 1
    print(f"wrote {OUT_PATH}: {len(variants)} cases "
          f"({dropped} duplicates dropped)")
    for name in sorted(by_family):
        print(f"  {name:26s} {by_family[name]}")


if __name__ == "__main__":
    main()
