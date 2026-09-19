import { createContext, PropsWithChildren, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import {
  ApiError,
  apiRequest,
  getCurrentUser,
  login as loginRequest,
  refreshAccessToken,
  registerCustomer,
  type AuthResponse,
  type User,
} from '@/lib/api';
import { deleteItem, getItem, setItem } from '@/lib/session-storage';

const sessionKey = 'den-auth-session';

type Session = {
  access: string;
  refresh: string;
};

type AuthContextValue = {
  user: User | null;
  status: 'loading' | 'authenticated' | 'unauthenticated';
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (input: {
    email: string;
    password: string;
    password_confirm: string;
    first_name: string;
    last_name: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  authenticatedRequest: <T>(path: string, options?: RequestInit) => Promise<T>;
  clearError: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

async function saveSession(response: AuthResponse) {
  await setItem(sessionKey, JSON.stringify({ access: response.access, refresh: response.refresh }));
}

async function saveTokens(session: Session) {
  await setItem(sessionKey, JSON.stringify(session));
}

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.';
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<AuthContextValue['status']>('loading');
  const [error, setError] = useState<string | null>(null);

  const establishSession = useCallback(async (response: AuthResponse) => {
    await saveSession(response);
    setSession({ access: response.access, refresh: response.refresh });
    setUser(response.user);
    setStatus('authenticated');
    setError(null);
  }, []);

  const restoreSession = useCallback(async () => {
    try {
      const stored = await getItem(sessionKey);
      if (!stored) {
        setStatus('unauthenticated');
        return;
      }

      const storedSession = JSON.parse(stored) as Session;
      let currentSession = storedSession;
      let currentUser: User;

      try {
        currentUser = await getCurrentUser(currentSession.access);
      } catch (restoreError) {
        if (!(restoreError instanceof ApiError) || restoreError.status !== 401) throw restoreError;
        const refreshed = await refreshAccessToken(currentSession.refresh);
        currentSession = { access: refreshed.access, refresh: currentSession.refresh };
        await saveTokens(currentSession);
        currentUser = await getCurrentUser(currentSession.access);
      }

      setSession(currentSession);
      setUser(currentUser);
      setStatus('authenticated');
    } catch {
      try {
        await deleteItem(sessionKey);
      } catch {
        // Preserve the original authentication error if cleanup fails.
      }
      setSession(null);
      setUser(null);
      setStatus('unauthenticated');
    }
  }, []);

  useEffect(() => {
    const restoreTask = setTimeout(() => {
      void restoreSession();
    }, 0);
    return () => clearTimeout(restoreTask);
  }, [restoreSession]);

  const login = useCallback(async (email: string, password: string) => {
    try {
      await establishSession(await loginRequest(email.trim(), password));
    } catch (requestError) {
      setError(getErrorMessage(requestError));
      throw requestError;
    }
  }, [establishSession]);

  const register = useCallback(async (input: {
    email: string;
    password: string;
    password_confirm: string;
    first_name: string;
    last_name: string;
  }) => {
    try {
      await establishSession(await registerCustomer({ ...input, email: input.email.trim() }));
    } catch (requestError) {
      setError(getErrorMessage(requestError));
      throw requestError;
    }
  }, [establishSession]);

  const logout = useCallback(async () => {
    try {
      await deleteItem(sessionKey);
    } catch {
      // Clear in-memory auth even when storage cleanup is unavailable.
    }
    setSession(null);
    setUser(null);
    setError(null);
    setStatus('unauthenticated');
  }, []);

  const authenticatedRequest = useCallback(async <T,>(path: string, options: RequestInit = {}) => {
    if (!session) throw new Error('You need to be signed in.');
    try {
      return await apiRequest<T>(path, options, session.access);
    } catch (requestError) {
      if (!(requestError instanceof ApiError) || requestError.status !== 401) throw requestError;
      const refreshed = await refreshAccessToken(session.refresh);
      const nextSession = { access: refreshed.access, refresh: session.refresh };
      await saveTokens(nextSession);
      setSession(nextSession);
      return apiRequest<T>(path, options, nextSession.access);
    }
  }, [session]);

  const value = useMemo(() => ({
    user,
    status,
    error,
    login,
    register,
    logout,
    authenticatedRequest,
    clearError: () => setError(null),
  }), [user, status, error, login, register, logout, authenticatedRequest]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider.');
  return context;
}
