"""Công cụ chỉnh trọng số beam: bộ dev khác seed, và so ghép cặp giữa các cấu hình.

Hai công cụ này quyết định việc có đổi mặc định của mô hình ngôn ngữ hay không, nên sai ở đây là
sai ở một quyết định sản phẩm — dù không có dòng mã sản phẩm nào đổi.
"""

from __future__ import annotations

import json

from tools import make_t1, paired_compare


def test_seed_base_reaches_generator(monkeypatch, tmp_path):
    """Bộ dev phải khác seed T1 (1000-1499), nếu không 'chỉnh trên dev' chính là chỉnh trên T1."""
    seen = {}

    def fake_generate(out_dir, full, clips, seed_base=1000, corpus=None):
        seen["seed_base"], seen["corpus"] = seed_base, corpus
        return []

    monkeypatch.setattr(make_t1, "generate_matrix", fake_generate)
    make_t1.main(["--out", str(tmp_path), "--seed-base", "500000"])
    assert seen["seed_base"] == 500000
    make_t1.main(["--out", str(tmp_path)])
    assert seen["seed_base"] == 1000 and seen["corpus"] is None   # mặc định vẫn là T1
    # dev-OOV: văn bản từ holdout (model âm học lẫn LM chưa thấy), không phải danh sách dựng sẵn
    make_t1.main(["--out", str(tmp_path), "--seed-base", "700000", "--holdout-text"])
    assert {p.name for p in seen["corpus"].values()} == {"en.holdout.txt", "ru.holdout.txt", "kk.holdout.txt"}


def _write(tmp_path, name, params, hyps):
    p = tmp_path / name
    p.write_text(json.dumps({"params": params, "hyps": hyps}), encoding="utf-8")
    return p


def _manifest(tmp_path, refs):
    p = tmp_path / "m.jsonl"
    p.write_text("\n".join(json.dumps({"text": r, "text_original": r}) for r in refs),
                 encoding="utf-8")
    return p


def test_paired_compare_flags_a_real_improvement(tmp_path, capsys):
    refs = [f"CQ DE K{i}" for i in range(60)]
    m = _manifest(tmp_path, refs)
    base = _write(tmp_path, "base.json", {}, ["CQ DE"] * 60)          # luôn thiếu một từ
    better = _write(tmp_path, "b.json", {"alpha": 0.3}, refs)          # đúng hết
    assert paired_compare.main([str(m), str(base), str(better)]) == 0
    assert "TỐT HƠN chắc chắn" in capsys.readouterr().out


def test_paired_compare_identical_runs_are_indistinguishable(tmp_path, capsys):
    refs = [f"CQ DE K{i}" for i in range(40)]
    hyps = ["CQ DE" if i % 3 else refs[i] for i in range(40)]
    m = _manifest(tmp_path, refs)
    a = _write(tmp_path, "a.json", {}, hyps)
    b = _write(tmp_path, "b.json", {"beta": 1.0}, hyps)
    paired_compare.main([str(m), str(a), str(b)])
    out = capsys.readouterr().out
    assert "không phân biệt được" in out and "+0.00" in out


def test_paired_compare_rejects_mismatched_lengths(tmp_path):
    """Kết quả từ một manifest khác (số clip khác) không được âm thầm so với nhau."""
    import pytest

    m = _manifest(tmp_path, ["A", "B", "C"])
    a = _write(tmp_path, "a.json", {}, ["A", "B", "C"])
    b = _write(tmp_path, "b.json", {}, ["A", "B"])
    with pytest.raises(ValueError):
        paired_compare.main([str(m), str(a), str(b)])
