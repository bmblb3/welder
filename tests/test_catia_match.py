from weldfinder.catia import CatiaBody, match_visible
from weldfinder.step_io import Solid


def S(i, n):
    return Solid(f"S{i:03d}", n, None)


def test_match_by_name_filters_hidden():
    solids = [S(0, "Shell"), S(1, "Baffle"), S(2, "Tube")]
    bodies = [CatiaBody("tube", True), CatiaBody("Shell", True), CatiaBody("Baffle", False)]
    got, how = match_visible(solids, bodies)
    assert how == "name" and [s.id for s in got] == ["S000", "S002"]


def test_match_by_order_when_names_differ():
    solids = [S(0, "a"), S(1, "b")]
    got, how = match_visible(solids, [CatiaBody("x", False), CatiaBody("y", True)])
    assert how == "order" and [s.id for s in got] == ["S001"]


def test_unmatched_falls_back_to_all():
    solids = [S(0, "a"), S(1, "b"), S(2, "c")]
    got, how = match_visible(solids, [CatiaBody("x", True)])
    assert how == "none" and len(got) == 3


def test_match_strips_hash_suffix():
    solids = [S(0, "Part2#0"), S(1, "Part2#1")]
    # CATIA bodies cannot both be called Part2, so this must not match by name; falls to order
    bodies = [CatiaBody("A", True), CatiaBody("B", False)]
    got, how = match_visible(solids, bodies)
    assert how == "order" and [s.id for s in got] == ["S000"]
    got, how = match_visible([S(0, "Baffle#0"), S(1, "Tube#0")], [CatiaBody("Tube", True), CatiaBody("Baffle", False)])
    assert how == "name" and [s.id for s in got] == ["S001"]
