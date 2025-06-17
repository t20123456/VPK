'use client';


// Force dynamic rendering to avoid SSR issues with auth
export const dynamic = 'force-dynamic';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Layout from '@/components/Layout';
import { useAuth } from '@/contexts/AuthContext';
import { settingsApi, storageApi, Settings, SettingsUpdate } from '@/services/api';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { 
  Settings as SettingsIcon, 
  DollarSign, 
  HardDrive, 
  Calendar, 
  Cloud, 
  Key,
  TestTube,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Database,
  RefreshCw
} from 'lucide-react';

export default function SettingsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [testResults, setTestResults] = useState<{aws?: any; vast?: any}>({});
  const [populatingCatalog, setPopulatingCatalog] = useState(false);
  const [catalogResult, setCatalogResult] = useState<{detail: string, total_entries: number, pages_scraped: number} | null>(null);

  // Form state
  const [formData, setFormData] = useState<SettingsUpdate>({});

  useEffect(() => {
    // Check if user is admin
    if (user?.role !== 'admin') {
      router.push('/dashboard');
      return;
    }
    fetchSettings();
  }, [user, router]);

  const fetchSettings = async () => {
    try {
      const data = await settingsApi.getSettings();
      setSettings(data);
      setFormData({
        max_cost_per_hour: data.max_cost_per_hour,
        max_total_cost: data.max_total_cost,
        max_upload_size_mb: data.max_upload_size_mb,
        max_hash_file_size_mb: data.max_hash_file_size_mb,
        data_retention_days: data.data_retention_days,
        s3_bucket_name: data.s3_bucket_name || '',
        s3_region: data.s3_region || 'us-east-1',
      });
    } catch (err: any) {
      setError('Failed to fetch settings: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSuccess('');

    try {
      const updatedSettings = await settingsApi.updateSettings(formData);
      setSettings(updatedSettings);
      setSuccess('Settings updated successfully');
    } catch (err: any) {
      setError('Failed to update settings: ' + (err.response?.data?.detail || err.message));
    } finally {
      setSaving(false);
    }
  };

  const testConnection = async (type: 'aws' | 'vast') => {
    try {
      const result = type === 'aws' 
        ? await settingsApi.testAwsConnection()
        : await settingsApi.testVastConnection();
      
      setTestResults(prev => ({ ...prev, [type]: result }));
    } catch (err: any) {
      setTestResults(prev => ({ 
        ...prev, 
        [type]: { 
          status: 'error', 
          message: err.response?.data?.detail || err.message 
        }
      }));
    }
  };

  const getTestIcon = (result: any) => {
    if (!result) return null;
    switch (result.status) {
      case 'success': return <CheckCircle className="h-4 w-4 text-emerald-400" />;
      case 'warning': return <AlertTriangle className="h-4 w-4 text-amber-400" />;
      case 'error': return <XCircle className="h-4 w-4 text-red-400" />;
      default: return null;
    }
  };

  const populateCatalog = async () => {
    setPopulatingCatalog(true);
    setCatalogResult(null);
    setError('');
    setSuccess('');

    try {
      const result = await storageApi.populateCatalog(10);
      setCatalogResult(result);
      setSuccess(`Wordlist catalog updated successfully! ${result.total_entries} entries from ${result.pages_scraped} pages.`);
    } catch (err: any) {
      setError('Failed to populate catalog: ' + (err.response?.data?.detail || err.message));
    } finally {
      setPopulatingCatalog(false);
    }
  };

  if (user?.role !== 'admin') {
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
              <span className="text-blue-400 font-black">Application</span>
              <span className="text-slate-300 ml-3 font-normal">Settings</span>
            </h1>
            <p className="text-slate-400 mt-2 font-medium">
              Configure system-wide settings and integrations
            </p>
          </div>
        </div>

        {error && (
          <Alert variant="destructive" className="bg-red-900/20 border-red-500/50 text-red-400">
            {error}
          </Alert>
        )}
        {success && (
          <Alert variant="default" className="bg-emerald-900/20 border-emerald-500/50 text-emerald-400">
            {success}
          </Alert>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Cost Limits */}
          <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm">
            <CardHeader className="border-b border-slate-700/50">
              <CardTitle className="flex items-center text-slate-200">
                <DollarSign className="h-5 w-5 mr-2 text-emerald-400" />
                Cost Limits
              </CardTitle>
              <CardDescription className="text-slate-400">Set maximum spending limits for job execution</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-6">
              <div>
                <label className="block text-sm font-medium mb-2 text-slate-300">Max Cost Per Hour ($)</label>
                <Input
                  type="number"
                  step="0.01"
                  min="0.01"
                  max="1000"
                  value={formData.max_cost_per_hour || ''}
                  onChange={(e) => setFormData({ ...formData, max_cost_per_hour: parseFloat(e.target.value) })}
                  required
                  className="bg-slate-800/50 border-slate-600/50 text-slate-200 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2 text-slate-300">Max Total Cost ($)</label>
                <Input
                  type="number"
                  step="0.01"
                  min="1"
                  max="100000"
                  value={formData.max_total_cost || ''}
                  onChange={(e) => setFormData({ ...formData, max_total_cost: parseFloat(e.target.value) })}
                  required
                  className="bg-slate-800/50 border-slate-600/50 text-slate-200 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
                />
              </div>
            </CardContent>
          </Card>

          {/* File Limits */}
          <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm">
            <CardHeader className="border-b border-slate-700/50">
              <CardTitle className="flex items-center text-slate-200">
                <HardDrive className="h-5 w-5 mr-2 text-blue-400" />
                File Storage Limits
              </CardTitle>
              <CardDescription className="text-slate-400">Configure file size and retention policies</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-6">
              <div>
                <label className="block text-sm font-medium mb-2 text-slate-300">Max Upload Size (MB)</label>
                <Input
                  type="number"
                  min="1"
                  max="10000"
                  value={formData.max_upload_size_mb || ''}
                  onChange={(e) => setFormData({ ...formData, max_upload_size_mb: parseInt(e.target.value) })}
                  required
                  className="bg-slate-800/50 border-slate-600/50 text-slate-200 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2 text-slate-300">Max Hash File Size (MB)</label>
                <Input
                  type="number"
                  min="1"
                  max="1000"
                  value={formData.max_hash_file_size_mb || ''}
                  onChange={(e) => setFormData({ ...formData, max_hash_file_size_mb: parseInt(e.target.value) })}
                  required
                  className="bg-slate-800/50 border-slate-600/50 text-slate-200 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2 text-slate-300">
                  <Calendar className="h-4 w-4 inline mr-1" />
                  Data Retention (Days)
                </label>
                <Input
                  type="number"
                  min="1"
                  max="365"
                  value={formData.data_retention_days || ''}
                  onChange={(e) => setFormData({ ...formData, data_retention_days: parseInt(e.target.value) })}
                  required
                  className="bg-slate-800/50 border-slate-600/50 text-slate-200 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
                />
              </div>
            </CardContent>
          </Card>

          {/* AWS S3 Configuration */}
          <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm">
            <CardHeader className="border-b border-slate-700/50">
              <CardTitle className="flex items-center text-slate-200">
                <Cloud className="h-5 w-5 mr-2 text-orange-400" />
                AWS S3 Configuration
                {settings?.aws_configured && <CheckCircle className="h-4 w-4 ml-2 text-emerald-400" />}
              </CardTitle>
              <CardDescription className="text-slate-400">Configure AWS S3 for wordlist and rule storage</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pt-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2 text-slate-300">S3 Bucket Name</label>
                  <Input
                    value={formData.s3_bucket_name || ''}
                    onChange={(e) => setFormData({ ...formData, s3_bucket_name: e.target.value })}
                    placeholder="vpk-storage"
                    className="bg-slate-800/50 border-slate-600/50 text-slate-200 placeholder:text-slate-500 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2 text-slate-300">AWS Region</label>
                  <Input
                    value={formData.s3_region || ''}
                    onChange={(e) => setFormData({ ...formData, s3_region: e.target.value })}
                    placeholder="us-east-1"
                    className="bg-slate-800/50 border-slate-600/50 text-slate-200 placeholder:text-slate-500 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2 text-slate-300">AWS Access Key ID</label>
                  <Input
                    type="password"
                    value={formData.aws_access_key_id || ''}
                    onChange={(e) => setFormData({ ...formData, aws_access_key_id: e.target.value })}
                    placeholder={settings?.aws_configured ? '••••••••••••' : 'AKIAEXAMPLE'}
                    className="bg-slate-800/50 border-slate-600/50 text-slate-200 placeholder:text-slate-500 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2 text-slate-300">AWS Secret Access Key</label>
                  <Input
                    type="password"
                    value={formData.aws_secret_access_key || ''}
                    onChange={(e) => setFormData({ ...formData, aws_secret_access_key: e.target.value })}
                    placeholder={settings?.aws_configured ? '••••••••••••' : 'Secret key'}
                    className="bg-slate-800/50 border-slate-600/50 text-slate-200 placeholder:text-slate-500 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
                  />
                </div>
              </div>
              
              <div className="flex items-center space-x-2">
                <Button type="button" variant="outline" onClick={() => testConnection('aws')} className="border-orange-500/50 text-orange-400 hover:bg-orange-900/20 hover:text-orange-300 hover:border-orange-400 bg-transparent rounded-lg font-medium shadow-sm transition-all duration-200">
                  <TestTube className="h-4 w-4 mr-2" />
                  Test AWS Connection
                </Button>
                {testResults.aws && (
                  <div className="flex items-center space-x-2">
                    {getTestIcon(testResults.aws)}
                    <span className="text-sm text-slate-300">{testResults.aws.message}</span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Vast.ai Configuration */}
          <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm">
            <CardHeader className="border-b border-slate-700/50">
              <CardTitle className="flex items-center text-slate-200">
                <Key className="h-5 w-5 mr-2 text-purple-400" />
                Vast.ai Configuration
                {settings?.vast_configured && <CheckCircle className="h-4 w-4 ml-2 text-emerald-400" />}
              </CardTitle>
              <CardDescription className="text-slate-400">Configure Vast.ai for GPU instance management</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pt-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium mb-2 text-slate-300">Vast.ai API Key</label>
                  <Input
                    type="password"
                    value={formData.vast_api_key || ''}
                    onChange={(e) => setFormData({ ...formData, vast_api_key: e.target.value })}
                    placeholder={settings?.vast_configured ? '••••••••••••' : 'API key'}
                    className="bg-slate-800/50 border-slate-600/50 text-slate-200 placeholder:text-slate-500 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
                  />
                </div>
              </div>
              
              <div className="flex items-center space-x-2">
                <Button type="button" variant="outline" onClick={() => testConnection('vast')} className="border-purple-500/50 text-purple-400 hover:bg-purple-900/20 hover:text-purple-300 hover:border-purple-400 bg-transparent rounded-lg font-medium shadow-sm transition-all duration-200">
                  <TestTube className="h-4 w-4 mr-2" />
                  Test Vast.ai Connection
                </Button>
                {testResults.vast && (
                  <div className="flex items-center space-x-2">
                    {getTestIcon(testResults.vast)}
                    <span className="text-sm text-slate-300">{testResults.vast.message}</span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Wordlist Catalog Management */}
          <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm">
            <CardHeader className="border-b border-slate-700/50">
              <CardTitle className="flex items-center text-slate-200">
                <Database className="h-5 w-5 mr-2 text-cyan-400" />
                Wordlist Catalog Management
              </CardTitle>
              <CardDescription className="text-slate-400">
                Populate the wordlist catalog with metadata from well-known wordlist sources
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pt-6">
              <div className="flex flex-col space-y-4">
                <div className="text-sm text-slate-300">
                  <p className="mb-2">
                    The wordlist catalog contains metadata for popular wordlists including file sizes, 
                    line counts, and compression ratios. This data is used to provide accurate disk space 
                    estimates and job planning.
                  </p>
                  <p className="text-slate-400">
                    Clicking &quot;Populate Catalog&quot; will scrape wordlist metadata from Weakpass.com and other sources.
                  </p>
                </div>
                
                <div className="flex items-center space-x-4">
                  <Button 
                    type="button" 
                    variant="outline" 
                    onClick={populateCatalog}
                    disabled={populatingCatalog}
                    loading={populatingCatalog}
                    className="border-cyan-500/50 text-cyan-400 hover:bg-cyan-900/20 hover:text-cyan-300 hover:border-cyan-400 bg-transparent rounded-lg font-medium shadow-sm transition-all duration-200"
                  >
                    <RefreshCw className={`h-4 w-4 mr-2 ${populatingCatalog ? 'animate-spin' : ''}`} />
                    {populatingCatalog ? 'Populating Catalog...' : 'Populate Catalog'}
                  </Button>
                  
                  {catalogResult && (
                    <div className="flex items-center space-x-2 text-sm">
                      <CheckCircle className="h-4 w-4 text-emerald-400" />
                      <span className="text-emerald-400">
                        {catalogResult.total_entries} entries from {catalogResult.pages_scraped} pages
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Save Button */}
          <div className="flex justify-end">
            <Button type="submit" loading={saving} disabled={saving} className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 text-white border-0 rounded-lg font-semibold shadow-lg transition-all duration-200 px-6 py-3">
              Save Settings
            </Button>
          </div>
        </form>
      </div>
    </Layout>
  );
}