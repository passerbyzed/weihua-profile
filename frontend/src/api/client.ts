import axios from 'axios';
import type {
  AgreementCheckResult,
  AgreementDoc,
  Alert,
  AlertConfig,
  Analysis,
  Answer,
  CheckResult,
  Dictionaries,
  Issue,
  IssueAskResult,
  LlmStatus,
  Machine,
  Overview,
} from '../types';

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
});

export const getOverview = async (): Promise<Overview> => {
  const { data } = await api.get<Overview>('/overview');
  return data;
};

export const listMachines = async (): Promise<Machine[]> => {
  const { data } = await api.get<Machine[]>('/machines');
  return data;
};

export const listIssues = async (params?: {
  search?: string;
  status?: string;
  machine_id?: string;
}): Promise<Issue[]> => {
  const { data } = await api.get<Issue[]>('/issues', { params });
  return data;
};

export const getIssueAnalysis = async (id: number): Promise<Analysis> => {
  const { data } = await api.get<Analysis>(`/issues/${id}`);
  return data;
};

export const listAlerts = async (): Promise<Alert[]> => {
  const { data } = await api.get<Alert[]>('/alerts');
  return data;
};

export const updateAlert = async (
  alertNo: string,
  action: 'confirm' | 'dismiss' | 'rectify',
  reason = ''
): Promise<{ ok: boolean; status: string }> => {
  const { data } = await api.post(`/alerts/${alertNo}/action`, { action, reason });
  return data;
};

export const suggestAlert = async (
  alertNo: string
): Promise<{ ok: boolean; suggestion: string; mode: string; model?: string; elapsed_ms?: number; error?: string }> => {
  const { data } = await api.post(`/alerts/${alertNo}/suggest`, {}, { timeout: 120000 });
  return data;
};

export const saveAlertNote = async (
  alertNo: string,
  note: string
): Promise<{ ok: boolean; note: string }> => {
  const { data } = await api.post(`/alerts/${alertNo}/note`, { note });
  return data;
};

export const askKb = async (docId: string, question: string): Promise<Answer> => {
  const { data } = await api.post<Answer>(
    '/kb/ask',
    { doc_id: docId, question },
    { timeout: 120000 }
  );
  return data;
};

export const getAgreements = async (): Promise<AgreementDoc[]> => {
  const { data } = await api.get<AgreementDoc[]>('/kb/agreements');
  return data;
};

export const getAgreement = async (docId: string): Promise<AgreementDoc> => {
  const { data } = await api.get<AgreementDoc>('/kb/agreement', { params: { doc_id: docId } });
  return data;
};

export const checkKb = async (
  docId: string,
  itemCode: string,
  measured: number
): Promise<AgreementCheckResult> => {
  const { data } = await api.post<AgreementCheckResult>('/kb/check', {
    doc_id: docId,
    item_code: itemCode,
    measured,
  });
  return data;
};

export const checkNonconformance = async (
  machineId: string,
  itemCode: string,
  measured: number
): Promise<CheckResult> => {
  const { data } = await api.post<CheckResult>('/kb/check', {
    machine_id: machineId,
    item_code: itemCode,
    measured,
  });
  return data;
};

export const reviewAnswer = async (
  documentId: string,
  question: string,
  action: 'confirm' | 'dispute',
  comment = ''
): Promise<{ ok: boolean; status: string }> => {
  const { data } = await api.post('/kb/review', {
    document_id: documentId,
    question,
    action,
    comment,
  });
  return data;
};

export const resetDemo = async (): Promise<{ ok: boolean }> => {
  const { data } = await api.post('/demo/reset', {});
  return data;
};

export const getLlmStatus = async (): Promise<LlmStatus> => {
  const { data } = await api.get<LlmStatus>('/llm/status');
  return data;
};

export const askIssues = async (
  question: string,
  machineId = ''
): Promise<IssueAskResult> => {
  const { data } = await api.post<IssueAskResult>(
    '/issues/ask',
    { question, machine_id: machineId },
    { timeout: 120000 }
  );
  return data;
};

export type ReportFormat = 'excel' | 'pdf' | 'doc';

export const generateIssueReport = async (
  question: string,
  format: ReportFormat
): Promise<{ blob: Blob; filename: string }> => {
  const response = await api.post('/issues/report', { question, format }, {
    responseType: 'blob',
    timeout: 120000,
  });
  const disposition = String(response.headers['content-disposition'] || '');
  const match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  let filename = `售后质量问题统计报表.${format === 'excel' ? 'xlsx' : format === 'pdf' ? 'pdf' : 'docx'}`;
  if (match) {
    try {
      filename = decodeURIComponent(match[1]);
    } catch {
      // keep fallback filename
    }
  }
  return { blob: response.data as Blob, filename };
};

export const getAlertConfig = async (): Promise<AlertConfig> => {
  const { data } = await api.get<AlertConfig>('/alert-config');
  return data;
};

export const getDictionaries = async (): Promise<Dictionaries> => {
  const { data } = await api.get<Dictionaries>('/dictionaries');
  return data;
};

export const saveAlertConfig = async (config: AlertConfig): Promise<AlertConfig> => {
  const { data } = await api.post<AlertConfig>('/alert-config', config);
  return data;
};

export function getErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { message?: string } } })?.response?.data
    ?.message;
  if (detail) return detail;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}
