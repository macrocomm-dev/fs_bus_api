import { inject, Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap } from 'rxjs/operators';
import { Observable } from 'rxjs';
import {
  AuthSession,
  UserLoginRequest,
  UserLoginResponse,
  UserRefreshResponse,
} from '../models/auth.models';
import { environment } from '../../../environments/environment';

const SESSION_KEY = 'fs_bus_session';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  readonly session = signal<AuthSession | null>(this.loadSession());

  login(email: string, password: string): Observable<UserLoginResponse> {
    const payload: UserLoginRequest = { email, password };
    return this.http
      .post<UserLoginResponse>(`${environment.apiUrl}/auth/get_token`, payload)
      .pipe(tap((res) => this.persistSession(res)));
  }

  refresh(refreshToken: string): Observable<UserRefreshResponse> {
    return this.http
      .post<UserRefreshResponse>(`${environment.apiUrl}/auth/refresh`, {
        refresh_token: refreshToken,
      })
      .pipe(tap((res) => this.persistSession(res)));
  }

  logout(): void {
    localStorage.removeItem(SESSION_KEY);
    this.session.set(null);
    this.router.navigate(['/login']);
  }

  isLoggedIn(): boolean {
    const s = this.session();
    if (!s) return false;
    if (!s.expiresAt) return true;
    return new Date(s.expiresAt) > new Date();
  }

  getAccessToken(): string | null {
    return this.session()?.accessToken ?? null;
  }

  private persistSession(res: UserLoginResponse | UserRefreshResponse): void {
    const session: AuthSession = {
      accessToken: res.access_token,
      refreshToken: res.refresh_token,
      expiresAt: res.expires_at,
      role: res.role,
      userId: res.user_id,
      name: res.name,
      surname: res.surname,
    };
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    this.session.set(session);
  }

  private loadSession(): AuthSession | null {
    try {
      const raw = localStorage.getItem(SESSION_KEY);
      return raw ? (JSON.parse(raw) as AuthSession) : null;
    } catch {
      return null;
    }
  }
}
