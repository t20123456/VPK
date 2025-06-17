'use client';

import React, { useEffect, useState } from 'react';

// Force dynamic rendering to avoid SSR issues with auth
export const dynamic = 'force-dynamic';
import Layout from '@/components/Layout';
import { useAuth } from '@/contexts/AuthContext';
import { userApi, User } from '@/services/api';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { 
  Users, 
  UserPlus, 
  Edit2, 
  Trash2, 
  Shield, 
  User as UserIcon, 
  CheckCircle, 
  XCircle 
} from 'lucide-react';
import { useRouter } from 'next/navigation';

export default function AdminPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const router = useRouter();

  // Form state
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    role: 'user' as 'admin' | 'user',
    is_active: true
  });

  useEffect(() => {
    // Check if user is admin
    if (currentUser?.role !== 'admin') {
      router.push('/dashboard');
      return;
    }
    fetchUsers();
  }, [currentUser, router]);

  const fetchUsers = async () => {
    try {
      const data = await userApi.getUsers();
      setUsers(data);
    } catch (error: any) {
      setError('Failed to fetch users: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    try {
      if (editingUser) {
        // Update existing user (exclude password if empty)
        const updateData: Partial<typeof formData> = { ...formData };
        if (!updateData.password) {
          delete updateData.password;
        }
        await userApi.updateUser(editingUser.id, updateData);
      } else {
        // Create new user
        await userApi.createUser(formData);
      }
      
      resetForm();
      fetchUsers();
    } catch (error: any) {
      setError(error.response?.data?.detail || error.message || 'Operation failed');
    }
  };

  const handleEdit = (user: User) => {
    setEditingUser(user);
    setFormData({
      email: user.email,
      password: '',
      role: user.role,
      is_active: user.is_active
    });
    setShowAddForm(true);
  };

  const handleDelete = async (userId: string) => {
    if (!confirm('Are you sure you want to delete this user?')) return;

    try {
      await userApi.deleteUser(userId);
      fetchUsers();
    } catch (error: any) {
      setError('Failed to delete user: ' + (error.response?.data?.detail || error.message));
    }
  };

  const resetForm = () => {
    setFormData({
      email: '',
      password: '',
      role: 'user',
      is_active: true
    });
    setEditingUser(null);
    setShowAddForm(false);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  if (currentUser?.role !== 'admin') {
    return null; // Will redirect
  }

  if (loading) {
    return (
      <Layout>
        <div className="flex justify-center items-center h-64">
          <Spinner />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-8">
        {/* Header */}
        <div className="relative overflow-hidden bg-gradient-to-r from-slate-900 to-slate-800 border border-slate-700/60 rounded-lg p-8 shadow-xl">
          <div className="absolute inset-0 bg-gradient-to-r from-slate-900/50 via-slate-800/30 to-slate-900/50"></div>
          <div className="absolute inset-0 opacity-30">
            <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-purple-400/40 to-transparent"></div>
            <div className="absolute bottom-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-slate-500/40 to-transparent"></div>
          </div>
          <div className="relative flex justify-between items-center">
            <div>
              <h1 className="text-4xl font-bold text-slate-100 tracking-tight">
                <span className="text-purple-400 font-black">Admin</span>
                <span className="text-slate-300 ml-3 font-normal">Panel</span>
              </h1>
              <p className="text-slate-400 mt-2 font-medium">
                Manage users and system settings
              </p>
            </div>
            <Button 
              onClick={() => setShowAddForm(true)}
              disabled={showAddForm}
              className="bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-500 hover:to-purple-600 text-white border-0 rounded-lg font-semibold shadow-lg transition-all duration-200 px-6 py-3"
            >
              <UserPlus className="h-4 w-4 mr-2" />
              Add User
            </Button>
          </div>
        </div>

        {error && (
          <Alert variant="destructive" className="bg-red-900/20 border-red-500/50 text-red-400">
            {error}
          </Alert>
        )}

        {/* Add/Edit User Form */}
        {showAddForm && (
          <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm">
            <CardHeader className="border-b border-slate-700/50">
              <CardTitle className="text-xl font-semibold text-slate-200">
                {editingUser ? 'Edit User' : 'Add New User'}
              </CardTitle>
              <CardDescription className="text-slate-400">
                {editingUser ? 'Update user information' : 'Create a new user account'}
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2 text-slate-300">Email</label>
                    <Input
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      required
                      className="bg-slate-800/50 border-slate-600/50 text-slate-200 focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/20"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2 text-slate-300">
                      Password {editingUser && '(leave blank to keep current)'}
                    </label>
                    <Input
                      type="password"
                      value={formData.password}
                      onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                      required={!editingUser}
                      className="bg-slate-800/50 border-slate-600/50 text-slate-200 focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/20"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2 text-slate-300">Role</label>
                    <select
                      value={formData.role}
                      onChange={(e) => setFormData({ ...formData, role: e.target.value as 'admin' | 'user' })}
                      className="w-full p-2 border rounded-lg bg-slate-800/50 border-slate-600/50 text-slate-200 focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/20"
                    >
                      <option value="user">User</option>
                      <option value="admin">Admin</option>
                    </select>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="is_active"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                    className="rounded border-slate-600 bg-slate-800/50 text-purple-500 focus:ring-purple-500/20"
                  />
                  <label htmlFor="is_active" className="text-sm font-medium text-slate-300">Active</label>
                </div>
                <div className="flex space-x-2">
                  <Button type="submit" className="bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-500 hover:to-purple-600 text-white border-0 rounded-lg font-semibold shadow-lg transition-all duration-200">
                    {editingUser ? 'Update User' : 'Create User'}
                  </Button>
                  <Button type="button" variant="outline" onClick={resetForm} className="border-slate-600 text-slate-300 hover:bg-white/10 hover:text-slate-100 hover:border-slate-500 bg-transparent rounded-lg font-semibold shadow-md transition-all duration-200">
                    Cancel
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {/* Users List */}
        <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm">
          <CardHeader className="border-b border-slate-700/50">
            <CardTitle className="text-xl font-semibold text-slate-200 flex items-center">
              <Users className="h-5 w-5 mr-2 text-purple-400" />
              Users ({users.length})
            </CardTitle>
            <CardDescription className="text-slate-400">Manage user accounts and permissions</CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            {users.length === 0 ? (
              <div className="text-center py-12 text-slate-400">
                <div className="p-4 bg-slate-800/50 rounded-lg mb-4 inline-block">
                  <Users className="h-12 w-12 text-purple-400" />
                </div>
                <p className="mb-4 text-sm">
                  No users found in the system.
                </p>
                <Button 
                  onClick={() => setShowAddForm(true)} 
                  className="bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-500 hover:to-purple-600 text-white border-0 rounded-lg font-semibold shadow-lg transition-all duration-200"
                >
                  <UserPlus className="h-4 w-4 mr-2" />
                  Add First User
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {users.map((user) => (
                <div
                  key={user.id}
                  className="flex items-center justify-between p-4 rounded-lg border border-slate-700/60 bg-white/5 hover:bg-white/10 transition-all duration-200 shadow-sm backdrop-blur-sm"
                >
                  <div className="flex items-center space-x-4">
                    <div className="p-2 rounded-full bg-slate-800/50">
                      {user.role === 'admin' ? (
                        <Shield className="h-5 w-5 text-purple-400" />
                      ) : (
                        <UserIcon className="h-5 w-5 text-slate-400" />
                      )}
                    </div>
                    <div>
                      <h4 className="font-semibold text-slate-200">{user.email}</h4>
                      <p className="text-xs text-slate-400">
                        Created: {formatDate(user.created_at)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-4">
                    <div className="text-right">
                      <span className={`px-2 py-1 text-xs font-medium rounded-md ${
                        user.role === 'admin' 
                          ? 'bg-purple-900/30 text-purple-400 border border-purple-500/50' 
                          : 'bg-slate-800/50 text-slate-300 border border-slate-600/50'
                      }`}>
                        {user.role.charAt(0).toUpperCase() + user.role.slice(1)}
                      </span>
                      <div className="flex items-center justify-end mt-1">
                        {user.is_active ? (
                          <CheckCircle className="h-4 w-4 text-emerald-400" />
                        ) : (
                          <XCircle className="h-4 w-4 text-red-400" />
                        )}
                        <span className="text-xs ml-1 text-slate-400">
                          {user.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </div>
                    </div>
                    <div className="flex space-x-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleEdit(user)}
                        className="border-purple-500/50 text-purple-400 hover:bg-purple-900/20 hover:text-purple-300 hover:border-purple-400 bg-transparent rounded-lg font-medium shadow-sm transition-all duration-200"
                      >
                        <Edit2 className="h-4 w-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDelete(user.id)}
                        disabled={user.id === currentUser?.id}
                        className="border-red-500/50 text-red-400 hover:bg-red-900/20 hover:text-red-300 hover:border-red-400 bg-transparent rounded-lg font-medium shadow-sm transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </Layout>
  );
}