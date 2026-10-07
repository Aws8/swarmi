from swarm_md.board import load
from swarm_md.viz import build_graph, render_viz


def test_graph_shape(busy_swarm):
    g = build_graph(load(busy_swarm))
    kinds = [n["kind"] for n in g["nodes"]]
    assert kinds.count("goal") == 1
    assert kinds.count("agent") == 2
    assert kinds.count("finding") == 2
    assert kinds.count("question") == 2
    assert kinds.count("answer") == 1
    assert g["stats"]["open"] == 1
    # edges: 2 members + 2 findings + 2 asks + 1 answer = 7
    assert len(g["edges"]) == 7


def test_question_linked_to_asker(busy_swarm):
    g = build_graph(load(busy_swarm))
    asks = [e for e in g["edges"] if e["kind"] == "asks"]
    agents = {n["id"]: n["label"] for n in g["nodes"] if n["kind"] == "agent"}
    # database's question should hang off the database agent node
    db_id = next(i for i, l in agents.items() if l == "database")
    assert any(e["a"] == db_id for e in asks)


def test_render_html(busy_swarm):
    html = render_viz(load(busy_swarm))
    assert html.startswith("<!doctype html>")
    assert "__GRAPH__" not in html
    assert '"question"' in html
    assert "p99 latency" in html
