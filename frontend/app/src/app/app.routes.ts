import { Routes } from '@angular/router';
import { LoginComponent } from './features/login/login.component';
import { ReportingComponent } from './features/reporting/reporting.component';

export const routes: Routes = [
  { path: '', redirectTo: 'login', pathMatch: 'full' },
  { path: 'login', component: LoginComponent },
  { path: 'home', redirectTo: 'reporting', pathMatch: 'full' },
  { path: 'reporting', component: ReportingComponent },
];
