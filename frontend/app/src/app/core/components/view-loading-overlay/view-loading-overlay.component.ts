import { CommonModule } from '@angular/common';
import { Component, computed, inject, input } from '@angular/core';

import { ViewLoadingService } from '../../services/view-loading.service';

@Component({
  selector: 'app-view-loading-overlay',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './view-loading-overlay.component.html',
  styleUrl: './view-loading-overlay.component.css',
})
export class ViewLoadingOverlayComponent {
  private readonly viewLoading = inject(ViewLoadingService);

  readonly active = input(false);
  readonly label = input('Loading view');
  readonly visible = computed(() => this.viewLoading.isActive(this.active()));
}

