export type DailySignup = { date: string; count: number };

export type TrafficRoute = {
  method: string;
  route: string;
  requests: number;
  server_errors: number;
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
  generated_at: string;
};
