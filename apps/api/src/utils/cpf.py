"""Validação de CPF — algoritmo oficial dos dígitos verificadores.

Regras:
1. 11 dígitos.
2. Sequências repetidas (`11111111111`, etc.) são inválidas — mesmo passando
   no algoritmo, são sentinelas comuns.
3. Os 2 últimos dígitos são checksum dos 9 primeiros, em duas passadas:
   - 1º DV: soma dos 9 dígitos × pesos 10..2, mod 11; resultado < 2 → 0,
     senão `11 - resultado`.
   - 2º DV: soma dos 10 dígitos × pesos 11..2, mesma regra.
"""
from __future__ import annotations

import re


def normalize(cpf: str | None) -> str | None:
    """Remove pontuação e espaços. Retorna 11 dígitos crus ou None."""
    if cpf is None:
        return None
    digits = re.sub(r"\D", "", cpf)
    if not digits:
        return None
    return digits


def _check_digit(digits: str, weights_start: int) -> int:
    total = sum(int(d) * (weights_start - i) for i, d in enumerate(digits))
    rest = total % 11
    return 0 if rest < 2 else 11 - rest


def is_valid(cpf: str) -> bool:
    """Aceita só 11 dígitos crus (use `normalize` antes)."""
    if not cpf or len(cpf) != 11 or not cpf.isdigit():
        return False
    if cpf == cpf[0] * 11:
        return False
    return (
        _check_digit(cpf[:9], 10) == int(cpf[9])
        and _check_digit(cpf[:10], 11) == int(cpf[10])
    )
