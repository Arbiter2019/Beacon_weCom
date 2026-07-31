export type AnalysisDateRange = {
  startDate: string;
  endDate: string;
};

export type AnalysisSummaryParams = AnalysisDateRange & {
  conversationType: 'all' | 'single' | 'room';
};

export type AnalysisOverview = {
  single_message_count: number;
  room_message_count: number;
  received_message_count: number;
  sent_message_count: number;
  question_count: number;
  avg_response_seconds: number;
};

export type MessageTrendPoint = {
  analysis_date: string;
  single_received_count: number;
  single_sent_count: number;
  room_received_count: number;
  room_sent_count: number;
  received_count: number;
  sent_count: number;
};

export type MessageTypeDistribution = {
  msg_type: string;
  received_count: number;
  sent_count: number;
};

export type SentimentSummary = {
  positive_count: number;
  neutral_count: number;
  negative_count: number;
  total_count: number;
  covered_room_count: number;
};

export type Hotword = {
  word: string;
  count: number;
};

export type QuestionCategoryStat = {
  code: string;
  display_name: string;
  count: number;
};

export type ResponseDailyStat = {
  analysis_date: string;
  avg_seconds: number;
  median_seconds: number;
  q1_seconds: number;
  q3_seconds: number;
  min_seconds: number;
  max_seconds: number;
  sample_count: number;
};

export type AnalysisSummary = {
  overview: AnalysisOverview;
  message_trend: MessageTrendPoint[];
  message_type_distribution: MessageTypeDistribution[];
  sentiment_summary: SentimentSummary;
  hotwords: Hotword[];
  question_category_stats: QuestionCategoryStat[];
  response_daily_stats: ResponseDailyStat[];
};

export type QuestionCategory = {
  code: string;
  display_name: string;
  sort_order: number;
  enabled: boolean;
};

export type AnalysisQuestion = {
  id: number;
  content_text: string;
  question_category: string;
  question_category_name: string;
  sender_display_name: string;
  room_name: string;
  msg_time?: string | null;
};

export type PagedResult<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

export type AnalysisQuestionsParams = AnalysisDateRange & {
  questionCategories?: string[];
  page: number;
  pageSize: number;
  sort: 'msg_time' | 'analysis_date' | 'question_category' | 'room_name';
  order: 'asc' | 'desc';
};

export type ResponseGroupSort = 'analysis_date' | 'room_name' | 'avg' | 'median' | 'q1' | 'q3' | 'max' | 'min';

export type ResponseGroupsParams = AnalysisDateRange & {
  page: number;
  pageSize: number;
  sort: ResponseGroupSort;
  order: 'asc' | 'desc';
  roomName?: string;
};

export type ResponseGroupStat = ResponseDailyStat & {
  roomid: string;
  room_name: string;
};

export type AnalysisCustomerChat = {
  roomid: string;
  room_name: string;
  member_count?: number | null;
  owner_userid?: string | null;
  owner_name?: string | null;
};
