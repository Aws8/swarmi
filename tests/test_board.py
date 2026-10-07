from swarm_md.board import load, parse_questions, render_report, status_lines


def test_load_scaffolded_swarm(swarm_dir):
    b = load(swarm_dir)
    assert b.name == "slow-checkout"
    assert "checkout" in b.goal
    assert b.agents == ["cache", "database"]
    assert b.questions == []
    assert not b.converged
    assert b.missing_files == []


def test_questions_and_answers(busy_swarm):
    qs = parse_questions(busy_swarm / "questions.md")
    assert len(qs) == 2
    assert qs[0].asker == "database"
    assert qs[0].answered
    assert qs[0].answers == ("yes, 400ms write lock every 10s",)
    assert qs[1].asker == "cache"
    assert not qs[1].answered


def test_converged_flag(busy_swarm):
    b = load(busy_swarm)
    assert not b.converged  # cache's question is open
    (busy_swarm / "questions.md").write_text(
        "# Questions\n- a asks: x?\n  - y\n", encoding="utf-8"
    )
    assert load(busy_swarm).converged


def test_status_and_report(busy_swarm):
    b = load(busy_swarm)
    status = "\n".join(status_lines(b, [("database", "running — url")]))
    assert "questions: 2 (1 open)" in status
    assert "cache asks" in status
    assert "not converged" in status
    rep = render_report(b)
    assert "# Swarm report: slow-checkout" in rep
    assert "**database** asked:" in rep
