export interface DocBrief {
  id: string;
  type: string;
  title: string;
  version: string;
  doc_no: string;
  effective_date: string;
  clause_count: number;
}

export interface Machine {
  product_no: string;
  model_code: string;
  model_name: string;
  spec: string;
  customer: string;
  contract_no: string;
  manufacture_date: string;
  delivery_date: string;
  warranty_months: number;
  warranty_end: string;
  serial_no: string;
  designer: string;
  team: string;
  workshop: string;
  usage_env: string;
  doc_count: number;
  issue_count: number;
  docs: DocBrief[];
}

export interface Issue {
  id: number;
  issue_no: string;
  repair_no: string;
  date: string;
  source: string;
  source_no: string;
  machine_id: string;
  customer: string;
  component: string;
  component_code: string;
  phenomenon: string;
  description: string;
  fault_type: string;
  cause: string;
  attribution_raw: string;
  cause_detail: string;
  team: string;
  designer: string;
  supplier: string;
  stage: string;
  severity: string;
  status: string;
  quality_status: string;
  after_sales_status: string;
  responsibility_status: string;
  source_channel: string;
  entry_method: string;
  after_sales_order: string;
  contact_name: string;
  contact_phone: string;
  department: string;
  report_time: string;
  handling: string;
  handling_method: string;
  resolved: boolean;
  recurrence_of: number | null;
  closed_at: string | null;
  cost: number;
  batch: string;
  duration_days: number | null;
  model_code: string;
  model_name: string;
  spec: string;
}

export interface Similar {
  issue: Issue;
  score: number;
  tier: string;
  reasons: string[];
}

export interface ChainStage {
  stage: string;
  status: 'ok' | 'missing';
  summary: string;
  refs: string[];
}

export interface Chain {
  stages: ChainStage[];
  completeness: number;
  total: number;
  gaps: string[];
}

export interface Hypothesis {
  cause: string;
  verify: string;
  evidence: string[];
  confidence: string;
}

export interface Suggestion {
  measure: string;
  score: number;
  history: string;
  evidence: string[];
}

export interface Analysis {
  issue: Issue;
  machine: Machine;
  similar: Similar[];
  chain: Chain;
  hypotheses: Hypothesis[];
  suggestions: Suggestion[];
  extraction: Record<string, { value: string; confidence: number }>;
  confidence: string;
  summary: {
    similar_count: number;
    high_count: number;
    chain_completeness: string;
  };
}

export type Verdict =
  | 'standard'
  | 'non_standard'
  | 'vague'
  | 'non_compliant'
  | 'not_mentioned'
  | 'conflict'
  | 'specified';

export interface AgreementDoc {
  id: string;
  type: string;
  type_code: string;
  title: string;
  doc_no: string;
  version: string;
  effective_date: string;
  status: string;
  pages: number;
  file_name: string;
  summary: string;
  clause_count: number;
  chunk_count?: number;
}

export interface Citation {
  cid: string;
  doc_id: string;
  doc_title: string;
  doc_no: string;
  doc_type: string;
  version: string;
  effective_date: string;
  clause_id: string;
  clause_no: string;
  section: string;
  page: number;
  text: string;
  verify_status: string;
}

export interface AnswerItem {
  object: string;
  verdict: Verdict;
  requirement: string;
  standard_value: string;
  difference: string;
  citations: string[];
  confidence: string;
  notes: string[];
}

export interface Conflict {
  object: string;
  description: string;
  citations: string[];
  suggested: string;
  need_confirm: boolean;
}

export interface Answer {
  ok: boolean;
  answer_type: string;
  question: string;
  machine?: Machine;
  document?: AgreementDoc;
  documents?: DocBrief[];
  conclusion: string;
  items: AnswerItem[];
  conflicts: Conflict[];
  gaps: string[];
  citations: Citation[];
  confidence: string;
  mode: string;
  llm?: {
    model?: string;
    elapsed_ms?: number;
    usage?: Record<string, number>;
    error?: string;
  };
  review_status: string;
}

export interface LlmStatus {
  configured: boolean;
  model: string;
  base_url: string;
  key_hint: string;
  env_file: string;
}

export interface IssueAskResult {
  ok: boolean;
  question: string;
  answer: string;
  related: Issue[];
  mode: 'llm' | 'rule' | string;
  model?: string;
  elapsed_ms?: number;
  usage?: Record<string, number>;
  issue_count: number;
  error?: string;
}

export interface AlertRule {
  id: string;
  name: string;
  fault_type: string;
  attribution: string;
  manufacturer: string;
  component: string;
  remark: string;
  window_days: number;
  threshold: number;
  level: string;
  enabled: boolean;
}

export interface AlertConfig {
  rules: AlertRule[];
}

export interface Dictionaries {
  machines: { product_no: string; label: string }[];
  components: string[];
  causes: string[];
  teams: string[];
  designers: string[];
  suppliers: string[];
  fault_types: string[];
  attributions: string[];
  alert_levels: string[];
  check_items: Record<string, { label: string; unit: string; compare: string }>;
}

export interface Alert {
  alert_no: string;
  alert_key: string;
  rule_id: string;
  rule_name: string;
  level: string;
  fault_type: string;
  attribution: string;
  manufacturer: string;
  component: string;
  remark: string;
  condition_text: string;
  window_days: number;
  threshold: number;
  pattern: string;
  metric: {
    n: number;
    machine_count: number;
    customer_count: number;
  };
  evidence: number[];
  machines: string[];
  customers: string[];
  teams: string[];
  designers: string[];
  suppliers: string[];
  possible_cause: string;
  suggested_action: string;
  status: string;
  owner: string;
  reason: string;
  note: string;
  ai_suggestion: string;
  ai_generated_at: string;
  ai_model: string;
  created_at: string;
  closed_at: string | null;
  evidence_detail: Issue[];
}

export interface CheckColumn {
  value: number | null;
  display: string;
  source: {
    doc_title: string;
    version: string;
    doc_no: string;
    clause_no: string;
    page: number;
    text: string;
    doc_id: string;
    clause_id: string;
    value: string;
  } | null;
}

export interface CheckResult {
  ok: boolean;
  machine: Machine;
  item: { label: string; unit: string; compare: string; code: string };
  measured: number;
  verdict: string;
  severity: string;
  reason: string;
  columns: {
    drawing: CheckColumn;
    agreement: CheckColumn;
    standard: CheckColumn;
  };
  checks: { drawing: boolean; agreement: boolean; standard: boolean };
  suggestions: string[];
  review_status: string;
}

export interface AgreementCheckResult {
  ok: boolean;
  document: AgreementDoc;
  item: { label: string; unit: string; code: string };
  measured: number;
  requirement: {
    value: number;
    display: string;
    source: {
      doc_title: string;
      version: string;
      doc_no: string;
      doc_id: string;
      clause_id: string;
      clause_no: string;
      page: number;
      text: string;
    };
  };
  verdict: string;
  severity: string;
  reason: string;
  suggestions: string[];
  review_status: string;
}

export interface Overview {
  kpis: {
    issue_total: number;
    issue_open: number;
    alert_pending: number;
    avg_close_days: number;
    chain_completeness: number;
    clause_total: number;
    machine_total: number;
  };
  trend: { month: string; count: number }[];
  by_cause: { name: string; count: number }[];
  top_components: { name: string; count: number }[];
  recent_issues: Issue[];
  alerts: Alert[];
  today: string;
}
