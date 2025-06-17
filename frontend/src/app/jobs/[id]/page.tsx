'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Layout from '@/components/Layout';
import { jobApi, Job } from '@/services/api';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { 
  ArrowLeft, 
  Play, 
  Square, 
  Download, 
  Clock, 
  CheckCircle, 
  XCircle, 
  FileText,
  Key,
  Target,
  TrendingUp,
  Trash2,
  Loader2
} from 'lucide-react';

interface JobWithStats extends Job {
  total_hashes?: number;
  cracked_hashes?: number;
  success_rate?: number;
}

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params?.id as string;

  const [job, setJob] = useState<JobWithStats | null>(null);
  const [logs, setLogs] = useState<string>('');
  const [potFilePreview, setPotFilePreview] = useState<{preview: string; total_lines_shown: number; truncated: boolean} | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  const fetchJobDetails = useCallback(async () => {
    try {
      // Fetch job details
      const jobData = await jobApi.getJob(jobId);
      
      // Fetch additional data for completed jobs
      if (jobData.status.toLowerCase() === 'completed') {
        const [stats, logs, potPreview] = await Promise.allSettled([
          jobApi.getJobStats(jobId),
          jobApi.getJobLogs(jobId),
          jobApi.getPotFilePreview(jobId)
        ]);

        const jobWithStats = {
          ...jobData,
          ...(stats.status === 'fulfilled' ? stats.value : {}),
        };

        setJob(jobWithStats);
        setLogs(logs.status === 'fulfilled' ? logs.value.logs : 'No logs available');
        setPotFilePreview(potPreview.status === 'fulfilled' ? potPreview.value : null);
      } else {
        setJob(jobData);
        // For non-completed jobs, still try to get logs
        try {
          const jobLogs = await jobApi.getJobLogs(jobId);
          setLogs(jobLogs.logs);
        } catch {
          setLogs('No logs available yet');
        }
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch job details');
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    if (jobId) {
      fetchJobDetails();
    }
  }, [jobId, fetchJobDetails]);

  useEffect(() => {
    if (job && ['queued', 'instance_creating', 'running'].includes(job.status.toLowerCase())) {
      const interval = setInterval(() => {
        fetchJobDetails();
      }, 5000);
      
      return () => clearInterval(interval);
    }
  }, [job, fetchJobDetails]);

  const handleStartJob = async () => {
    setActionLoading(true);
    try {
      await jobApi.startJob(jobId);
      fetchJobDetails();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start job');
    } finally {
      setActionLoading(false);
    }
  };

  const handleStopJob = async () => {
    setActionLoading(true);
    try {
      await jobApi.stopJob(jobId);
      fetchJobDetails();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to stop job');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteJob = async () => {
    if (!job || !confirm(`Are you sure you want to delete the job "${job.name}"? This action cannot be undone.`)) {
      return;
    }

    setActionLoading(true);
    try {
      await jobApi.deleteJob(jobId);
      router.push('/jobs'); // Redirect to jobs list after deletion
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete job');
      setActionLoading(false);
    }
  };

  const handleDownloadResults = async () => {
    if (!job) return;
    
    try {
      // Get the full potfile content
      const response = await jobApi.getPotFile(jobId);
      
      // Create a blob with the content
      const blob = new Blob([response], { type: 'text/plain' });
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${job.name}_cracked_passwords.txt`;
      
      // Trigger download
      document.body.appendChild(link);
      link.click();
      
      // Cleanup
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to download results');
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Not started';
    return new Date(dateString).toLocaleString();
  };

  const formatDuration = (start?: string, end?: string) => {
    if (!start) return 'N/A';
    if (!end) return 'In progress';
    
    const duration = new Date(end).getTime() - new Date(start).getTime();
    const minutes = Math.floor(duration / 60000);
    const hours = Math.floor(minutes / 60);
    
    if (hours > 0) {
      return `${hours}h ${minutes % 60}m`;
    }
    return `${minutes}m`;
  };

  const getStatusIcon = (status: Job['status']) => {
    const lowerStatus = status.toLowerCase();
    switch (lowerStatus) {
      case 'completed':
        return <CheckCircle className="h-4 w-4" />;
      case 'failed':
        return <XCircle className="h-4 w-4" />;
      case 'running':
      case 'instance_creating':
      case 'queued':
        return <Loader2 className="h-4 w-4 animate-spin" />;
      default:
        return <Clock className="h-4 w-4" />;
    }
  };

  const getStatusColor = (status: string) => {
    const lowerStatus = status.toLowerCase();
    switch (lowerStatus) {
      case 'completed': return 'text-green-600';
      case 'failed': return 'text-red-600';
      case 'running': return 'text-blue-600';
      case 'cancelled': return 'text-gray-600';
      default: return 'text-yellow-600';
    }
  };

  const getStatusBadgeColor = (status: string) => {
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

  if (loading) {
    return (
      <Layout>
        <div className="flex justify-center items-center h-64">
          <Spinner />
        </div>
      </Layout>
    );
  }

  if (error || !job) {
    return (
      <Layout>
        <div className="space-y-4">
          <Button variant="outline" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <Alert variant="destructive">
            {error || 'Job not found'}
          </Alert>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div className="relative overflow-hidden bg-gradient-to-r from-slate-900 to-slate-800 border border-slate-700/60 rounded-lg shadow-xl">
          <div className="absolute inset-0 bg-gradient-to-r from-slate-900/50 via-slate-800/30 to-slate-900/50"></div>
          <div className="absolute inset-0 opacity-30">
            <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-blue-400/40 to-transparent"></div>
            <div className="absolute bottom-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-slate-500/40 to-transparent"></div>
          </div>
          <div className="relative p-8">
            <div className="flex items-start justify-between">
              <div className="flex items-start space-x-6">
                <Button variant="outline" onClick={() => router.back()} className="mt-1 border-slate-600 text-slate-300 hover:bg-white/10 hover:text-slate-100 hover:border-slate-500 transition-all duration-200">
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  Back
                </Button>
                <div className="space-y-4">
                  <div>
                    <h1 className="text-3xl font-bold text-slate-100 tracking-tight">{job.name}</h1>
                    <p className="text-slate-400 mt-1 font-medium">Hash type: <span className="text-blue-400">{job.hash_type}</span></p>
                  </div>
                  
                  {/* Status Section */}
                  <div className="space-y-3">
                    <div className="flex items-center space-x-3">
                      <span className={`inline-flex items-center px-3 py-2 rounded-md text-sm font-medium ${getStatusBadgeColor(job.status)}`}>
                        {getStatusIcon(job.status)}
                        <span className="ml-2">{job.status.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, l => l.toUpperCase())}</span>
                      </span>
                      <div className="text-sm text-slate-400">
                        {formatDate(job.created_at)}
                      </div>
                    </div>
                    
                    {/* Progress Bar */}
                    {job.progress > 0 && (
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-slate-300 font-medium">Progress</span>
                          <span className="text-blue-400 font-semibold">{job.progress}%</span>
                        </div>
                        <div className="relative">
                          <div className="w-80 bg-slate-700/50 rounded-full h-3">
                            <div 
                              className="bg-gradient-to-r from-blue-500 to-emerald-500 h-3 rounded-full transition-all duration-700 ease-out"
                              style={{ width: `${job.progress}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    )}
                    
                    {/* Status Message */}
                    {job.status_message && ['queued', 'instance_creating', 'running'].includes(job.status.toLowerCase()) && (
                      <div className="bg-blue-900/20 border-l-4 border-blue-500 rounded-r-lg p-4">
                        <div className="flex items-start">
                          <Loader2 className="h-4 w-4 animate-spin text-blue-400 mt-0.5 mr-3 flex-shrink-0" />
                          <p className="text-sm text-blue-300 leading-relaxed">
                            {job.status_message}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            
              <div className="flex space-x-2">
                {job.status.toLowerCase() === 'ready_to_start' && (
                  <Button 
                    onClick={handleStartJob} 
                    loading={actionLoading}
                    className="bg-gradient-to-r from-emerald-600 to-emerald-700 hover:from-emerald-500 hover:to-emerald-600 text-white border-0 rounded-lg font-semibold shadow-lg transition-all duration-200 px-4 py-2"
                  >
                    <Play className="h-4 w-4 mr-2" />
                    Start Job
                  </Button>
                )}
                {['queued', 'instance_creating', 'running'].includes(job.status.toLowerCase()) && (
                  <Button 
                    variant="destructive" 
                    onClick={handleStopJob} 
                    loading={actionLoading}
                    className="bg-gradient-to-r from-red-600 to-red-700 hover:from-red-500 hover:to-red-600 text-white border-0 rounded-lg font-semibold shadow-lg transition-all duration-200 px-4 py-2"
                  >
                    <Square className="h-4 w-4 mr-2" />
                    Stop Job
                  </Button>
                )}
                {job.cracked_hashes !== undefined && job.cracked_hashes > 0 && (
                  <Button 
                    variant="outline" 
                    onClick={handleDownloadResults}
                    className="border-blue-500/50 text-blue-400 hover:bg-blue-900/20 hover:text-blue-300 hover:border-blue-400 bg-transparent rounded-lg font-semibold shadow-md transition-all duration-200 px-4 py-2"
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Download Results
                  </Button>
                )}
                {!['queued', 'instance_creating', 'running', 'cancelling'].includes(job.status.toLowerCase()) && (
                  <Button 
                    variant="outline" 
                    onClick={handleDeleteJob} 
                    loading={actionLoading}
                    className="border-red-500/50 text-red-400 hover:bg-red-900/20 hover:text-red-300 hover:border-red-400 bg-transparent rounded-lg font-semibold shadow-md transition-all duration-200 px-4 py-2"
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete Job
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>

        {error && (
          <Alert variant="destructive">
            {error}
          </Alert>
        )}

        {/* Job Overview */}
        <div className="grid gap-6 md:grid-cols-2">
          {/* Job Details */}
          <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm">
            <CardHeader className="border-b border-slate-700/50">
              <CardTitle className="flex items-center text-slate-200 text-lg">
                <FileText className="h-5 w-5 mr-3 text-slate-400" />
                Job Details
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6">
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-6">
                  <div className="space-y-1">
                    <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Created</span>
                    <p className="text-slate-200 font-medium">{formatDate(job.created_at)}</p>
                  </div>
                  <div className="space-y-1">
                    <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Started</span>
                    <p className="text-slate-200 font-medium">{formatDate(job.time_started)}</p>
                  </div>
                  <div className="space-y-1">
                    <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Finished</span>
                    <p className="text-slate-200 font-medium">{formatDate(job.time_finished)}</p>
                  </div>
                  <div className="space-y-1">
                    <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Duration</span>
                    <p className="text-slate-200 font-medium">{formatDuration(job.time_started, job.time_finished)}</p>
                  </div>
                  {job.actual_cost && (
                    <div className="space-y-1">
                      <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Cost</span>
                      <p className="text-emerald-400 font-semibold">${job.actual_cost.toFixed(2)}</p>
                    </div>
                  )}
                  {job.instance_type && (
                    <div className="space-y-1">
                      <span className="text-slate-400 text-xs font-medium uppercase tracking-wider">Instance</span>
                      <p className="text-slate-200 font-medium">{job.instance_type}</p>
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Crack Statistics */}
          {job.total_hashes !== undefined && (
            <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm">
              <CardHeader className="border-b border-slate-700/50">
                <CardTitle className="flex items-center text-slate-200 text-lg">
                  <TrendingUp className="h-5 w-5 mr-3 text-slate-400" />
                  Results
                </CardTitle>
              </CardHeader>
              <CardContent className="p-6">
                <div className="space-y-6">
                  <div className="grid grid-cols-3 gap-4">
                    <div className="text-center p-4">
                      <span className="text-slate-400 text-xs font-medium uppercase tracking-wider block">Total</span>
                      <span className="text-2xl font-bold text-slate-200 block mt-2">{job.total_hashes?.toLocaleString() ?? 0}</span>
                    </div>
                    <div className="text-center p-4">
                      <span className="text-slate-400 text-xs font-medium uppercase tracking-wider block">Cracked</span>
                      <span className="text-2xl font-bold text-emerald-400 block mt-2">{job.cracked_hashes?.toLocaleString() ?? 0}</span>
                    </div>
                    <div className="text-center p-4">
                      <span className="text-slate-400 text-xs font-medium uppercase tracking-wider block">Success</span>
                      <span className="text-2xl font-bold text-blue-400 block mt-2">{job.success_rate ?? 0}%</span>
                    </div>
                  </div>
                  
                  {/* Progress Bar */}
                  <div className="space-y-3">
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-400 font-medium">Recovery Progress</span>
                      <span className="text-emerald-400 font-semibold">{job.cracked_hashes?.toLocaleString() ?? 0} of {job.total_hashes?.toLocaleString() ?? 0}</span>
                    </div>
                    <div className="relative">
                      <div className="w-full bg-slate-700/50 rounded-full h-3">
                        <div 
                          className="bg-gradient-to-r from-emerald-500 to-emerald-600 h-3 rounded-full transition-all duration-700 ease-out"
                          style={{ width: `${job.success_rate ?? 0}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Results and Logs */}
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Cracked Passwords */}
          <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm">
            <CardHeader className="border-b border-slate-700/50">
              <CardTitle className="flex items-center text-slate-200">
                <Key className="h-5 w-5 mr-2 text-orange-400" />
                Cracked Passwords
                {job.cracked_hashes !== undefined && (
                  <span className="ml-2 text-sm bg-orange-900/30 text-orange-400 border border-orange-500/50 px-2 py-1 rounded-md">
                    {job.cracked_hashes} found
                  </span>
                )}
              </CardTitle>
              <CardDescription className="text-slate-400">
                {potFilePreview ? (
                  <>
                    Preview of recovered passwords (showing {potFilePreview.total_lines_shown} results)
                    {potFilePreview.truncated && <span className="text-amber-400"> - truncated</span>}
                  </>
                ) : (
                  'Preview of recovered passwords'
                )}
              </CardDescription>
            </CardHeader>
            <CardContent className="p-6">
              <div className="bg-slate-800/90 rounded-lg border border-slate-600/50 max-h-96 overflow-hidden">
                <div className="bg-slate-700/50 px-4 py-2 border-b border-slate-600/50">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-300 uppercase tracking-wider">Hash:Password Pairs</span>
                    {potFilePreview && (
                      <span className="text-xs text-slate-400">
                        {potFilePreview.total_lines_shown} shown{potFilePreview.truncated ? ' (truncated)' : ''}
                      </span>
                    )}
                  </div>
                </div>
                <div className="p-4 overflow-y-auto max-h-80">
                  {potFilePreview?.preview ? (
                    <div className="space-y-1">
                      {potFilePreview.preview.split('\n').filter(line => line.trim()).map((line, index) => {
                        // Split on the last ':' to handle complex hashes like NTLMv2
                        const lastColonIndex = line.lastIndexOf(':');
                        const hash = lastColonIndex !== -1 ? line.substring(0, lastColonIndex) : line;
                        const password = lastColonIndex !== -1 ? line.substring(lastColonIndex + 1) : '';
                        
                        return (
                          <div key={index} className="group hover:bg-slate-700/30 rounded px-2 py-1 transition-colors">
                            <div className="flex flex-col space-y-1">
                              <div className="flex items-center space-x-2">
                                <span className="text-xs font-medium text-emerald-400 bg-emerald-900/30 px-1.5 py-0.5 rounded border border-emerald-500/30">
                                  #{index + 1}
                                </span>
                                <span className="text-xs text-slate-400 font-mono truncate max-w-md">
                                  Hash: {hash || 'N/A'}
                                </span>
                              </div>
                              <div className="pl-6">
                                <span className="text-sm font-medium text-slate-200 bg-slate-700/50 px-2 py-1 rounded border border-slate-600/30">
                                  Password: <span className="text-orange-300 font-mono">{password || 'N/A'}</span>
                                </span>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <Key className="h-8 w-8 text-slate-500 mx-auto mb-2" />
                      <p className="text-sm text-slate-400">No cracked passwords available</p>
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Job Logs */}
          <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm">
            <CardHeader className="border-b border-slate-700/50">
              <CardTitle className="flex items-center text-slate-200">
                <Target className="h-5 w-5 mr-2 text-blue-400" />
                Execution Logs
              </CardTitle>
              <CardDescription className="text-slate-400">
                Job execution output
              </CardDescription>
            </CardHeader>
            <CardContent className="p-6">
              <div className="bg-slate-800/90 rounded-lg border border-slate-600/50 max-h-96 overflow-hidden">
                <div className="bg-slate-700/50 px-4 py-2 border-b border-slate-600/50">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-300 uppercase tracking-wider">Job Execution Output</span>
                    <div className="flex items-center space-x-2">
                      <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                      <span className="text-xs text-slate-400"></span>
                    </div>
                  </div>
                </div>
                <div className="p-4 overflow-y-auto max-h-80 bg-slate-900/50">
                  {logs ? (
                    <div className="space-y-0.5">
                      {logs.split('\n').map((line, index) => {
                        const trimmedLine = line.trim();
                        if (!trimmedLine) return null;
                        
                        // Color coding for different log levels
                        let lineColor = 'text-slate-300';
                        let bgColor = '';
                        let prefix = '';
                        
                        if (trimmedLine.toLowerCase().includes('error') || trimmedLine.toLowerCase().includes('failed')) {
                          lineColor = 'text-red-400';
                          bgColor = 'bg-red-900/20';
                          prefix = '❌';
                        } else if (trimmedLine.toLowerCase().includes('warning') || trimmedLine.toLowerCase().includes('warn')) {
                          lineColor = 'text-amber-400';
                          bgColor = 'bg-amber-900/20';
                          prefix = '⚠️';
                        } else if (trimmedLine.toLowerCase().includes('success') || trimmedLine.toLowerCase().includes('completed')) {
                          lineColor = 'text-emerald-400';
                          bgColor = 'bg-emerald-900/20';
                          prefix = '✅';
                        } else if (trimmedLine.toLowerCase().includes('info') || trimmedLine.toLowerCase().includes('starting')) {
                          lineColor = 'text-blue-400';
                          prefix = 'ℹ️';
                        }
                        
                        return (
                          <div key={index} className={`group hover:bg-slate-700/30 rounded px-2 py-1 transition-colors ${bgColor}`}>
                            <div className="flex items-start space-x-2">
                              <span className="text-xs text-slate-500 font-mono w-8 flex-shrink-0 mt-0.5">
                                {String(index + 1).padStart(3, '0')}
                              </span>
                              {prefix && (
                                <span className="text-xs mt-0.5 flex-shrink-0">{prefix}</span>
                              )}
                              <pre className={`text-xs font-mono whitespace-pre-wrap break-words ${lineColor} flex-1`}>
                                {trimmedLine}
                              </pre>
                            </div>
                          </div>
                        );
                      }).filter(Boolean)}
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <Target className="h-8 w-8 text-slate-500 mx-auto mb-2" />
                      <p className="text-sm text-slate-400">No execution logs available yet</p>
                      {['queued', 'instance_creating', 'running'].includes(job.status.toLowerCase()) && (
                        <p className="text-xs text-blue-400 mt-1">Logs will appear when job execution begins</p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </Layout>
  );
}