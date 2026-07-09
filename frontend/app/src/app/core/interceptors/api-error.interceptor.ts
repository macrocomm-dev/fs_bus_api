import { Injectable, inject } from '@angular/core';
import {
  HttpErrorResponse,
  HttpEvent,
  HttpHandler,
  HttpInterceptor,
  HttpRequest,
} from '@angular/common/http';
import { Observable, catchError, throwError } from 'rxjs';

import { ApiErrorToastService } from '../services/api-error-toast.service';

@Injectable()
export class ApiErrorInterceptor implements HttpInterceptor {
  private readonly toast = inject(ApiErrorToastService);

  intercept(request: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    return next.handle(request).pipe(
      catchError((error: unknown) => {
        if (error instanceof HttpErrorResponse) {
          console.error('API request failed', {
            method: request.method,
            url: request.urlWithParams,
            status: error.status,
            statusText: error.statusText,
            error,
          });
          this.toast.showSomethingWentWrong();
        }

        return throwError(() => error);
      }),
    );
  }
}
