from pathlib import Path

from code.plot_genai_taskdna_chord import (
    _build_edges,
    _parse_sim,
    write_summary_xml,
)


def test_parse_sim() -> None:
    pairs = _parse_sim("D1:0.4,D3:0.2")
    assert pairs == [("D1", 0.4), ("D3", 0.2)]


def test_build_edges_with_topk() -> None:
    rows = [
        {"task_id": "T1", "task_text": "Task one", "w": "0.5", "sim": "D1:0.5,D2:0.5"},
        {"task_id": "T2", "task_text": "Task two", "w": "0.2", "sim": "D3:1.0"},
        {"task_id": "T3", "task_text": "Task three", "w": "0.1", "sim": "D4:1.0"},
    ]
    left_nodes, right_nodes, edges, label_map, keep_ids = _build_edges(
        rows, top_task_ids=["T2"], top_n_fallback=2
    )
    assert left_nodes[0] == "D1"
    assert right_nodes == ["T2", "Other"]
    assert "T2" in label_map
    assert "Other" in label_map
    assert "T2" in keep_ids
    assert any(e[1] == "T2" for e in edges)


def test_write_summary_xml(tmp_path: Path) -> None:
    xml_path = tmp_path / "summary.xml"
    payload = {"soc": "17-2199.08", "edges": 12}
    write_summary_xml(xml_path, payload)
    content = xml_path.read_text(encoding="utf-8")
    assert "<soc>17-2199.08</soc>" in content
    assert "<edges>12</edges>" in content
