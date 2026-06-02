"""Reproducibility gate: verify the vendored raw inputs against the pinned sha256 in
sources.lock.json (default), or re-download them from their URLs (`--download`).

The build reads ONLY data/raw, so a green `verify` is the guarantee that `make build` operates
on exactly the pinned inputs. Re-downloading may legitimately drift (OpenBible regenerates its
file with a date header); the tool reports drift rather than hiding it — update the lock
deliberately if you intend to bump a source.
"""
import sys, json, hashlib, io, zipfile, pathlib, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
LOCK = ROOT / "sources.lock.json"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(key, src):
    """Fetch a source to its data/raw path. Handles the OpenBible .zip (extract the .txt)."""
    dest = ROOT / src["file"]
    url = src["url"]
    print(f"  downloading {key} <- {url}")
    data = urllib.request.urlopen(url, timeout=120).read()
    if url.endswith(".zip"):
        zf = zipfile.ZipFile(io.BytesIO(data))
        member = next(n for n in zf.namelist() if n.endswith(".txt"))
        data = zf.read(member)
    dest.write_bytes(data)


def main(argv):
    do_download = "--download" in argv
    lock = json.load(open(LOCK))
    bad = 0
    for key, src in lock["sources"].items():
        path = ROOT / src["file"]
        if do_download:
            try:
                download(key, src)
            except Exception as e:                       # noqa: BLE001
                print(f"  [ERROR] {key}: download failed: {e}"); bad += 1; continue
        if not path.exists():
            print(f"  [MISSING] {key}: {src['file']}"); bad += 1; continue
        got = sha256(path)
        if got == src["sha256"]:
            print(f"  [OK]    {key}: sha256 matches pin")
        else:
            print(f"  [DRIFT] {key}: {got}\n          != pinned {src['sha256']}"); bad += 1
    if bad:
        print(f"\n{bad} source(s) missing or drifted from the pin.")
        return 1
    print("\nAll raw inputs match their pins.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
