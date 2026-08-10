export type UserResponse = {
  id: string;
  username: string;
  email: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type LoginInput = {
  email: string;
  password: string;
};

export type RegisterInput = {
  username: string;
  email: string;
  password: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: "bearer";
};

export type BackendError = {
  detail?:
    | string
    | Array<{
        type?: string;
        loc?: Array<string | number>;
        msg?: string;
        input?: unknown;
      }>;
};