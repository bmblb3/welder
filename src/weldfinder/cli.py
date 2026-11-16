"""weldfinder CLI.

  weldfinder                       -> `catia` (what the .exe does when double-clicked)
  weldfinder catia [--rank N]      -> read the document open in CATIA, push ONE candidate curve
  weldfinder detect model.stp      -> offline: write all candidates to JSON
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from .detect import Candidate, Params, detect
from .step_io import load_solids


def _params(a) -> Params:
    return Params(max_gap=a.max_gap, min_length=a.min_length, step=a.step)


def _summary(c: Candidate, names: dict[str, str]) -> str:
    return (f"{c.id} {c.curve_type} L={c.length:.1f} mm  gap min/mean/max="
            f"{c.gap_min:.2f}/{c.gap_mean:.2f}/{c.gap_max:.2f} mm  "
            f"{c.source}({names.get(c.source, '')}) -> {c.target}({names.get(c.target, '')})")


def cmd_detect(a) -> int:
    t0 = time.time()
    solids = load_solids(a.step_file)
    cands = detect(solids, _params(a))
    doc = {
        "step_file": a.step_file, "units": "mm",
        "params": _params(a).__dict__,
        "note": "Candidates are geometric proximity only, not confirmed weld intent.",
        "solids": [{"id": s.id, "name": s.name} for s in solids],
        "candidates": [c.to_dict() for c in cands],
    }
    with open(a.output, "w") as f:
        json.dump(doc, f, indent=1)
    print(f"{len(solids)} solids, {len(cands)} candidates -> {a.output} ({time.time() - t0:.1f}s)")
    return 0


def cmd_catia(a) -> int:
    from . import catia

    t0 = time.time()
    app = catia.connect()
    doc = app.ActiveDocument
    print(f"CATIA document: {doc.FullName}")
    bodies = catia.read_bodies(doc)
    print(f"{len(bodies)} bodies, {sum(b.visible for b in bodies)} visible")
    path = a.step_file
    if not path:
        try:
            path = catia.find_step_file(doc)
        except FileNotFoundError:
            path = input("STEP file not found next to the part. Path to the .stp: ").strip().strip('"')
    print(f"STEP source: {path}")

    solids = load_solids(path)
    solids, how = catia.match_visible(solids, bodies)
    if how == "none":
        print(f"WARNING: could not match {len(bodies)} CATIA bodies to {len(solids)} STEP solids "
              "(by name or count): visibility NOT applied, using ALL solids.")
    else:
        print(f"{len(solids)} visible solids (matched by {how})")
    if len(solids) < 2:
        print("Need at least two visible solids.")
        return 1

    cands = detect(solids, _params(a))
    if not cands:
        print(f"No candidates within {a.max_gap} mm.")
        return 1
    names = {s.id: s.name for s in solids}
    for c in cands[:5]:
        print("  ", _summary(c, names))
    if a.rank >= len(cands):
        print(f"--rank {a.rank} out of range ({len(cands)} candidates)")
        return 1
    c = cands[a.rank]
    print(f"{'Would push (dry run)' if a.dry_run else 'Pushing'}: {_summary(c, names)}")
    if not a.dry_run:
        gs = catia.push_curve(doc, c.points, f"WeldCandidate_{c.id}_{names[c.source]}_to_{names[c.target]}")
        print(f"Created geometrical set '{gs}' in CATIA ({time.time() - t0:.1f}s)")
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    double_clicked = not argv
    if double_clicked:
        argv = ["catia"]
    elif argv[0] not in ("detect", "catia", "-h", "--help"):
        argv = ["catia"] + argv  # `weldfinder --dry-run` means `weldfinder catia --dry-run`

    def common(p):
        p.add_argument("--max-gap", type=float, default=5.0, help="max edge-to-face distance, mm")
        p.add_argument("--min-length", type=float, default=3.0, help="drop candidates shorter than this, mm")
        p.add_argument("--step", type=float, default=1.0, help="sample spacing along edges, mm")

    ap = argparse.ArgumentParser(prog="weldfinder", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("detect", help="offline detection from a STEP file")
    d.add_argument("step_file")
    d.add_argument("--output", default="candidates.json")
    common(d)
    d.set_defaults(fn=cmd_detect)
    c = sub.add_parser("catia", help="detect on the document open in CATIA and push one curve")
    c.add_argument("--rank", type=int, default=0, help="which candidate to push (0 = best score)")
    c.add_argument("--step-file", help="the STEP file that was opened in CATIA (skips auto-detection)")
    c.add_argument("--dry-run", action="store_true", help="compute but do not touch CATIA's model")
    common(c)
    c.set_defaults(fn=cmd_catia)

    a = ap.parse_args(argv)
    try:
        rc = a.fn(a)
    except Exception as e:
        print(f"ERROR: {e}")
        rc = 2
    if double_clicked:
        input("Press Enter to close...")
    return rc


if __name__ == "__main__":
    sys.exit(main())
