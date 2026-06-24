import { HttpClient, HttpHeaders } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { AuthService } from './auth.service';

export interface SmartFleetIframeUrlResponse {
  iframe_url: string;
}

@Injectable({ providedIn: 'root' })
export class SmartFleetService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);

  getIframeUrl(): Observable<SmartFleetIframeUrlResponse> {
    const token = this.auth.getAccessToken();
    const headers = token
      ? new HttpHeaders({ Authorization: `Bearer ${token}` })
      : undefined;

    return this.http.get<SmartFleetIframeUrlResponse>(
      `${environment.apiUrl}/smartfleet/iframe-login-url`,
      { headers },
    );
  }
}