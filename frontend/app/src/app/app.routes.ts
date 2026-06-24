import { Routes } from '@angular/router';
import { LoginComponent } from './features/login/login.component';
import { ReportingComponent } from './features/reporting/reporting.component';
import { SmartFleetComponent } from './features/smart-fleet/smart-fleet.component';
import { VehiclesComponent } from './features/vehicles/vehicles.component';

export const routes: Routes = [
  { path: '', redirectTo: 'login', pathMatch: 'full' },
  { path: 'login', component: LoginComponent },
  { path: 'home', redirectTo: 'reporting', pathMatch: 'full' },
  { path: 'reporting', component: ReportingComponent },
  { path: 'smart-fleet', component: SmartFleetComponent },
  { path: 'vehicles', component: VehiclesComponent },
];
