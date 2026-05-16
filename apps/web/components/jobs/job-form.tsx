"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormDescription,
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
import { ApiError, type JobRead } from "@/lib/api-types";
import { useCreateJob, useUpdateJob } from "@/lib/hooks";

import { EMPLOYMENT_OPTIONS } from "./status-badge";

const TiptapEditor = dynamic(() => import("./tiptap-editor"), {
  ssr: false,
  loading: () => (
    <div className="min-h-[176px] rounded-md border border-input bg-muted/30" />
  ),
});

const schema = z
  .object({
    title: z.string().trim().min(3, "Mínimo 3 caracteres"),
    employment_type: z.enum(["clt", "pj", "estagio", "temp", "freelancer"]),
    location: z.string().trim().optional(),
    salary_min: z
      .union([z.coerce.number().int().min(0), z.literal("")])
      .optional(),
    salary_max: z
      .union([z.coerce.number().int().min(0), z.literal("")])
      .optional(),
    description: z.string().optional(),
  })
  .refine(
    (d) =>
      d.salary_min === "" ||
      d.salary_max === "" ||
      d.salary_min == null ||
      d.salary_max == null ||
      Number(d.salary_max) >= Number(d.salary_min),
    { path: ["salary_max"], message: "Máximo deve ser ≥ mínimo" },
  );

type FormValues = z.input<typeof schema>;

export function JobForm({
  mode,
  job,
  onSaved,
}: {
  mode: "create" | "edit";
  job?: JobRead;
  onSaved?: (job: JobRead) => void;
}) {
  const router = useRouter();
  const createMut = useCreateJob();
  const updateMut = useUpdateJob(job?.id ?? "");

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: job?.title ?? "",
      employment_type: job?.employment_type ?? "clt",
      location: job?.location ?? "",
      salary_min: job?.salary_min ?? "",
      salary_max: job?.salary_max ?? "",
      description: job?.description ?? "",
    },
  });

  const submitting = createMut.isPending || updateMut.isPending;

  async function onSubmit(values: FormValues) {
    const payload = {
      title: values.title.trim(),
      employment_type: values.employment_type,
      location: values.location?.trim() || null,
      salary_min:
        values.salary_min === "" || values.salary_min == null
          ? null
          : Number(values.salary_min),
      salary_max:
        values.salary_max === "" || values.salary_max == null
          ? null
          : Number(values.salary_max),
      description: values.description || null,
    };

    try {
      if (mode === "create") {
        const created = await createMut.mutateAsync(payload);
        toast.success("Vaga criada");
        if (onSaved) onSaved(created);
        else router.push(`/jobs/${created.id}`);
      } else {
        const updated = await updateMut.mutateAsync(payload);
        toast.success("Vaga atualizada");
        onSaved?.(updated);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        const fields = err.fieldErrors();
        for (const [name, msg] of Object.entries(fields)) {
          form.setError(name as keyof FormValues, { message: msg });
        }
        if (Object.keys(fields).length === 0)
          toast.error("Dados inválidos. Revise o formulário.");
        return;
      }
      // 409 e demais já viram toast no MutationCache global.
    }
  }

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        className="space-y-5"
        noValidate
      >
        <FormField
          control={form.control}
          name="title"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Título *</FormLabel>
              <FormControl>
                <Input placeholder="Pessoa Vendedora Loja Tatuapé" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="grid gap-5 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="employment_type"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Tipo de contratação</FormLabel>
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
                    {EMPLOYMENT_OPTIONS.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="location"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Localização</FormLabel>
                <FormControl>
                  <Input placeholder="São Paulo, SP" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="salary_min"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Salário mínimo (R$)</FormLabel>
                <FormControl>
                  <Input
                    type="number"
                    min={0}
                    placeholder="2500"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="salary_max"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Salário máximo (R$)</FormLabel>
                <FormControl>
                  <Input
                    type="number"
                    min={0}
                    placeholder="3500"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Descrição</FormLabel>
              <FormControl>
                <TiptapEditor
                  value={field.value ?? ""}
                  onChange={field.onChange}
                />
              </FormControl>
              <FormDescription>
                Negrito, itálico, listas e links.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="flex justify-end gap-2">
          {onSaved && (
            <Button
              type="button"
              variant="outline"
              onClick={() => router.back()}
              disabled={submitting}
            >
              Cancelar
            </Button>
          )}
          <Button type="submit" disabled={submitting}>
            {submitting
              ? "Salvando…"
              : mode === "create"
                ? "Criar vaga"
                : "Salvar alterações"}
          </Button>
        </div>
      </form>
    </Form>
  );
}
