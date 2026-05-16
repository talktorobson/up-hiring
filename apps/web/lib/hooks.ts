"use client";

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import type {
  ApplicationCreate,
  ApplicationListParams,
  ApplicationStageMove,
  CandidateCreate,
  CandidateListParams,
  CandidateUpdate,
  JobCreate,
  JobListParams,
  JobStatus,
  JobUpdate,
} from "./api-types";
import { useApiClient } from "./use-api-client";

export const qk = {
  me: () => ["me"] as const,
  jobs: (params?: JobListParams) => ["jobs", params ?? {}] as const,
  job: (id: string) => ["job", id] as const,
  pipeline: (jobId: string) => ["pipeline", jobId] as const,
  candidates: (params?: CandidateListParams) =>
    ["candidates", params ?? {}] as const,
  candidate: (id: string) => ["candidate", id] as const,
  applications: (params?: ApplicationListParams) =>
    ["applications", params ?? {}] as const,
  application: (id: string) => ["application", id] as const,
};

export function useMe() {
  const api = useApiClient();
  return useQuery({ queryKey: qk.me(), queryFn: () => api.me() });
}

export function useJobsInfinite(status?: JobStatus, limit = 25) {
  const api = useApiClient();
  return useInfiniteQuery({
    queryKey: qk.jobs({ status, limit }),
    queryFn: ({ pageParam }) =>
      api.jobs.list({ status, limit, cursor: pageParam || undefined }),
    initialPageParam: "",
    getNextPageParam: (last) => (last.has_more ? last.next_cursor : undefined),
  });
}

export function useJob(id: string) {
  const api = useApiClient();
  return useQuery({ queryKey: qk.job(id), queryFn: () => api.jobs.get(id) });
}

export function usePipeline(jobId: string) {
  const api = useApiClient();
  return useQuery({
    queryKey: qk.pipeline(jobId),
    queryFn: () => api.jobs.pipeline(jobId),
  });
}

export function useCreateJob() {
  const api = useApiClient();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: JobCreate) => api.jobs.create(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

export function useUpdateJob(id: string) {
  const api = useApiClient();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: JobUpdate) => api.jobs.update(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.job(id) });
      qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function useDeleteJob() {
  const api = useApiClient();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.jobs.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

export function useCandidatesInfinite(q?: string, limit = 25) {
  const api = useApiClient();
  return useInfiniteQuery({
    queryKey: qk.candidates({ q, limit }),
    queryFn: ({ pageParam }) =>
      api.candidates.list({ q, limit, cursor: pageParam || undefined }),
    initialPageParam: "",
    getNextPageParam: (last) => (last.has_more ? last.next_cursor : undefined),
  });
}

export function useCandidate(id: string) {
  const api = useApiClient();
  return useQuery({
    queryKey: qk.candidate(id),
    queryFn: () => api.candidates.get(id),
  });
}

export function useCreateCandidate() {
  const api = useApiClient();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CandidateCreate) => api.candidates.create(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["candidates"] }),
  });
}

export function useUpdateCandidate(id: string) {
  const api = useApiClient();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CandidateUpdate) => api.candidates.update(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.candidate(id) });
      qc.invalidateQueries({ queryKey: ["candidates"] });
    },
  });
}

export function useApplications(params: ApplicationListParams) {
  const api = useApiClient();
  return useQuery({
    queryKey: qk.applications(params),
    queryFn: () => api.applications.list(params),
  });
}

export function useApplication(id: string, enabled = true) {
  const api = useApiClient();
  return useQuery({
    queryKey: qk.application(id),
    queryFn: () => api.applications.get(id),
    enabled: enabled && !!id,
  });
}

export function useCreateApplication() {
  const api = useApiClient();
  return useMutation({
    mutationFn: (payload: ApplicationCreate) =>
      api.applications.create(payload),
  });
}

export function useMoveStage(jobId: string) {
  const api = useApiClient();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { applicationId: string } & ApplicationStageMove) =>
      api.applications.moveStage(vars.applicationId, {
        target_stage_id: vars.target_stage_id,
      }),
    onSettled: () =>
      qc.invalidateQueries({ queryKey: qk.pipeline(jobId) }),
  });
}
