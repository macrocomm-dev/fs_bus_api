import { CommonModule } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import type { EChartsOption } from 'echarts';
import { NgxEchartsDirective } from 'ngx-echarts';
import { catchError, forkJoin, map, of, throwError } from 'rxjs';
import type { MenuItem } from 'primeng/api';
import { AvatarModule } from 'primeng/avatar';
import { ButtonModule } from 'primeng/button';
import { DrawerModule } from 'primeng/drawer';
import { FieldsetModule } from 'primeng/fieldset';
import { FloatLabelModule } from 'primeng/floatlabel';
import { IconFieldModule } from 'primeng/iconfield';
import { ImageModule } from 'primeng/image';
import { InputIconModule } from 'primeng/inputicon';
import { InputTextModule } from 'primeng/inputtext';
import { MenuModule } from 'primeng/menu';
import { SelectModule } from 'primeng/select';
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { TimelineModule } from 'primeng/timeline';
import { ToolbarModule } from 'primeng/toolbar';
import { TooltipModule } from 'primeng/tooltip';

import { InspectionService } from '../../core/api/api/inspection.service';
import { ImageService } from '../../core/api/api/image.service';
import { ShiftsService } from '../../core/api/api/shifts.service';
import type { GroupedBusInspectionResponse } from '../../core/api/model/groupedBusInspectionResponse';
import type { MonitorSummaryResponse } from '../../core/api/model/monitorSummaryResponse';
import type { SelfieResponse } from '../../core/api/model/selfieResponse';
import type { ShiftResponse } from '../../core/api/model/shiftResponse';
import { ViewLoadingOverlayComponent } from '../../core/components/view-loading-overlay/view-loading-overlay.component';
import { AuthService } from '../../core/services/auth.service';

type MonitorOption = {
  label: string;
  value: string;
  shiftCount: number;
  inspectionCount: number;
};

type MonitorInspectionItem = {
  inspectionId: number;
  shiftId: number;
  busId: string;
  fleetNumber: string;
  dutyNumber: string;
  type: string;
  inspectionTime: string;
  gps: string;
  pass: boolean | null | undefined;
  summary: string;
};

type MonitorShiftRow = ShiftResponse & {
  loggedBy: string;
  duration: string;
  startGps: string;
  endGps: string;
  inspections: MonitorInspectionItem[];
  selfies: SelfieResponse[];
  inspectionCount: number;
  failedInspectionCount: number;
};

type MonitorInspectionBusGroup = {
  key: string;
  busId: string;
  fleetNumber: string;
  dutyNumber: string;
  inspections: MonitorInspectionItem[];
};

type MonitorTimelineEvent = {
  id: string;
  kind: 'selfie' | 'inspection';
  timestamp: string;
  title: string;
  subtitle: string;
  details: string;
  gps: string;
  icon: string;
  severity: 'success' | 'danger' | 'warn' | 'info';
  selfie?: SelfieResponse;
  inspection?: MonitorInspectionItem;
};

const INSPECTION_SHIFT_LOOKUP_CHUNK_SIZE = 80;
const MONITOR_INSPECTION_TYPES = [
  'External',
  'Internal',
  'Driver',
  'Passenger Count',
  'Behind Schedule',
] as const;
const MONITOR_INSPECTION_TYPE_COLORS = ['#2563eb', '#16a34a', '#d97706', '#7c3aed', '#dc2626'];

@Component({
  selector: 'app-monitors',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    AvatarModule,
    ButtonModule,
    DrawerModule,
    FieldsetModule,
    FloatLabelModule,
    IconFieldModule,
    ImageModule,
    InputIconModule,
    InputTextModule,
    MenuModule,
    NgxEchartsDirective,
    SelectModule,
    TableModule,
    TagModule,
    TimelineModule,
    ToolbarModule,
    TooltipModule,
    ViewLoadingOverlayComponent,
  ],
  templateUrl: './monitors.component.html',
  styleUrl: './monitors.component.css',
})
export class MonitorsComponent implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly shiftsApi = inject(ShiftsService);
  private readonly inspectionApi = inject(InspectionService);
  private readonly imageApi = inject(ImageService);

  readonly session = this.auth.session;
  readonly monitorSummaries = signal<MonitorSummaryResponse[]>([]);
  readonly shifts = signal<MonitorShiftRow[]>([]);
  readonly selectedMonitorId = signal<string | null>(null);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  readonly monitorOptions = computed<MonitorOption[]>(() => {
    return this.monitorSummaries()
      .map((summary) => ({
        label: this.monitorSummaryLabel(summary),
        value: summary.user_id,
        shiftCount: summary.shift_count ?? 0,
        inspectionCount: summary.inspection_count ?? 0,
      }))
      .sort((a, b) => a.label.localeCompare(b.label));
  });

  readonly selectedMonitorSummary = computed(() => {
    const selected = this.selectedMonitorId();
    if (!selected) return null;
    return this.monitorSummaries().find((summary) => summary.user_id === selected) ?? null;
  });

  readonly selectedShifts = computed(() => {
    const selected = this.selectedMonitorId();
    if (!selected) return [];
    return this.shifts().filter((shift) => this.monitorKey(shift) === selected);
  });

  readonly selectedInspections = computed(() =>
    this.selectedShifts()
      .flatMap((shift) => shift.inspections)
      .sort((a, b) => Date.parse(b.inspectionTime) - Date.parse(a.inspectionTime)),
  );

  readonly selectedSelfies = computed(() =>
    this.selectedShifts()
      .flatMap((shift) => shift.selfies)
      .sort((a, b) => Date.parse(b.timestamp) - Date.parse(a.timestamp)),
  );

  readonly lastSelfie = computed(() => this.selectedSelfies()[0] ?? null);

  readonly summary = computed(() => {
    const shifts = this.selectedShifts();
    const inspections = this.selectedInspections();
    const selectedSummary = this.selectedMonitorSummary();
    return {
      shifts: selectedSummary?.shift_count ?? shifts.length,
      inspections:
        selectedSummary?.inspection_count ??
        shifts.reduce((total, shift) => total + shift.inspectionCount, 0),
      failed:
        selectedSummary?.failed_inspection_count ??
        shifts.reduce((total, shift) => total + shift.failedInspectionCount, 0),
      buses: new Set(inspections.map((inspection) => inspection.busId).filter(Boolean)).size,
    };
  });

  readonly monitorChartOptions = computed(() => this.buildMonitorChartOptions(this.selectedShifts()));

  menuVisible = true;
  readonly navigationItems: MenuItem[] = [
    { label: 'Reports', icon: 'pi pi-chart-bar', command: () => this.openReporting() },
    { label: 'Live Map', icon: 'pi pi-map', command: () => this.openSmartFleet() },
    { label: 'Analytics', icon: 'pi pi-chart-line', command: () => this.openAnalytics() },
    { label: 'Vehicles', icon: 'pi pi-car', command: () => this.openVehicles() },
    { label: 'Inspections', icon: 'pi pi-search', command: () => this.openInspections() },
    { label: 'Shifts', icon: 'pi pi-calendar', command: () => this.openShifts() },
    { label: 'Monitors', icon: 'pi pi-users', styleClass: 'nav-item-active', command: () => this.closeMenu() },
  ];

  ngOnInit(): void {
    if (!this.auth.isLoggedIn()) {
      this.router.navigate(['/login']);
      return;
    }

    this.loadMonitorSummaries();
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

  logout(): void {
    this.auth.logout();
  }

  statusSeverity(pass: boolean | null | undefined): 'success' | 'danger' | 'warn' {
    if (pass === true) return 'success';
    if (pass === false) return 'danger';
    return 'warn';
  }

  statusLabel(pass: boolean | null | undefined): string {
    if (pass === true) return 'Pass';
    if (pass === false) return 'Fail';
    return 'Not set';
  }

  onMonitorChange(monitorId: string | null): void {
    this.selectedMonitorId.set(monitorId);
    this.shifts.set([]);
    if (monitorId) {
      this.loadMonitorData(monitorId);
      return;
    }
    this.loading.set(false);
  }

  inspectionGroupsForShift(row: MonitorShiftRow): MonitorInspectionBusGroup[] {
    const groups = new Map<string, MonitorInspectionBusGroup>();
    for (const inspection of row.inspections) {
      const key = [
        inspection.busId || 'unknown-bus',
        inspection.fleetNumber || 'unknown-fleet',
        inspection.dutyNumber || 'unknown-duty',
      ].join('|');
      const existing =
        groups.get(key) ??
        {
          key,
          busId: inspection.busId || '-',
          fleetNumber: inspection.fleetNumber || '-',
          dutyNumber: inspection.dutyNumber || '-',
          inspections: [],
        };
      existing.inspections.push(inspection);
      groups.set(key, existing);
    }

    return [...groups.values()];
  }

  busGroupLegend(group: MonitorInspectionBusGroup): string {
    const bus = group.busId !== '-' ? `Bus ${group.busId}` : 'Unknown bus';
    const fleet = group.fleetNumber !== '-' ? `Fleet ${group.fleetNumber}` : 'Fleet not set';
    const duty = group.dutyNumber !== '-' ? `Duty ${group.dutyNumber}` : 'Duty not set';
    return `${bus} | ${fleet} | ${duty}`;
  }

  selfieImageSrc(photo: string): string {
    return photo.startsWith('data:image/') ? photo : `data:image/jpeg;base64,${photo}`;
  }

  timelineEventsForShift(row: MonitorShiftRow): MonitorTimelineEvent[] {
    const selfieEvents: MonitorTimelineEvent[] = row.selfies.map((selfie) => ({
      id: `selfie-${selfie.id}`,
      kind: 'selfie',
      timestamp: selfie.timestamp,
      title: 'Shift selfie',
      subtitle: 'Monitor verification',
      details: 'Selfie captured during the shift.',
      gps: this.gps(selfie.lat, selfie.lon),
      icon: 'pi pi-camera',
      severity: 'info',
      selfie,
    }));

    const inspectionEvents: MonitorTimelineEvent[] = row.inspections.map((inspection) => ({
      id: `inspection-${inspection.inspectionId}`,
      kind: 'inspection',
      timestamp: inspection.inspectionTime,
      title: inspection.type,
      subtitle: [
        inspection.busId ? `Bus ${inspection.busId}` : 'Unknown bus',
        inspection.fleetNumber ? `Fleet ${inspection.fleetNumber}` : null,
        inspection.dutyNumber ? `Duty ${inspection.dutyNumber}` : null,
      ]
        .filter(Boolean)
        .join(' | '),
      details: inspection.summary,
      gps: inspection.gps,
      icon: inspection.pass === false ? 'pi pi-times' : 'pi pi-check',
      severity: this.statusSeverity(inspection.pass),
      inspection,
    }));

    return [...selfieEvents, ...inspectionEvents].sort(
      (a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp),
    );
  }

  private loadMonitorSummaries(): void {
    this.loading.set(true);
    this.error.set(null);

    this.shiftsApi
      .getMonitorSummariesShiftMonitorsSummaryGet('body', false, { transferCache: false })
      .subscribe({
        next: (response) => {
          const summaries = response ?? [];
          this.monitorSummaries.set(summaries);
          const selected = this.selectedMonitorId() ?? summaries[0]?.user_id ?? null;
          this.selectedMonitorId.set(selected);
          if (selected) {
            this.loadMonitorData(selected);
            return;
          }
          this.shifts.set([]);
          this.loading.set(false);
        },
        error: (err) => {
          this.loading.set(false);
          this.error.set(err?.error?.detail ?? 'Could not load monitor list.');
        },
      });
  }

  private loadMonitorData(userId: string): void {
    this.loading.set(true);
    this.error.set(null);

    this.shiftsApi
      .getAllShiftsShiftShiftsGet({ userId, limit: 1000 }, 'body', false, { transferCache: false })
      .subscribe({
        next: (response) => {
          const shifts = response ?? [];
          const shiftIds = shifts.map((shift) => shift.id);
          if (shiftIds.length === 0) {
            this.shifts.set([]);
            this.loading.set(false);
            return;
          }

          forkJoin({
            inspectionGroups: this.loadInspectionGroupsByShiftIds(shiftIds),
            selfies: this.loadSelfiesByShiftIds(shiftIds),
          })
            .subscribe({
              next: ({ inspectionGroups, selfies }) => {
                const rows = this.buildShiftRows(shifts, inspectionGroups ?? [], selfies ?? []);
                this.shifts.set(rows);
                this.loading.set(false);
              },
              error: (err) => {
                if (err?.status === 404) {
                  const rows = this.buildShiftRows(shifts, []);
                  this.shifts.set(rows);
                  this.loading.set(false);
                  return;
                }

                this.loading.set(false);
                this.error.set(err?.error?.detail ?? 'Could not load monitor inspections.');
              },
            });
        },
        error: (err) => {
          this.loading.set(false);
          this.error.set(err?.error?.detail ?? 'Could not load monitor shifts.');
        },
      });
  }

  private monitorSummaryLabel(summary: MonitorSummaryResponse): string {
    const fullName =
      summary.full_name ||
      [summary.user_name, summary.user_surname].filter(Boolean).join(' ').trim();
    return fullName || summary.email || summary.user_id;
  }

  private loadInspectionGroupsByShiftIds(shiftIds: number[]) {
    const chunks: number[][] = [];
    for (let index = 0; index < shiftIds.length; index += INSPECTION_SHIFT_LOOKUP_CHUNK_SIZE) {
      chunks.push(shiftIds.slice(index, index + INSPECTION_SHIFT_LOOKUP_CHUNK_SIZE));
    }

    if (chunks.length === 0) {
      return of<GroupedBusInspectionResponse[]>([]);
    }

    return forkJoin(
      chunks.map((chunk) =>
        this.inspectionApi
          .getBusInspectionsByShiftInspectionBusInspectionsByShiftIdsGet(
            { shiftIds: chunk },
            'body',
            false,
            { transferCache: false },
          )
          .pipe(
            catchError((error) =>
              error?.status === 404
                ? of<GroupedBusInspectionResponse[]>([])
                : throwError(() => error),
            ),
          ),
      ),
    ).pipe(map((results) => results.flat()));
  }

  private loadSelfiesByShiftIds(shiftIds: number[]) {
    const chunks: number[][] = [];
    for (let index = 0; index < shiftIds.length; index += INSPECTION_SHIFT_LOOKUP_CHUNK_SIZE) {
      chunks.push(shiftIds.slice(index, index + INSPECTION_SHIFT_LOOKUP_CHUNK_SIZE));
    }

    if (chunks.length === 0) {
      return of<SelfieResponse[]>([]);
    }

    return forkJoin(
      chunks.map((chunk) =>
        this.imageApi
          .getSelfiesByShiftImageSelfiesByShiftIdsGet(
            { shiftIds: chunk },
            'body',
            false,
            { transferCache: false },
          )
          .pipe(
            catchError((error) =>
              error?.status === 404 ? of<SelfieResponse[]>([]) : throwError(() => error),
            ),
          ),
      ),
    ).pipe(map((results) => results.flat()));
  }

  private buildShiftRows(
    shifts: ShiftResponse[],
    inspectionGroups: GroupedBusInspectionResponse[],
    selfies: SelfieResponse[] = [],
  ): MonitorShiftRow[] {
    const inspectionsByShift = new Map<number, MonitorInspectionItem[]>();
    for (const group of inspectionGroups) {
      const items = this.flattenShiftInspectionGroup(group);
      const existing = inspectionsByShift.get(group.shift_id) ?? [];
      inspectionsByShift.set(group.shift_id, [...existing, ...items]);
    }
    const selfiesByShift = this.groupSelfiesByShift(selfies);

    return shifts
      .map((shift) => {
        const inspections = (inspectionsByShift.get(shift.id) ?? []).sort(
          (a, b) => Date.parse(b.inspectionTime) - Date.parse(a.inspectionTime),
        );
        return {
          ...shift,
          loggedBy: this.loggedBy(shift),
          duration: this.duration(shift.start_time, shift.end_time),
          startGps: this.gps(shift.start_lat, shift.start_lon),
          endGps: this.gps(shift.end_lat, shift.end_lon),
          inspections,
          selfies: selfiesByShift.get(shift.id) ?? [],
          inspectionCount: inspections.length || shift.inspection_count || 0,
          failedInspectionCount:
            inspections.length > 0
              ? inspections.filter((inspection) => inspection.pass === false).length
              : shift.failed_inspection_count || 0,
        };
      })
      .sort((a, b) => Date.parse(b.start_time) - Date.parse(a.start_time));
  }

  private groupSelfiesByShift(selfies: SelfieResponse[]): Map<number, SelfieResponse[]> {
    const selfiesByShift = new Map<number, SelfieResponse[]>();
    for (const selfie of selfies) {
      const existing = selfiesByShift.get(selfie.shift_id) ?? [];
      existing.push(selfie);
      selfiesByShift.set(selfie.shift_id, existing);
    }

    for (const shiftSelfies of selfiesByShift.values()) {
      shiftSelfies.sort((a, b) => Date.parse(b.timestamp) - Date.parse(a.timestamp));
    }

    return selfiesByShift;
  }

  private flattenShiftInspectionGroup(group: GroupedBusInspectionResponse): MonitorInspectionItem[] {
    const rows: MonitorInspectionItem[] = [];
    const base = {
      shiftId: group.shift_id,
      busId: group.bus_id,
      fleetNumber: group.fleet_number ?? '',
      dutyNumber: group.duty_number ?? '',
    };
    const inspections = group.inspections;

    if (inspections.external) {
      const ext = inspections.external;
      rows.push({
        ...base,
        inspectionId: ext.inspection_id,
        type: 'External',
        inspectionTime: ext.inspection_time,
        gps: this.gps(ext.inspection_lat, ext.inspection_lon),
        pass: ext.pass_,
        summary: [
          `Tyres: ${this.itemLabel(ext.tyres.pass_)}`,
          `Windows: ${this.itemLabel(ext.windows.pass_)}`,
          `Other: ${this.itemLabel(ext.other.pass_)}`,
        ].join(' | '),
      });
    }

    if (inspections.internal) {
      const internal = inspections.internal;
      rows.push({
        ...base,
        inspectionId: internal.inspection_id,
        type: 'Internal',
        inspectionTime: internal.inspection_time,
        gps: this.gps(internal.inspection_lat, internal.inspection_lon),
        pass: internal.pass_,
        summary: [
          `Fire extinguisher: ${internal.fire_extinguisher_present ? 'Present' : 'Missing'}`,
          `Seats: ${this.itemLabel(internal.seats.pass_)}`,
          `Aisle: ${this.itemLabel(internal.aisle.pass_)}`,
          `Other: ${this.itemLabel(internal.other.pass_)}`,
        ].join(' | '),
      });
    }

    if (inspections.driver) {
      const driver = inspections.driver;
      rows.push({
        ...base,
        inspectionId: driver.inspection_id,
        type: 'Driver',
        inspectionTime: driver.inspection_time,
        gps: this.gps(driver.inspection_lat, driver.inspection_lon),
        pass: driver.pass_,
        summary: [
          `Driver: ${driver.driver_name ?? 'Unknown'}`,
          `PRDP scan: ${this.itemLabel(driver.prdp_scan_succeeded)}`,
          `Driver identified: ${this.itemLabel(driver.driver_identified)}`,
        ].join(' | '),
      });
    }

    for (const passenger of inspections.passenger_counts ?? []) {
      rows.push({
        ...base,
        inspectionId: passenger.inspection_id,
        type: 'Passenger Count',
        inspectionTime: passenger.inspection_time,
        gps: this.gps(passenger.inspection_lat, passenger.inspection_lon),
        pass: passenger.pass_,
        summary: `Seated: ${passenger.number_seated ?? 0} | Standing: ${passenger.number_standing ?? 0} | Total: ${passenger.count ?? 0}`,
      });
    }

    for (const report of inspections.behind_schedule_reports ?? []) {
      rows.push({
        ...base,
        inspectionId: report.inspection_id,
        type: 'Behind Schedule',
        inspectionTime: report.inspection_time,
        gps: this.gps(report.inspection_lat, report.inspection_lon),
        pass: report.pass_,
        summary: `Interval: ${report.behind_schedule_interval ?? 'Not set'}`,
      });
    }

    return rows;
  }

  private buildMonitorChartOptions(shifts: MonitorShiftRow[]): EChartsOption {
    const buckets = new Map<string, Record<string, number>>();
    for (const shift of shifts) {
      const key = new Date(shift.start_time).toISOString().slice(0, 10);
      const bucket = buckets.get(key) ?? {};
      for (const inspectionType of MONITOR_INSPECTION_TYPES) {
        bucket[inspectionType] ??= 0;
      }
      for (const inspection of shift.inspections) {
        bucket[inspection.type] = (bucket[inspection.type] ?? 0) + 1;
      }
      buckets.set(key, bucket);
    }

    const dateFormatter = new Intl.DateTimeFormat('en-ZA', {
      day: '2-digit',
      month: '2-digit',
    });
    const dateKeys = [...buckets.keys()].sort();
    const labels = dateKeys.map((key) => dateFormatter.format(new Date(`${key}T00:00:00`)));
    const valuesByType = new Map<string, number[]>();

    for (const inspectionType of MONITOR_INSPECTION_TYPES) {
      const values = dateKeys.map((key) => buckets.get(key)?.[inspectionType] ?? 0);
      if (values.some((value) => value > 0) || dateKeys.length === 0) {
        valuesByType.set(inspectionType, values);
      }
    }

    return {
      color: MONITOR_INSPECTION_TYPE_COLORS,
      tooltip: { trigger: 'axis', axisPointer: { type: 'line' } },
      legend: {
        top: 0,
        data: [...valuesByType.keys()],
        textStyle: { color: '#374151', fontWeight: 700 },
      },
      grid: { left: 46, right: 24, top: 52, bottom: 42 },
      xAxis: {
        type: 'category',
        data: labels,
        axisLabel: { color: '#4b5563', fontWeight: 600 },
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        axisLabel: { color: '#4b5563' },
        splitLine: { lineStyle: { color: '#e5e7eb' } },
      },
      series: [...valuesByType.entries()].map(([inspectionType, values]) => ({
        name: inspectionType,
        type: 'line' as const,
        stack: 'inspection-count',
        smooth: true,
        symbolSize: 7,
        areaStyle: { opacity: 0.16 },
        emphasis: { focus: 'series' as const },
        data: values,
      })),
    };
  }

  private monitorKey(shift: ShiftResponse): string {
    return shift.user_id || this.loggedBy(shift).toLowerCase();
  }

  private gps(lat: number, lon: number): string {
    return `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
  }

  private loggedBy(shift: ShiftResponse): string {
    const nameParts = [shift.user_name, shift.user_surname].filter(Boolean);
    return nameParts.length > 0 ? nameParts.join(' ') : 'Unknown';
  }

  private duration(start: string, end: string): string {
    const diffMs = Math.max(Date.parse(end) - Date.parse(start), 0);
    const totalMinutes = Math.floor(diffMs / 60000);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return `${hours}h ${minutes}m`;
  }

  private itemLabel(value: boolean | null | undefined): string {
    if (value === true) return 'Pass';
    if (value === false) return 'Fail';
    return 'Not set';
  }
}
