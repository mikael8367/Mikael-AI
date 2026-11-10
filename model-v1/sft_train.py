"""Instruction fine-tuning simples com loss mascarada na resposta."""
import argparse
import json
from pathlib import Path
import torch
from torch.utils.data import Dataset, DataLoader
from mikael_ai_v1 import Config, MikaelAI, ByteTokenizer

IGNORE_INDEX = -100

class SFTDataset(Dataset):
    def __init__(self, path, config=None, tokenizer=None):
        self.config = config or Config()
        self.tokenizer = tokenizer or ByteTokenizer()
        self.rows = []
        path = Path(path)
        if not path.is_file():
            raise ValueError(f"arquivo de dataset não encontrado: {path}")
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSON inválido na linha {line_no}: {exc.msg}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"linha {line_no}: esperado objeto JSON")
            instruction, response = row.get("instruction"), row.get("response")
            if not isinstance(instruction, str) or not instruction.strip():
                raise ValueError(f"linha {line_no}: instruction vazia")
            if not isinstance(response, str) or not response.strip():
                raise ValueError(f"linha {line_no}: response vazia")
            prefix = "Usuário: " + instruction.strip() + "\nMikael AI: "
            prefix_ids = self.tokenizer.encode(prefix)
            answer_ids = self.tokenizer.encode(response.strip(), add_eos=True)
            full = [self.tokenizer.bos_id] + prefix_ids + answer_ids
            if len(full) < 2:
                raise ValueError(f"linha {line_no}: exemplo sem tokens")
            if len(full) > self.config.context_size + 1:
                raise ValueError(
                    f"linha {line_no}: exemplo tem {len(full)-1} tokens; "
                    f"limite atual é {self.config.context_size}. Reduza ou aumente contexto."
                )
            x = full[:-1]
            y = full[1:]
            # O primeiro token da resposta é prefix_length; y[i] prediz full[i+1].
            response_start = 1 + len(prefix_ids)
            first_answer_target_index = response_start - 1
            y[:first_answer_target_index] = [IGNORE_INDEX] * first_answer_target_index
            self.rows.append((torch.tensor(x, dtype=torch.long), torch.tensor(y, dtype=torch.long)))
        if not self.rows:
            raise ValueError(f"nenhum exemplo válido em {path}")

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        return self.rows[index]

def collate_sft(batch):
    max_len = max(x.numel() for x, _ in batch)
    xs, ys = [], []
    for x, y in batch:
        pad = max_len - x.numel()
        xs.append(torch.nn.functional.pad(x, (0, pad), value=0))
        ys.append(torch.nn.functional.pad(y, (0, pad), value=IGNORE_INDEX))
    return torch.stack(xs), torch.stack(ys)

def evaluate(model, loader, device):
    model.eval()
    losses = []
    with torch.inference_mode():
        for x, y in loader:
            _, loss = model(x.to(device), y.to(device))
            if loss is not None and torch.isfinite(loss):
                losses.append(loss.item())
    if not losses:
        raise RuntimeError("não foi possível calcular loss de validação")
    return sum(losses) / len(losses)

def train(args):
    if args.epochs < 1 or args.batch_size < 1 or args.lr <= 0:
        raise ValueError("epochs, batch-size e lr devem ser positivos")
    cfg = Config()
    train_ds = SFTDataset(args.train, cfg)
    val_ds = SFTDataset(args.val, cfg)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, collate_fn=collate_sft)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, collate_fn=collate_sft)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(args.seed)
    model = MikaelAI(cfg).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.1)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    step = 0
    for epoch in range(1, args.epochs + 1):
        model.train()
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad(set_to_none=True)
            _, loss = model(x, y)
            if loss is None or not torch.isfinite(loss):
                raise RuntimeError(f"loss inválida no passo {step+1}")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            step += 1
        val_loss = evaluate(model, val_loader, device)
        print(f"epoch={epoch} step={step} val_loss={val_loss:.4f}", flush=True)
        temp = out / "mikael-ai-v1-sft.pt.tmp"
        torch.save({
            "format": "mikael-ai-v1-sft",
            "epoch": epoch,
            "step": step,
            "config": cfg.__dict__,
            "model_state": model.state_dict(),
            "optimizer_state": optimizer.state_dict(),
        }, temp)
        temp.replace(out / "mikael-ai-v1-sft.pt")

def main():
    p = argparse.ArgumentParser(description="Instruction fine-tuning da Mikael AI V1")
    p.add_argument("--train", default="data/train.jsonl")
    p.add_argument("--val", default="data/val.jsonl")
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", default="checkpoints")
    train(p.parse_args())

if __name__ == "__main__":
    main()
