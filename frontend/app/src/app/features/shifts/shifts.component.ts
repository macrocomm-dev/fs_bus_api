import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';

import type { MenuItem } from 'primeng/api';
import { AvatarModule } from 'primeng/avatar';
import { ButtonModule } from 'primeng/button';
import { DrawerModule } from 'primeng/drawer';
import { IconFieldModule } from 'primeng/iconfield';
import { InputIconModule } from 'primeng/inputicon';
import { InputTextModule } from 'primeng/inputtext';
import { MenuModule } from 'primeng/menu';
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { ToolbarModule } from 'primeng/toolbar';
import { TooltipModule } from 'primeng/tooltip';

import { ShiftsService } from '../../core/api/api/shifts.service';
import type { ShiftResponse } from '../../core/api/model/shiftResponse';
import { AuthService } from '../../core/services/auth.service';

type ShiftRow = ShiftResponse & {
  loggedBy: string;
  duration: string;
  startGps: string;
  endGps: string;
};

@Component({
  selector: 'app-shifts',
  standalone: true,
  imports: [
    CommonModule,
    AvatarModule,
    ButtonModule,
    DrawerModule,
    IconFieldModule,
    InputIconModule,
    InputTextModule,
    MenuModule,
    TableModule,
    TagModule,
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

  readonly session = this.auth.session;
  readonly shifts = signal<ShiftRow[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  menuVisible = true;
  readonly navigationItems: MenuItem[] = [
    { label: 'Reports', icon: 'pi pi-chart-bar', command: () => this.openReporting() },
    { label: 'Live Map', icon: 'pi pi-map', command: () => this.openSmartFleet() },
    { label: 'Analytics', icon: 'pi pi-chart-line', command: () => this.openAnalytics() },
    { label: 'Vehicles', icon: 'pi pi-car', command: () => this.openVehicles() },
    { label: 'Inspections', icon: 'pi pi-search', command: () => this.openInspections() },
    { label: 'Shifts', icon: 'pi pi-calendar', styleClass: 'nav-item-active', command: () => this.closeMenu() },
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

  logout(): void {
    this.auth.logout();
  }

  private loadShifts(): void {
    this.loading.set(true);
    this.error.set(null);

    this.shiftsApi
      .getAllShiftsShiftShiftsGet(
        { limit: 500 },
        'body',
        false,
        { transferCache: false },
      )
      .subscribe({
        next: (response) => {
          this.shifts.set(
            (response ?? [])
              .map((shift) => ({
                ...shift,
                loggedBy: this.loggedBy(shift),
                duration: this.duration(shift.start_time, shift.end_time),
                startGps: this.gps(shift.start_lat, shift.start_lon),
                endGps: this.gps(shift.end_lat, shift.end_lon),
              }))
              .sort((a, b) => Date.parse(b.start_time) - Date.parse(a.start_time)),
          );
          this.loading.set(false);
        },
        error: (err) => {
          this.loading.set(false);
          this.error.set(err?.error?.detail ?? 'Could not load shifts.');
        },
      });
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
}
