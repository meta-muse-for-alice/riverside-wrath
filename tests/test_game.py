"""Headless tests for the Riverside Wrath game logic.

Run from the repo root:  python3 tests/test_game.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from riverside_wrath.game import GameState, PLAY_TOP

PASS = []
FAIL = []


def check(name, fn):
    try:
        fn()
    except AssertionError as exc:
        FAIL.append((name, str(exc)))
        print("FAIL {}: {}".format(name, exc))
    else:
        PASS.append(name)
        print("ok   {}".format(name))


def test_trash_drifts_and_breaches():
    g = GameState(seed=1)
    g.spawn_timer = 10 ** 9  # no auto-spawns during the test
    g.trash.append({"x": g.spirit_x, "y": g.play_bottom, "cd": 1, "kind": "trash"})
    purity = g.purity
    g.tick()
    assert len(g.trash) == 0, "breached trash should be removed"
    assert g.purity == purity - GameState.BREACH_DAMAGE, "breach should damage purity"
    assert g.breaches == 1


def test_surge_cleanses_nearby_trash():
    g = GameState(seed=2)
    g.trash.append({"x": g.spirit_x, "y": g.spirit_y, "cd": 5, "kind": "trash"})
    g.trash.append({"x": 1, "y": PLAY_TOP, "cd": 5, "kind": "trash"})  # far away
    assert g.surge() is True
    assert len(g.trash) == 1, "only nearby trash should be cleansed"
    assert g.score == GameState.TRASH_SCORE
    assert g.surge_cooldown > 0
    assert g.surge() is False, "surge should be on cooldown"


def test_surge_scares_polluters():
    g = GameState(seed=3)
    g.polluters.append({"x": g.spirit_x + 2, "y": g.spirit_y,
                        "side": -1, "kind": "walker", "state": "in", "t": 0})
    assert g.surge() is True
    assert len(g.polluters) == 0, "nearby polluter should flee"
    assert g.score == GameState.POLLUTER_SCORE
    assert g.wrath > 0, "scaring polluters should feed wrath"


def test_polluter_walks_in_and_litters():
    g = GameState(seed=4)
    g.spawn_timer = 10 ** 9
    p = {"x": 2, "y": 10, "side": -1, "kind": "walker", "state": "in", "t": 0}
    g.polluters.append(p)
    edge = g.river_left - 1
    for _ in range(500):
        g.tick()
        if p["state"] == "litter":
            break
    assert p["state"] == "litter", "polluter should reach the river edge"
    assert p["x"] == edge
    before = len(g.trash)
    for _ in range(30):
        g.tick()
        if len(g.trash) > before:
            break
    assert len(g.trash) > before, "littering polluter should toss trash"


def test_wrath_unleash_clears_everything():
    g = GameState(seed=5)
    g.spawn_timer = 10 ** 9
    g.purity = 60
    g.wrath = 100
    g.trash = [{"x": 10, "y": 10, "cd": 5, "kind": "trash"}, {"x": 12, "y": 12, "cd": 5, "kind": "trash"}]
    g.polluters = [{"x": 5, "y": 5, "side": 1, "kind": "walker", "state": "in", "t": 0}]
    assert g.unleash_wrath() is True
    assert g.trash == [] and g.polluters == []
    assert g.wrath == 0
    assert g.purity == 75, "wrath should restore some purity"
    assert g.flood_ttl > 0, "flood animation should trigger"
    assert g.unleash_wrath() is False, "wrath needs to recharge"


def test_game_over_at_zero_purity():
    g = GameState(seed=6)
    g.spawn_timer = 10 ** 9
    g.purity = 5
    g.trash.append({"x": g.spirit_x, "y": g.play_bottom, "cd": 1, "kind": "trash"})
    g.tick()
    assert g.game_over is True
    assert g.purity == 0
    score = g.score
    g.tick()
    assert g.score == score, "dead rivers do not score"


def test_spirit_movement_clamped():
    g = GameState(seed=7)
    for _ in range(1000):
        g.move_spirit(-1)
    assert g.spirit_y == PLAY_TOP
    for _ in range(1000):
        g.move_spirit(1)
    assert g.spirit_y == g.play_bottom


def test_level_increases_spawn_pressure():
    slow = GameState(seed=8)
    slow.score = 0
    slow.spawn_timer = 1  # fires on the next tick
    slow.tick()
    interval_calm = slow.spawn_timer
    fast = GameState(seed=8)
    fast.score = 1000  # level 5
    fast.spawn_timer = 1
    fast.tick()
    interval_angry = fast.spawn_timer
    assert interval_calm == 31, "level 1 interval should be 31, got {}".format(interval_calm)
    assert interval_angry < interval_calm, "higher level should spawn faster"


def test_combo_multiplies_chained_cleanses():
    g = GameState(seed=9)
    g.spawn_timer = 10 ** 9
    g.trash.append({"x": g.spirit_x, "y": g.spirit_y, "cd": 5, "kind": "trash"})
    assert g.surge() is True
    assert g.score == 10 and g.combo == 1
    g.surge_cooldown = 0  # test-only reset
    g.trash.append({"x": g.spirit_x, "y": g.spirit_y, "cd": 5, "kind": "trash"})
    assert g.surge() is True
    assert g.combo == 2, "chained cleanse should raise the combo"
    assert g.score == 10 + 20, "second cleanse should score double"
    # let the combo window expire
    g.surge_cooldown = 0
    for _ in range(GameState.COMBO_WINDOW + 1):
        g.tick()
    assert g.combo == 0, "combo should expire"
    g.trash.append({"x": g.spirit_x, "y": g.spirit_y, "cd": 5, "kind": "trash"})
    before = g.score
    assert g.surge() is True
    assert g.score == before + 10, "fresh combo should score base points"


def test_wrath_unleash_scores_half_rate():
    g = GameState(seed=5)
    g.spawn_timer = 10 ** 9
    g.wrath = 100
    g.trash = [{"x": 10, "y": 10, "cd": 5, "kind": "trash"},
               {"x": 12, "y": 12, "cd": 5, "kind": "sludge"}]
    assert g.unleash_wrath() is True
    assert g.score == (GameState.TRASH_SCORE // 2
                       + GameState.SLUDGE_SCORE // 2), \
        "flood should pay half the surge rate per item, got {}".format(g.score)


def test_wrath_unleash_resets_combo():
    g = GameState(seed=5)
    g.spawn_timer = 10 ** 9
    g.wrath = 100
    g.combo = 3
    g.combo_timer = GameState.COMBO_WINDOW
    g.trash = [{"x": 10, "y": 10, "cd": 5, "kind": "trash"}]
    assert g.unleash_wrath() is True
    assert g.combo == 0 and g.combo_timer == 0, \
        "a flood that clears the river should end the combo"


def test_breach_resets_combo():
    g = GameState(seed=10)
    g.spawn_timer = 10 ** 9
    g.combo = 3
    g.combo_timer = GameState.COMBO_WINDOW
    g.trash.append({"x": g.spirit_x, "y": g.play_bottom, "cd": 1, "kind": "trash"})
    g.tick()
    assert g.combo == 0 and g.combo_timer == 0, "a breach should break the combo"


def test_dumper_dumps_triple_trash():
    g = GameState(seed=11)
    g.spawn_timer = 10 ** 9
    edge = g.river_left - 1
    g.polluters.append({"x": edge, "y": 10, "side": -1, "kind": "dumper",
                        "state": "litter", "t": 10})
    for _ in range(3):  # toss happens when the litter timer hits 7
        g.tick()
    assert len(g.trash) == 3, "dumper should dump three trash, got {}".format(len(g.trash))
    ys = sorted(t["y"] for t in g.trash)
    assert ys == [9, 10, 11], "dumper trash should fan out vertically"


def test_dumper_at_edge_dumps_distinct_rows():
    for y, expected in ((PLAY_TOP, [PLAY_TOP, PLAY_TOP + 1, PLAY_TOP + 2]),):
        g = GameState(seed=11)
        g.spawn_timer = 10 ** 9
        edge = g.river_left - 1
        g.polluters.append({"x": edge, "y": y, "side": -1, "kind": "dumper",
                            "state": "litter", "t": 10})
        for _ in range(3):  # toss happens when the litter timer hits 7
            g.tick()
        assert len(g.trash) == 3, "dumper should dump three trash"
        assert sorted(t["y"] for t in g.trash) == expected, \
            "dumper at the top edge should fan out, not stack two trash on one row"
    g = GameState(seed=11)
    g.spawn_timer = 10 ** 9
    edge = g.river_left - 1
    g.polluters.append({"x": edge, "y": g.play_bottom, "side": -1, "kind": "dumper",
                        "state": "litter", "t": 10})
    for _ in range(3):
        g.tick()
    ys = sorted(t["y"] for t in g.trash)
    assert ys == [g.play_bottom - 2, g.play_bottom - 1, g.play_bottom], \
        "dumper at the bottom edge should fan out, got {}".format(ys)


def test_dumper_scare_worth_more():
    g = GameState(seed=12)
    g.spawn_timer = 10 ** 9
    g.polluters.append({"x": g.spirit_x + 2, "y": g.spirit_y, "side": -1,
                        "kind": "dumper", "state": "in", "t": 0})
    assert g.surge() is True
    assert g.score == GameState.DUMPER_SCORE
    assert g.wrath == GameState.WRATH_PER_DUMPER


def test_sludge_breach_hits_harder():
    g = GameState(seed=13)
    g.spawn_timer = 10 ** 9
    g.trash.append({"x": g.spirit_x, "y": g.play_bottom, "cd": 1, "kind": "sludge"})
    purity = g.purity
    g.tick()
    assert g.purity == purity - GameState.SLUDGE_DAMAGE


def test_sludge_cleanses_for_more():
    g = GameState(seed=14)
    g.spawn_timer = 10 ** 9
    g.trash.append({"x": g.spirit_x, "y": g.spirit_y, "cd": 5, "kind": "sludge"})
    assert g.surge() is True
    assert g.score == GameState.SLUDGE_SCORE
    assert g.wrath == GameState.WRATH_PER_SLUDGE


def test_cli_version_flag_skips_curses():
    import io
    from contextlib import redirect_stdout
    from riverside_wrath import __main__ as front
    from riverside_wrath import __version__
    buf = io.StringIO()
    with redirect_stdout(buf):
        front.run(["--version"])
    assert __version__ in buf.getvalue(), "version flag should print the version"


def test_cli_help_flag_skips_curses():
    import io
    from contextlib import redirect_stdout
    from riverside_wrath import __main__ as front
    buf = io.StringIO()
    with redirect_stdout(buf):
        front.run(["--help"])
    assert "usage" in buf.getvalue().lower(), "help flag should print usage"
    assert "difficulty" in buf.getvalue().lower(), "help should mention difficulty"


def test_cli_help_lists_help_and_version():
    import io
    from contextlib import redirect_stdout
    from riverside_wrath import __main__ as front
    buf = io.StringIO()
    with redirect_stdout(buf):
        front.run(["--help"])
    assert "--help, -h" in buf.getvalue(), "help should list --help"
    assert "--version, -V" in buf.getvalue(), "help should list --version"


def test_difficulty_affects_spawn_rate():
    from riverside_wrath.game import DIFFICULTIES
    calm = GameState(seed=1, difficulty="calm")
    raging = GameState(seed=1, difficulty="raging")
    # calm should have longer spawn interval than raging at same level
    calm.spawn_timer = 1
    raging.spawn_timer = 1
    calm.tick()
    raging.tick()
    assert calm.spawn_timer > raging.spawn_timer, \
        "calm should spawn slower than raging"


def test_difficulty_affects_damage():
    calm = GameState(seed=1, difficulty="calm")
    raging = GameState(seed=1, difficulty="raging")
    calm_dmg = calm._breach_damage("trash")
    raging_dmg = raging._breach_damage("trash")
    assert raging_dmg > calm_dmg, "raging should hit harder than calm"
    # sludge should always hurt more than trash at same difficulty
    assert calm._breach_damage("sludge") > calm_dmg


def test_level_progress():
    g = GameState(seed=1)
    g.score = 0
    assert g.level_progress() == 0.0
    g.score = 125
    assert 0.4 < g.level_progress() < 0.6, "125/250 should be ~50%"
    g.score = 250
    # level recalculates on tick
    g.tick()
    assert g.level == 2
    assert g.score_to_next_level() == 250


def test_draw_surge_cooldown_shows_real_seconds():
    import curses
    from unittest import mock
    from riverside_wrath import __main__ as front

    class FakeScr:
        def __init__(self):
            self.strs = []

        def getmaxyx(self):
            return (24, 80)

        def addch(self, y, x, ch, attr=0):
            pass

        def addstr(self, y, x, s, attr=0):
            self.strs.append(s)

    for cooldown, expected in ((11, "Surge ready in 1"), (14, "Surge ready in 2")):
        g = GameState(seed=1)
        g.surge_cooldown = cooldown
        scr = FakeScr()
        with mock.patch.object(curses, "color_pair", return_value=0):
            front.draw(scr, g, 0, False)
        assert any(expected in s for s in scr.strs), \
            "cooldown {} ticks ({}s) should show '{}', got {}".format(
                cooldown, cooldown * front.TICK_SECONDS, expected, scr.strs)


def test_bar_clamps_out_of_range_values():
    from riverside_wrath import __main__ as front
    assert front.bar("Wrath", 150) == "Wrath [##########] 100%"
    assert front.bar("Wrath", -10) == "Wrath [----------]   0%"
    assert front.bar("Wrath", 50) == "Wrath [#####-----]  50%"


def test_invalid_difficulty_raises_value_error():
    try:
        GameState(seed=1, difficulty="bogus")
    except ValueError as exc:
        assert "bogus" in str(exc) and "calm" in str(exc)
    else:
        raise AssertionError("unknown difficulty should raise ValueError, not KeyError")


def test_difficulty_preset_is_not_shared():
    from riverside_wrath.game import DIFFICULTIES
    g1 = GameState(seed=1, difficulty="normal")
    g1._diff["spawn_base"] = 999
    assert DIFFICULTIES["normal"]["spawn_base"] != 999, \
        "mutating one game must not rewrite the shared preset"
    g2 = GameState(seed=1, difficulty="normal")
    assert g2._diff["spawn_base"] == DIFFICULTIES["normal"]["spawn_base"]


def test_tiny_board_raises_value_error():
    for width, height in ((10, 24), (80, 5), (13, 6)):
        try:
            GameState(width=width, height=height, seed=1)
        except ValueError:
            pass
        else:
            raise AssertionError(
                "GameState({}x{}) should raise ValueError".format(width, height))


def test_load_scores_discards_malformed_entries():
    import json
    import tempfile
    from riverside_wrath import __main__ as front
    cases = [
        ({"best": 10, "scores": "notalist"},
         {"best": 10, "scores": []}),
        ({"best": 10, "scores": [{"name": "AAA", "score": 30},
                                  {"name": "BBB"}, "junk",
                                  {"name": "CCC", "score": "not-a-score"},
                                  {"name": "DDD", "score": 20}]},
         {"best": 10, "scores": [{"name": "AAA", "score": 30},
                                  {"name": "DDD", "score": 20}]}),
        ({"best": "not-a-number", "scores": []},
         {"best": 0, "scores": []}),
        ([1, 2, 3], {"best": 0, "scores": []}),
    ]
    for raw, expected in cases:
        with tempfile.NamedTemporaryFile("w", delete=False) as fh:
            json.dump(raw, fh)
            path = fh.name
        orig = front.BEST_FILE
        try:
            front.BEST_FILE = path
            data = front.load_scores()
            assert data == expected, "load_scores({!r}) gave {!r}".format(raw, data)
            # the cleaned data must be usable, not crash qualifies/record_score
            assert front.qualifies(data, 5) is True
            front.record_score(data, "ZZZ", 5)
        finally:
            front.BEST_FILE = orig
            os.unlink(path)


def test_save_scores_is_atomic_and_round_trips():
    import tempfile
    from riverside_wrath import __main__ as front
    orig = front.BEST_FILE
    with tempfile.TemporaryDirectory() as directory:
        try:
            front.BEST_FILE = os.path.join(directory, "best")
            data = {"best": 42, "scores": [{"name": "AAA", "score": 42}]}
            front.save_scores(data)
            assert os.listdir(directory) == ["best"], \
                "save_scores should leave no temp file behind"
            assert front.load_scores() == data
        finally:
            front.BEST_FILE = orig


def test_cli_rejects_unknown_positional():
    import io
    from contextlib import redirect_stderr, redirect_stdout
    from riverside_wrath import __main__ as front
    buf, err = io.StringIO(), io.StringIO()
    with redirect_stdout(buf), redirect_stderr(err):
        front.run(["mystery-river"])
    assert "Unknown argument: mystery-river" in err.getvalue()
    assert "needs a real terminal" not in buf.getvalue(), \
        "a stray argument should not start the game"


def test_cli_missing_option_value():
    import io
    from contextlib import redirect_stderr, redirect_stdout
    from riverside_wrath import __main__ as front
    for args, expected in ((["--difficulty"], "Missing value for --difficulty"),
                           (["--seed"], "Missing value for --seed")):
        buf, err = io.StringIO(), io.StringIO()
        with redirect_stdout(buf), redirect_stderr(err):
            front.run(args)
        assert expected in err.getvalue(), "run({}) should report {}".format(args, expected)


def test_cli_rejects_bad_equals_form():
    import io
    from contextlib import redirect_stderr, redirect_stdout
    from riverside_wrath import __main__ as front
    for args, expected in ((["--difficulty=bogus"], "Unknown difficulty: bogus"),
                           (["--seed=abc"], "Seed must be an integer: abc")):
        buf, err = io.StringIO(), io.StringIO()
        with redirect_stdout(buf), redirect_stderr(err):
            front.run(args)
        assert expected in err.getvalue(), "run({}) should report {}".format(args, expected)


def test_trash_near_estuary_warning():
    g = GameState(seed=1)
    g.spawn_timer = 10 ** 9
    assert g.trash_near_estuary() == 0
    g.trash.append({"x": 10, "y": g.play_bottom, "cd": 5, "kind": "trash"})
    g.trash.append({"x": 11, "y": g.play_bottom - 5, "cd": 5, "kind": "trash"})
    assert g.trash_near_estuary(threshold=3) == 1, "only one trash near edge"


if __name__ == "__main__":
    for name, fn in sorted(
            [(k, v) for k, v in globals().items() if k.startswith("test_")]):
        check(name, fn)
    print("\n{} passed, {} failed".format(len(PASS), len(FAIL)))
    sys.exit(1 if FAIL else 0)
