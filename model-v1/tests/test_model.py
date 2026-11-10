import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch
from mikael_ai_v1 import Config, ByteTokenizer, MikaelAI

def small():
    return Config(vocab_size=259, context_size=16, d_model=32, n_heads=4, n_layers=2)

def test_utf8_roundtrip():
    text = "Olá, Mikael AI! çã🙂"
    tok = ByteTokenizer()
    assert tok.decode(tok.encode(text)) == text

def test_forward_shape_and_loss():
    model = MikaelAI(small())
    x = torch.randint(0, 259, (2, 12))
    logits, loss = model(x, x)
    assert logits.shape == (2, 12, 259)
    assert loss is not None and torch.isfinite(loss)

def test_attention_is_causal():
    torch.manual_seed(3)
    model = MikaelAI(small()).eval()
    a = torch.tensor([[10, 11, 12, 13]])
    b = torch.tensor([[10, 11, 90, 91]])
    with torch.inference_mode():
        ya, _ = model(a)
        yb, _ = model(b)
    assert torch.allclose(ya[:, :2], yb[:, :2], atol=1e-6)

def test_gradients_are_finite():
    model = MikaelAI(small())
    x = torch.randint(0, 259, (2, 12))
    _, loss = model(x, x)
    loss.backward()
    grads = [p.grad for p in model.parameters() if p.grad is not None]
    assert grads and all(torch.isfinite(g).all() for g in grads)

def test_generation_limit():
    model = MikaelAI(small())
    output = model.generate(torch.tensor([[1, 10, 11]]), max_new_tokens=4, top_k=10)
    assert output.shape == (1, 7)
