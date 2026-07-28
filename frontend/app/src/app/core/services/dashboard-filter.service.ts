import { computed, Injectable, signal } from '@angular/core';

import type {
  GetAnalyticsSummaryRequestParams,
  GetReportingSummaryRequestParams,
} from '../api/api/analytics.serviceInterface';

export type DashboardFilters = {
  operators: string[];
  terminals: string[];
  routes: string[];
  dateFrom: Date;
  dateTo: Date;
};

export type DashboardFilterDraft = {
  dateRange: Date[];
  operator: string;
  terminals: string[];
  routes: string[];
};

export type DashboardFilterOption = {
  label: string;
  value: string;
};

@Injectable({ providedIn: 'root' })
export class DashboardFilterService {
  readonly operatorOptions: DashboardFilterOption[] = [
    { label: 'All Operators', value: 'all' },
    { label: 'Interstate Bus Lines', value: 'interstate' },
    { label: 'Free State Express', value: 'fse' },
    { label: 'Maluti Bus Services', value: 'maluti' },
    { label: 'Bophelong Transport', value: 'bophelong' },
    { label: 'Mangaung City Bus', value: 'mangaung' },
    { label: 'Motheo Bus Service', value: 'motheo' },
    { label: 'Welkom Transport Co', value: 'welkom' },
    { label: 'SA Roadlink FS', value: 'saroadlink' },
  ];

  readonly operators = this.operatorOptions.filter((option) => option.value !== 'all');

  readonly terminals: DashboardFilterOption[] = [
    { label: 'Bloemfontein', value: 'bfn' },
    { label: 'Welkom', value: 'welkom' },
    { label: 'Botshabelo', value: 'botshabelo' },
    { label: 'Thaba Nchu', value: 'thabaNchu' },
  ];

  readonly routes: DashboardFilterOption[] = [
    { label: 'R03', value: 'r03' },
    { label: 'R04', value: 'r04' },
    { label: 'R05', value: 'r05' },
    { label: 'R07', value: 'r07' },
    { label: 'R08', value: 'r08' },
    { label: 'R11', value: 'r11' },
    { label: 'R12', value: 'r12' },
    { label: 'R14', value: 'r14' },
    { label: 'R15', value: 'r15' },
    { label: 'R16', value: 'r16' },
    { label: 'R18', value: 'r18' },
    { label: 'R19', value: 'r19' },
    { label: 'R22', value: 'r22' },
    { label: 'R23', value: 'r23' },
    { label: 'R26', value: 'r26' },
    { label: 'R30', value: 'r30' },
  ];

  readonly appliedFilters = signal<DashboardFilters>(this.defaultFilters());
  readonly draftFilters = signal<DashboardFilterDraft>(this.defaultDraft());

  readonly activeFilterCount = computed(() => {
    const filters = this.appliedFilters();
    return (
      (filters.operators.length > 0 ? 1 : 0) +
      (filters.terminals.length > 0 ? 1 : 0) +
      (filters.routes.length > 0 ? 1 : 0)
    );
  });

  setDraft(patch: Partial<DashboardFilterDraft>): void {
    this.draftFilters.update((draft) => ({
      ...draft,
      ...patch,
      dateRange: patch.dateRange ? this.cloneDateArray(patch.dateRange) : this.cloneDateArray(draft.dateRange),
      terminals: patch.terminals ? [...patch.terminals] : [...draft.terminals],
      routes: patch.routes ? [...patch.routes] : [...draft.routes],
    }));
  }

  applyDraft(): DashboardFilters {
    const draft = this.draftFilters();
    const [dateFrom, dateTo] = this.normalizedDateRange(draft.dateRange);
    const filters: DashboardFilters = {
      dateFrom,
      dateTo,
      operators: draft.operator === 'all' ? [] : [draft.operator],
      terminals: [...draft.terminals],
      routes: [...draft.routes],
    };

    this.appliedFilters.set(filters);
    this.draftFilters.set({
      dateRange: [new Date(dateFrom), new Date(dateTo)],
      operator: draft.operator,
      terminals: [...draft.terminals],
      routes: [...draft.routes],
    });
    return filters;
  }

  reset(): DashboardFilters {
    const filters = this.defaultFilters();
    this.appliedFilters.set(filters);
    this.draftFilters.set(this.defaultDraft());
    return filters;
  }

  formatApiDate(date: Date): string {
    const year = date.getFullYear();
    const month = `${date.getMonth() + 1}`.padStart(2, '0');
    const day = `${date.getDate()}`.padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  toAnalyticsSummaryRequestParams(
    filters: Pick<DashboardFilters, 'dateFrom' | 'dateTo'> = this.appliedFilters(),
  ): GetAnalyticsSummaryRequestParams {
    return {
      startDate: this.formatApiDate(filters.dateFrom),
      endDate: this.formatApiDate(filters.dateTo),
    };
  }

  toReportingSummaryRequestParams(
    filters: Pick<DashboardFilters, 'dateFrom' | 'dateTo'> = this.appliedFilters(),
  ): GetReportingSummaryRequestParams {
    return {
      startDate: this.formatApiDate(filters.dateFrom),
      endDate: this.formatApiDate(filters.dateTo),
    };
  }

  defaultDateFrom(): Date {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  }

  private defaultFilters(): DashboardFilters {
    return {
      dateFrom: this.defaultDateFrom(),
      dateTo: new Date(),
      operators: [],
      terminals: [],
      routes: [],
    };
  }

  private defaultDraft(): DashboardFilterDraft {
    const filters = this.defaultFilters();
    return {
      dateRange: [new Date(filters.dateFrom), new Date(filters.dateTo)],
      operator: 'all',
      terminals: [],
      routes: [],
    };
  }

  private normalizedDateRange(dateRange: Date[]): [Date, Date] {
    const [from, to] = dateRange ?? [];
    const dateFrom = from ? new Date(from) : this.defaultDateFrom();
    const dateTo = to ? new Date(to) : new Date(dateFrom);
    return dateFrom <= dateTo ? [dateFrom, dateTo] : [dateTo, dateFrom];
  }

  private cloneDateArray(dates: Date[]): Date[] {
    return dates.map((date) => new Date(date));
  }
}
