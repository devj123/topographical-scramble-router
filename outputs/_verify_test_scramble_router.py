import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "outputs"))
from scramble_router import AStarRouter, RouterConfig, Terrain, route_stats


def router(elevation, **config):
    return AStarRouter(Terrain(np.array(elevation, dtype=float), 10, 10), RouterConfig(**config))


def test_post_search_smoothing_removes_grid_staircase_on_flat_ground():
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


def test_hand_computed_flat_cost_and_smoothed_route():
    subject = router([[0, 0, 0]], preferred_min_slope=0, preferred_max_slope=30, impassable_slope=50)
    path, cost = subject.route((0, 0), (0, 2))
    assert path == [(0, 0), (0, 2)]
    assert cost == pytest.approx(20.0)


def test_smoothing_never_costs_more_than_the_grid_path():
    subject = router(np.zeros((4, 5)), preferred_min_slope=0, preferred_max_slope=30, impassable_slope=50)
    raw = [(0, 0), (1, 1), (2, 2), (3, 3), (3, 4)]
    smooth, smooth_cost = subject._smooth_path(raw)
    raw_cost = sum(subject._edge_cost(a, b) for a, b in zip(raw, raw[1:]))
    assert smooth[0] == raw[0] and smooth[-1] == raw[-1]
    assert smooth_cost <= raw_cost + 1e-9


def _run_with_timeout(func, seconds):
    """Fail fast instead of hanging the suite if smoothing regresses to an infinite loop."""
    import signal

    def _raise_timeout(signum, frame):
        raise TimeoutError(f"did not return within {seconds}s -- possible infinite loop")

    previous = signal.signal(signal.SIGALRM, _raise_timeout)
    signal.alarm(seconds)
    try:
        return func()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def test_smooth_path_terminates_even_when_no_shortcut_ever_numerically_qualifies():
    # Regression test: candidate_index == anchor + 1 (the original grid edge) must
    # be accepted unconditionally. Before the fix, every candidate -- including
    # the trivially-valid adjacent one -- went through the same cost comparison,
    # so a comparison that never succeeds (simulated here by forcing every
    # line-of-sight cost to infinity) left `anchor` stuck forever.
    subject = router(np.zeros((3, 6)), preferred_min_slope=0, preferred_max_slope=30, impassable_slope=50)
    raw = [(0, c) for c in range(6)]
    subject._line_cost = lambda a, b: math.inf
    smoothed, cost = _run_with_timeout(lambda: subject._smooth_path(raw), seconds=5)
    assert smoothed == raw
    assert cost == math.inf


def test_smooth_path_relative_tolerance_accepts_near_equal_shortcuts_at_large_scale():
    # Regression test: `original` is an accumulated prefix sum that can dwarf a
    # single edge cost on long routes, so a fixed absolute epsilon (the old
    # 1e-9) is too tight to absorb the resulting floating-point noise and can
    # reject an even a shortcut that is essentially tied. The relative epsilon
    # (1e-9 * max(1, original)) should accept it.
    subject = router(np.zeros((2, 4)), preferred_min_slope=0, preferred_max_slope=30, impassable_slope=50)
    raw = [(0, 0), (0, 1), (0, 2), (0, 3)]
    subject._edge_cost = lambda a, b: 100_000.0
    subject._line_cost = lambda a, b: 300_000.0001 if (a, b) == ((0, 0), (0, 3)) else 100_000.0
    smoothed, cost = subject._smooth_path(raw)
    assert smoothed == [(0, 0), (0, 3)]
    assert cost == pytest.approx(300_000.0001)


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


def test_penalized_copy_scales_inbound_edges_into_route_cells_too():
    # Regression test: penalized_copy used to scale only edges leaving a route
    # cell (directional_costs[:, rows, cols]). A neighbor stepping INTO a route
    # cell is stored at the neighbor's own array position for that direction,
    # so it needs to be penalized separately, or the alternate route can walk
    # into the primary route's corridor for free.
    subject = router(np.zeros((5, 5)), preferred_min_slope=0, preferred_max_slope=30, impassable_slope=50)
    route = [(0, 0), (2, 2), (4, 4)]
    factor = 7.0
    alternate = subject.penalized_copy(route, factor=factor)

    r, c = route[1]  # interior route cell, not a shared endpoint
    step = (1, 1)  # neighbor at (r - 1, c - 1) steps into (r, c) via this direction
    index = subject.step_index[step]
    neighbor = (r - step[0], c - step[1])
    original_inbound = subject.directional_costs[index, neighbor[0], neighbor[1]]
    penalized_inbound = alternate.directional_costs[index, neighbor[0], neighbor[1]]
    assert penalized_inbound == pytest.approx(original_inbound * factor)

    outbound_step = subject.step_index[(1, 1)]
    original_outbound = subject.directional_costs[outbound_step, r, c]
    penalized_outbound = alternate.directional_costs[outbound_step, r, c]
    assert penalized_outbound == pytest.approx(original_outbound * factor)

    start_r, start_c = route[0]
    assert alternate.directional_costs[outbound_step, start_r, start_c] == pytest.approx(
        subject.directional_costs[outbound_step, start_r, start_c]
    )  # shared endpoints stay unpenalized


@pytest.mark.parametrize("kwargs", [
    {"preferred_min_slope": 30, "preferred_max_slope": 20, "impassable_slope": 50},
    {"preferred_min_slope": 10, "preferred_max_slope": 55, "impassable_slope": 50},
])
def test_invalid_slope_bands_are_rejected(kwargs):
    with pytest.raises(ValueError):
        RouterConfig(**kwargs)
