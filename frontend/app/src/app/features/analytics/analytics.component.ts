import { CommonModule } from '@angular/common';
import { Component, inject, OnInit } from '@angular/core';
import { Router } from '@angular/router';

import type { MenuItem } from 'primeng/api';
import { AvatarModule } from 'primeng/avatar';
import { ButtonModule } from 'primeng/button';
import { DrawerModule } from 'primeng/drawer';
import { MenuModule } from 'primeng/menu';
import { TableModule } from 'primeng/table';
import { TagModule } from 'primeng/tag';
import { ToolbarModule } from 'primeng/toolbar';
import { TooltipModule } from 'primeng/tooltip';

import { AuthService } from '../../core/services/auth.service';

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
  distanceCost: string;
  tripDuration: string;
  speedCost: string;
  idleDuration: string;
  highRiskTrips: number;
  afterHoursCost: string;
  score: number;
};

@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [
    CommonModule,
    AvatarModule,
    ButtonModule,
    DrawerModule,
    MenuModule,
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

  readonly session = this.auth.session;
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
  ];

  readonly metricTiles: MetricTile[] = [
    {
      title: 'Distance traveled/cost',
      icon: 'pi pi-arrow-right',
      color: '#1d4ed8',
      primary: '28,705.34 km',
      secondary: 'R 44,888.00',
    },
    {
      title: 'Trip duration',
      icon: 'pi pi-stopwatch',
      color: '#16a34a',
      primary: '699 hrs 43 mins',
    },
    {
      title: 'Speed duration/cost',
      icon: 'pi pi-gauge',
      color: '#d97706',
      primary: '00 hrs 00 mins',
      secondary: 'R 0.00',
    },
    {
      title: 'Excess idle duration',
      icon: 'pi pi-clock',
      color: '#7c3aed',
      primary: '00 hrs 00 mins',
      secondary: 'R 0.00',
    },
    {
      title: 'High risk trips',
      icon: 'pi pi-exclamation-circle',
      color: '#dc2626',
      primary: '13',
    },
    {
      title: 'After hours distance/cost',
      icon: 'pi pi-moon',
      color: '#0891b2',
      primary: '842.97 km',
      secondary: 'R 1,325.04',
    },
  ];

  readonly gaugeScores: GaugeScore[] = [
    {
      label: 'Speeding',
      score: 92,
      color: '#1d4ed8',
    },
    {
      label: 'Cornering',
      score: 88,
      color: '#16a34a',
    },
    {
      label: 'Acceleration',
      score: 84,
      color: '#d97706',
    },
    {
      label: 'After Hours',
      score: 79,
      color: '#0891b2',
    },
    {
      label: 'Braking',
      score: 91,
      color: '#dc2626',
    },
  ];

  readonly vehiclePerformance: VehiclePerformance[] = [
    {
      fleetNo: '1024',
      registration: 'FSB123FS',
      operator: 'Interstate Bus Lines',
      distanceCost: '4,922.18 km / R 7,610.00',
      tripDuration: '112 hrs 18 mins',
      speedCost: '00 hrs 00 mins / R 0.00',
      idleDuration: '00 hrs 00 mins',
      highRiskTrips: 2,
      afterHoursCost: '123.40 km / R 185.10',
      score: 94,
    },
    {
      fleetNo: '1045',
      registration: 'FSB456FS',
      operator: 'Bophelong Transport',
      distanceCost: '3,744.08 km / R 5,880.00',
      tripDuration: '96 hrs 02 mins',
      speedCost: '00 hrs 00 mins / R 0.00',
      idleDuration: '00 hrs 00 mins',
      highRiskTrips: 1,
      afterHoursCost: '88.75 km / R 132.64',
      score: 97,
    },
    {
      fleetNo: '1056',
      registration: 'FSB321FS',
      operator: 'Interstate Bus Lines',
      distanceCost: '5,108.55 km / R 8,050.00',
      tripDuration: '121 hrs 45 mins',
      speedCost: '00 hrs 00 mins / R 0.00',
      idleDuration: '00 hrs 00 mins',
      highRiskTrips: 4,
      afterHoursCost: '181.90 km / R 290.25',
      score: 88,
    },
    {
      fleetNo: '1078',
      registration: 'FSB654FS',
      operator: 'Bophelong Transport',
      distanceCost: '3,996.21 km / R 6,180.00',
      tripDuration: '101 hrs 12 mins',
      speedCost: '00 hrs 00 mins / R 0.00',
      idleDuration: '00 hrs 00 mins',
      highRiskTrips: 3,
      afterHoursCost: '142.12 km / R 224.88',
      score: 91,
    },
    {
      fleetNo: '1090',
      registration: 'FSB987FS',
      operator: 'Interstate Bus Lines',
      distanceCost: '6,934.32 km / R 11,328.00',
      tripDuration: '168 hrs 26 mins',
      speedCost: '00 hrs 00 mins / R 0.00',
      idleDuration: '00 hrs 00 mins',
      highRiskTrips: 3,
      afterHoursCost: '306.80 km / R 492.17',
      score: 90,
    },
  ];

  ngOnInit(): void {
    if (!this.auth.isLoggedIn()) {
      this.router.navigate(['/login']);
    }
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

  scoreSeverity(score: number): 'success' | 'warn' | 'danger' {
    if (score >= 94) return 'success';
    if (score >= 88) return 'warn';
    return 'danger';
  }
}
