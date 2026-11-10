import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mikael_ai_v1 import Config
from sft_train import SFTDataset

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

def test_programming_splits_are_large_enough_and_loadable():
    cfg = Config()
    train = SFTDataset(DATA / "programming_train.jsonl", cfg)
    val = SFTDataset(DATA / "programming_val.jsonl", cfg)
    test = SFTDataset(DATA / "programming_test.jsonl", cfg)
    assert len(train) >= 384
    assert len(val) >= 10
    assert len(test) >= 10

def test_programming_splits_have_no_instruction_leakage():
    def instructions(name):
        import json
        rows = [json.loads(line) for line in (DATA / name).read_text(encoding="utf-8").splitlines() if line.strip()]
        return {row["instruction"] for row in rows}
    train = instructions("programming_train.jsonl")
    val = instructions("programming_val.jsonl")
    test = instructions("programming_test.jsonl")
    assert len(train) == 384
    assert len(train) == len(set(train))
    assert train.isdisjoint(val)
    assert train.isdisjoint(test)
    assert val.isdisjoint(test)

def test_all_programming_examples_fit_current_context():
    for name in ("programming_train.jsonl", "programming_val.jsonl", "programming_test.jsonl"):
        dataset = SFTDataset(DATA / name, Config())
        for x, y in dataset.rows:
            assert 1 <= x.numel() <= Config().context_size
            assert x.shape == y.shape
            assert (y != -100).any()

def test_curriculum_covers_multiple_programming_languages():
    import json
    rows = [json.loads(line) for line in (DATA / "programming_train.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    languages = {row.get("language") for row in rows if row.get("language")}
    assert {"java", "cpp", "python", "javascript", "kotlin", "csharp", "sql", "git"}.issubset(languages)
    assert sum(row.get("language") == "java" for row in rows) >= 80
    assert sum(row.get("language") == "cpp" for row in rows) >= 80
