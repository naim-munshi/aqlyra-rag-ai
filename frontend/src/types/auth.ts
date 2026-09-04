export type UserResponse = {
  id: string;
  username: string;
  email: string;
  is_active: boolean;
  email_verified_at: string | null;
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

export type RegistrationResponse = UserResponse & {
  verification_required: boolean;
  verification_email_sent: boolean;
};

export type BackendRegistrationResponse = RegistrationResponse & {
  verification_token: string | null;
};

export type VerifyEmailInput = {
  email: string;
  code: string;
};

export type ResendVerificationInput = {
  email: string;
};

export type GoogleCredentialInput = {
  credential: string;
};

export type MessageResponse = {
  message: string;
};

export type VerificationDispatchResponse = MessageResponse & {
  verification_token: string | null;
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
