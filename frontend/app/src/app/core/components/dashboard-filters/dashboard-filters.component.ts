import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, OnInit, Output, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { DatePickerModule } from 'primeng/datepicker';
import { FloatLabelModule } from 'primeng/floatlabel';
import { SelectModule } from 'primeng/select';

import {
  DashboardFilterService,
  type DashboardFilters,
} from '../../services/dashboard-filter.service';

@Component({
  selector: 'app-dashboard-filters',
  standalone: true,
  imports: [CommonModule, FormsModule, ButtonModule, DatePickerModule, FloatLabelModule, SelectModule],
  templateUrl: './dashboard-filters.component.html',
  styleUrl: './dashboard-filters.component.css',
})
export class DashboardFiltersComponent implements OnInit {
  private readonly filterService = inject(DashboardFilterService);

  @Input() idPrefix = 'dashboard';
  @Output() filtersApplied = new EventEmitter<DashboardFilters>();

  readonly activeFilterCount = this.filterService.activeFilterCount;
  readonly operatorOptions = this.filterService.operatorOptions;

  draftDateRange: Date[] = [];
  draftOperator = 'all';

  ngOnInit(): void {
    this.syncFromService();
  }

  onDateRangeChange(dateRange: Date[] | Date | null): void {
    const range = Array.isArray(dateRange) ? dateRange : dateRange ? [dateRange] : [];
    this.draftDateRange = range;
    this.filterService.setDraft({ dateRange: range });
  }

  onOperatorChange(operator: string | null): void {
    this.draftOperator = operator ?? 'all';
    this.filterService.setDraft({ operator: this.draftOperator });
  }

  applyFilters(): void {
    this.filterService.setDraft({
      dateRange: this.draftDateRange,
      operator: this.draftOperator,
    });
    this.filtersApplied.emit(this.filterService.applyDraft());
  }

  resetFilters(): void {
    this.filtersApplied.emit(this.filterService.reset());
    this.syncFromService();
  }

  private syncFromService(): void {
    const draft = this.filterService.draftFilters();
    this.draftDateRange = draft.dateRange.map((date) => new Date(date));
    this.draftOperator = draft.operator;
  }
}
