import { CommonModule } from '@angular/common';
import { Component, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ActivatedRoute, Router } from '@angular/router';

import type { MenuItem } from 'primeng/api';
import { AvatarModule } from 'primeng/avatar';
import { ButtonModule } from 'primeng/button';
import { DrawerModule } from 'primeng/drawer';
import { ProgressSpinnerModule } from 'primeng/progressspinner';
import { MenuModule } from 'primeng/menu';
import { TagModule } from 'primeng/tag';
import { ToolbarModule } from 'primeng/toolbar';
import { TooltipModule } from 'primeng/tooltip';

import { AuthService } from '../../core/services/auth.service';
import { SmartFleetService } from '../../core/services/smart-fleet.service';

@Component({
  selector: 'app-smart-fleet',
  standalone: true,
  imports: [
    CommonModule,
    AvatarModule,
    ButtonModule,
    DrawerModule,
    MenuModule,
    ProgressSpinnerModule,
    TagModule,
    ToolbarModule,
    TooltipModule,
  ],
  templateUrl: './smart-fleet.component.html',
  styleUrl: './smart-fleet.component.css',
})
export class SmartFleetComponent implements OnInit, OnDestroy {
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly smartFleet = inject(SmartFleetService);

  readonly session = this.auth.session;
  readonly iframeUrl = signal<string | null>(null);
  readonly iframeSrc = signal<SafeResourceUrl | null>(null);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly iframeLoading = signal(false);
  readonly targetDeviceId = signal<string | null>(null);
  readonly targetVehicle = signal<string | null>(null);
  private iframeRetryAttempted = false;
  private iframeLoadTimer: ReturnType<typeof setTimeout> | null = null;

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
      styleClass: 'nav-item-active',
      command: () => this.closeMenu(),
    },
    {
      label: 'Analytics',
      icon: 'pi pi-chart-line',
      command: () => this.openAnalytics(),
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

  ngOnInit(): void {
    if (!this.auth.isLoggedIn()) {
      this.router.navigate(['/login']);
      return;
    }

    const queryParams = this.route.snapshot.queryParamMap;
    this.targetDeviceId.set(queryParams.get('deviceId'));
    this.targetVehicle.set(queryParams.get('vehicle'));
    this.loadIframeUrl();
  }

  ngOnDestroy(): void {
    this.clearIframeLoadTimer();
  }

  toggleMenu(): void {
    this.menuVisible = !this.menuVisible;
  }

  closeMenu(): void {
    this.menuVisible = false;
  }

  openVehicles(): void {
    this.menuVisible = false;
    this.router.navigate(['/vehicles']);
  }

  openReporting(): void {
    this.menuVisible = false;
    this.router.navigate(['/reporting']);
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

  openInNewWindow(): void {
    const url = this.iframeUrl();
    if (!url) return;
    window.open(url, '_blank', 'noopener,noreferrer');
  }

  retry(): void {
    this.iframeRetryAttempted = false;
    this.loadIframeUrl();
  }

  onIframeLoad(): void {
    this.iframeLoading.set(false);
    this.clearIframeLoadTimer();
  }

  onIframeError(): void {
    this.retryIframeOnce();
  }

  logout(): void {
    this.auth.logout();
  }

  private loadIframeUrl(): void {
    this.loading.set(true);
    this.iframeLoading.set(false);
    this.error.set(null);
    this.clearIframeLoadTimer();

    this.smartFleet.getIframeUrl().subscribe({
      next: (response) => {
        const url = response?.iframe_url;
        if (!url) {
          this.error.set('Smart Fleet did not return a login URL.');
          this.loading.set(false);
          return;
        }

        this.iframeUrl.set(url);
        this.iframeSrc.set(this.sanitizer.bypassSecurityTrustResourceUrl(url));
        this.iframeLoading.set(true);
        this.loading.set(false);
        this.startIframeLoadTimer();
      },
      error: (err) => {
        this.loading.set(false);
        this.iframeLoading.set(false);
        const detail = err?.error?.detail;
        this.error.set(detail ?? 'Could not load Smart Fleet.');
      },
    });
  }

  private startIframeLoadTimer(): void {
    this.clearIframeLoadTimer();
    this.iframeLoadTimer = setTimeout(() => this.retryIframeOnce(), 12000);
  }

  private retryIframeOnce(): void {
    this.clearIframeLoadTimer();
    if (this.iframeRetryAttempted) {
      this.iframeLoading.set(false);
      this.error.set('Smart Fleet did not finish loading. Please retry or open it in a new window.');
      return;
    }

    this.iframeRetryAttempted = true;
    this.iframeSrc.set(null);
    this.loadIframeUrl();
  }

  private clearIframeLoadTimer(): void {
    if (!this.iframeLoadTimer) return;
    clearTimeout(this.iframeLoadTimer);
    this.iframeLoadTimer = null;
  }
}
