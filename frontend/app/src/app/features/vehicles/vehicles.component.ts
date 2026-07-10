import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
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

import { VehicleService } from '../../core/api/api/vehicle.service';
import type { VehicleResponse } from '../../core/api/model/vehicleResponse';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-vehicles',
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
  templateUrl: './vehicles.component.html',
  styleUrl: './vehicles.component.css',
})
export class VehiclesComponent implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly vehicleApi = inject(VehicleService);

  readonly session = this.auth.session;
  readonly vehicles = signal<VehicleResponse[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly total = signal(0);

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
      command: () => this.closeMenu(),
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
  ];

  ngOnInit(): void {
    if (!this.auth.isLoggedIn()) {
      this.router.navigate(['/login']);
      return;
    }

    this.loadVehicles();
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

  openLiveMapForVehicle(vehicle: VehicleResponse): void {
    if (!vehicle.smart_fleet_device_id) {
      return;
    }

    this.menuVisible = false;
    this.router.navigate(['/smart-fleet'], {
      queryParams: {
        deviceId: vehicle.smart_fleet_device_id,
        vehicle: vehicle.registration_number ?? vehicle.fleet_number ?? vehicle.vin,
      },
    });
  }

  openAnalytics(): void {
    this.menuVisible = false;
    this.router.navigate(['/analytics']);
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

  statusSeverity(isActive: boolean): 'success' | 'danger' {
    return isActive ? 'success' : 'danger';
  }

  inspectionSeverity(passed: boolean | null | undefined): 'success' | 'danger' | 'secondary' {
    if (passed === true) {
      return 'success';
    }
    if (passed === false) {
      return 'danger';
    }
    return 'secondary';
  }

  inspectionStatusLabel(passed: boolean | null | undefined): string {
    if (passed === true) {
      return 'Passed';
    }
    if (passed === false) {
      return 'Failed';
    }
    return 'No inspection';
  }

  mapTooltip(vehicle: VehicleResponse): string {
    return vehicle.smart_fleet_last_address || 'No Smart Fleet address available';
  }

  private loadVehicles(): void {
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
          if (!response) {
            this.error.set('Vehicle service returned an empty response.');
            this.loading.set(false);
            return;
          }

          this.vehicles.set(response.vehicles ?? []);
          this.total.set(response.total ?? response.vehicles?.length ?? 0);
          this.loading.set(false);
        },
        error: (err) => {
          this.loading.set(false);
          const detail = err?.error?.detail;
          this.error.set(detail ?? 'Could not load vehicles.');
        },
      });
  }
}
