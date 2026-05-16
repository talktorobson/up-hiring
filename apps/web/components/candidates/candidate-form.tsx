"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, type CandidateRead } from "@/lib/api-types";
import { isValidCpf, maskCpfInput, onlyDigits } from "@/lib/cpf";
import { useCreateCandidate, useUpdateCandidate } from "@/lib/hooks";

const SOURCES = [
  { value: "indicação", label: "Indicação" },
  { value: "manual", label: "Manual" },
  { value: "outro", label: "Outro" },
];

const schema = z.object({
  full_name: z.string().trim().min(2, "Mínimo 2 caracteres"),
  email: z.string().trim().email("E-mail inválido"),
  phone: z.string().trim().optional(),
  cpf: z
    .string()
    .optional()
    .refine((v) => !v || isValidCpf(v), "CPF inválido"),
  linkedin_url: z
    .string()
    .trim()
    .url("URL inválida")
    .optional()
    .or(z.literal("")),
  source: z.string().optional(),
  notes: z.string().optional(),
});

type Values = z.infer<typeof schema>;

export function CandidateForm({
  mode,
  candidate,
  onSaved,
  onDuplicate,
}: {
  mode: "create" | "edit";
  candidate?: CandidateRead;
  onSaved: (c: CandidateRead) => void;
  onDuplicate?: (err: ApiError) => void;
}) {
  const createMut = useCreateCandidate();
  const updateMut = useUpdateCandidate(candidate?.id ?? "");
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      full_name: candidate?.full_name ?? "",
      email: candidate?.email ?? "",
      phone: candidate?.phone ?? "",
      cpf: candidate?.cpf ? maskCpfInput(candidate.cpf) : "",
      linkedin_url: candidate?.linkedin_url ?? "",
      source: candidate?.source ?? "manual",
      notes: candidate?.notes ?? "",
    },
  });

  const submitting = createMut.isPending || updateMut.isPending;

  async function onSubmit(values: Values) {
    const payload = {
      full_name: values.full_name.trim(),
      email: values.email.trim(),
      phone: values.phone?.trim() || null,
      cpf: values.cpf ? onlyDigits(values.cpf) : null,
      linkedin_url: values.linkedin_url?.trim() || null,
      source: values.source || null,
      notes: values.notes?.trim() || null,
    };
    try {
      const saved =
        mode === "create"
          ? await createMut.mutateAsync(payload)
          : await updateMut.mutateAsync(payload);
      toast.success(
        mode === "create" ? "Candidato criado" : "Candidato atualizado",
      );
      onSaved(saved);
    } catch (err) {
      if (!(err instanceof ApiError)) return;
      if (err.status === 422 && err.code === "invalid_cpf") {
        form.setError("cpf", { message: "CPF inválido (servidor)" });
        return;
      }
      if (
        err.status === 409 &&
        (err.code === "duplicate_cpf" || err.code === "duplicate_email")
      ) {
        onDuplicate?.(err);
        if (!onDuplicate)
          toast.error(
            err.code === "duplicate_cpf"
              ? "Já existe candidato com esse CPF."
              : "Já existe candidato com esse e-mail.",
          );
        return;
      }
    }
  }

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        className="space-y-4"
        noValidate
      >
        <FormField
          control={form.control}
          name="full_name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Nome completo *</FormLabel>
              <FormControl>
                <Input placeholder="Joana Silva" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>E-mail *</FormLabel>
                <FormControl>
                  <Input
                    type="email"
                    placeholder="joana@email.com"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="phone"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Telefone</FormLabel>
                <FormControl>
                  <Input placeholder="(11) 99999-9999" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="cpf"
            render={({ field }) => (
              <FormItem>
                <FormLabel>CPF</FormLabel>
                <FormControl>
                  <Input
                    placeholder="000.000.000-00"
                    value={field.value ?? ""}
                    onChange={(e) =>
                      field.onChange(maskCpfInput(e.target.value))
                    }
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="source"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Fonte</FormLabel>
                <Select
                  onValueChange={field.onChange}
                  defaultValue={field.value}
                >
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {SOURCES.map((s) => (
                      <SelectItem key={s.value} value={s.value}>
                        {s.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
        <FormField
          control={form.control}
          name="linkedin_url"
          render={({ field }) => (
            <FormItem>
              <FormLabel>LinkedIn</FormLabel>
              <FormControl>
                <Input
                  placeholder="https://linkedin.com/in/…"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="notes"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Notas</FormLabel>
              <FormControl>
                <Textarea rows={3} {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <div className="flex justify-end">
          <Button type="submit" disabled={submitting}>
            {submitting
              ? "Salvando…"
              : mode === "create"
                ? "Criar candidato"
                : "Salvar"}
          </Button>
        </div>
      </form>
    </Form>
  );
}
