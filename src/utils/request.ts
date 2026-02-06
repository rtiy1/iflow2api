import { invoke } from '@tauri-apps/api/core';

// Check if running in Tauri
export const isTauri = (): boolean => {
  return typeof window !== 'undefined' && (window as any).__TAURI__ !== undefined;
};

// Generic request function
export async function request<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  if (isTauri()) {
    return await invoke<T>(command, args);
  }
  // Fallback for web mode - use fetch
  const response = await fetch(`/api/${command}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(args || {}),
  });
  return await response.json();
}

// API endpoints wrapper
export const api = {
  // Service control
  startService: (port: number) => request<void>('start_service', { port }),
  stopService: () => request<void>('stop_service'),
  getServiceStatus: () => request<ServiceStatus>('get_service_status'),

  // Stats
  getStats: () => request<Stats>('get_stats'),
  getSystemInfo: () => request<SystemInfo>('get_system_info'),

  // Config
  getConfig: () => request<Config>('get_config'),
  saveConfig: (config: Config) => request<void>('save_config', { config }),

  // Logs
  getLogs: () => request<LogEntry[]>('get_logs'),
  clearLogs: () => request<void>('clear_logs'),

  // OAuth
  getOAuthCreds: () => request<Record<string, unknown> | null>('get_oauth_creds'),
  startOAuth: () => request<{ status: string; credentials: Record<string, unknown> }>('start_oauth'),
  deleteOAuth: () => request<void>('delete_oauth_creds'),
};

import type { Config, ServiceStatus, Stats, SystemInfo, LogEntry } from '../types';
