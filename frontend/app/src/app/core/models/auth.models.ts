export interface UserLoginRequest {
  email: string;
  password: string;
}

export interface UserLoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  role: string;
  user_id: string;
  name: string | null;
  surname: string | null;
  expires_at: string | null;
}

export type UserRefreshResponse = UserLoginResponse;

export interface AuthSession {
  accessToken: string;
  refreshToken: string;
  expiresAt: string | null;
  role: string;
  userId: string;
  name: string | null;
  surname: string | null;
}
