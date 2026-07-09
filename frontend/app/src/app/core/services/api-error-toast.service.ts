import { inject, Injectable } from '@angular/core';
import { MessageService } from 'primeng/api';

@Injectable({ providedIn: 'root' })
export class ApiErrorToastService {
  private readonly messages = inject(MessageService);

  showSomethingWentWrong(): void {
    this.messages.add({
      severity: 'error',
      summary: 'Something went wrong',
      detail: 'Please try again.',
      life: 5000,
    });
  }
}
