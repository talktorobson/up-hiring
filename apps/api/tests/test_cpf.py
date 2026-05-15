"""CPF normalize + is_valid."""
import pytest

from src.utils.cpf import is_valid, normalize


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("123.456.789-09", "12345678909"),
        ("12345678909", "12345678909"),
        ("  123 456 789-09 ", "12345678909"),
        ("", None),
        (None, None),
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected


@pytest.mark.parametrize(
    "cpf",
    [
        # CPFs gerados via algoritmo. Não usar dados pessoais reais.
        "11144477735",
        "52998224725",
    ],
)
def test_is_valid_true(cpf):
    assert is_valid(cpf)


@pytest.mark.parametrize(
    "cpf",
    [
        "00000000000",
        "11111111111",
        "99999999999",  # sequências repetidas
        "12345678900",  # checksum errado
        "123456789",  # curto demais
        "123456789012",  # longo demais
        "1234567890a",  # tem letra
        "",
    ],
)
def test_is_valid_false(cpf):
    assert not is_valid(cpf)
