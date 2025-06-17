import axios, { AxiosError } from 'axios';

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000') + '/api/v1';

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Token management
let accessToken: string | null = null;
let refreshToken: string | null = null;

// Helper function to get cookie value
const getCookie = (name: string): string | null => {
  if (typeof document === 'undefined') return null;
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(';').shift() || null;
  return null;
};

// Load tokens from localStorage and cookies on initialization
if (typeof window !== 'undefined') {
  accessToken = localStorage.getItem('access_token') || getCookie('access_token');
  refreshToken = localStorage.getItem('refresh_token') || getCookie('refresh_token');
}

// Request interceptor to add token
api.interceptors.request.use(
  (config) => {
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle token refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as any;

    if (error.response?.status === 401 && !originalRequest._retry && refreshToken) {
      originalRequest._retry = true;

      try {
        const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });

        const { access_token, refresh_token } = response.data;
        setTokens(access_token, refresh_token);
        // Update the module-level variables immediately
        accessToken = access_token;
        refreshToken = refresh_token;

        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return api(originalRequest);
      } catch (refreshError) {
        clearTokens();
        window.location.href = '/';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

// Token management functions
export const setTokens = (access: string, refresh: string) => {
  accessToken = access;
  refreshToken = refresh;
  
  // Store in localStorage
  localStorage.setItem('access_token', access);
  localStorage.setItem('refresh_token', refresh);
  
  // Also store in cookies for middleware access
  document.cookie = `access_token=${access}; path=/; max-age=${7 * 24 * 60 * 60}`; // 7 days
  document.cookie = `refresh_token=${refresh}; path=/; max-age=${30 * 24 * 60 * 60}`; // 30 days
};

export const clearTokens = () => {
  accessToken = null;
  refreshToken = null;
  
  // Clear localStorage
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  
  // Clear cookies
  document.cookie = 'access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
  document.cookie = 'refresh_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
};

export const getTokens = () => ({
  accessToken,
  refreshToken,
});

// Auth API types
export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
}

export interface User {
  id: string;
  email: string;
  role: 'admin' | 'user';
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// Auth API endpoints
export const authApi = {
  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    const response = await api.post('/auth/login', credentials);
    const data = response.data;
    setTokens(data.access_token, data.refresh_token);
    return data;
  },

  register: async (data: RegisterData): Promise<User> => {
    const response = await api.post('/users/register', data);
    return response.data;
  },

  getCurrentUser: async (): Promise<User> => {
    const response = await api.get('/auth/me');
    return response.data;
  },

  logout: () => {
    clearTokens();
  },
};

// Job API types
export interface Job {
  id: string;
  user_id: string;
  name: string;
  hash_type: string;
  word_list?: string;
  rule_list?: string;
  custom_attack?: string;
  hard_end_time?: string;
  instance_type?: string;
  status: 'ready_to_start' | 'queued' | 'instance_creating' | 'running' | 'paused' | 'cancelling' | 'completed' | 'failed' | 'cancelled';
  created_at: string;
  time_started?: string;
  time_finished?: string;
  progress: number;
  estimated_time?: number;
  actual_cost?: number;
  error_message?: string;
  status_message?: string;
  user_email?: string; // Only present for admin endpoints
}

export interface JobCreateRequest {
  name: string;
  hash_type: string;
  word_list?: string;
  rule_files?: string[];
  custom_attack?: string;
  hard_end_time?: string;
  instance_type?: string;
  required_disk_gb?: number;
}

export interface JobTimeEstimate {
  estimated_seconds: number;
  formatted_time: string;
  explanation: string;
  confidence: 'high' | 'medium' | 'low';
  warning: string | null;
}

// Job API endpoints
export const jobApi = {
  getJobs: async (): Promise<Job[]> => {
    const response = await api.get('/jobs/');
    return response.data;
  },

  getAllJobs: async (): Promise<Job[]> => {
    const response = await api.get('/jobs/all');
    return response.data;
  },

  getJob: async (id: string): Promise<Job> => {
    const response = await api.get(`/jobs/${id}`);
    return response.data;
  },

  createJob: async (data: JobCreateRequest): Promise<Job> => {
    const response = await api.post('/jobs/', data);
    return response.data;
  },

  startJob: async (id: string): Promise<Job> => {
    const response = await api.post(`/jobs/${id}/start`);
    return response.data;
  },

  stopJob: async (id: string): Promise<void> => {
    await api.post(`/jobs/${id}/stop`);
  },

  deleteJob: async (id: string): Promise<void> => {
    await api.delete(`/jobs/${id}`);
  },

  getPotFile: async (id: string): Promise<string> => {
    const response = await api.get(`/events/${id}/pot`);
    return response.data;
  },

  getPotFilePreview: async (id: string): Promise<{preview: string; total_lines_shown: number; truncated: boolean}> => {
    const response = await api.get(`/events/${id}/pot/preview`);
    return response.data;
  },

  getJobStats: async (id: string): Promise<{total_hashes: number; cracked_hashes: number; success_rate: number}> => {
    const response = await api.get(`/jobs/${id}/stats`);
    return response.data;
  },

  getJobLogs: async (id: string): Promise<{logs: string}> => {
    const response = await api.get(`/events/${id}/logs`);
    return response.data;
  },

  estimateTime: async (params: {
    hash_mode: string;
    gpu_model: string;
    num_gpus: number;
    num_hashes: number;
    wordlist?: string;
    rule_files?: string[];
    custom_attack?: string;
  }): Promise<JobTimeEstimate> => {
    const response = await api.post('/jobs/estimate-time', params);
    return response.data;
  },
};

// User management API (admin only)
export const userApi = {
  getUsers: async (): Promise<User[]> => {
    const response = await api.get('/users/');
    return response.data;
  },

  getUser: async (id: string): Promise<User> => {
    const response = await api.get(`/users/${id}`);
    return response.data;
  },

  createUser: async (data: RegisterData): Promise<User> => {
    const response = await api.post('/users/', data);
    return response.data;
  },

  updateUser: async (id: string, data: Partial<User>): Promise<User> => {
    const response = await api.patch(`/users/${id}`, data);
    return response.data;
  },

  deleteUser: async (id: string): Promise<void> => {
    await api.delete(`/users/${id}`);
  },
};

// Settings API types
export interface Settings {
  max_cost_per_hour: number;
  max_total_cost: number;
  max_upload_size_mb: number;
  max_hash_file_size_mb: number;
  data_retention_days: number;
  s3_bucket_name?: string;
  s3_region?: string;
  vast_cloud_connection_id?: string;
  aws_configured: boolean;
  vast_configured: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface SettingsUpdate {
  max_cost_per_hour?: number;
  max_total_cost?: number;
  max_upload_size_mb?: number;
  max_hash_file_size_mb?: number;
  data_retention_days?: number;
  s3_bucket_name?: string;
  s3_region?: string;
  vast_cloud_connection_id?: string;
  aws_access_key_id?: string;
  aws_secret_access_key?: string;
  vast_api_key?: string;
}

export interface ConnectionTestResponse {
  status: string;
  message: string;
}

// Settings API endpoints (admin only)
export const settingsApi = {
  getSettings: async (): Promise<Settings> => {
    const response = await api.get('/settings/');
    return response.data;
  },

  updateSettings: async (data: SettingsUpdate): Promise<Settings> => {
    const response = await api.patch('/settings/', data);
    return response.data;
  },

  testAwsConnection: async (): Promise<ConnectionTestResponse> => {
    const response = await api.post('/settings/test-aws');
    return response.data;
  },

  testVastConnection: async (): Promise<ConnectionTestResponse> => {
    const response = await api.post('/settings/test-vast');
    return response.data;
  },
};

// Storage API types
export interface StorageFile {
  key: string;
  name: string;
  size: number;
  last_modified: string;
  type: 'wordlist' | 'rules';
  line_count?: number;  // For wordlists
  rule_count?: number;  // For rule files
  
  // Enhanced metadata fields from catalog (optional)
  uncompressed_size?: number;
  compression_format?: string;
  compression_ratio?: number;
  source?: string;
  tags?: string[];
  description?: string;
  has_metadata?: boolean;
}

export interface UploadResponse {
  detail: string;
  key: string;
  filename: string;
}

export interface StorageHealthResponse {
  status: 'healthy' | 'error' | 'not_configured';
  bucket?: string;
  region?: string;
  detail?: string;
}

// Storage API endpoints
export const storageApi = {
  // Wordlists
  listWordlists: async (): Promise<StorageFile[]> => {
    const response = await api.get('/storage/wordlists');
    return response.data;
  },

  // Enhanced wordlists with catalog metadata
  listEnhancedWordlists: async (): Promise<StorageFile[]> => {
    const response = await api.get('/storage/wordlists/enhanced');
    return response.data;
  },

  uploadWordlist: async (file: File): Promise<UploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/storage/wordlists/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  deleteWordlist: async (key: string): Promise<{detail: string}> => {
    const response = await api.delete(`/storage/wordlists/${encodeURIComponent(key)}`);
    return response.data;
  },

  // Populate wordlist catalog
  populateCatalog: async (maxPages?: number): Promise<{detail: string, total_entries: number, pages_scraped: number}> => {
    const response = await api.post('/storage/wordlists/catalog/build', {
      max_pages: maxPages || 10
    });
    return response.data;
  },

  // Rules
  listRules: async (): Promise<StorageFile[]> => {
    const response = await api.get('/storage/rules');
    return response.data;
  },

  uploadRules: async (file: File): Promise<UploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/storage/rules/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  deleteRules: async (key: string): Promise<{detail: string}> => {
    const response = await api.delete(`/storage/rules/${encodeURIComponent(key)}`);
    return response.data;
  },

  // Health check
  getHealthCheck: async (): Promise<StorageHealthResponse> => {
    const response = await api.get('/storage/health');
    return response.data;
  },
};

// Vast.ai API types
export interface VastOffer {
  id: number;
  num_gpus: number;
  gpu_name: string;
  cpu_cores: number;
  cpu_ram: number;
  gpu_ram: number;
  disk_space: number;
  dph_total: number;
  reliability: number;
  geolocation: string;
  datacenter: boolean;
  verified: boolean;
  compute_cap: number;
  total_flops: number;
}

// Vast.ai API types for pagination
export interface VastOffersResponse {
  offers: VastOffer[];
  pagination: {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
  filters: {
    search: string;
    min_gpus: number;
    max_cost: number;
    gpu_filter: string;
    location_filter: string;
    min_disk_space_gb: number;
  };
}

export interface VastOfferFilters {
  page?: number;
  per_page?: number;
  search?: string;
  min_gpus?: number;
  max_cost?: number;
  gpu_filter?: string;
  location_filter?: string;
  min_disk_space_gb?: number;
}

// Vast.ai API endpoints
export const vastApi = {
  getOffers: async (filters?: VastOfferFilters): Promise<VastOffersResponse> => {
    const params = new URLSearchParams();
    
    if (filters?.page) params.append('page', filters.page.toString());
    if (filters?.per_page) params.append('per_page', filters.per_page.toString());
    if (filters?.search) params.append('search', filters.search);
    if (filters?.min_gpus) params.append('min_gpus', filters.min_gpus.toString());
    if (filters?.max_cost) params.append('max_cost', filters.max_cost.toString());
    if (filters?.gpu_filter) params.append('gpu_filter', filters.gpu_filter);
    if (filters?.location_filter) params.append('location_filter', filters.location_filter);
    if (filters?.min_disk_space_gb) params.append('min_disk_space_gb', filters.min_disk_space_gb.toString());
    
    const response = await api.get(`/vast/offers-for-job?${params.toString()}`);
    return response.data;
  },
};

export default api;