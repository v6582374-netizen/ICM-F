from pathlib import Path

from code.plot_task_dna_robotics_wordcloud import (
    build_frequencies,
    load_top_task_ids,
    read_task_dna_csv,
    write_summary_xml,
)


def _write_csv(path: Path) -> None:
    path.write_text(
        "task_id,task_text,IM,FR,w,s,c,evidence_note\n"
        "T1,Calibrate sensors,4.0,4.2,0.2,0.5,0.5,ok\n"
        "T2,Plan motion trajectories,4.1,4.0,0.5,0.5,0.5,ok\n",
        encoding="utf-8",
    )


def test_read_task_dna_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "task_dna.csv"
    _write_csv(csv_path)
    rows = read_task_dna_csv(csv_path)
    assert len(rows) == 2
    assert rows[0]["task_id"] == "T1"


def test_load_top_task_ids(tmp_path: Path) -> None:
    payload = {
        "by_soc": {
            "17-2199.08": {"topK_task_id": ["T1", "T2", "T3"]},
        }
    }
    json_path = tmp_path / "topk.json"
    json_path.write_text(__import__("json").dumps(payload), encoding="utf-8")
    task_ids = load_top_task_ids(json_path, "17-2199.08", top_n=2)
    assert task_ids == ["T1", "T2"]


def test_build_frequencies_boost() -> None:
    rows = [
        {"task_id": "T1", "task_text": "Calibrate sensors", "w": "0.2"},
        {"task_id": "T2", "task_text": "Plan motion trajectories", "w": "0.5"},
    ]
    freqs, _ = build_frequencies(rows, top_task_ids=["T2"], boost=2.0)
    assert freqs["Plan motion trajectories"] == 1.0
    assert freqs["Calibrate sensors"] == 0.2


def test_write_summary_xml(tmp_path: Path) -> None:
    xml_path = tmp_path / "summary.xml"
    payload = {"soc": "17-2199.08", "top_n": 8}
    write_summary_xml(xml_path, payload)
    content = xml_path.read_text(encoding="utf-8")
    assert "<soc>17-2199.08</soc>" in content
    assert "<top_n>8</top_n>" in content
