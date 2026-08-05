import { Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root',
})
export class ViewLoadingService {
  isActive(value: boolean | null | undefined): boolean {
    return value === true;
  }
}

