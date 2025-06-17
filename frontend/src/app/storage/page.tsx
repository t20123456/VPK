'use client';


// Force dynamic rendering to avoid SSR issues with auth
export const dynamic = 'force-dynamic';
import { useState, useEffect } from 'react';
import Layout from '@/components/Layout';
import { useAuth } from '@/contexts/AuthContext';
import { storageApi, StorageFile, StorageHealthResponse } from '@/services/api';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/Alert';
import { FileText, Upload, Trash2, RefreshCw, AlertCircle, CheckCircle, XCircle } from 'lucide-react';

interface FileUploadProps {
  type: 'wordlist' | 'rules';
  onUploadSuccess: () => void;
}

function FileUpload({ type, onUploadSuccess }: FileUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);

    try {
      if (type === 'wordlist') {
        await storageApi.uploadWordlist(file);
      } else {
        await storageApi.uploadRules(file);
      }
      setFile(null);
      if (document.getElementById('file-input')) {
        (document.getElementById('file-input') as HTMLInputElement).value = '';
      }
      onUploadSuccess();
    } catch (err: any) {
      setError(err.response?.data?.detail || `Failed to upload ${type}`);
    } finally {
      setUploading(false);
    }
  };

  const allowedExtensions = type === 'wordlist' 
    ? ['.txt', '.lst', '.dict'] 
    : ['.rule', '.rules', '.txt'];

  return (
    <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm mb-6">
      <CardHeader className="border-b border-slate-700/50">
        <CardTitle className={`flex items-center gap-2 text-slate-200 ${
          type === 'wordlist' ? 'text-emerald-400' : 'text-blue-400'
        }`}>
          <Upload className={`h-5 w-5 ${
            type === 'wordlist' ? 'text-emerald-400' : 'text-blue-400'
          }`} />
          Upload {type === 'wordlist' ? 'Wordlist' : 'Rules'}
        </CardTitle>
        <CardDescription className="text-slate-400">
          Allowed file types: {allowedExtensions.join(', ')}
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-6">
        <div className="flex gap-4 items-end">
          <div className="flex-1">
            <Input
              id="file-input"
              type="file"
              accept={allowedExtensions.join(',')}
              onChange={handleFileChange}
              disabled={uploading}
              className="bg-slate-800/50 border-slate-600/50 text-slate-200 file:bg-slate-700/50 file:text-slate-300 file:border-slate-600/50 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
            />
          </div>
          <Button 
            onClick={handleUpload} 
            disabled={!file || uploading}
            className={`min-w-[100px] font-semibold rounded-lg shadow-md transition-all duration-200 ${
              type === 'wordlist'
                ? 'bg-gradient-to-r from-emerald-600 to-emerald-700 hover:from-emerald-500 hover:to-emerald-600 text-white border-0'
                : 'bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 text-white border-0'
            }`}
          >
            {uploading ? (
              <>
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Uploading
              </>
            ) : (
              <>
                <Upload className="mr-2 h-4 w-4" />
                Upload
              </>
            )}
          </Button>
        </div>
        {error && (
          <Alert className="mt-4 bg-red-900/20 border-red-500/50 text-red-400" variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}

interface FileListProps {
  files: StorageFile[];
  type: 'wordlist' | 'rules';
  onDeleteSuccess: () => void;
  loading: boolean;
  canDelete?: boolean;
}

function FileList({ files, type, onDeleteSuccess, loading, canDelete = false }: FileListProps) {
  const [deletingFile, setDeletingFile] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleDelete = async (key: string) => {
    setDeletingFile(key);
    setError(null);

    try {
      if (type === 'wordlist') {
        await storageApi.deleteWordlist(key);
      } else {
        await storageApi.deleteRules(key);
      }
      onDeleteSuccess();
    } catch (err: any) {
      setError(err.response?.data?.detail || `Failed to delete ${type}`);
    } finally {
      setDeletingFile(null);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  if (loading) {
    return (
      <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm">
        <CardContent className="flex items-center justify-center p-6">
          <RefreshCw className="h-6 w-6 animate-spin mr-2 text-blue-400" />
          <span className="text-slate-300">Loading {type}s...</span>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm">
      <CardHeader className="border-b border-slate-700/50">
        <CardTitle className="flex items-center gap-2 text-slate-200">
          <FileText className={`h-5 w-5 ${
            type === 'wordlist' ? 'text-emerald-400' : 'text-blue-400'
          }`} />
          {type === 'wordlist' ? 'Wordlists' : 'Rules'} ({files.length})
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-6">
        {error && (
          <Alert className="mb-4 bg-red-900/20 border-red-500/50 text-red-400" variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        
        {files.length === 0 ? (
          <div className="text-center py-8">
            <FileText className={`h-12 w-12 mx-auto mb-2 ${
              type === 'wordlist' ? 'text-emerald-500/50' : 'text-blue-500/50'
            }`} />
            <p className="text-slate-400">No {type}s uploaded yet</p>
          </div>
        ) : (
          <div className="space-y-3">
            {files.map((file) => (
              <div
                key={file.key}
                className={`flex items-center justify-between p-4 border rounded-lg hover:bg-white/10 transition-all duration-200 shadow-sm backdrop-blur-sm ${
                  type === 'wordlist' 
                    ? 'border-emerald-500/30 bg-emerald-900/5' 
                    : 'border-blue-500/30 bg-blue-900/5'
                }`}
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <FileText className={`h-4 w-4 ${
                      type === 'wordlist' ? 'text-emerald-400' : 'text-blue-400'
                    }`} />
                    <span className="font-medium text-slate-200">{file.name}</span>
                  </div>
                  <div className="text-sm text-slate-400 mt-1 flex items-center gap-2 flex-wrap">
                    <span>{formatFileSize(file.size)} • {formatDate(file.last_modified)}</span>
                    {file.line_count && (
                      <Badge className="bg-emerald-900/30 text-emerald-400 border border-emerald-500/50 text-xs rounded-md">
                        {file.line_count.toLocaleString()} passwords
                      </Badge>
                    )}
                    {file.rule_count && (
                      <Badge className="bg-blue-900/30 text-blue-400 border border-blue-500/50 text-xs rounded-md">
                        {file.rule_count.toLocaleString()} rules
                      </Badge>
                    )}
                  </div>
                </div>
                
{canDelete && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleDelete(file.key)}
                    disabled={deletingFile === file.key}
                    className="border-red-500/50 text-red-400 hover:bg-red-900/20 hover:text-red-300 hover:border-red-400 bg-transparent rounded-lg font-semibold shadow-md transition-all duration-200"
                  >
                    {deletingFile === file.key ? (
                      <RefreshCw className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function StorageHealth() {
  const [health, setHealth] = useState<StorageHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const checkHealth = async () => {
    setLoading(true);
    try {
      const response = await storageApi.getHealthCheck();
      setHealth(response);
    } catch (err) {
      setHealth({
        status: 'error',
        detail: 'Failed to check storage health'
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  const getStatusIcon = () => {
    if (loading) return <RefreshCw className="h-4 w-4 animate-spin" />;
    
    switch (health?.status) {
      case 'healthy':
        return <CheckCircle className="h-4 w-4 text-green-600" />;
      case 'not_configured':
        return <AlertCircle className="h-4 w-4 text-yellow-600" />;
      case 'error':
      default:
        return <XCircle className="h-4 w-4 text-red-600" />;
    }
  };

  const getStatusColor = () => {
    switch (health?.status) {
      case 'healthy':
        return 'bg-emerald-900/30 text-emerald-400 border border-emerald-500/50';
      case 'not_configured':
        return 'bg-amber-900/30 text-amber-400 border border-amber-500/50';
      case 'error':
      default:
        return 'bg-red-900/30 text-red-400 border border-red-500/50';
    }
  };

  return (
    <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm mb-6">
      <CardHeader className="border-b border-slate-700/50">
        <CardTitle className="flex items-center gap-2 text-slate-200">
          Storage Status
          <Button
            variant="outline"
            size="sm"
            onClick={checkHealth}
            disabled={loading}
            className="border-slate-600 text-slate-300 hover:bg-white/10 hover:text-slate-100 hover:border-slate-500 bg-transparent rounded-lg font-medium shadow-sm transition-all duration-200"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-6">
        <div className="flex items-center gap-2">
          {getStatusIcon()}
          <Badge className={`${getStatusColor()} rounded-md font-medium`}>
            {health?.status || 'Unknown'}
          </Badge>
          {health?.bucket && (
            <span className="text-sm text-slate-400">
              Bucket: <span className="text-blue-400 font-mono">{health.bucket}</span>
            </span>
          )}
        </div>
        {health?.detail && (
          <p className="text-sm text-slate-400 mt-2">{health.detail}</p>
        )}
      </CardContent>
    </Card>
  );
}

export default function StoragePage() {
  const { user } = useAuth();
  const [wordlists, setWordlists] = useState<StorageFile[]>([]);
  const [rules, setRules] = useState<StorageFile[]>([]);
  const [loadingWordlists, setLoadingWordlists] = useState(true);
  const [loadingRules, setLoadingRules] = useState(true);
  const [activeTab, setActiveTab] = useState('wordlists');

  const loadWordlists = async () => {
    setLoadingWordlists(true);
    try {
      const data = await storageApi.listWordlists();
      setWordlists(data);
    } catch (err) {
      console.error('Failed to load wordlists:', err);
      setWordlists([]);
    } finally {
      setLoadingWordlists(false);
    }
  };

  const loadRules = async () => {
    setLoadingRules(true);
    try {
      const data = await storageApi.listRules();
      setRules(data);
    } catch (err) {
      console.error('Failed to load rules:', err);
      setRules([]);
    } finally {
      setLoadingRules(false);
    }
  };

  // Initial load of both tabs
  useEffect(() => {
    loadWordlists();
    loadRules();
  }, []);

  const handleTabChange = (value: string) => {
    setActiveTab(value);
    // Always refresh data when switching tabs to ensure accuracy
    if (value === 'wordlists') {
      loadWordlists();
    } else if (value === 'rules') {
      loadRules();
    }
  };

  if (!user) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-64">
          <p className="text-muted-foreground">Please log in to access storage management.</p>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div className="relative overflow-hidden bg-gradient-to-r from-slate-900 to-slate-800 border border-slate-700/60 rounded-lg p-8 shadow-xl">
          <div className="absolute inset-0 bg-gradient-to-r from-slate-900/50 via-slate-800/30 to-slate-900/50"></div>
          <div className="absolute inset-0 opacity-30">
            <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-blue-400/40 to-transparent"></div>
            <div className="absolute bottom-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-slate-500/40 to-transparent"></div>
          </div>
          <div className="relative">
            <h1 className="text-4xl font-bold text-slate-100 tracking-tight">
              <span className="text-blue-400 font-black">Storage</span>
              <span className="text-slate-300 ml-3 font-normal">Management</span>
            </h1>
            <p className="text-slate-400 mt-2 font-medium">
              Manage wordlists and rules for password cracking jobs
            </p>
          </div>
        </div>

        <StorageHealth />

        <Tabs value={activeTab} onValueChange={handleTabChange} className="w-full">
          <div className="flex items-center justify-between mb-6">
            <TabsList className="grid grid-cols-2 bg-slate-800/50 border border-slate-700/60 rounded-lg p-1">
              <TabsTrigger 
                value="wordlists"
                className="data-[state=active]:bg-gradient-to-r data-[state=active]:from-emerald-600 data-[state=active]:to-emerald-700 data-[state=active]:text-white text-slate-300 hover:text-slate-100 hover:bg-white/10 transition-all duration-200 rounded-md font-medium"
              >
                Wordlists
              </TabsTrigger>
              <TabsTrigger 
                value="rules"
                className="data-[state=active]:bg-gradient-to-r data-[state=active]:from-blue-600 data-[state=active]:to-blue-700 data-[state=active]:text-white text-slate-300 hover:text-slate-100 hover:bg-white/10 transition-all duration-200 rounded-md font-medium"
              >
                Rules
              </TabsTrigger>
            </TabsList>
            
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (activeTab === 'wordlists') {
                  loadWordlists();
                } else {
                  loadRules();
                }
              }}
              disabled={activeTab === 'wordlists' ? loadingWordlists : loadingRules}
              className="border-slate-600 text-slate-300 hover:bg-white/10 hover:text-slate-100 hover:border-slate-500 bg-transparent rounded-lg font-medium shadow-sm transition-all duration-200"
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${
                (activeTab === 'wordlists' ? loadingWordlists : loadingRules) ? 'animate-spin' : ''
              }`} />
              Refresh
            </Button>
          </div>
          
          <TabsContent value="wordlists" className="space-y-6">
            {user.role === 'admin' && (
              <FileUpload type="wordlist" onUploadSuccess={loadWordlists} />
            )}
            <FileList 
              files={wordlists} 
              type="wordlist" 
              onDeleteSuccess={loadWordlists}
              loading={loadingWordlists}
              canDelete={user?.role === 'admin'}
            />
          </TabsContent>
          
          <TabsContent value="rules" className="space-y-6">
            {user.role === 'admin' && (
              <FileUpload type="rules" onUploadSuccess={loadRules} />
            )}
            <FileList 
              files={rules} 
              type="rules" 
              onDeleteSuccess={loadRules}
              loading={loadingRules}
              canDelete={user?.role === 'admin'}
            />
          </TabsContent>
        </Tabs>
      </div>
    </Layout>
  );
}