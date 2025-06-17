'use client';

// Force dynamic rendering to avoid SSR issues with auth
export const dynamic = 'force-dynamic';

import React, { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Layout from '@/components/Layout';
import { useAuth } from '@/contexts/AuthContext';
import { jobApi, Job } from '@/services/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { 
  Plus, 
  CheckCircle, 
  XCircle, 
  Clock, 
  Loader2,
  Play,
  Square,
  Trash2
} from 'lucide-react';

interface JobWithStats extends Job {
  total_hashes?: number;
  cracked_hashes?: number;
  success_rate?: number;
}

export default function JobsPage() {
  const { user } = useAuth();
  const [jobs, setJobs] = useState<JobWithStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const router = useRouter();

  const fetchJobs = useCallback(async () => {
    try {
      // Use getAllJobs for admin users, getJobs for regular users
      const data = user?.role === 'admin' 
        ? await jobApi.getAllJobs()
        : await jobApi.getJobs();
      
      // Fetch stats for completed jobs
      const jobsWithStats = await Promise.all(
        data.map(async (job) => {
          if (job.status.toLowerCase() === 'completed') {
            try {
              const stats = await jobApi.getJobStats(job.id);
              return { ...job, ...stats };
            } catch {
              return job;
            }
          }
          return job;
        })
      );
      
      setJobs(jobsWithStats);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch jobs');
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (user) {
      fetchJobs();
      // Poll for updates every 10 seconds
      const interval = setInterval(fetchJobs, 10000);
      return () => clearInterval(interval);
    }
  }, [user, fetchJobs]);

  const getStatusIcon = (status: Job['status']) => {
    const lowerStatus = status.toLowerCase();
    switch (lowerStatus) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-500" />;
      case 'running':
      case 'instance_creating':
      case 'queued':
        return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />;
      default:
        return <Clock className="h-5 w-5 text-gray-500" />;
    }
  };

  const getStatusBadge = (status: Job['status']) => {
    const statusStyles: Record<string, string> = {
      'ready_to_start': 'bg-slate-800/50 text-slate-300 border border-slate-600/50',
      'queued': 'bg-amber-900/30 text-amber-400 border border-amber-500/50',
      'instance_creating': 'bg-blue-900/30 text-blue-400 border border-blue-500/50',
      'running': 'bg-emerald-900/30 text-emerald-400 border border-emerald-500/50',
      'paused': 'bg-orange-900/30 text-orange-400 border border-orange-500/50',
      'cancelling': 'bg-red-900/30 text-red-400 border border-red-500/50',
      'completed': 'bg-emerald-900/30 text-emerald-400 border border-emerald-500/50',
      'failed': 'bg-red-900/30 text-red-400 border border-red-500/50',
      'cancelled': 'bg-slate-800/50 text-slate-300 border border-slate-600/50',
    };

    const lowerStatus = status.toLowerCase();
    const styleClass = statusStyles[lowerStatus] || 'bg-slate-800/50 text-slate-300 border border-slate-600/50';

    const displayStatus = status.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase());

    return (
      <span className={`px-2 py-1 text-xs font-medium rounded-md ${styleClass}`}>
        {displayStatus}
      </span>
    );
  };

  const getStatusBadgeClass = (status: string) => {
    const lowerStatus = status.toLowerCase();
    switch (lowerStatus) {
      case 'completed': 
        return 'bg-emerald-900/30 text-emerald-400 border border-emerald-500/50';
      case 'failed': 
        return 'bg-red-900/30 text-red-400 border border-red-500/50';
      case 'running':
      case 'instance_creating':
      case 'queued':
        return 'bg-blue-900/30 text-blue-400 border border-blue-500/50';
      case 'cancelled':
        return 'bg-slate-800/50 text-slate-300 border border-slate-600/50';
      case 'ready_to_start':
        return 'bg-amber-900/30 text-amber-400 border border-amber-500/50';
      default:
        return 'bg-slate-800/50 text-slate-300 border border-slate-600/50';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const handleJobAction = async (jobId: string, action: 'start' | 'stop') => {
    try {
      if (action === 'start') {
        await jobApi.startJob(jobId);
      } else {
        await jobApi.stopJob(jobId);
      }
      fetchJobs(); // Refresh the list
    } catch (err: any) {
      setError(err.response?.data?.detail || `Failed to ${action} job`);
    }
  };

  const handleDeleteJob = async (jobId: string, jobName: string) => {
    if (!confirm(`Are you sure you want to delete the job "${jobName}"? This action cannot be undone.`)) {
      return;
    }

    try {
      await jobApi.deleteJob(jobId);
      fetchJobs(); // Refresh the list
      setError(''); // Clear any existing errors
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete job');
    }
  };

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
            <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-blue-400/40 to-transparent"></div>
            <div className="absolute bottom-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-slate-500/40 to-transparent"></div>
          </div>
          <div className="relative flex justify-between items-center">
            <div>
              <h1 className="text-4xl font-bold text-slate-100 tracking-tight">
                <span className="text-blue-400 font-black">Jobs</span>
              </h1>
              <p className="text-slate-400 mt-2 font-medium">
                {user?.role === 'admin' 
                  ? 'Manage all password cracking jobs' 
                  : 'Manage your password cracking jobs'
                }
              </p>
            </div>
            <Button 
              onClick={() => router.push('/jobs/new')} 
              className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 text-white border-0 rounded-lg font-semibold shadow-lg transition-all duration-200 px-6 py-3"
            >
              <Plus className="h-4 w-4 mr-2" />
              New Job
            </Button>
          </div>
        </div>

        {error && (
          <Alert variant="destructive">
            {error}
          </Alert>
        )}

        {/* Jobs List */}
        <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm">
          <CardHeader className="border-b border-slate-700/50">
            <CardTitle className="text-xl font-semibold text-slate-200">
              {user?.role === 'admin' ? 'All Jobs' : 'Your Jobs'} ({jobs.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            {jobs.length === 0 ? (
              <div className="text-center py-12 text-slate-400">
                <div className="p-4 bg-slate-800/50 rounded-lg mb-4 inline-block">
                  <Plus className="h-12 w-12 text-slate-400" />
                </div>
                <p className="mb-4 text-sm">
                  {user?.role === 'admin' 
                    ? 'No jobs found. No users have created any jobs yet.' 
                    : 'No jobs found. Create your first job to get started.'
                  }
                </p>
                <Button 
                  onClick={() => router.push('/jobs/new')} 
                  className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 text-white border-0 rounded-lg font-semibold shadow-lg transition-all duration-200"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Create Job
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {jobs.map((job: JobWithStats) => (
                  <div
                    key={job.id}
                    className="flex items-center justify-between p-4 rounded-lg border border-slate-700/60 bg-white/5 hover:bg-white/10 transition-all duration-200 shadow-sm backdrop-blur-sm"
                  >
                    <div 
                      className="flex items-center space-x-4 flex-1 cursor-pointer"
                      onClick={() => router.push(`/jobs/${job.id}`)}
                    >
                      <div className="flex items-center space-x-3">
                        {getStatusIcon(job.status)}
                        <span className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium ${getStatusBadgeClass(job.status)}`}>
                          {job.status.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase())}
                        </span>
                      </div>
                      <div className="flex-1 min-w-0 pr-4">
                        <div className="flex items-center gap-2">
                          <h4 className="font-semibold text-slate-200">{job.name}</h4>
                          {user?.role === 'admin' && job.user_id !== user.id && (
                            <span className="px-2 py-0.5 text-xs rounded-md bg-amber-900/30 text-amber-400 border border-amber-500/50">
                              Other User
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-slate-400">
                          <span className="font-medium text-blue-400">{job.hash_type}</span> • Created {formatDate(job.created_at)}
                          {user?.role === 'admin' && job.user_email && (
                            <span className="ml-2 text-blue-400 font-medium">
                              • {job.user_email}
                            </span>
                          )}
                          {job.cracked_hashes !== undefined && (
                            <span className="ml-2 text-emerald-400 font-medium">
                              • {job.cracked_hashes}/{job.total_hashes} cracked
                            </span>
                          )}
                        </p>
                        {job.status_message && ['queued', 'instance_creating', 'running'].includes(job.status.toLowerCase()) && (
                          <div className="bg-blue-900/20 border border-blue-500/50 rounded-md p-2 mt-2 max-w-lg">
                            <p className="text-sm text-blue-300 font-medium">
                              {job.status_message}
                            </p>
                          </div>
                        )}
                        {job.progress > 0 && ['queued', 'instance_creating', 'running'].includes(job.status.toLowerCase()) && (
                          <div className="w-64 mt-2">
                            <div className="flex justify-between text-xs text-slate-400 mb-1">
                              <span>Progress</span>
                              <span className="font-medium text-blue-400">{job.progress}%</span>
                            </div>
                            <div className="w-full bg-slate-700/50 rounded-full h-2">
                              <div 
                                className="bg-gradient-to-r from-blue-500 to-emerald-500 h-2 rounded-full transition-all duration-700 ease-out"
                                style={{ width: `${job.progress}%` }}
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                    
                    <div className="flex items-center space-x-3">
                      {job.success_rate !== undefined && (
                        <div className="text-right">
                          <div className="text-sm font-medium">{job.success_rate}%</div>
                          <div className="text-xs text-muted-foreground">Success</div>
                        </div>
                      )}
                      
                      {getStatusBadge(job.status)}
                      
                      <div className="flex space-x-2">
                        {job.status.toLowerCase() === 'ready_to_start' && (
                          <Button
                            size="sm"
                            onClick={(e: React.MouseEvent) => {
                              e.stopPropagation();
                              handleJobAction(job.id, 'start');
                            }}
                          >
                            <Play className="h-4 w-4" />
                          </Button>
                        )}
                        {['queued', 'instance_creating', 'running'].includes(job.status.toLowerCase()) && (
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={(e: React.MouseEvent) => {
                              e.stopPropagation();
                              handleJobAction(job.id, 'stop');
                            }}
                          >
                            <Square className="h-4 w-4" />
                          </Button>
                        )}
                        {!['queued', 'instance_creating', 'running', 'cancelling'].includes(job.status.toLowerCase()) && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={(e: React.MouseEvent) => {
                              e.stopPropagation();
                              handleDeleteJob(job.id, job.name);
                            }}
                            className="text-red-400 hover:text-red-300 hover:bg-red-900/20 border-red-500/50"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
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