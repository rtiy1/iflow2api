import { create } from 'zustand';
import type { Config, ServiceStatus } from '../types';

interface ConfigState {
  config: Config | null;
  status: ServiceStatus;
  loading: boolean;
  loadConfig: () => Promise<void>;
  saveConfig: (config: Config) => Promise<void>;
  startService: (port: number) => Promise<void>;
  stopService: () => Promise<void>;
  refreshStatus: () => Promise<void>;
}

const defaultConfig: Config = {
  port: 8000,
  baseUrl: 'https://apis.iflow.cn/v1',
  retry: 3,
  timeout: 60,
  theme: 'dark',
  language: 'zh-CN',
};

export const useConfigStore = create<ConfigState>((set) => ({
  config: null,
  status: { running: false, port: 0 },
  loading: false,

  loadConfig: async () => {
    try {
      // Try to load from localStorage for web mode
      const saved = localStorage.getItem('iflow2api_config');
      if (saved) {
        set({ config: { ...defaultConfig, ...JSON.parse(saved) } });
      } else {
        set({ config: defaultConfig });
      }
    } catch (error) {
      console.error('Failed to load config:', error);
      set({ config: defaultConfig });
    }
  },

  saveConfig: async (newConfig) => {
    try {
      localStorage.setItem('iflow2api_config', JSON.stringify(newConfig));
      set({ config: newConfig });
    } catch (error) {
      console.error('Failed to save config:', error);
    }
  },

  startService: async (port) => {
    set({ loading: true });
    try {
      // In Tauri mode, this would call the Rust backend
      // For now, just simulate the status change
      set({
        status: { running: true, port },
        loading: false,
      });
    } catch (error) {
      console.error('Failed to start service:', error);
      set({ loading: false });
    }
  },

  stopService: async () => {
    set({ loading: true });
    try {
      set({
        status: { running: false, port: 0 },
        loading: false,
      });
    } catch (error) {
      console.error('Failed to stop service:', error);
      set({ loading: false });
    }
  },

  refreshStatus: async () => {
    // This would fetch actual status from backend
  },
}));
