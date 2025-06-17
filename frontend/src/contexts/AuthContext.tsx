'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { authApi, User, LoginCredentials, RegisterData } from '@/services/api';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => void;
  isAdmin: boolean;
}

// Default context value for SSR
const defaultContextValue: AuthContextType = {
  user: null,
  loading: false,
  login: async () => {},
  register: async () => {},
  logout: () => {},
  isAdmin: false
};

const AuthContext = createContext<AuthContextType>(defaultContextValue);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // Check if user is logged in on mount - only on client side
  useEffect(() => {
    if (typeof window !== 'undefined') {
      checkAuth();
    }
  }, []);

  const checkAuth = async () => {
    try {
      // Only access localStorage on the client side
      if (typeof window !== 'undefined') {
        const token = localStorage.getItem('access_token');
        if (token) {
          const userData = await authApi.getCurrentUser();
          setUser(userData);
        }
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      if (typeof window !== 'undefined') {
        authApi.logout();
      }
    } finally {
      setLoading(false);
    }
  };

  const login = async (credentials: LoginCredentials) => {
    await authApi.login(credentials);
    // After successful login, get user data
    const userData = await authApi.getCurrentUser();
    setUser(userData);
    if (typeof window !== 'undefined') {
      router.push('/dashboard');
    }
  };

  const register = async (data: RegisterData) => {
    await authApi.register(data);
    // Don't auto-login since account needs admin approval
  };

  const logout = () => {
    if (typeof window !== 'undefined') {
      authApi.logout();
    }
    setUser(null);
    setLoading(true); // Set loading to prevent any UI flash
    if (typeof window !== 'undefined') {
      // Use setTimeout to ensure state updates are processed first
      setTimeout(() => {
        router.replace('/login');
      }, 0);
    }
  };

  const isAdmin = user?.role === 'admin';

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, isAdmin }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  // Always return the context, even if it's the default value
  return useContext(AuthContext);
}