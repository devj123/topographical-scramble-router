import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "outputs"))
from scramble_router import AStarRouter, RouterConfig, Terrain, route_stats


def router(elevation, **config):
    return AStarRouter(Terrain(np.array(elevation, dtype=float), 10, 10), RouterConfig(**config))


def test_theta_star_removes_grid_staircase_on_flat_ground():
    subject = router(np.zeros((8, 8)), preferred_min_slope=0, preferred_max_slope=30, impassable_slope=50)
    path, cost = subject.route((0, 0), (7, 5))
    assert path == [(0, 0), (7, 5)]
    assert math.isfinite(cost)


def test_deferred_shortcut_keeps_parent_cost_consistent_on_asymmetric_terrain():
    subject = router([[0, 5, 10, 15], [0, 5, 10, 15], [0, 5, 10, 15]], preferred_min_slope=0, preferred_max_slope=30, impassable_slope=50)
    path, cost = subject.route((1, 0), (1, 3))
    assert path == [(1, 0), (1, 3)]
    verified_cost = sum(subject._line_cost(a, b) for a, b in zip(path, path[1:]))
    assert cost == pytest.approx(verified_cost)


def test_cliff_band_blocks_route():
    subject = router([[0, 0, 1_000, 0, 0]] * 3, preferred_min_slope=0, preferred_max_slope=20, impassable_slope=45)
    path, cost = subject.route((1, 0), (1, 4))
    assert path == []
    assert cost == math.inf


def test_isolated_valid_cell_has_no_path():
    subject = router([[0, np.nan, np.nan], [np.nan, np.nan, np.nan], [np.nan, np.nan, 0]], preferred_min_slope=0, preferred_max_slope=20, impassable_slope=45)
    assert subject.route((0, 0), (2, 2)) == ([], math.inf)


def test_directed_costs_are_asymmetric_and_stats_are_correct():
    subject = router([[0, 10]], preferred_min_slope=0, preferred_max_slope=30, impassable_slope=50)
    assert subject._edge_cost((0, 0), (0, 1)) > subject._edge_cost((0, 1), (0, 0))
    distance, gain, loss, hours = route_stats(subject.terrain, [(0, 0), (0, 1)])
    assert (distance, gain, loss) == (10, 10, 0)
    assert hours == pytest.approx(10 / 5_000 + 10 / 600)


@pytest.mark.parametrize("kwargs", [
    {"preferred_min_slope": 30, "preferred_max_slope": 20, "impassable_slope": 50},
    {"preferred_min_slope": 10, "preferred_max_slope": 55, "impassable_slope": 50},
])
def test_invalid_slope_bands_are_rejected(kwargs):
    with pytest.raises(ValueError):
        RouterConfig(**kwargs)
