export type Lang = { code: string; name: string };

export interface Budget {
  cap_usd: number;
  used_usd: number;
  remaining_usd: number;
  blocked: boolean;
}

export interface PrivacyEngine {
  mode: "glimmer" | "rules";
  label: string;
  model: string | null;
}

export interface Health {
  status: "ok";
  demo_mode: boolean;
  privacy_engine: PrivacyEngine;
  budget: Budget;
  models: Record<string, string>;
}

export interface Sample {
  id: string;
  title: string;
  description: string;
  suggested_request: string;
}

export interface DocumentInfo {
  document_id: string;
  filename: string;
  page_count: number;
  original_pdf_url: string;
}

export type StepStatus = "pending" | "running" | "done" | "error" | "waiting";

export interface Step {
  id: string;
  tool: string;
  title: string;
  status: StepStatus;
  model: string | null;
  location: "local" | "cloud";
  replayed: boolean;
  cost_usd: number;
  detail: string | null;
}

export interface Field {
  name: string;
  label: string;
  value: string;
  confidence: number;
  needs_review: boolean;
  note: string | null;
  kind: "text" | "multiline" | "checkbox";
  contains_pii: boolean;
  page: number;
  rect: [number, number, number, number] | null;
}

export interface Deadline {
  id?: number;
  title: string;
  date: string;
  description: string;
  task_id?: string | null;
  days_remaining?: number;
}

export interface Explanation {
  summary: string;
  what_it_means: string;
  steps: string[];
  warnings: string[];
}

export interface Plan {
  document_type: string;
  intent: string;
  actions: { tool: string; reason: string }[];
}

export interface Verification {
  overall_confidence: number;
  summary: string;
  issues: string[];
}

export type TaskStatus = "running" | "awaiting_confirmation" | "confirmed" | "error";

export interface Task {
  task_id: string;
  document_id: string;
  status: TaskStatus;
  error: string | null;
  request_text: string;
  user_language: Lang;
  document_type: string;
  document_title: string;
  page_count: number;
  explanation: Explanation | null;
  plan: Plan | null;
  deadlines: Deadline[];
  fields: Field[];
  letter: { subject: string; body: string } | null;
  verification: Verification | null;
  steps: Step[];
  cost_usd: number;
  original_pdf_url: string;
  filled_pdf_url: string | null;
  final_pdf_url: string | null;
  letter_pdf_url: string | null;
}

export interface PrivacyItem {
  placeholder: string;
  type: string;
  type_label: string;
  original: string;
}

export interface CloudRequest {
  model: string;
  task: string;
  replayed: boolean;
  chars: number;
  raw_pii_found: number;
}

export interface Privacy {
  engine: PrivacyEngine;
  items: PrivacyItem[];
  original_excerpt: string;
  sanitized_excerpt: string;
  cloud_requests: CloudRequest[];
  raw_pii_sent: number;
  protected_count: number;
}

export interface UsageCall {
  model: string;
  task: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  replayed: boolean;
  ts: string;
}

export interface Usage extends Budget {
  demo_mode: boolean;
  calls: UsageCall[];
}

export interface Transcription {
  text: string;
  language: Lang | null;
  model: string;
  replayed: boolean;
  cost_usd: number;
}

export type AgentEvent =
  | { type: "step"; step: Step; task_cost_usd: number }
  | { type: "done"; task: Task }
  | { type: "error"; message: string };
