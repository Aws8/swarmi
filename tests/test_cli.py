import json

from swarm_md.cli import main


def test_new_then_plan(memory_repo, capsys):
    rc = main(["new", "slow-checkout", str(memory_repo), "--goal", "why slow?", "--roles", "db", "cache"])
    assert rc == 0
    rc = main(["plan", str(memory_repo / "swarms" / "slow-checkout")])
    out = capsys.readouterr().out
    assert "goal:" in out and "db" in out and "cache" in out


def test_run_dry_run(swarm_dir, capsys):
    rc = main(["run", str(swarm_dir), "--repo-url", "https://github.com/x/mem", "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "dry-run" in out
    state = json.loads((swarm_dir / ".swarm" / "sessions.json").read_text())
    assert set(state) == {"cache", "database"}
    # rerunning skips existing
    rc = main(["run", str(swarm_dir), "--repo-url", "u", "--dry-run"])
    assert "already spawned" in capsys.readouterr().out


def test_status_and_report_and_viz(busy_swarm, capsys):
    assert main(["status", str(busy_swarm)]) == 0
    out = capsys.readouterr().out
    assert "1 open" in out
    assert main(["report", str(busy_swarm)]) == 0
    assert (busy_swarm / "report.md").exists()
    assert main(["viz", str(busy_swarm)]) == 0
    html = (busy_swarm / "mind.html").read_text(encoding="utf-8")
    assert "slow-checkout" in html and "converged" not in html.split("<b>")[1].split("</b>")[0]


def test_watch_times_out_quickly(busy_swarm, capsys):
    rc = main(["watch", str(busy_swarm), "--interval", "0", "--timeout", "0"])
    assert rc == 2  # timeout path


def test_missing_swarm_dir_errors(tmp_path):
    import pytest

    with pytest.raises(SystemExit):
        main(["status", str(tmp_path / "nope")])
