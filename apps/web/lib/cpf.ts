/**
 * Espelho client do algoritmo de `apps/api/src/utils/cpf.py` — mesmas regras:
 * 11 dígitos, rejeita sequência repetida, dois dígitos verificadores.
 * Só pré-valida no browser; o backend continua sendo a fonte da verdade.
 */
export function onlyDigits(value: string | null | undefined): string {
  return (value ?? "").replace(/\D/g, "");
}

function checkDigit(digits: string, weightsStart: number): number {
  let total = 0;
  for (let i = 0; i < digits.length; i++) {
    total += Number(digits[i]) * (weightsStart - i);
  }
  const rest = total % 11;
  return rest < 2 ? 0 : 11 - rest;
}

export function isValidCpf(raw: string | null | undefined): boolean {
  const cpf = onlyDigits(raw);
  if (cpf.length !== 11) return false;
  if (cpf === cpf[0]!.repeat(11)) return false;
  return (
    checkDigit(cpf.slice(0, 9), 10) === Number(cpf[9]) &&
    checkDigit(cpf.slice(0, 10), 11) === Number(cpf[10])
  );
}

/** Máscara incremental 000.000.000-00 enquanto digita. */
export function maskCpfInput(value: string): string {
  const d = onlyDigits(value).slice(0, 11);
  const parts = [
    d.slice(0, 3),
    d.slice(3, 6),
    d.slice(6, 9),
    d.slice(9, 11),
  ].filter(Boolean);
  if (d.length <= 3) return parts[0] ?? "";
  if (d.length <= 6) return `${parts[0]}.${parts[1]}`;
  if (d.length <= 9) return `${parts[0]}.${parts[1]}.${parts[2]}`;
  return `${parts[0]}.${parts[1]}.${parts[2]}-${parts[3]}`;
}
