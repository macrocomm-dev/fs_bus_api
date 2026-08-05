import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';

import { catchError, forkJoin, of, throwError } from 'rxjs';
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
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { TimelineModule } from 'primeng/timeline';
import { ToolbarModule } from 'primeng/toolbar';
import { TooltipModule } from 'primeng/tooltip';

import { InspectionService } from '../../core/api/api/inspection.service';
import { ImageService } from '../../core/api/api/image.service';
import type { GroupedBusInspectionResponse } from '../../core/api/model/groupedBusInspectionResponse';
import type { SelfieResponse } from '../../core/api/model/selfieResponse';
import { ShiftsService } from '../../core/api/api/shifts.service';
import type { ShiftResponse } from '../../core/api/model/shiftResponse';
import { AuthService } from '../../core/services/auth.service';

type ShiftInspectionItem = {
  inspectionId: number;
  busId: string;
  fleetNumber: string;
  dutyNumber: string;
  type: string;
  inspectionTime: string;
  gps: string;
  pass: boolean | null | undefined;
  summary: string;
};

type ShiftRow = ShiftResponse & {
  loggedBy: string;
  duration: string;
  startGps: string;
  endGps: string;
  inspections: ShiftInspectionItem[];
  selfies: SelfieResponse[];
  inspectionCount: number;
  failedInspectionCount: number;
};

type ShiftInspectionBusGroup = {
  key: string;
  busId: string;
  fleetNumber: string;
  dutyNumber: string;
  inspections: ShiftInspectionItem[];
};

type ShiftLazyLoadEvent = {
  first?: number | null;
  rows?: number | null;
  sortField?: string | string[] | null;
  sortOrder?: number | null;
  multiSortMeta?: { field: string; order: number }[] | null;
};

type ShiftTimelineEvent = {
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
  inspection?: ShiftInspectionItem;
};

@Component({
  selector: 'app-shifts',
  standalone: true,
  imports: [
    CommonModule,
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
    TableModule,
    TagModule,
    TimelineModule,
    ToolbarModule,
    TooltipModule,
  ],
  templateUrl: './shifts.component.html',
  styleUrl: './shifts.component.css',
})
export class ShiftsComponent implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly shiftsApi = inject(ShiftsService);
  private readonly inspectionApi = inject(InspectionService);
  private readonly imageApi = inject(ImageService);

  readonly session = this.auth.session;
  readonly shifts = signal<ShiftRow[]>([]);
  readonly totalRecords = signal(0);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly searchTerm = signal('');
  readonly rowsPerPage = signal(25);
  private lastLazyEvent: ShiftLazyLoadEvent = {
    first: 0,
    rows: 25,
    sortField: 'created_at',
    sortOrder: -1,
  };

  menuVisible = true;
  readonly navigationItems: MenuItem[] = [
    { label: 'Reports', icon: 'pi pi-chart-bar', command: () => this.openReporting() },
    { label: 'Live Map', icon: 'pi pi-map', command: () => this.openSmartFleet() },
    { label: 'Analytics', icon: 'pi pi-chart-line', command: () => this.openAnalytics() },
    { label: 'Vehicles', icon: 'pi pi-car', command: () => this.openVehicles() },
    { label: 'Inspections', icon: 'pi pi-search', command: () => this.openInspections() },
    { label: 'Shifts', icon: 'pi pi-calendar', styleClass: 'nav-item-active', command: () => this.closeMenu() },
    { label: 'Monitors', icon: 'pi pi-users', command: () => this.openMonitors() },
  ];

  ngOnInit(): void {
    if (!this.auth.isLoggedIn()) {
      this.router.navigate(['/login']);
      return;
    }

    this.loadShifts();
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

  openMonitors(): void {
    this.menuVisible = false;
    this.router.navigate(['/monitors']);
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

  inspectionGroupsForShift(row: ShiftRow): ShiftInspectionBusGroup[] {
    const groups = new Map<string, ShiftInspectionBusGroup>();
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

  busGroupLegend(group: ShiftInspectionBusGroup): string {
    const bus = group.busId !== '-' ? `Bus ${group.busId}` : 'Unknown bus';
    const fleet = group.fleetNumber !== '-' ? `Fleet ${group.fleetNumber}` : 'Fleet not set';
    const duty = group.dutyNumber !== '-' ? `Duty ${group.dutyNumber}` : 'Duty not set';
    return `${bus} | ${fleet} | ${duty}`;
  }

  selfieImageSrc(photo: string): string {
    return photo.startsWith('data:image/') ? photo : `data:image/jpeg;base64,${photo}`;
  }

  timelineEventsForShift(row: ShiftRow): ShiftTimelineEvent[] {
    const selfieEvents: ShiftTimelineEvent[] = row.selfies.map((selfie) => ({
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

    const inspectionEvents: ShiftTimelineEvent[] = row.inspections.map((inspection) => ({
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

  onLazyLoad(event: ShiftLazyLoadEvent): void {
    this.lastLazyEvent = event;
    this.loadShifts(event);
  }

  onSearch(value: string, table: { reset: () => void }): void {
    this.searchTerm.set(value);
    table.reset();
  }

  private loadShifts(event: ShiftLazyLoadEvent = this.lastLazyEvent): void {
    this.loading.set(true);
    this.error.set(null);

    const rows = event.rows ?? this.rowsPerPage();
    this.rowsPerPage.set(rows);

    this.shiftsApi
      .getShiftsPagedShiftShiftsPagedGet(
        {
          first: event.first ?? 0,
          rows,
          search: this.searchTerm().trim() || undefined,
          sortField: this.sortField(event),
          sortOrder: this.sortOrder(event),
        },
        'body',
        false,
        { transferCache: false },
      )
      .subscribe({
        next: (response) => {
          const shifts = response.items ?? [];
          const shiftIds = shifts.map((shift) => shift.id);
          this.totalRecords.set(response.total ?? 0);

          if (shiftIds.length === 0) {
            this.shifts.set([]);
            this.loading.set(false);
            return;
          }

          forkJoin({
            inspectionGroups: this.inspectionApi
              .getBusInspectionsByShiftInspectionBusInspectionsByShiftIdsGet(
                { shiftIds },
                'body',
                false,
                { transferCache: false },
              )
              .pipe(
                catchError((err) =>
                  err?.status === 404
                    ? of<GroupedBusInspectionResponse[]>([])
                    : throwError(() => err),
                ),
              ),
            selfies: this.imageApi
              .getSelfiesByShiftImageSelfiesByShiftIdsGet(
                { shiftIds },
                'body',
                false,
                { transferCache: false },
              )
              .pipe(
                catchError((err) =>
                  err?.status === 404 ? of<SelfieResponse[]>([]) : throwError(() => err),
                ),
              ),
          })
            .subscribe({
              next: ({ inspectionGroups, selfies }) => {
                this.shifts.set(this.buildShiftRows(shifts, inspectionGroups ?? [], selfies ?? []));
                this.loading.set(false);
              },
              error: (err) => {
                this.loading.set(false);
                this.error.set(err?.error?.detail ?? 'Could not load shift details.');
              },
            });
        },
        error: (err) => {
          this.loading.set(false);
          this.totalRecords.set(0);
          this.error.set(err?.error?.detail ?? 'Could not load shifts.');
        },
      });
  }

  private buildShiftRows(
    shifts: ShiftResponse[],
    inspectionGroups: GroupedBusInspectionResponse[],
    selfies: SelfieResponse[] = [],
  ): ShiftRow[] {
    const inspectionsByShift = new Map<number, ShiftInspectionItem[]>();
    for (const group of inspectionGroups) {
      const items = this.flattenShiftInspectionGroup(group);
      const existing = inspectionsByShift.get(group.shift_id) ?? [];
      inspectionsByShift.set(group.shift_id, [...existing, ...items]);
    }
    const selfiesByShift = this.groupSelfiesByShift(selfies);

    return shifts.map((shift) => {
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
    });
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

  private sortField(event: ShiftLazyLoadEvent): string {
    const multiSortField = event.multiSortMeta?.[0]?.field;
    const sortField = Array.isArray(event.sortField) ? event.sortField[0] : event.sortField;
    return multiSortField || sortField || 'created_at';
  }

  private sortOrder(event: ShiftLazyLoadEvent): number {
    return event.multiSortMeta?.[0]?.order ?? event.sortOrder ?? -1;
  }

  private flattenShiftInspectionGroup(group: GroupedBusInspectionResponse): ShiftInspectionItem[] {
    const rows: ShiftInspectionItem[] = [];
    const base = {
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
