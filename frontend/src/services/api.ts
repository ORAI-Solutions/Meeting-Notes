// API configuration and utilities for connecting to the backend

// Default to window.location.origin (pywebview desktop)

class ApiService {
  private baseUrl: string = typeof window !== 'undefined' && window.location ? window.location.origin : 'http://127.0.0.1:8000';
  private isInitialized: boolean = false;
  private initPromise: Promise<void> | null = null;

  constructor() {
    // Start initialization immediately
    this.initPromise = this.initialize();
  }

  private async initialize(): Promise<void> {
    if (this.isInitialized) return;
    // Use current origin (pywebview desktop serves at http://127.0.0.1:<random_port>)
    this.baseUrl = typeof window !== 'undefined' && window.location ? window.location.origin : this.baseUrl;
    this.isInitialized = true;
  }

  async ensureInitialized(): Promise<void> {
    if (this.initPromise) {
      await this.initPromise;
    }
  }

  async getBaseUrl(): Promise<string> {
    await this.ensureInitialized();
    return this.baseUrl;
  }

  async fetch(path: string, options?: RequestInit): Promise<Response> {
    await this.ensureInitialized();
    const url = `${this.baseUrl}${path}`;
    return fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });
  }

  async get<T>(path: string): Promise<T> {
    const response = await this.fetch(path);
    if (!response.ok) {
      throw new Error(`API request failed: ${response.statusText}`);
    }
    return response.json();
  }

  async post<T>(path: string, body?: any): Promise<T> {
    const response = await this.fetch(path, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) {
      throw new Error(`API request failed: ${response.statusText}`);
    }
    return response.json();
  }

  async put<T>(path: string, body?: any): Promise<T> {
    const response = await this.fetch(path, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) {
      throw new Error(`API request failed: ${response.statusText}`);
    }
    return response.json();
  }

  async delete<T>(path: string): Promise<T> {
    const response = await this.fetch(path, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error(`API request failed: ${response.statusText}`);
    }
    return response.json();
  }

  // WebSocket connection with dynamic URL
  async createWebSocket(path: string): Promise<WebSocket> {
    await this.ensureInitialized();
    const wsUrl = this.baseUrl.replace('http://', 'ws://');
    return new WebSocket(`${wsUrl}${path}`);
  }
}

// Export singleton instance
export const api = new ApiService();

// Export convenience functions
export const apiGet = <T>(path: string) => api.get<T>(path);
export const apiPost = <T>(path: string, body?: any) => api.post<T>(path, body);
export const apiPut = <T>(path: string, body?: any) => api.put<T>(path, body);
export const apiDelete = <T>(path: string) => api.delete<T>(path);
export const apiFetch = (path: string, options?: RequestInit) => api.fetch(path, options);


