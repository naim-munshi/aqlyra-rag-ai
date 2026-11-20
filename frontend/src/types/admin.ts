export type DailySignup = { date: string; count: number };

export type TrafficRoute = {
  method: string;
  route: string;
  requests: number;
  server_errors: number;
};

export type AdminChatActivity = {
  active_users_last_24h: number;
  active_users_last_7d: number;
  user_messages_last_24h: number;
  user_messages_last_7d: number;
  daily_last_7_utc_days: { date: string; users: number; messages: number }[];
  scope: "persisted_authenticated_user_messages";
};

export type AdminOverview = {
  users: {
    registered_total: number;
    active_accounts: number;
    verified_accounts: number;
    documents_total: number;
    conversations_total: number;
    signups_last_7_days: DailySignup[];
  };
  // Optional until the matching backend change is released.
  chat_activity?: AdminChatActivity;
  traffic: {
    scope: "single_backend_process";
    uptime_seconds: number;
    request_total: number;
    client_errors: number;
    server_errors: number;
    server_error_percent: number;
    average_latency_ms: number;
    rate_limit_exceeded: number;
    routes: TrafficRoute[];
  };
  cloud_storage: {
    claimed: number;
    stale_claimed: number;
    cleanup_candidates: number;
    failed_intents: number;
    scope: "database_aggregate";
  };
  generated_at: string;
};
