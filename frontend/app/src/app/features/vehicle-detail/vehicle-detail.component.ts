import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';

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

import { VehicleService } from '../../core/api/api/vehicle.service';
import type { VehicleDataQualityResponse } from '../../core/api/model/vehicleDataQualityResponse';
import type { VehicleDetailResponse } from '../../core/api/model/vehicleDetailResponse';
import type { VehicleResponse } from '../../core/api/model/vehicleResponse';
import type { VehicleScorePointResponse } from '../../core/api/model/vehicleScorePointResponse';
import { AuthService } from '../../core/services/auth.service';

type DetailMetric = {
  label: string;
  value: string;
  icon: string;
  severity?: 'success' | 'danger' | 'secondary';
};

type QualityItem = {
  label: string;
  matched: boolean;
  count?: number;
};

@Component({
  selector: 'app-vehicle-detail',
  standalone: true,
  imports: [
    CommonModule,
    AvatarModule,
    ButtonModule,
    DrawerModule,
    MenuModule,
    NgxEchartsDirective,
    TableModule,
    TagModule,
    ToolbarModule,
    TooltipModule,
  ],
  templateUrl: './vehicle-detail.component.html',
  styleUrl: './vehicle-detail.component.css',
})
export class VehicleDetailComponent implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly vehicleApi = inject(VehicleService);

  readonly session = this.auth.session;
  readonly detail = signal<VehicleDetailResponse | null>(null);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly scoreChartOptions = computed(() => this.buildScoreChartOptions(this.detail()?.score_points ?? []));

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
      command: () => this.openAnalytics(),
    },
    {
      label: 'Vehicles',
      icon: 'pi pi-car',
      styleClass: 'nav-item-active',
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

  ngOnInit(): void {
    if (!this.auth.isLoggedIn()) {
      this.router.navigate(['/login']);
      return;
    }

    this.route.paramMap.subscribe((params) => {
      const vehicleKey = params.get('vehicleKey');
      if (!vehicleKey) {
        this.error.set('No vehicle was selected.');
        return;
      }
      this.loadVehicle(vehicleKey);
    });
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

  openAnalytics(): void {
    this.menuVisible = false;
    this.router.navigate(['/analytics']);
  }

  openVehicles(): void {
    this.menuVisible = false;
    this.router.navigate(['/vehicles']);
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

  goBack(): void {
    this.router.navigate(['/vehicles']);
  }

  vehicleTitle(vehicle: VehicleResponse): string {
    return vehicle.fleet_number || vehicle.registration_number || vehicle.vin;
  }

  statusSeverity(isActive: boolean): 'success' | 'danger' {
    return isActive ? 'success' : 'danger';
  }

  resultSeverity(passed: boolean | null | undefined): 'success' | 'danger' | 'secondary' {
    if (passed === true) return 'success';
    if (passed === false) return 'danger';
    return 'secondary';
  }

  resultLabel(passed: boolean | null | undefined): string {
    if (passed === true) return 'Passed';
    if (passed === false) return 'Failed';
    return 'No result';
  }

  yesNoSeverity(value: boolean): 'success' | 'danger' {
    return value ? 'success' : 'danger';
  }

  statusMetrics(detail: VehicleDetailResponse): DetailMetric[] {
    const status = detail.current_status;
    return [
      {
        label: 'Current Location',
        value: status.current_location || 'No Smart Fleet address',
        icon: 'pi pi-map-marker',
      },
      {
        label: 'Last Ping',
        value: status.last_ping_time ? this.formatDateTime(status.last_ping_time) : 'No ping yet',
        icon: 'pi pi-clock',
      },
      {
        label: 'Latest Inspection',
        value: status.latest_inspection_at ? this.formatDateTime(status.latest_inspection_at) : 'No inspection yet',
        icon: 'pi pi-search',
      },
      {
        label: 'Inspection Type',
        value: status.latest_inspection_type || 'No type captured',
        icon: 'pi pi-list-check',
      },
      {
        label: 'Latest Result',
        value: this.resultLabel(status.latest_inspection_passed),
        icon: 'pi pi-clipboard',
        severity: this.resultSeverity(status.latest_inspection_passed),
      },
      {
        label: 'Smart Fleet Device',
        value: status.smart_fleet_device_id ? String(status.smart_fleet_device_id) : 'Not matched',
        icon: 'pi pi-mobile',
      },
    ];
  }

  dataQualityItems(quality: VehicleDataQualityResponse): QualityItem[] {
    return [
      { label: 'Vehicle Master', matched: quality.matched_vehicle_master },
      { label: 'Smart Fleet', matched: quality.matched_smart_fleet },
      { label: 'Trip Data', matched: quality.matched_trip_data, count: quality.trip_count },
      { label: 'BI Scores', matched: quality.matched_bi_data, count: quality.bi_score_count },
      { label: 'Events', matched: quality.matched_events, count: quality.event_count },
      { label: 'Inspections', matched: quality.matched_inspections, count: quality.inspection_count },
    ];
  }

  formatDateTime(value: string): string {
    return new Intl.DateTimeFormat('en-ZA', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value));
  }

  formatNumber(value: number | null | undefined, digits = 1): string {
    if (value === null || value === undefined || Number.isNaN(value)) return '-';
    return value.toFixed(digits);
  }

  failedChecksLabel(checks: string[] | undefined): string {
    return checks && checks.length > 0 ? checks.join(', ') : '-';
  }

  private loadVehicle(vehicleKey: string): void {
    this.loading.set(true);
    this.error.set(null);

    this.vehicleApi
      .getVehicleDetailVehicleVehicleDetailVehicleKeyGet(
        { vehicleKey },
        'body',
        false,
        { transferCache: false },
      )
      .subscribe({
        next: (response) => {
          this.detail.set(response.detail);
          this.loading.set(false);
        },
        error: (err) => {
          this.loading.set(false);
          this.detail.set(null);
          this.error.set(err?.error?.detail ?? 'Could not load vehicle detail.');
        },
      });
  }

  private buildScoreChartOptions(scorePoints: VehicleScorePointResponse[]): EChartsOption {
    const hasRouteScore = scorePoints.some((point) => (point.route_score ?? 0) > 0);

    return {
      color: ['#1d4ed8', '#f97316'],
      tooltip: {
        trigger: 'axis',
        valueFormatter: (value) => `${value}%`,
      },
      legend: {
        top: 0,
        data: hasRouteScore ? ['Style Score', 'Route Score'] : ['Style Score'],
        textStyle: {
          color: '#374151',
          fontWeight: 700,
        },
      },
      grid: {
        left: 48,
        right: 24,
        top: 54,
        bottom: 70,
      },
      xAxis: {
        type: 'category',
        data: scorePoints.map((point) => point.label),
        axisLabel: {
          color: '#4b5563',
          rotate: 35,
        },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        axisLabel: {
          color: '#4b5563',
          formatter: '{value}%',
        },
        splitLine: {
          lineStyle: {
            color: '#e5e7eb',
          },
        },
      },
      series: [
        {
          name: 'Style Score',
          type: 'line' as const,
          smooth: true,
          symbolSize: 7,
          data: scorePoints.map((point) => point.style_score),
        },
        ...(hasRouteScore
          ? [
              {
                name: 'Route Score',
                type: 'line' as const,
                smooth: true,
                symbolSize: 7,
                data: scorePoints.map((point) => point.route_score),
              },
            ]
          : []),
      ],
    };
  }
}
