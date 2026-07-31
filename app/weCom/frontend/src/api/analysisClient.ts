import type {
  AnalysisCustomerChat,
  AnalysisQuestionsParams,
  AnalysisSummary,
  AnalysisSummaryParams,
  PagedResult,
  QuestionCategory,
  ResponseGroupStat,
  ResponseGroupsParams
} from './analysisTypes';

const token = import.meta.env.VITE_INTERNAL_ADMIN_TOKEN || 'dev-admin-token';

async function getJson<T>(path: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(path, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!response.ok) return fallback;
    return (await response.json()) as T;
  } catch {
    return fallback;
  }
}

function dateParams(params: { startDate: string; endDate: string }) {
  return new URLSearchParams({
    start_date: params.startDate,
    end_date: params.endDate
  });
}

export async function fetchObservedEmployeeSummary(
  userid: string,
  params: AnalysisSummaryParams
): Promise<AnalysisSummary> {
  const query = dateParams(params);
  query.set('conversation_type', params.conversationType);
  return getJson<AnalysisSummary>(
    `/api/analysis/observed-employees/${userid}/summary?${query.toString()}`,
    emptySummary()
  );
}

export async function fetchCustomerChatSummary(
  observerUserid: string,
  roomid: string,
  params: Omit<AnalysisSummaryParams, 'conversationType'>
): Promise<AnalysisSummary> {
  const query = dateParams(params);
  query.set('observer_userid', observerUserid);
  return getJson<AnalysisSummary>(
    `/api/analysis/customer-chats/${roomid}/summary?${query.toString()}`,
    emptySummary()
  );
}

export async function fetchQuestionCategories(): Promise<{ items: QuestionCategory[] }> {
  return getJson<{ items: QuestionCategory[] }>('/api/analysis/question-categories', { items: [] });
}

export async function fetchAnalysisQuestions(
  scope: 'employee' | 'customerChat',
  id: string,
  params: AnalysisQuestionsParams,
  observerUserid?: string
): Promise<PagedResult<import('./analysisTypes').AnalysisQuestion>> {
  const query = dateParams(params);
  if (params.questionCategories?.length) query.set('question_categories', params.questionCategories.join(','));
  query.set('page', String(params.page));
  query.set('page_size', String(params.pageSize));
  query.set('sort', params.sort);
  query.set('order', params.order);
  if (scope === 'customerChat' && observerUserid) query.set('observer_userid', observerUserid);
  const path =
    scope === 'employee'
      ? `/api/analysis/observed-employees/${id}/questions?${query.toString()}`
      : `/api/analysis/customer-chats/${id}/questions?${query.toString()}`;
  return getJson(path, { items: [], total: 0, page: params.page, page_size: params.pageSize });
}

export async function fetchResponseGroups(
  userid: string,
  params: ResponseGroupsParams
): Promise<PagedResult<ResponseGroupStat>> {
  const query = dateParams(params);
  query.set('page', String(params.page));
  query.set('page_size', String(params.pageSize));
  query.set('sort', params.sort);
  query.set('order', params.order);
  if (params.roomName) query.set('room_name', params.roomName);
  return getJson(
    `/api/analysis/observed-employees/${userid}/response-groups?${query.toString()}`,
    { items: [], total: 0, page: params.page, page_size: params.pageSize }
  );
}

export async function fetchAnalysisCustomerChats(params: {
  observerUserid: string;
  keyword?: string;
  page: number;
  pageSize: number;
}): Promise<PagedResult<AnalysisCustomerChat>> {
  const query = new URLSearchParams({
    observer_userid: params.observerUserid,
    page: String(params.page),
    page_size: String(params.pageSize)
  });
  if (params.keyword) query.set('keyword', params.keyword);
  return getJson(`/api/analysis/customer-chats?${query.toString()}`, {
    items: [],
    total: 0,
    page: params.page,
    page_size: params.pageSize
  });
}

function emptySummary(): AnalysisSummary {
  return {
    overview: {
      single_message_count: 0,
      room_message_count: 0,
      received_message_count: 0,
      sent_message_count: 0,
      question_count: 0,
      avg_response_seconds: 0
    },
    message_trend: [],
    message_type_distribution: [],
    sentiment_summary: {
      positive_count: 0,
      neutral_count: 0,
      negative_count: 0,
      total_count: 0,
      covered_room_count: 0
    },
    hotwords: [],
    question_category_stats: [],
    response_daily_stats: []
  };
}
