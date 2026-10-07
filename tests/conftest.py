import pytest


@pytest.fixture()
def memory_repo(tmp_path):
    (tmp_path / "MEMORY.md").write_text(
        "# Memory: demo\n\n## Index\n", encoding="utf-8"
    )
    return tmp_path


@pytest.fixture()
def swarm_dir(memory_repo):
    from swarm_md.swarm import new_swarm

    new_swarm(memory_repo, "slow-checkout", "why is checkout slow?", ["database", "cache"])
    return memory_repo / "swarms" / "slow-checkout"


@pytest.fixture()
def busy_swarm(swarm_dir):
    (swarm_dir / "findings.md").write_text(
        "# Findings\n"
        "- p99 latency is 2.4s [source: https://s/1]\n"
        "- cache rebuild takes 400ms [source: https://s/2]\n",
        encoding="utf-8",
    )
    (swarm_dir / "questions.md").write_text(
        "# Questions\n"
        "- database asks: does the price cache lock during rebuild? [source: https://s/1]\n"
        "  - yes, 400ms write lock every 10s [source: https://s/2]\n"
        "- cache asks: which table does the refresh rebuild?\n",
        encoding="utf-8",
    )
    return swarm_dir
