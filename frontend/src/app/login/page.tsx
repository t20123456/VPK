'use client';

// Force dynamic rendering to avoid SSR issues with auth
export const dynamic = 'force-dynamic';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/Card';
import { Alert, AlertDescription } from '@/components/ui/Alert';
import { Shield } from 'lucide-react';

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await login({ email, password });
      // Navigation is handled by the auth context
    } catch (err: any) {
      setError(err.message || 'Failed to login. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 px-4 relative overflow-hidden">
      {/* Background Effects */}
      <div className="absolute inset-0 bg-gradient-to-r from-slate-900/50 via-slate-800/30 to-slate-900/50"></div>
      <div className="absolute inset-0 opacity-20">
        <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-blue-400/40 to-transparent"></div>
        <div className="absolute bottom-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-slate-500/40 to-transparent"></div>
        <div className="absolute top-1/4 left-0 w-full h-px bg-gradient-to-r from-transparent via-blue-300/20 to-transparent"></div>
        <div className="absolute bottom-1/4 left-0 w-full h-px bg-gradient-to-r from-transparent via-slate-400/20 to-transparent"></div>
      </div>
      
      <Card className="w-full max-w-md bg-white/5 border border-slate-700/60 rounded-lg shadow-xl backdrop-blur-sm relative z-10">
        <CardHeader className="space-y-6 border-b border-slate-700/50 pb-6">
          <div className="flex items-center justify-center">
            <div className="p-4 bg-gradient-to-r from-blue-600/20 to-blue-700/20 rounded-full border border-blue-500/30">
              <Shield className="h-12 w-12 text-blue-400" />
            </div>
          </div>
          <div className="text-center space-y-2">
            <CardTitle className="text-3xl font-bold text-slate-100 tracking-tight">
              <span className="text-blue-400 font-black">VPK</span>
              <span className="text-slate-300 ml-2 font-normal">Login</span>
            </CardTitle>
            <CardDescription className="text-slate-400 font-medium">
              Enter your credentials to access the portal
            </CardDescription>
          </div>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-6 pt-6">
            {error && (
              <Alert variant="destructive" className="bg-red-900/20 border-red-500/50 text-red-400">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium text-slate-300">
                Email
              </label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={loading}
                className="bg-slate-800/50 border-slate-600/50 text-slate-200 placeholder:text-slate-500 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium text-slate-300">
                Password
              </label>
              <Input
                id="password"
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={loading}
                className="bg-slate-800/50 border-slate-600/50 text-slate-200 placeholder:text-slate-500 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
              />
            </div>
          </CardContent>
          <CardFooter className="flex flex-col space-y-4 pt-6">
            <Button
              type="submit"
              className="w-full bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 text-white border-0 rounded-lg font-semibold shadow-lg transition-all duration-200 py-3"
              loading={loading}
              disabled={loading}
            >
              Sign in
            </Button>
            <p className="text-sm text-center text-slate-400">
              Don&apos;t have an account?{' '}
              <Link href="/register" className="text-blue-400 hover:text-blue-300 hover:underline font-medium transition-colors">
                Sign up
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}