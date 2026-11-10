"""Valida exemplos supervisionados e prepara texto para o treino next-token atual."""
import argparse
import json
from pathlib import Path

def load_jsonl(path: Path):
    examples = []
    errors = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"linha {line_no}: JSON inválido ({exc.msg})")
            continue
        if not isinstance(item, dict):
            errors.append(f"linha {line_no}: cada exemplo precisa ser um objeto")
            continue
        instruction, response = item.get("instruction"), item.get("response")
        if not isinstance(instruction, str) or not instruction.strip():
            errors.append(f"linha {line_no}: instruction ausente ou vazia")
            continue
        if not isinstance(response, str) or not response.strip():
            errors.append(f"linha {line_no}: response ausente ou vazia")
            continue
        if len(instruction) > 10000 or len(response) > 20000:
            errors.append(f"linha {line_no}: exemplo excede o limite de tamanho")
            continue
        examples.append((instruction.strip(), response.strip()))
    return examples, errors

def prepare(source: Path, output: Path):
    examples, errors = load_jsonl(source)
    if errors:
        raise ValueError("\n".join(errors[:30]))
    if not examples:
        raise ValueError("Nenhum exemplo válido encontrado.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for instruction, response in examples:
            handle.write(f"Usuário: {instruction}\nMikael AI: {response}\n\n")
    return len(examples)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    count = prepare(args.source, args.output)
    print(f"{count} exemplos preparados em {args.output}")

if __name__ == "__main__":
    main()
