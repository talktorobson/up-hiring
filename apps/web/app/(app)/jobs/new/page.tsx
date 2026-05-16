import { JobForm } from "@/components/jobs/job-form";

export default function NewJobPage() {
  return (
    <div className="mx-auto max-w-2xl p-6 lg:p-8">
      <h1 className="mb-6 text-2xl font-bold tracking-tight">Nova vaga</h1>
      <JobForm mode="create" />
    </div>
  );
}
