import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import torch
from mikael_ai_v1 import Config
from sft_train import SFTDataset, collate_sft, IGNORE_INDEX

def test_sft_masks_prompt_and_trains_response_only(tmp_path):
    path = tmp_path / "data.jsonl"
    path.write_text('{"instruction":"Oi","response":"Olá!"}\n', encoding="utf-8")
    ds = SFTDataset(path, Config(context_size=256))
    x, y = ds[0]
    assert x[0].item() == 1
    assert (y == IGNORE_INDEX).any()
    assert (y != IGNORE_INDEX).any()
    first = torch.where(y != IGNORE_INDEX)[0][0].item()
    assert first > 0

def test_sft_rejects_missing_dataset(tmp_path):
    with pytest.raises(ValueError):
        SFTDataset(tmp_path / "missing.jsonl")

def test_sft_rejects_too_long_example(tmp_path):
    path = tmp_path / "long.jsonl"
    path.write_text('{"instruction":"' + ("a" * 80) + '","response":"' + ("b" * 80) + '"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="limite atual"):
        SFTDataset(path, Config(context_size=32))

def test_sft_collate_pads_targets_with_ignore_index(tmp_path):
    path = tmp_path / "data.jsonl"
    path.write_text(
        '{"instruction":"Oi","response":"Olá"}\n'
        '{"instruction":"Uma pergunta maior","response":"Resposta um pouco maior"}\n',
        encoding="utf-8"
    )
    ds = SFTDataset(path)
    x, y = collate_sft([ds[0], ds[1]])
    assert x.shape == y.shape
    assert (y == IGNORE_INDEX).any()
