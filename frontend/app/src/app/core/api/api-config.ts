import { Configuration } from './configuration';
import { environment } from '../../../environments/environment';

export function createApiConfiguration(token?: string): Configuration {
  return new Configuration({
    basePath: environment.apiUrl,
    credentials: token ? { BearerAuth: () => token } : {},
  });
}
