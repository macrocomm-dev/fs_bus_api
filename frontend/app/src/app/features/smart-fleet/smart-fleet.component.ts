import { CommonModule } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { Router } from '@angular/router';

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
export class SmartFleetComponent implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly smartFleet = inject(SmartFleetService);

  readonly session = this.auth.session;
  readonly iframeUrl = signal<string | null>(null);
  readonly iframeSrc = signal<SafeResourceUrl | null>(null);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  menuVisible = true;
  readonly navigationItems: MenuItem[] = [
    {
      label: 'Vehicles',
      icon: 'pi pi-car',
      command: () => this.openVehicles(),
    },
    {
      label: 'Live Map',
      icon: 'pi pi-map',
      command: () => this.closeMenu(),
    },
    {
      label: 'Inspections',
      icon: 'pi pi-search',
      command: () => this.closeMenu(),
    },
    {
      label: 'Shifts',
      icon: 'pi pi-calendar',
      command: () => this.closeMenu(),
    },
    {
      label: 'Reports',
      icon: 'pi pi-chart-bar',
      command: () => this.openReporting(),
    },
  ];

  ngOnInit(): void {
    if (!this.auth.isLoggedIn()) {
      this.router.navigate(['/login']);
      return;
    }

    this.loadIframeUrl();
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

  openInNewWindow(): void {
    const url = this.iframeUrl();
    if (!url) return;
    window.open(url, '_blank', 'noopener,noreferrer');
  }

  retry(): void {
    this.loadIframeUrl();
  }

  logout(): void {
    this.auth.logout();
  }

  private loadIframeUrl(): void {
    this.loading.set(true);
    this.error.set(null);

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
        this.loading.set(false);
      },
      error: (err) => {
        this.loading.set(false);
        const detail = err?.error?.detail;
        this.error.set(detail ?? 'Could not load Smart Fleet.');
      },
    });
  }
}