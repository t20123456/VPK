'use client';

import React, { useEffect, useState } from 'react';

// Force dynamic rendering to avoid SSR issues with auth
export const dynamic = 'force-dynamic';
import Layout from '@/components/Layout';
import { useAuth } from '@/contexts/AuthContext';
import { jobApi, Job } from '@/services/api';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { Shield, Briefcase, Clock, CheckCircle, Plus, Play, XCircle, Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';

interface JobWithStats extends Job {
  total_hashes?: number;
  cracked_hashes?: number;
  success_rate?: number;
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [jobs, setJobs] = useState<JobWithStats[]>([]);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    fetchJobs();
    // Poll for updates every 5 seconds
    const interval = setInterval(fetchJobs, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchJobs = async () => {
    try {
      const data = await jobApi.getJobs();
      
      // Fetch job statistics for completed jobs
      const jobsWithStats = await Promise.all(
        data.map(async (job) => {
          if (job.status.toLowerCase() === 'completed') {
            try {
              const stats = await jobApi.getJobStats(job.id);
              return {
                ...job,
                total_hashes: stats.total_hashes,
                cracked_hashes: stats.cracked_hashes,
                success_rate: stats.success_rate
              };
            } catch (error) {
              console.log(`No stats available for job ${job.name}:`, error);
              return {
                ...job,
                total_hashes: 0,
                cracked_hashes: 0,
                success_rate: 0
              };
            }
          }
          return job;
        })
      );
      
      setJobs(jobsWithStats);
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
    } finally {
      setLoading(false);
    }
  };

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
      case 'paused':
      case 'cancelling':
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

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  // Calculate stats
  const totalJobs = jobs.length;
  const activeJobs = jobs.filter(job => 
    ['queued', 'instance_creating', 'running', 'paused', 'cancelling'].includes(job.status.toLowerCase())
  ).length;
  const completedJobs = jobs.filter(job => job.status.toLowerCase() === 'completed').length;
  const failedJobs = jobs.filter(job => ['failed', 'cancelled'].includes(job.status.toLowerCase())).length;
  
  // Calculate password cracking success rate based on actual results
  const completedJobsWithData = jobs.filter(job => 
    job.status.toLowerCase() === 'completed' && job.cracked_hashes !== undefined
  );
  const totalCrackedPasswords = completedJobsWithData.reduce((sum, job) => sum + (job.cracked_hashes || 0), 0);
  const totalHashes = completedJobsWithData.reduce((sum, job) => sum + (job.total_hashes || 0), 0);
  
  // Overall success rate: percentage of all hashes that were cracked
  const successRate = totalHashes > 0 
    ? Math.round((totalCrackedPasswords / totalHashes) * 100) 
    : 0;

  const recentJobs = jobs
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner />
      </div>
    );
  }

  return (
    <Layout>
      <div className="space-y-8">
        {/* Welcome Section */}
        <div className="relative overflow-hidden bg-gradient-to-r from-slate-900 to-slate-800 border border-slate-700/60 rounded-lg p-8 shadow-xl">
          <div className="absolute inset-0 bg-gradient-to-r from-slate-900/50 via-slate-800/30 to-slate-900/50"></div>
          <div className="absolute inset-0 opacity-30">
            <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-blue-400/40 to-transparent"></div>
            <div className="absolute bottom-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-slate-500/40 to-transparent"></div>
          </div>
          <div className="relative flex justify-between items-center">
            <div>
              <h1 className="text-4xl font-bold text-slate-100 tracking-tight">
                <span className="text-blue-400 font-black">VPK</span>
                <span className="text-slate-300 ml-3 font-normal">Dashboard</span>
              </h1>
              <p className="text-slate-400 mt-2 font-medium">
                Welcome back, <span className="text-blue-400 font-semibold">{user?.email.split('@')[0]}</span>
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

        {/* Stats Cards */}
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-5">
          <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm hover:bg-white/10 transition-all duration-200">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">Total Jobs</CardTitle>
              <div className="p-2 bg-slate-800/50 rounded-md">
                <Briefcase className="h-4 w-4 text-slate-300" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-slate-100">{totalJobs}</div>
              <p className="text-xs text-slate-500 mt-1">
                {totalJobs === 0 ? 'No jobs yet' : 'All time'}
              </p>
            </CardContent>
          </Card>

          <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm hover:bg-white/10 transition-all duration-200">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">Active Jobs</CardTitle>
              <div className="p-2 bg-amber-900/50 rounded-md">
                <Clock className="h-4 w-4 text-amber-400" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-amber-400">{activeJobs}</div>
              <p className="text-xs text-slate-500 mt-1">
                {activeJobs === 0 ? 'Idle' : 'Running'}
              </p>
            </CardContent>
          </Card>

          <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm hover:bg-white/10 transition-all duration-200">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">Completed</CardTitle>
              <div className="p-2 bg-emerald-900/50 rounded-md">
                <CheckCircle className="h-4 w-4 text-emerald-400" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-emerald-400">{completedJobs}</div>
              <p className="text-xs text-slate-500 mt-1">
                {completedJobs === 0 ? 'None yet' : 'Successful'}
              </p>
            </CardContent>
          </Card>

          <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm hover:bg-white/10 transition-all duration-200">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">Passwords Cracked</CardTitle>
              <div className="p-2 bg-orange-900/50 rounded-md">
                <Shield className="h-4 w-4 text-orange-400" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-orange-400">{totalCrackedPasswords.toLocaleString()}</div>
              <p className="text-xs text-slate-500 mt-1">
                {totalCrackedPasswords === 0 ? 'None yet' : 'Total found'}
              </p>
            </CardContent>
          </Card>

          <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm hover:bg-white/10 transition-all duration-200">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">Success Rate</CardTitle>
              <div className="p-2 bg-blue-900/50 rounded-md">
                <CheckCircle className="h-4 w-4 text-blue-400" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-blue-400">
                {totalHashes > 0 ? `${successRate}%` : '—'}
              </div>
              <p className="text-xs text-slate-500 mt-1">
                {totalHashes === 0 ? 'No data' : 'Overall efficiency'}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Quick Actions */}
        <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm">
          <CardHeader className="border-b border-slate-700/50">
            <CardTitle className="text-xl font-semibold text-slate-200">Quick Actions</CardTitle>
            <CardDescription className="text-slate-400">Common tasks and navigation</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-4 pt-6">
            <Button 
              onClick={() => router.push('/jobs/new')} 
              className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 text-white border-0 rounded-lg font-semibold shadow-lg transition-all duration-200"
            >
              <Plus className="h-4 w-4 mr-2" />
              New Job
            </Button>
            <Button 
              variant="outline" 
              onClick={() => router.push('/jobs')} 
              className="border border-slate-600 text-slate-300 hover:bg-slate-700/50 bg-transparent font-semibold rounded-lg shadow-md transition-all duration-200"
            >
              <Briefcase className="h-4 w-4 mr-2" />
              View Jobs
            </Button>
            {user?.role === 'admin' && (
              <Button 
                variant="outline" 
                onClick={() => router.push('/admin')} 
                className="border border-slate-600 text-slate-300 hover:bg-slate-700/50 bg-transparent font-semibold rounded-lg shadow-md transition-all duration-200"
              >
                <Shield className="h-4 w-4 mr-2" />
                Admin Panel
              </Button>
            )}
          </CardContent>
        </Card>

        {/* Recent Jobs */}
        <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm">
          <CardHeader className="border-b border-slate-700/50">
            <CardTitle className="text-xl font-semibold text-slate-200">Recent Jobs</CardTitle>
            <CardDescription className="text-slate-400">Your latest password cracking operations</CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            {recentJobs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-slate-400">
                <div className="p-4 bg-slate-800/50 rounded-lg mb-4">
                  <Briefcase className="h-12 w-12 text-slate-400" />
                </div>
                <p className="text-center mb-4 text-sm">No jobs found</p>
                <Button 
                  onClick={() => router.push('/jobs/new')} 
                  className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 text-white border-0 rounded-lg font-semibold shadow-lg transition-all duration-200"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Create First Job
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {recentJobs.map((job: JobWithStats) => (
                  <div
                    key={job.id}
                    className="group p-4 rounded-lg border border-slate-700/60 bg-white/5 hover:bg-white/10 cursor-pointer transition-all duration-200 shadow-sm"
                    onClick={() => router.push(`/jobs/${job.id}`)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-4">
                        <div className="p-2 bg-slate-800/50 rounded-md">
                          {getStatusIcon(job.status)}
                        </div>
                        <div>
                          <h4 className="font-semibold text-slate-200 mb-1">{job.name}</h4>
                          <p className="text-sm text-slate-400">
                            <span className="font-medium text-blue-400">{job.hash_type}</span> <span className="text-slate-500">•</span> {formatDate(job.created_at)}
                            {job.cracked_hashes !== undefined && (
                              <span className="ml-2 text-emerald-400 font-medium">
                                <span className="text-slate-500">•</span> {job.cracked_hashes.toLocaleString()}/{job.total_hashes?.toLocaleString()} cracked
                              </span>
                            )}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-4">
                        {job.progress > 0 && ['running', 'instance_creating', 'queued'].includes(job.status.toLowerCase()) && (
                          <div className="w-28">
                            <div className="w-full bg-slate-700/50 rounded-full h-2">
                              <div 
                                className="bg-gradient-to-r from-blue-500 to-emerald-500 h-2 rounded-full transition-all duration-700 ease-out"
                                style={{ width: `${job.progress}%` }}
                              />
                            </div>
                            <div className="text-xs text-blue-400 mt-1 text-center font-medium">
                              {job.progress}%
                            </div>
                          </div>
                        )}
                        <div>{getStatusBadge(job.status)}</div>
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