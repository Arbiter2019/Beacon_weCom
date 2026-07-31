import { beforeEach, describe, expect, it, vi } from 'vitest';

import { fetchAnalysisQuestions, fetchObservedEmployeeSummary, fetchResponseGroups } from './analysisClient';

describe('analysisClient', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total: 0 })
    }));
  });

  it('builds observed employee summary query parameters', async () => {
    await fetchObservedEmployeeSummary('XiaoHaiYan_3', {
      startDate: '2026-07-23',
      endDate: '2026-07-29',
      conversationType: 'room'
    });

    expect(fetch).toHaveBeenCalledWith(
      '/api/analysis/observed-employees/XiaoHaiYan_3/summary?start_date=2026-07-23&end_date=2026-07-29&conversation_type=room',
      { headers: { Authorization: 'Bearer dev-admin-token' } }
    );
  });

  it('builds paged question query with category filters', async () => {
    await fetchAnalysisQuestions('employee', 'wang_teacher', {
      startDate: '2026-07-23',
      endDate: '2026-07-29',
      questionCategories: ['course', 'refund'],
      page: 2,
      pageSize: 50,
      sort: 'msg_time',
      order: 'desc'
    });

    expect(fetch).toHaveBeenCalledWith(
      '/api/analysis/observed-employees/wang_teacher/questions?start_date=2026-07-23&end_date=2026-07-29&question_categories=course%2Crefund&page=2&page_size=50&sort=msg_time&order=desc',
      { headers: { Authorization: 'Bearer dev-admin-token' } }
    );
  });

  it('builds response group sorting query', async () => {
    await fetchResponseGroups('wang_teacher', {
      startDate: '2026-07-23',
      endDate: '2026-07-29',
      page: 1,
      pageSize: 50,
      sort: 'median',
      order: 'asc'
    });

    expect(fetch).toHaveBeenCalledWith(
      '/api/analysis/observed-employees/wang_teacher/response-groups?start_date=2026-07-23&end_date=2026-07-29&page=1&page_size=50&sort=median&order=asc',
      { headers: { Authorization: 'Bearer dev-admin-token' } }
    );
  });
});
