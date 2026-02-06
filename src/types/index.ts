export interface Config {
  port: number;
  baseUrl: string;
  retry: number;
  timeout: number;
  theme: 'light' | 'dark';
  language: string;
}

export interface ServiceStatus {
  running: boolean;
  port: number;
  pid?: number;
}

export interface Stats {
  total: number;
  success: number;
  error: number;
  successRate: number;
}

export interface SystemInfo {
  cpu: number;
  memory: number;
  uptime: string;
}

export interface Account {
  id: string;
  email: string;
  name?: string;
  apiKey?: string;
}

export interface LogEntry {
  time: string;
  method: string;
  path: string;
  status: number;
  model?: string;
}
