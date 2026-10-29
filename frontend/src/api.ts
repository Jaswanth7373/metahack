import type {
  Deadline,
  DocumentInfo,
  Health,
  Privacy,
  Sample,
  Task,
  Transcription,
  Usage,
} from "./types";

export const MSG = {
  network: "AI service temporarily unavailable. You can retry or switch to Demo Mode.",
  unreadable: "We couldn't read this document clearly. Please upload a clearer image.",
  placement: "Some fields could not be placed automatically. Please review them manually.",
  generic: "Something went wrong. Please try again.",
};

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function friendlyFor(status: number, path: string): string {
  if (status === 0 || status >= 500) return MSG.network;
  if (status === 402 || status === 429) return MSG.network;
  if (path.includes("/documents") && (status === 400 || status === 422)) return MSG.unreadable;
  if (path.includes("/fields")) return MSG.placement;
  return MSG.generic;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError(MSG.network, 0);
  }
  if (!res.ok) {
    let detail: string | null = null;
    try {
      const body = await res.json();
      if (body && typeof body.detail === "string") detail = body.detail;
      else if (body && Array.isArray(body.detail)) detail = null; // pydantic validation list: keep friendly message
    } catch {
      /* not JSON */
    }
    throw new ApiError(detail ?? friendlyFor(res.status, path), res.status);
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") ?? "";
  if (!ct.includes("application/json")) return undefined as T;
  return (await res.json()) as T;
}

function json(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export const api = {
  health: () => request<Health>("/api/health"),
  usage: () => request<Usage>("/api/usage"),
  samples: () => request<Sample[]>("/api/samples"),
  fromSample: (sample_id: string) =>
    request<DocumentInfo>("/api/documents/from-sample", json("POST", { sample_id })),
  upload: (file: File) => {
    const fd = new FormData();
    fd.append("file", file, file.name);
    return request<DocumentInfo>("/api/documents/upload", { method: "POST", body: fd });
  },
  transcribe: (wav: Blob, language: string) => {
    const fd = new FormData();
    fd.append("audio", wav, "request.wav");
    if (language && language !== "auto") fd.append("language", language);
    return request<Transcription>("/api/voice/transcribe", { method: "POST", body: fd });
  },
  runAgent: (document_id: string, request_text: string, language: string) =>
    request<{ task_id: string }>("/api/agent/run", json("POST", { document_id, request_text, language })),
  task: (id: string) => request<Task>(`/api/tasks/${encodeURIComponent(id)}`),
  saveFields: (id: string, values: Record<string, string>) =>
    request<Task>(`/api/tasks/${encodeURIComponent(id)}/fields`, json("PATCH", { values })),
  confirm: (id: string, letter_body?: string) =>
    request<Task>(`/api/tasks/${encodeURIComponent(id)}/confirm`, json("POST", { confirmed: true, letter_body })),
  privacy: (id: string) => request<Privacy>(`/api/privacy/${encodeURIComponent(id)}`),
  deadlines: () => request<Deadline[]>("/api/deadlines"),
  addDeadline: (d: { title: string; date: string; description: string }) =>
    request<Deadline>("/api/deadlines", json("POST", d)),
  deleteDeadline: (id: number) => request<void>(`/api/deadlines/${id}`, { method: "DELETE" }),
};

export const urls = {
  originalPage: (documentId: string, n: number) =>
    `/api/documents/${encodeURIComponent(documentId)}/pages/${n}.png`,
  filledPage: (taskId: string, n: number, v?: number) =>
    `/api/tasks/${encodeURIComponent(taskId)}/filled/pages/${n}.png${v ? `?v=${v}` : ""}`,
  events: (taskId: string) => `/api/agent/events/${encodeURIComponent(taskId)}`,
  deadlineIcs: (id: number) => `/api/deadlines/${id}/ics`,
  exportIcs: "/api/deadlines/export.ics",
};

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error && e.message) return e.message;
  return MSG.generic;
}
