"""Precompute candidate-skill x role-skill cosine similarity (D-16, D-33). Local only."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import hashlib
import json
from datetime import datetime, timezone

from core.paths import DATA
from scripts.profile_data import load_csv, _tokens

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
PINNED_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"


def _candidate_tokens(cands: list[dict]) -> list[str]:
    vocab = set()
    for r in cands:
        vocab.update(_tokens(r["skills"]))
    return sorted(vocab)


def _atomic_role_tokens(roles: list[dict], aliases: dict) -> list[str]:
    expand = aliases.get("expand", {})
    atoms = set()
    for r in roles:
        for token in _tokens(r["required_skills"]) + _tokens(r["nice_to_have_skills"]):
            atoms.update(expand[token] if token in expand else [token])
    return sorted(atoms)


def _vocab_hash(candidate_tokens: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(candidate_tokens)).encode()).hexdigest()


def _print_spot_check(similarity: dict) -> None:
    for probe in ("rest apis", "python", "kafka"):
        top3 = sorted(similarity[probe].items(), key=lambda kv: -kv[1])[:3]
        print(f"{probe} top-3: {top3}")


def main() -> None:
    from sentence_transformers import SentenceTransformer
    import numpy as np

    cands = load_csv(DATA / "candidate_profiles.csv")
    roles = load_csv(DATA / "open_roles.csv")
    aliases = json.loads((DATA / "skill_aliases.json").read_text())

    cand_tokens = _candidate_tokens(cands)
    role_tokens = _atomic_role_tokens(roles, aliases)

    model = SentenceTransformer(MODEL, revision=PINNED_REVISION)
    cand_emb = model.encode(cand_tokens, normalize_embeddings=True)
    role_emb = model.encode(role_tokens, normalize_embeddings=True)

    similarity = {}
    for i, rtok in enumerate(role_tokens):
        similarity[rtok] = {
            ctok: round(float(np.dot(role_emb[i], cand_emb[j])), 3)
            for j, ctok in enumerate(cand_tokens)
        }

    out = {
        "_meta": {
            "model": MODEL,
            "revision": PINNED_REVISION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "vocab_hash": _vocab_hash(cand_tokens),
        },
        "similarity": similarity,
    }
    (DATA / "skill_similarity.json").write_text(json.dumps(out, sort_keys=True, indent=2))
    _print_spot_check(similarity)


if __name__ == "__main__":
    main()
