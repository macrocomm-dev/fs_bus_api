import { Configuration } from './configuration';
import { environment } from '../../../environments/environment';

function getStoredAccessToken(): string | undefined {
  try {
    const raw = globalThis.localStorage?.getItem('fs_bus_session');
    if (!raw) return undefined;
    const parsed = JSON.parse(raw) as { accessToken?: string | null };
    return parsed.accessToken ?? undefined;
  } catch {
    return undefined;
  }
}

export function createApiConfiguration(): Configuration {
  return new Configuration({
    basePath: environment.apiUrl,
    credentials: {
      HTTPBearer: () => getStoredAccessToken(),
    },
  });
}
