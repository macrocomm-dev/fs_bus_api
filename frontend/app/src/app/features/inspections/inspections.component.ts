import { CommonModule } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';

import type { MenuItem } from 'primeng/api';
import { AvatarModule } from 'primeng/avatar';
import { ButtonModule } from 'primeng/button';
import { DrawerModule } from 'primeng/drawer';
import { FloatLabelModule } from 'primeng/floatlabel';
import { IconFieldModule } from 'primeng/iconfield';
import { InputIconModule } from 'primeng/inputicon';
import { InputTextModule } from 'primeng/inputtext';
import { MenuModule } from 'primeng/menu';
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { ToolbarModule } from 'primeng/toolbar';
import { TooltipModule } from 'primeng/tooltip';

import { InspectionService } from '../../core/api/api/inspection.service';
import { VehicleService } from '../../core/api/api/vehicle.service';
import type { GroupedBusInspectionResponse } from '../../core/api/model/groupedBusInspectionResponse';
import type { VehicleResponse } from '../../core/api/model/vehicleResponse';
import { AuthService } from '../../core/services/auth.service';

type InspectionRow = {
  inspectionId: number;
  shiftId: number;
  busId: string;
  fleetNumber: string;
  registrationNumber: string;
  dutyNumber: string;
  type: string;
  inspectionTime: string;
  gps: string;
  pass: boolean | null | undefined;
  notes: string | null | undefined;
  summary: string;
  details: InspectionDetailItem[];
};

type InspectionDetailItem = {
  label: string;
  value: string;
  status?: boolean | null | undefined;
  note?: string | null | undefined;
  photoCount?: number;
};

type InspectionMetricTile = {
  type: string;
  label: string;
  icon: string;
  color: string;
  failed: number;
  total: number;
  vehicles: number;
};

const INSPECTION_METRIC_TYPES = [
  { type: 'External', label: 'External', icon: 'pi pi-car', color: '#1d4ed8' },
  { type: 'Internal', label: 'Internal', icon: 'pi pi-wrench', color: '#16a34a' },
  { type: 'Driver', label: 'Driver', icon: 'pi pi-id-card', color: '#d97706' },
  { type: 'Passenger Count', label: 'Passenger', icon: 'pi pi-users', color: '#7c3aed' },
  { type: 'Behind Schedule', label: 'Behind Schedule', icon: 'pi pi-clock', color: '#dc2626' },
];

@Component({
  selector: 'app-inspections',
  standalone: true,
  imports: [
    CommonModule,
    AvatarModule,
    ButtonModule,
    DrawerModule,
    FloatLabelModule,
    IconFieldModule,
    InputIconModule,
    InputTextModule,
    MenuModule,
    TableModule,
    TagModule,
    ToolbarModule,
    TooltipModule,
  ],
  templateUrl: './inspections.component.html',
  styleUrl: './inspections.component.css',
})
export class InspectionsComponent implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly inspectionApi = inject(InspectionService);
  private readonly vehicleApi = inject(VehicleService);
  private readonly vehicleRegistrationByKey = new Map<string, string>();

  readonly session = this.auth.session;
  readonly inspections = signal<InspectionRow[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly selectedFailedType = signal<string | null>(null);

  readonly inspectionMetricTiles = computed<InspectionMetricTile[]>(() =>
    INSPECTION_METRIC_TYPES.map((metric) => {
      const rows = this.inspections().filter((row) => row.type === metric.type);
      const failedRows = rows.filter((row) => row.pass === false);

      return {
        ...metric,
        failed: failedRows.length,
        total: rows.length,
        vehicles: new Set(rows.map((row) => row.busId).filter(Boolean)).size,
      };
    }),
  );

  readonly visibleInspections = computed(() => {
    const selectedType = this.selectedFailedType();
    if (!selectedType) return this.inspections();
    return this.inspections().filter((row) => row.type === selectedType && row.pass === false);
  });

  menuVisible = true;
  readonly navigationItems: MenuItem[] = [
    { label: 'Reports', icon: 'pi pi-chart-bar', command: () => this.openReporting() },
    { label: 'Live Map', icon: 'pi pi-map', command: () => this.openSmartFleet() },
    { label: 'Analytics', icon: 'pi pi-chart-line', command: () => this.openAnalytics() },
    { label: 'Vehicles', icon: 'pi pi-car', command: () => this.openVehicles() },
    { label: 'Inspections', icon: 'pi pi-search', styleClass: 'nav-item-active', command: () => this.closeMenu() },
    { label: 'Shifts', icon: 'pi pi-calendar', command: () => this.openShifts() },
  ];

  ngOnInit(): void {
    if (!this.auth.isLoggedIn()) {
      this.router.navigate(['/login']);
      return;
    }

    this.loadInspections();
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

  detailValue(item: InspectionDetailItem): string {
    if (item.status !== undefined) {
      return this.itemLabel(item.status);
    }
    return item.value;
  }

  filterFailedType(type: string): void {
    this.selectedFailedType.set(this.selectedFailedType() === type ? null : type);
  }

  private loadInspections(): void {
    this.loading.set(true);
    this.error.set(null);

    this.vehicleApi
      .getVehiclesVehicleVehiclesGet(
        { page: 1, pageSize: 500 },
        'body',
        false,
        { transferCache: false },
      )
      .subscribe({
        next: (response) => {
          this.indexVehicleRegistrations(response?.vehicles ?? []);
          this.fetchInspections();
        },
        error: () => {
          this.vehicleRegistrationByKey.clear();
          this.fetchInspections();
        },
      });
  }

  private fetchInspections(): void {
    this.inspectionApi
      .getAllBusInspectionsInspectionBusInspectionsGet(
        { limit: 500 },
        'body',
        false,
        { transferCache: false },
      )
      .subscribe({
        next: (response) => {
          this.inspections.set(this.flattenInspectionGroups(response ?? []));
          this.loading.set(false);
        },
        error: (err) => {
          this.loading.set(false);
          this.error.set(err?.error?.detail ?? 'Could not load inspections.');
        },
      });
  }

  private flattenInspectionGroups(groups: GroupedBusInspectionResponse[]): InspectionRow[] {
    const rows: InspectionRow[] = [];
    for (const group of groups) {
      const base = {
        shiftId: group.shift_id,
        busId: group.bus_id,
        fleetNumber: group.fleet_number ?? '',
        registrationNumber: this.registrationFor(group.bus_id, group.fleet_number),
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
          notes: ext.notes,
          summary: [
            `Tyres: ${this.itemLabel(ext.tyres.pass_)}`,
            `Windows: ${this.itemLabel(ext.windows.pass_)}`,
            `Other: ${this.itemLabel(ext.other.pass_)}`,
          ].join(' | '),
          details: [
            this.checkDetail('Tyres', ext.tyres.pass_, ext.tyres.reason, ext.tyres.photos?.length),
            this.checkDetail('Windows', ext.windows.pass_, ext.windows.reason, ext.windows.photos?.length),
            this.checkDetail('Other', ext.other.pass_, ext.other.reason, ext.other.photos?.length),
          ],
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
          notes: internal.notes,
          summary: [
            `Fire extinguisher: ${internal.fire_extinguisher_present ? 'Present' : 'Missing'}`,
            `Seats: ${this.itemLabel(internal.seats.pass_)}`,
            `Aisle: ${this.itemLabel(internal.aisle.pass_)}`,
            `Other: ${this.itemLabel(internal.other.pass_)}`,
          ].join(' | '),
          details: [
            {
              label: 'Fire extinguisher',
              value: internal.fire_extinguisher_present ? 'Present' : 'Missing',
              status: internal.fire_extinguisher_present,
              note: internal.fire_extinguisher_present ? null : 'Fire extinguisher missing',
            },
            this.checkDetail('Seats', internal.seats.pass_, internal.seats.reason, internal.seats.photos?.length),
            this.checkDetail('Aisle', internal.aisle.pass_, internal.aisle.reason, internal.aisle.photos?.length),
            this.checkDetail('Other', internal.other.pass_, internal.other.reason, internal.other.photos?.length),
          ],
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
          notes: driver.notes,
          summary: [
            `Driver: ${driver.driver_name ?? 'Unknown'}`,
            `PRDP scan: ${this.itemLabel(driver.prdp_scan_succeeded)}`,
            `Driver identified: ${this.itemLabel(driver.driver_identified)}`,
            driver.driver_fail_reason ? `Reason: ${driver.driver_fail_reason}` : '',
          ]
            .filter(Boolean)
            .join(' | '),
          details: [
            { label: 'Driver', value: driver.driver_name ?? 'Unknown' },
            this.checkDetail('PRDP scan', driver.prdp_scan_succeeded, null, driver.photos?.length),
            { label: 'PRDP expiry', value: driver.prdp_expiry_date ? new Date(driver.prdp_expiry_date).toLocaleDateString('en-ZA') : 'Not set' },
            this.checkDetail('Driver identified', driver.driver_identified, driver.driver_fail_reason),
          ],
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
          notes: passenger.notes,
          summary: `Seated: ${passenger.number_seated ?? 0} | Standing: ${passenger.number_standing ?? 0} | Total: ${passenger.count ?? 0}`,
          details: [
            { label: 'Seated passengers', value: String(passenger.number_seated ?? 0) },
            { label: 'Standing passengers', value: String(passenger.number_standing ?? 0) },
            { label: 'Total passengers', value: String(passenger.count ?? 0) },
          ],
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
          notes: report.notes,
          summary: `Interval: ${report.behind_schedule_interval ?? 'Not set'}`,
          details: [
            { label: 'Delayed start interval', value: report.behind_schedule_interval ?? 'Not set' },
          ],
        });
      }
    }

    return rows.sort((a, b) => Date.parse(b.inspectionTime) - Date.parse(a.inspectionTime));
  }

  private gps(lat: number, lon: number): string {
    return `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
  }

  private indexVehicleRegistrations(vehicles: VehicleResponse[]): void {
    this.vehicleRegistrationByKey.clear();

    for (const vehicle of vehicles) {
      const registration = vehicle.registration_number;
      if (!registration) {
        continue;
      }

      for (const key of this.vehicleKeys(vehicle.vin, vehicle.fleet_number, vehicle.registration_number)) {
        this.vehicleRegistrationByKey.set(key, registration);
      }
    }
  }

  private registrationFor(...values: Array<string | null | undefined>): string {
    for (const key of this.vehicleKeys(...values)) {
      const registration = this.vehicleRegistrationByKey.get(key);
      if (registration) {
        return registration;
      }
    }
    return '';
  }

  private vehicleKeys(...values: Array<string | null | undefined>): string[] {
    const keys = new Set<string>();
    for (const value of values) {
      if (!value) {
        continue;
      }

      const normalized = this.normalizeVehicleKey(value);
      if (normalized) {
        keys.add(normalized);
      }

      for (const token of value.match(/[A-Za-z0-9]+/g) ?? []) {
        const tokenKey = this.normalizeVehicleKey(token);
        if (tokenKey && tokenKey.length >= 3) {
          keys.add(tokenKey);
        }
      }
    }
    return [...keys];
  }

  private normalizeVehicleKey(value: string): string {
    return value.replace(/[^A-Za-z0-9]/g, '').toLowerCase();
  }

  private itemLabel(value: boolean | null | undefined): string {
    if (value === true) return 'Pass';
    if (value === false) return 'Fail';
    return 'Not set';
  }

  private checkDetail(
    label: string,
    status: boolean | null | undefined,
    note?: string | null,
    photoCount?: number,
  ): InspectionDetailItem {
    return {
      label,
      value: this.itemLabel(status),
      status,
      note,
      photoCount,
    };
  }
}
