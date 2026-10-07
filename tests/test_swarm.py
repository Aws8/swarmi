import pytest

from swarm_md.swarm import agent_prompt, load_state, new_swarm, save_state


def test_new_swarm_scaffold(memory_repo):
    actions = new_swarm(memory_repo, "slow-checkout", "why is checkout slow?", ["database", "cache"])
    d = memory_repo / "swarms" / "slow-checkout"
    for f in ["README.md", "findings.md", "questions.md", "agents/database.md", "agents/cache.md"]:
        assert (d / f).exists(), f
    text = (memory_repo / "MEMORY.md").read_text()
    assert "[[swarms/slow-checkout/README]]" in text
    assert any("indexed" in a for a in actions)


def test_new_swarm_refuses_existing(swarm_dir):
    with pytest.raises(FileExistsError):
        new_swarm(swarm_dir.parents[1], "slow-checkout", "again", ["x"])


def test_agent_prompt_contents(swarm_dir):
    p = agent_prompt(swarm_dir, "database", "https://github.com/x/mem", "main")
    assert "**database** agent" in p
    assert "slow-checkout" in p
    assert "https://github.com/x/mem" in p
    assert "findings.md" in p and "questions.md" in p
    assert "[source:" in p


def test_state_roundtrip(swarm_dir):
    save_state(swarm_dir, {"database": {"session_id": "devin-1", "url": "u", "status": "running"}})
    s = load_state(swarm_dir)
    assert s["database"]["session_id"] == "devin-1"
