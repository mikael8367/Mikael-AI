"""Mikael AI V1: Transformer causal experimental, com pesos aleatórios."""
from dataclasses import asdict, dataclass
from pathlib import Path
import argparse
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.data import Dataset, DataLoader

@dataclass
class Config:
    vocab_size: int = 259
    context_size: int = 256
    d_model: int = 128
    n_heads: int = 4
    n_layers: int = 4
    dropout: float = 0.0

    def validate(self):
        if self.vocab_size < 4 or self.context_size < 2:
            raise ValueError("vocab_size >= 4 e context_size >= 2")
        if min(self.d_model, self.n_heads, self.n_layers) <= 0 or self.d_model % self.n_heads:
            raise ValueError("dimensões inválidas; d_model deve ser divisível por n_heads")
        if not 0 <= self.dropout < 1:
            raise ValueError("dropout precisa estar em [0, 1)")

class ByteTokenizer:
    """IDs reservados PAD=0, BOS=1, EOS=2; bytes UTF-8 mapeados para 3..258."""
    pad_id, bos_id, eos_id, vocab_size = 0, 1, 2, 259

    def encode(self, text, add_bos=False, add_eos=False):
        if not isinstance(text, str):
            raise TypeError("text precisa ser str")
        ids = [b + 3 for b in text.encode("utf-8")]
        if add_bos: ids.insert(0, self.bos_id)
        if add_eos: ids.append(self.eos_id)
        return ids

    def decode(self, ids):
        raw = bytearray()
        for value in ids:
            value = int(value)
            if value in (0, 1, 2): continue
            if not 3 <= value <= 258: raise ValueError(f"token inválido: {value}")
            raw.append(value - 3)
        return raw.decode("utf-8", errors="replace")

class Attention(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.heads = cfg.n_heads
        self.head_dim = cfg.d_model // cfg.n_heads
        self.qkv = nn.Linear(cfg.d_model, 3 * cfg.d_model)
        self.proj = nn.Linear(cfg.d_model, cfg.d_model)
        self.dropout = cfg.dropout
        self.register_buffer("mask", torch.tril(torch.ones(cfg.context_size, cfg.context_size, dtype=torch.bool))[None, None], persistent=False)

    def forward(self, x):
        b, t, c = x.shape
        q, k, v = self.qkv(x).chunk(3, dim=-1)
        q = q.view(b, t, self.heads, self.head_dim).transpose(1, 2)
        k = k.view(b, t, self.heads, self.head_dim).transpose(1, 2)
        v = v.view(b, t, self.heads, self.head_dim).transpose(1, 2)
        y = F.scaled_dot_product_attention(q, k, v, attn_mask=self.mask[:, :, :t, :t], dropout_p=self.dropout if self.training else 0.0)
        return self.proj(y.transpose(1, 2).contiguous().view(b, t, c))

class Block(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.norm1, self.norm2 = nn.LayerNorm(cfg.d_model), nn.LayerNorm(cfg.d_model)
        self.attn = Attention(cfg)
        self.mlp = nn.Sequential(nn.Linear(cfg.d_model, 4*cfg.d_model), nn.GELU(), nn.Linear(4*cfg.d_model, cfg.d_model), nn.Dropout(cfg.dropout))

    def forward(self, x):
        x = x + self.attn(self.norm1(x))
        return x + self.mlp(self.norm2(x))

class MikaelAI(nn.Module):
    def __init__(self, cfg=None):
        super().__init__()
        self.cfg = cfg or Config()
        self.cfg.validate()
        c = self.cfg
        self.token = nn.Embedding(c.vocab_size, c.d_model)
        self.position = nn.Embedding(c.context_size, c.d_model)
        self.blocks = nn.Sequential(*[Block(c) for _ in range(c.n_layers)])
        self.norm = nn.LayerNorm(c.d_model)
        self.head = nn.Linear(c.d_model, c.vocab_size, bias=False)
        self.head.weight = self.token.weight
        self.apply(self._init)

    @staticmethod
    def _init(m):
        if isinstance(m, (nn.Linear, nn.Embedding)):
            nn.init.normal_(m.weight, mean=0.0, std=0.02)
            if isinstance(m, nn.Linear) and m.bias is not None:
                nn.init.zeros_(m.bias)

    def forward(self, ids, targets=None):
        if ids.ndim != 2: raise ValueError("ids precisa ter forma [batch, sequência]")
        b, t = ids.shape
        if not 1 <= t <= self.cfg.context_size: raise ValueError("sequência fora do contexto")
        if torch.any(ids < 0) or torch.any(ids >= self.cfg.vocab_size): raise ValueError("token ID fora do vocabulário")
        pos = torch.arange(t, device=ids.device)
        x = self.token(ids) + self.position(pos)[None, :, :]
        logits = self.head(self.norm(self.blocks(x)))
        loss = None
        if targets is not None:
            if targets.shape != ids.shape: raise ValueError("targets deve ter a mesma forma de ids")
            loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), targets.reshape(-1))
        return logits, loss

    @torch.inference_mode()
    def generate(self, ids, max_new_tokens=80, temperature=0.8, top_k=40):
        if ids.ndim != 2 or ids.shape[0] != 1: raise ValueError("use um prompt [1, sequência]")
        if max_new_tokens < 0 or temperature <= 0 or top_k < 0: raise ValueError("parâmetros de geração inválidos")
        self.eval()
        for _ in range(max_new_tokens):
            logits, _ = self(ids[:, -self.cfg.context_size:])
            scores = logits[:, -1, :] / temperature
            if top_k:
                k = min(top_k, scores.size(-1))
                cutoff = torch.topk(scores, k).values[:, -1, None]
                scores = scores.masked_fill(scores < cutoff, float("-inf"))
            ids = torch.cat((ids, torch.multinomial(F.softmax(scores, dim=-1), 1)), dim=1)
        return ids

class TextDataset(Dataset):
    def __init__(self, folder, context_size, tokenizer):
        files = sorted(Path(folder).rglob("*.txt")) if Path(folder).exists() else []
        texts = [p.read_text(encoding="utf-8", errors="replace").strip() for p in files]
        ids = []
        for text in texts:
            if text: ids.extend(tokenizer.encode(text, add_bos=True, add_eos=True))
        if len(ids) < context_size + 1:
            raise ValueError(f"corpus insuficiente em {folder}; mínimo {context_size+1} bytes/tokens")
        self.ids = torch.tensor(ids, dtype=torch.long)
        self.context = context_size

    def __len__(self): return len(self.ids) - self.context
    def __getitem__(self, i):
        part = self.ids[i:i+self.context+1]
        return part[:-1], part[1:]

def train(args):
    if args.steps < 1 or args.batch_size < 1 or args.lr <= 0: raise ValueError("steps, batch-size e lr devem ser positivos")
    torch.manual_seed(args.seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    cfg, tok = Config(), ByteTokenizer()
    train_data = TextDataset(Path(args.data_dir)/"train", cfg.context_size, tok)
    val_data = TextDataset(Path(args.data_dir)/"val", cfg.context_size, tok)
    loader = DataLoader(train_data, batch_size=args.batch_size, shuffle=True, drop_last=True)
    if not len(loader): raise ValueError("dataset pequeno demais para o batch size")
    val_loader = DataLoader(val_data, batch_size=args.batch_size)
    model = MikaelAI(cfg).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.1)
    iterator = iter(loader)
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    for step in range(1, args.steps+1):
        try: x, y = next(iterator)
        except StopIteration: iterator = iter(loader); x, y = next(iterator)
        model.train(); x, y = x.to(device), y.to(device)
        opt.zero_grad(set_to_none=True); _, loss = model(x, y)
        if loss is None or not torch.isfinite(loss): raise RuntimeError(f"loss inválida no passo {step}")
        loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step()
        if step == 1 or step % 100 == 0 or step == args.steps:
            model.eval(); vals = []
            with torch.inference_mode():
                for j, (vx, vy) in enumerate(val_loader):
                    if j >= 20: break
                    _, vl = model(vx.to(device), vy.to(device)); vals.append(vl.item())
            if not vals: raise RuntimeError("validação vazia")
            print(f"step={step} train_loss={loss.item():.4f} val_loss={sum(vals)/len(vals):.4f}", flush=True)
            tmp = out/"latest.pt.tmp"
            torch.save({"format":"mikael-ai-v1", "step":step, "config":asdict(cfg), "model_state":model.state_dict(), "optimizer_state":opt.state_dict(), "seed":args.seed}, tmp)
            tmp.replace(out/"latest.pt")

def main():
    p = argparse.ArgumentParser(description="Treinamento da Mikael AI V1 do zero")
    p.add_argument("--data-dir", default="data"); p.add_argument("--steps", type=int, default=2000)
    p.add_argument("--batch-size", type=int, default=16); p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--seed", type=int, default=42); p.add_argument("--output", default="checkpoints")
    p.add_argument("--prompt", default=None); p.add_argument("--checkpoint", default="checkpoints/latest.pt")
    p.add_argument("--max-new-tokens", type=int, default=80)
    args = p.parse_args()
    if args.prompt is None:
        train(args)
    else:
        state = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
        if state.get("format") != "mikael-ai-v1": raise ValueError("checkpoint incompatível")
        cfg = Config(**state["config"]); model = MikaelAI(cfg)
        model.load_state_dict(state["model_state"], strict=True); model.eval()
        tok = ByteTokenizer(); prompt_ids = tok.encode(args.prompt, add_bos=True)
        output = model.generate(torch.tensor([prompt_ids]), max_new_tokens=args.max_new_tokens)
        print(tok.decode(output[0, len(prompt_ids):].tolist()))

if __name__ == "__main__":
    main()
