import { afterEach, describe, expect, it, vi } from 'vitest';
import { DashboardFilterService } from './dashboard-filter.service';

afterEach(() => vi.useRealTimers());

describe('dashboard default dates', () => {
  it('uses seven calendar days including today across a year boundary', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2027, 0, 3, 10));
    const service = new DashboardFilterService();
    expect(service.toReportingSummaryRequestParams()).toEqual({ startDate: '2026-12-28', endDate: '2027-01-03' });
    expect(service.draftFilters().dateRange.map(d => service.formatApiDate(d))).toEqual(['2026-12-28', '2027-01-03']);
  });

  it('reset discards a previous session selection and uses the new login day', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 10, 24, 10));
    const service = new DashboardFilterService();
    service.setDraft({ dateRange: [new Date(2026, 0, 1), new Date(2026, 0, 2)], operator: 'interstate' });
    service.applyDraft();
    vi.setSystemTime(new Date(2026, 10, 25, 10));
    service.reset();
    expect(service.toReportingSummaryRequestParams()).toEqual({ startDate: '2026-11-19', endDate: '2026-11-25' });
    expect(service.appliedFilters().operators).toEqual([]);
  });
});
