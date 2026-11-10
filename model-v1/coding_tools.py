"""Apoio seguro à programação: análise estática, sem executar código gerado."""
import ast
from dataclasses import dataclass

@dataclass
class CodeCheck:
    language: str
    valid: bool
    message: str

def check_code(code: str, language: str = "python") -> CodeCheck:
    if not isinstance(code, str) or not code.strip():
        return CodeCheck(language, False, "O código está vazio.")
    if len(code) > 50000:
        return CodeCheck(language, False, "O código excede o limite de 50.000 caracteres.")
    lang = language.strip().lower()
    if lang in ("python", "py"):
        try:
            ast.parse(code)
            return CodeCheck("python", True, "Sintaxe Python válida. O código não foi executado.")
        except SyntaxError as exc:
            return CodeCheck("python", False, f"Erro de sintaxe na linha {exc.lineno}: {exc.msg}")
    if lang in ("javascript", "js", "java", "kotlin", "html", "css", "c", "cpp"):
        return CodeCheck(lang, False, "Validação sintática completa ainda não disponível para esta linguagem.")
    return CodeCheck(lang, False, "Linguagem não suportada pelo verificador.")

def coding_instructions() -> str:
    return (
        "Você pode ajudar com programação simples. Antes de responder, identifique a linguagem "
        "e o objetivo. Entregue código em bloco com a linguagem indicada, explique como usar "
        "e avise quando algo não foi testado. Nunca diga que executou ou testou código se isso "
        "não aconteceu. Não invente resultados. Para Python, o host pode verificar sintaxe "
        "estaticamente; isso não prova que o programa funciona. Não execute código gerado."
    )
