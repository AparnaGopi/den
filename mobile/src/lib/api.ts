export type User = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: 'customer' | 'vendor';
};

export type AuthResponse = {
  user: User;
  access: string;
  refresh: string;
};

export type TokenResponse = {
  access: string;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

const apiBaseUrl = process.env.EXPO_PUBLIC_API_URL?.replace(/\/$/, '');

if (!apiBaseUrl) {
  throw new Error('EXPO_PUBLIC_API_URL is not configured.');
}

function errorMessage(data: unknown): string {
  if (typeof data === 'string') return data;
  if (Array.isArray(data)) return data.map(errorMessage).join(' ');
  if (data && typeof data === 'object') {
    const messages = Object.entries(data).map(([key, value]) => {
      const message = errorMessage(value);
      return key === 'non_field_errors' || key === 'detail' ? message : `${key}: ${message}`;
    });
    if (messages.length) return messages.join(' ');
  }
  return 'Something went wrong. Please try again.';
}

export async function apiRequest<T>(path: string, options: RequestInit = {}, accessToken?: string) {
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);

  const response = await fetch(`${apiBaseUrl}${path}`, { ...options, headers });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    throw new ApiError(errorMessage(data), response.status);
  }

  return data as T;
}

export function registerCustomer(input: {
  email: string;
  password: string;
  password_confirm: string;
  first_name: string;
  last_name: string;
}) {
  return apiRequest<AuthResponse>('/auth/register/customer/', {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function login(email: string, password: string) {
  return apiRequest<AuthResponse>('/auth/login/', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export function refreshAccessToken(refresh: string) {
  return apiRequest<TokenResponse>('/auth/token/refresh/', {
    method: 'POST',
    body: JSON.stringify({ refresh }),
  });
}

export function getCurrentUser(accessToken: string) {
  return apiRequest<User>('/auth/me/', {}, accessToken);
}
