'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/Button';
import { 
  Menu, 
  X, 
  Home, 
  Briefcase, 
  Settings, 
  LogOut, 
  User,
  ChevronDown,
  Shield,
  Database
} from 'lucide-react';
import { cn } from '@/utils/cn';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const isAuthenticated = !!user;

  const navigation = [
    { name: 'Dashboard', href: '/dashboard', icon: Home },
    { name: 'Jobs', href: '/jobs', icon: Briefcase },
    { name: 'Storage', href: '/storage', icon: Database },
    ...(user?.role === 'admin' ? [
      { name: 'Admin', href: '/admin', icon: Shield },
      { name: 'Settings', href: '/settings', icon: Settings }
    ] : []),
  ];

  const isActive = (href: string) => pathname === href;

  const handleLogout = async () => {
    await logout();
  };

  if (!isAuthenticated) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Navigation */}
      <nav className="bg-white/5 backdrop-blur-sm border-b border-slate-700/60">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            {/* Logo and Desktop Navigation */}
            <div className="flex items-center">
              <Link href="/dashboard" className="flex items-center">
                <Shield className="h-8 w-8 text-blue-400" />
                <span className="ml-2 text-xl font-bold text-slate-100 tracking-tight">VPK</span>
              </Link>
              
              {/* Desktop Navigation */}
              <div className="hidden md:ml-10 md:flex md:space-x-4">
                {navigation.map((item) => {
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.name}
                      href={item.href}
                      className={cn(
                        'flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-all duration-200',
                        isActive(item.href)
                          ? 'bg-blue-600/20 text-blue-300 border border-blue-500/50 shadow-sm'
                          : 'text-slate-300 hover:bg-white/10 hover:text-slate-100 border border-transparent hover:border-slate-600/50'
                      )}
                    >
                      <Icon className="mr-2 h-4 w-4" />
                      {item.name}
                    </Link>
                  );
                })}
              </div>
            </div>

            {/* Desktop User Menu */}
            <div className="hidden md:flex md:items-center md:space-x-4">
              <div className="relative z-50">
                <button
                  onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
                  className="flex items-center space-x-3 rounded-lg px-3 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 hover:text-slate-100 transition-all duration-200 border border-transparent hover:border-slate-600/50"
                >
                  <div className="flex items-center space-x-2">
                    <User className="h-5 w-5" />
                    <span>{user?.email}</span>
                    <ChevronDown className="h-4 w-4" />
                  </div>
                </button>

                {/* User Dropdown Menu */}
                {isUserMenuOpen && (
                  <div className="absolute right-0 z-[9999] mt-2 w-48 origin-top-right rounded-lg bg-slate-800/95 backdrop-blur-sm border border-slate-700/60 shadow-xl">
                    <div className="p-2" role="menu">
                      <button
                        onClick={handleLogout}
                        className="flex w-full items-center px-3 py-2 text-sm font-medium text-slate-300 hover:bg-red-600/20 hover:text-red-400 transition-all duration-200 rounded-md"
                      >
                        <LogOut className="mr-2 h-4 w-4" />
                        Logout
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Mobile menu button */}
            <div className="flex md:hidden">
              <button
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="inline-flex items-center justify-center rounded-lg p-2 text-slate-300 hover:bg-white/10 hover:text-slate-100 transition-all duration-200"
              >
                {isMobileMenuOpen ? (
                  <X className="h-6 w-6" />
                ) : (
                  <Menu className="h-6 w-6" />
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Navigation */}
        {isMobileMenuOpen && (
          <div className="md:hidden">
            <div className="space-y-1 px-2 pb-3 pt-2 sm:px-3">
              {navigation.map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={cn(
                      'flex items-center px-3 py-2 rounded-lg text-base font-medium transition-all duration-200',
                      isActive(item.href)
                        ? 'bg-blue-600/20 text-blue-300 border border-blue-500/50 shadow-sm'
                        : 'text-slate-300 hover:bg-white/10 hover:text-slate-100 border border-transparent hover:border-slate-600/50'
                    )}
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    <Icon className="mr-3 h-5 w-5" />
                    {item.name}
                  </Link>
                );
              })}
              
              {/* Mobile User Info and Actions */}
              <div className="border-t pt-4 pb-3">
                <div className="flex items-center px-3 py-2">
                  <User className="h-8 w-8 text-blue-400" />
                  <div className="ml-3">
                    <div className="text-base font-semibold text-slate-100">
                      {user?.email || 'User'}
                    </div>
                    <div className="text-sm text-slate-400">
                      {user?.role === 'admin' ? 'Admin' : 'User'}
                    </div>
                  </div>
                </div>
                <div className="mt-3 space-y-1">
                  <Link
                    href="/profile"
                    className="flex items-center px-3 py-2 rounded-lg text-base font-medium text-slate-300 hover:bg-white/10 hover:text-slate-100 transition-all duration-200"
                    onClick={() => setIsMobileMenuOpen(false)}
                  >
                    <User className="mr-3 h-5 w-5" />
                    Profile
                  </Link>
                  <button
                    onClick={handleLogout}
                    className="flex w-full items-center px-3 py-2 rounded-lg text-base font-medium text-slate-300 hover:bg-red-600/20 hover:text-red-400 transition-all duration-200"
                  >
                    <LogOut className="mr-3 h-5 w-5" />
                    Logout
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </nav>

      {/* Page Content */}
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {children}
      </main>
    </div>
  );
};

export default Layout;