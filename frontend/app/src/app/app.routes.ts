import { Routes } from '@angular/router';
import { LoginComponent } from './features/login/login.component';
import { AnalyticsComponent } from './features/analytics/analytics.component';
import { InspectionsComponent } from './features/inspections/inspections.component';
import { ReportingComponent } from './features/reporting/reporting.component';
import { ShiftsComponent } from './features/shifts/shifts.component';
import { SmartFleetComponent } from './features/smart-fleet/smart-fleet.component';
import { VehicleDetailComponent } from './features/vehicle-detail/vehicle-detail.component';
import { VehiclesComponent } from './features/vehicles/vehicles.component';

export const routes: Routes = [
  { path: '', redirectTo: 'login', pathMatch: 'full' },
  { path: 'login', component: LoginComponent },
  { path: 'home', redirectTo: 'reporting', pathMatch: 'full' },
  { path: 'analytics', component: AnalyticsComponent },
  { path: 'inspections', component: InspectionsComponent },
  { path: 'reporting', component: ReportingComponent },
  { path: 'shifts', component: ShiftsComponent },
  { path: 'smart-fleet', component: SmartFleetComponent },
  { path: 'vehicles', component: VehiclesComponent },
  { path: 'vehicles/:vehicleKey', component: VehicleDetailComponent },
];
