#!/usr/bin/env python3
"""Publish Sinew to the Hugging Face Hub: the dataset + the static explorer Space.

Reproducible and idempotent — safe to re-run; it refreshes whatever changed.
Auth comes from a stored `hf auth login` token (or the HF_TOKEN env var).

Requires the optional `[publish]` extra:

    pip install -e ".[publish]"     # huggingface_hub

Usage:
    python scripts/publish_hf.py dataset     # create/refresh the dataset repo
    python scripts/publish_hf.py space       # create/refresh the static Space
    python scripts/publish_hf.py card        # refresh only the dataset card (cheap)
    python scripts/publish_hf.py all         # dataset + space
    python scripts/publish_hf.py --namespace someone all
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
HF = ROOT / "hf"

DATASET_NAME = "sinew"
SPACE_NAME = "sinew-explorer"


def _require(*paths: Path) -> None:
    missing = [p for p in paths if not p.exists()]
    if missing:
        sys.exit("missing inputs (run `make build` / `make viz` first):\n  "
                 + "\n  ".join(str(p) for p in missing))


def publish_card(api: HfApi, namespace: str) -> str:
    repo_id = f"{namespace}/{DATASET_NAME}"
    card = HF / "DATASET_CARD.md"
    _require(card)
    api.create_repo(repo_id, repo_type="dataset", exist_ok=True, private=False)
    api.upload_file(path_or_fileobj=str(card), path_in_repo="README.md",
                    repo_id=repo_id, repo_type="dataset",
                    commit_message="Update dataset card")
    url = f"https://huggingface.co/datasets/{repo_id}"
    print("dataset card ->", url)
    return url


def publish_dataset(api: HfApi, namespace: str) -> str:
    repo_id = f"{namespace}/{DATASET_NAME}"
    sqlite = DIST / "sinew.sqlite"
    parquet = DIST / "parquet"
    _require(sqlite, parquet, HF / "DATASET_CARD.md")
    api.create_repo(repo_id, repo_type="dataset", exist_ok=True, private=False)
    publish_card(api, namespace)
    api.upload_file(path_or_fileobj=str(sqlite), path_in_repo="sinew.sqlite",
                    repo_id=repo_id, repo_type="dataset",
                    commit_message="Upload sinew.sqlite")
    api.upload_folder(folder_path=str(parquet), path_in_repo="parquet",
                      repo_id=repo_id, repo_type="dataset",
                      commit_message="Upload Parquet tables",
                      ignore_patterns=["**/.DS_Store"])
    for extra in ("sources.lock.json", "LICENSE"):
        p = ROOT / extra
        if p.exists():
            api.upload_file(path_or_fileobj=str(p), path_in_repo=extra,
                            repo_id=repo_id, repo_type="dataset",
                            commit_message=f"Upload {extra}")
    url = f"https://huggingface.co/datasets/{repo_id}"
    print("dataset ->", url)
    return url


def publish_space(api: HfApi, namespace: str) -> str:
    repo_id = f"{namespace}/{SPACE_NAME}"
    viz = DIST / "viz"
    card = HF / "SPACE_README.md"
    _require(viz / "index.html", card)
    api.create_repo(repo_id, repo_type="space", exist_ok=True, private=False,
                    space_sdk="static")
    api.upload_file(path_or_fileobj=str(card), path_in_repo="README.md",
                    repo_id=repo_id, repo_type="space",
                    commit_message="Space card")
    api.upload_folder(folder_path=str(viz), path_in_repo="",
                      repo_id=repo_id, repo_type="space",
                      commit_message="Deploy explorer",
                      ignore_patterns=["**/.DS_Store"])
    url = f"https://huggingface.co/spaces/{repo_id}"
    print("space ->", url)
    return url


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", choices=["dataset", "space", "card", "all"])
    ap.add_argument("--namespace", default=None,
                    help="HF user/org (default: the logged-in user)")
    args = ap.parse_args()

    api = HfApi()
    me = api.whoami()["name"]  # raises a clear error if not logged in
    ns = args.namespace or me
    print(f"authenticated as {me!r}; publishing to namespace {ns!r}")

    if args.target in ("dataset", "all"):
        publish_dataset(api, ns)
    if args.target in ("space", "all"):
        publish_space(api, ns)
    if args.target == "card":
        publish_card(api, ns)


if __name__ == "__main__":
    main()
