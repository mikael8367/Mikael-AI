"""Treinamento supervisionado SFT da Mikael AI V1.

Treina pesos aleatórios com exemplos instruction/response, mede validação,
salva o melhor checkpoint e avalia um conjunto de teste separado.
"""
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
            x, y = full[:-1], full[1:]
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
    losses, token_count = [], 0
    with torch.inference_mode():
        for x, y in loader:
            y_device = y.to(device)
            valid = int((y_device != IGNORE_INDEX).sum().item())
            if not valid:
                continue
            _, loss = model(x.to(device), y_device)
            if loss is not None and torch.isfinite(loss):
                losses.append((loss.item(), valid))
                token_count += valid
    if not losses or not token_count:
        raise RuntimeError("não foi possível calcular loss de avaliação")
    return sum(loss * count for loss, count in losses) / token_count

def save_checkpoint(path, model, optimizer, cfg, epoch, step, val_loss, seed):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    state = {
        "format": "mikael-ai-v1-sft",
        "epoch": epoch,
        "step": step,
        "val_loss": val_loss,
        "seed": seed,
        "config": cfg.__dict__,
        "model_state": model.state_dict(),
        "optimizer_state": optimizer.state_dict(),
    }
    torch.save(state, temp)
    temp.replace(path)

def train(args):
    if args.epochs < 1 or args.batch_size < 1 or args.lr <= 0 or args.patience < 1:
        raise ValueError("epochs, batch-size, lr e patience devem ser positivos")
    if args.min_delta < 0:
        raise ValueError("min-delta não pode ser negativo")
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    cfg = Config()
    train_ds = SFTDataset(args.train, cfg)
    val_ds = SFTDataset(args.val, cfg)
    test_ds = SFTDataset(args.test, cfg) if args.test else None
    generator = torch.Generator().manual_seed(args.seed)
    train_loader = DataLoader(
        train_ds, batch_size=args.batch_size, shuffle=True,
        collate_fn=collate_sft, generator=generator
    )
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, collate_fn=collate_sft)
    test_loader = (
        DataLoader(test_ds, batch_size=args.batch_size, shuffle=False, collate_fn=collate_sft)
        if test_ds else None
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = MikaelAI(cfg).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.1)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    best_loss, best_epoch, step, stale = float("inf"), 0, 0, 0
    history = []
    best_path = out / "mikael-ai-v1-sft.pt"

    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss, total_tokens = 0.0, 0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            valid_tokens = int((y != IGNORE_INDEX).sum().item())
            optimizer.zero_grad(set_to_none=True)
            _, loss = model(x, y)
            if loss is None or not torch.isfinite(loss):
                raise RuntimeError(f"loss inválida no passo {step + 1}")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            step += 1
            total_loss += loss.item() * valid_tokens
            total_tokens += valid_tokens

        val_loss = evaluate(model, val_loader, device)
        train_loss = total_loss / max(total_tokens, 1)
        history.append({
            "epoch": epoch, "step": step,
            "train_loss": train_loss, "val_loss": val_loss,
        })
        improved = val_loss < best_loss - args.min_delta
        if improved:
            best_loss, best_epoch, stale = val_loss, epoch, 0
            save_checkpoint(best_path, model, optimizer, cfg, epoch, step, val_loss, args.seed)
        else:
            stale += 1
        print(
            f"epoch={epoch} step={step} train_loss={train_loss:.4f} "
            f"val_loss={val_loss:.4f} best={best_loss:.4f} "
            f"device={device} improved={improved}",
            flush=True,
        )
        (out / "training_report.json").write_text(
            json.dumps({
                "model": "Mikael AI V1",
                "task": "programming_sft",
                "device": str(device),
                "train_examples": len(train_ds),
                "validation_examples": len(val_ds),
                "test_examples": len(test_ds) if test_ds else 0,
                "best_epoch": best_epoch,
                "best_val_loss": best_loss,
                "steps": step,
                "history": history,
                "warning": "Loss menor não garante código correto; revise e teste as respostas.",
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if stale >= args.patience:
            print(f"early_stopping epoch={epoch} best_epoch={best_epoch}", flush=True)
            break

    if best_epoch == 0:
        raise RuntimeError("nenhum checkpoint válido foi salvo")
    best_state = torch.load(best_path, map_location=device, weights_only=True)
    model.load_state_dict(best_state["model_state"], strict=True)
    if test_loader:
        test_loss = evaluate(model, test_loader, device)
        print(f"test_loss={test_loss:.4f} (checkpoint da melhor validação)", flush=True)
        report_path = out / "training_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["test_loss"] = test_loss
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(description="SFT de programação da Mikael AI V1")
    parser.add_argument("--train", default="data/programming_train.jsonl")
    parser.add_argument("--val", default="data/programming_val.jsonl")
    parser.add_argument("--test", default="data/programming_test.jsonl")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--patience", type=int, default=7)
    parser.add_argument("--min-delta", type=float, default=0.0001)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="checkpoints/programming")
    train(parser.parse_args())

if __name__ == "__main__":
    main()
