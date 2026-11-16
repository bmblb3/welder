"""Offset-intersect seal: bridge the gap between two face sets.

Each face set is thickened by +/-r (r slightly more than half the gap), so the two
thickened volumes overlap across the gap; their common is the bridge solid.
r escalates until the result validates.
"""
import Part

MARGINS = (0.05, 0.15, 0.4, 1.0)  # fractions of the gap, tried in order


def _min_gap(fa, fb):
    best = None
    for a in fa:
        for b in fb:
            d = a.distToShape(b)[0]
            best = d if best is None else min(best, d)
    return best


def _thicken(faces, r):
    shell = Part.makeShell(faces) if len(faces) > 1 else faces[0]
    parts = []
    for sign in (r, -r):
        try:
            s = shell.makeOffsetShape(sign, 1e-4, fill=True)
            if s.isValid() and s.Volume > 0:
                parts.append(s)
        except Exception:
            pass
    if not parts:
        raise RuntimeError("offset failed")
    out = parts[0]
    for p in parts[1:]:
        out = out.fuse(p)
    return out.removeSplitter()


def seal(faces_a, faces_b, max_volume=None):
    """Return (bridge_shape, info). Raises RuntimeError if nothing validates."""
    gap = _min_gap(faces_a, faces_b)
    if gap is None:
        raise RuntimeError("empty selection")
    if gap < 1e-6:
        raise RuntimeError("faces already touch (gap=0); nothing to bridge")
    log = []
    for m in MARGINS:
        r = gap / 2 + m * gap
        try:
            common = _thicken(faces_a, r).common(_thicken(faces_b, r))
            common = common.removeSplitter()
        except Exception as e:
            log.append(f"margin {m}: {e}")
            continue
        if common.isNull() or not common.Solids or common.Volume <= 0 or not common.isValid():
            log.append(f"margin {m}: empty/invalid")
            continue
        if max_volume and common.Volume > max_volume:
            log.append(f"margin {m}: too large ({common.Volume:.3g})")
            continue
        return common, {"gap": gap, "r": r, "volume": common.Volume, "log": log}
    raise RuntimeError("no valid bridge; " + "; ".join(log))
