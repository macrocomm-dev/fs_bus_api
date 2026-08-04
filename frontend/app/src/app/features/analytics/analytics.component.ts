import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';

import type { EChartsOption } from 'echarts';
import { NgxEchartsDirective } from 'ngx-echarts';
import type { MenuItem } from 'primeng/api';
import { AvatarModule } from 'primeng/avatar';
import { ButtonModule } from 'primeng/button';
import { DrawerModule } from 'primeng/drawer';
import { MenuModule } from 'primeng/menu';
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { ToolbarModule } from 'primeng/toolbar';
import { TooltipModule } from 'primeng/tooltip';

import { AnalyticsService } from '../../core/api/api/analytics.service';
import type { AnalyticsSummaryResponse } from '../../core/api/model/analyticsSummaryResponse';
import type { AnalyticsVehicleScoreResponse } from '../../core/api/model/analyticsVehicleScoreResponse';
import { DashboardFiltersComponent } from '../../core/components/dashboard-filters/dashboard-filters.component';
import {
  DashboardFilterService,
  type DashboardFilters,
} from '../../core/services/dashboard-filter.service';
import { AuthService } from '../../core/services/auth.service';
import { operatorBadgeFor, type OperatorBadge } from '../../core/utils/operator-badge';

type MetricTile = {
  title: string;
  icon: string;
  color: string;
  primary: string;
  secondary?: string;
};

type GaugeScore = {
  label: string;
  score: number;
  color: string;
};

type VehiclePerformance = {
  fleetNo: string;
  registration: string;
  operator: string;
  distance: string;
  tripDuration: string;
  speedDuration: string;
  idleDuration: string;
  highRiskTrips: number;
  score: number;
};

type LastEvent = {
  bus: string;
  location: string;
  time: string;
  eventType: string;
  measurement: string;
  operator: string;
};

@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [
    CommonModule,
    AvatarModule,
    ButtonModule,
    DashboardFiltersComponent,
    DrawerModule,
    MenuModule,
    NgxEchartsDirective,
    TableModule,
    TagModule,
    ToolbarModule,
    TooltipModule,
  ],
  templateUrl: './analytics.component.html',
  styleUrl: './analytics.component.css',
})
export class AnalyticsComponent implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly analyticsApi = inject(AnalyticsService);
  private readonly filterService = inject(DashboardFilterService);

  readonly session = this.auth.session;
  readonly appliedFilters = this.filterService.appliedFilters;
  readonly metricTiles = signal<MetricTile[]>([]);
  readonly gaugeScores = signal<GaugeScore[]>([]);
  readonly vehiclePerformance = signal<VehiclePerformance[]>([]);
  readonly lastEvents = signal<LastEvent[]>([]);
  readonly vehicleScoreChartOptions = signal<EChartsOption>(this.buildVehicleScoreChartOptions([]));
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  menuVisible = true;

  readonly navigationItems: MenuItem[] = [
    {
      label: 'Reports',
      icon: 'pi pi-chart-bar',
      command: () => this.openReporting(),
    },
    {
      label: 'Live Map',
      icon: 'pi pi-map',
      command: () => this.openSmartFleet(),
    },
    {
      label: 'Analytics',
      icon: 'pi pi-chart-line',
      styleClass: 'nav-item-active',
      command: () => this.closeMenu(),
    },
    {
      label: 'Vehicles',
      icon: 'pi pi-car',
      command: () => this.openVehicles(),
    },
    {
      label: 'Inspections',
      icon: 'pi pi-search',
      command: () => this.openInspections(),
    },
    {
      label: 'Shifts',
      icon: 'pi pi-calendar',
      command: () => this.openShifts(),
    },
    {
      label: 'Monitors',
      icon: 'pi pi-users',
      command: () => this.openMonitors(),
    },
  ];

  private buildVehicleScoreChartOptions(scores: AnalyticsVehicleScoreResponse[]): EChartsOption {
    const sortedScores = [...scores].sort((a, b) => a.score - b.score);
    const operators = [...new Set(sortedScores.map((vehicle) => vehicle.operator))];

    return {
    color: ['#1d4ed8', '#f97316'],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const items = Array.isArray(params) ? params : [params];
        const item = items.find((entry) => entry.data !== null && entry.data !== undefined);
        if (!item) return '';
        return `${item.name}<br/>${item.seriesName}<br/>Score: ${item.data}%`;
      },
    },
    legend: {
      top: 0,
        data: operators,
      textStyle: {
        color: '#374151',
        fontWeight: 600,
      },
    },
    grid: {
      left: 48,
      right: 24,
      top: 56,
      bottom: 70,
    },
    xAxis: {
      type: 'category',
        data: sortedScores.map((vehicle) => vehicle.fleet_no),
      axisLabel: {
        color: '#4b5563',
        fontWeight: 600,
      },
      axisTick: { alignWithLabel: true },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: {
        formatter: '{value}%',
        color: '#4b5563',
      },
      splitLine: {
        lineStyle: {
          color: '#e5e7eb',
        },
      },
    },
      series: operators.map((operator, index) => ({
        name: operator,
        type: 'bar',
        barMaxWidth: 42,
        data: sortedScores.map((vehicle) => (vehicle.operator === operator ? vehicle.score : null)),
        label: {
          show: false,
        },
        itemStyle: {
          color: this.operatorColor(operator),
          borderRadius: [6, 6, 0, 0],
        },
        markLine: index === 0 ? {
          silent: true,
          symbol: 'none',
          lineStyle: {
            color: '#dc2626',
            width: 2,
            type: 'solid',
          },
          label: {
            color: '#dc2626',
            fontWeight: 800,
            formatter: '80% intervention line',
            position: 'end',
          },
          data: [{ yAxis: 80 }],
        } : undefined,
      })),
    };
  }

  ngOnInit(): void {
    if (!this.auth.isLoggedIn()) {
      this.router.navigate(['/login']);
      return;
    }

    this.loadAnalytics(this.appliedFilters());
  }

  toggleMenu(): void {
    this.menuVisible = !this.menuVisible;
  }

  closeMenu(): void {
    this.menuVisible = false;
  }

  openReporting(): void {
    this.menuVisible = false;
    this.router.navigate(['/reporting']);
  }

  openSmartFleet(): void {
    this.menuVisible = false;
    this.router.navigate(['/smart-fleet']);
  }

  openVehicles(): void {
    this.menuVisible = false;
    this.router.navigate(['/vehicles']);
  }

  openVehicleDetail(vehicleKey: string | null | undefined): void {
    if (!vehicleKey) {
      return;
    }

    this.router.navigate(['/vehicles', vehicleKey]);
  }

  openVehicleDetailFromPerformance(row: VehiclePerformance): void {
    this.openVehicleDetail(row.fleetNo || row.registration);
  }

  openVehicleDetailFromChart(event: { name?: string }): void {
    this.openVehicleDetail(event?.name);
  }

  openInspections(): void {
    this.menuVisible = false;
    this.router.navigate(['/inspections']);
  }

  openShifts(): void {
    this.menuVisible = false;
    this.router.navigate(['/shifts']);
  }

  openMonitors(): void {
    this.menuVisible = false;
    this.router.navigate(['/monitors']);
  }

  logout(): void {
    this.auth.logout();
  }

  onFiltersApplied(filters: DashboardFilters): void {
    this.loadAnalytics(filters);
  }

  private loadAnalytics(range: Pick<DashboardFilters, 'dateFrom' | 'dateTo'> = this.appliedFilters()): void {
    this.loading.set(true);
    this.error.set(null);

    this.analyticsApi
      .getAnalyticsSummary(
        this.filterService.toAnalyticsSummaryRequestParams(range),
        'body',
        false,
        { transferCache: false },
      )
      .subscribe({
        next: (response) => {
          this.applyAnalyticsSummary(response);
          this.loading.set(false);
        },
        error: (err) => {
          this.loading.set(false);
          this.error.set(err?.error?.detail ?? 'Could not load analytics.');
        },
      });
  }

  private applyAnalyticsSummary(response: AnalyticsSummaryResponse): void {
    const operatorMatches = (operator: string) => this.operatorMatchesFilter(operator);
    const vehicleScores = (response.vehicle_scores ?? []).filter((vehicle) =>
      operatorMatches(vehicle.operator),
    );

    this.metricTiles.set(
      (response.metric_tiles ?? [])
        // Temporarily hidden until the product owner confirms how they want excess idle shown.
        .filter((tile) => tile.title !== 'Excess idle duration')
        .map((tile) => ({
          title: tile.title,
          icon: tile.icon,
          color: tile.color,
          primary: tile.primary,
          secondary: tile.secondary ?? undefined,
        })),
    );
    this.gaugeScores.set(response.gauge_scores ?? []);
    this.lastEvents.set(
      (response.last_events ?? [])
        .filter((event) => operatorMatches(event.operator))
        .map((event) => ({
          bus: event.bus,
          location: event.location,
          time: event.time,
          eventType: event.event_type,
          measurement: event.measurement,
          operator: event.operator,
        })),
    );
    this.vehiclePerformance.set(
      (response.vehicle_performance ?? [])
        .filter((vehicle) => operatorMatches(vehicle.operator))
        .map((vehicle) => ({
          fleetNo: vehicle.fleet_no,
          registration: vehicle.registration,
          operator: vehicle.operator,
          distance: vehicle.distance,
          tripDuration: vehicle.trip_duration,
          speedDuration: vehicle.speed_duration,
          idleDuration: vehicle.idle_duration,
          highRiskTrips: vehicle.high_risk_trips,
          score: vehicle.score,
        })),
    );
    this.vehicleScoreChartOptions.set(this.buildVehicleScoreChartOptions(vehicleScores));
  }

  scoreSeverity(score: number): 'success' | 'warn' | 'danger' {
    if (score >= 94) return 'success';
    if (score >= 88) return 'warn';
    return 'danger';
  }

  eventSeverity(eventType: string): 'success' | 'info' | 'warn' | 'danger' {
    if (eventType === 'Speeding' || eventType === 'Harsh Braking' || eventType === 'Accident') return 'danger';
    if (eventType === 'Cornering' || eventType === 'Acceleration') return 'warn';
    return 'success';
  }

  operatorColor(operator: string): string {
    if (operator === 'Maluti Bus Services') return '#f97316';
    if (operator === 'Interstate Bus Lines') return '#1d4ed8';
    return '#64748b';
  }

  operatorBadge(operator: string | null | undefined): OperatorBadge | null {
    return operatorBadgeFor(operator);
  }

  private operatorMatchesFilter(operator: string): boolean {
    const selectedOperators = this.appliedFilters().operators;
    if (selectedOperators.length === 0) return true;
    return selectedOperators.includes(this.operatorCode(operator));
  }

  private operatorCode(operator: string): string {
    const normalized = operator.trim().toLowerCase();
    if (normalized === 'interstate bus lines') return 'interstate';
    if (normalized === 'maluti bus services') return 'maluti';
    if (normalized === 'bophelong transport') return 'bophelong';
    if (normalized === 'free state express') return 'fse';
    if (normalized === 'mangaung city bus') return 'mangaung';
    if (normalized === 'motheo bus service') return 'motheo';
    if (normalized === 'welkom transport co') return 'welkom';
    if (normalized === 'sa roadlink fs') return 'saroadlink';
    return normalized;
  }
}
