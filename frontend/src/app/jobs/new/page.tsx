'use client';


// Force dynamic rendering to avoid SSR issues with auth
export const dynamic = 'force-dynamic';
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '@/components/Layout';
import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';
import { jobApi, vastApi, storageApi, JobCreateRequest, VastOffer, VastOffersResponse, VastOfferFilters, StorageFile, JobTimeEstimate } from '@/services/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/Alert';
import { 
  ChevronLeft, 
  ChevronRight, 
  Upload, 
  Server, 
  Clock, 
  DollarSign,
  FileText,
  Shield,
  Cpu,
  HardDrive,
  Zap,
  Search,
  Filter,
  RefreshCw,
  Info
} from 'lucide-react';

interface WizardStep {
  id: string;
  title: string;
  description: string;
}

interface JobFormData {
  name: string;
  hash_type: string;
  hash_file?: File;
  hash_count?: number;
  word_list?: string;
  rule_files?: string[];
  custom_attack?: string;
  hard_end_time?: Date;
  instance_type?: string;
  selected_offer?: VastOffer;
}

const WIZARD_STEPS: WizardStep[] = [
  {
    id: 'basic',
    title: 'Job Details',
    description: 'Enter job name and select hash type'
  },
  {
    id: 'files',
    title: 'Files & Attack',
    description: 'Upload hash file and select attack method'
  },
  {
    id: 'instance',
    title: 'Instance Selection',
    description: 'Choose your compute instance'
  },
  {
    id: 'timing',
    title: 'Time & Cost',
    description: 'Set runtime limits and review costs'
  },
  {
    id: 'review',
    title: 'Review & Submit',
    description: 'Confirm your job configuration'
  }
];

const HASH_TYPES = [
  // Basic Hash Types
  { value: 'md5', label: '0 - MD5', mode: '0' },
  { value: 'sha1', label: '100 - SHA1', mode: '100' },
  { value: 'md4', label: '900 - MD4', mode: '900' },
  { value: 'sha224', label: '1300 - SHA224', mode: '1300' },
  { value: 'sha256', label: '1400 - SHA256', mode: '1400' },
  { value: 'sha512', label: '1700 - SHA512', mode: '1700' },
  { value: 'sha384', label: '10800 - SHA384', mode: '10800' },
  { value: 'sha3-224', label: '17300 - SHA3-224', mode: '17300' },
  { value: 'sha3-256', label: '17400 - SHA3-256', mode: '17400' },
  { value: 'sha3-384', label: '17500 - SHA3-384', mode: '17500' },
  { value: 'sha3-512', label: '17600 - SHA3-512', mode: '17600' },
  
  // Windows/NTLM Types  
  { value: 'ntlm', label: '1000 - NTLM', mode: '1000' },
  { value: 'domain-cached', label: '1100 - Domain Cached Credentials (DCC)', mode: '1100' },
  { value: 'domain-cached2', label: '2100 - Domain Cached Credentials 2 (DCC2)', mode: '2100' },
  { value: 'lm', label: '3000 - LM Hash', mode: '3000' },
  { value: 'net-ntlmv1', label: '5500 - NetNTLMv1 / NetNTLMv1+ESS', mode: '5500' },
  { value: 'net-ntlmv2', label: '5600 - NetNTLMv2', mode: '5600' },
  
  // Kerberos Types
  { value: 'krb5pa-etype23', label: '7500 - Kerberos 5 AS-REQ Pre-Auth etype 23', mode: '7500' },
  { value: 'krb5tgs-etype23', label: '13100 - Kerberos 5 TGS-REP etype 23', mode: '13100' },
  { value: 'krb5asrep', label: '18200 - Kerberos 5 AS-REP etype 23 (Kerberoasting)', mode: '18200' },
  { value: 'krb5pa-etype17', label: '19600 - Kerberos 5 AS-REQ Pre-Auth etype 17', mode: '19600' },
  { value: 'krb5pa-etype18', label: '19700 - Kerberos 5 AS-REQ Pre-Auth etype 18', mode: '19700' },
  
  // Linux/Unix Types
  { value: 'md5-crypt', label: '500 - md5crypt, MD5 (Unix)', mode: '500' },
  { value: 'des-crypt', label: '1500 - DES(Unix)', mode: '1500' },
  { value: 'sha512-crypt', label: '1800 - sha512crypt $6$, SHA512 (Unix)', mode: '1800' },
  { value: 'bcrypt', label: '3200 - bcrypt $2*$, Blowfish (Unix)', mode: '3200' },
  { value: 'sha256-crypt', label: '7400 - sha256crypt $5$, SHA256 (Unix)', mode: '7400' },
  { value: 'scrypt', label: '8900 - scrypt', mode: '8900' },
  { value: 'argon2', label: '25700 - Argon2', mode: '25700' },
  
  // Database Types
  { value: 'postgresql-md5', label: '11 - PostgreSQL MD5', mode: '11' },
  { value: 'postgresql', label: '12 - PostgreSQL', mode: '12' },
  { value: 'oracle-s', label: '112 - Oracle S: Type (Oracle 11+)', mode: '112' },
  { value: 'mssql2000', label: '131 - MSSQL(2000)', mode: '131' },
  { value: 'mssql2005', label: '132 - MSSQL(2005)', mode: '132' },
  { value: 'mysql323', label: '200 - MySQL323', mode: '200' },
  { value: 'mysql41', label: '300 - MySQL4.1/MySQL5', mode: '300' },
  { value: 'mssql2012', label: '1731 - MSSQL(2012, 2014)', mode: '1731' },
  { value: 'oracle-h', label: '3100 - Oracle H: Type (Oracle 7+)', mode: '3100' },
  { value: 'oracle-t', label: '12300 - Oracle T: Type (Oracle 12+)', mode: '12300' },
  { value: 'postgresql-scram-sha-256', label: '28600 - PostgreSQL SCRAM-SHA-256', mode: '28600' },
  
  // Application Types
  { value: 'joomla', label: '11 - Joomla < 2.5.18', mode: '11' },
  { value: 'oscommerce', label: '21 - osCommerce, xt:Commerce MD5', mode: '21' },
  { value: 'phpass', label: '400 - phpass (WordPress, phpBB3, etc.)', mode: '400' },
  { value: 'django-sha1', label: '1900 - Django (SHA1)', mode: '1900' },
  { value: 'mediawiki', label: '3711 - MediaWiki B type', mode: '3711' },
  { value: 'drupal7', label: '7900 - Drupal7', mode: '7900' },
  { value: 'atlassian', label: '12001 - Atlassian (PBKDF2-HMAC-SHA1)', mode: '12001' },
  
  // Archive/Document Types
  { value: 'office2007', label: '9400 - MS Office 2007', mode: '9400' },
  { value: 'office2010', label: '9500 - MS Office 2010', mode: '9500' },
  { value: 'office2013', label: '9600 - MS Office 2013', mode: '9600' },
  { value: 'pdf', label: '10400 - PDF 1.1 - 1.3 (Acrobat 2 - 4)', mode: '10400' },
  { value: '7zip', label: '11600 - 7-Zip', mode: '11600' },
  { value: 'rar3', label: '12500 - RAR3-hp', mode: '12500' },
  { value: 'rar5', label: '13000 - RAR5', mode: '13000' },
  { value: 'zip', label: '13600 - WinZip', mode: '13600' },
  
  // WiFi/Network Types
  { value: 'wep', label: '1 - WEP', mode: '1' },
  { value: 'cisco-pix', label: '2400 - Cisco-PIX MD5', mode: '2400' },
  { value: 'wpa-legacy', label: '2500 - WPA/WPA2 (Legacy)', mode: '2500' },
  { value: 'wpa-pmk', label: '16800 - WPA-PMKID-PMK', mode: '16800' },
  { value: 'wpa-pmkid', label: '22000 - WPA-PBKDF2-PMKID+EAPOL', mode: '22000' },
  
  // Other Common Types
  { value: 'lastpass', label: '6800 - LastPass', mode: '6800' },
  { value: 'pbkdf2-sha256', label: '10900 - PBKDF2-HMAC-SHA256', mode: '10900' },
  { value: 'bitcoin', label: '11300 - Bitcoin/Litecoin wallet.dat', mode: '11300' },
  { value: 'pbkdf2-sha1', label: '12000 - PBKDF2-HMAC-SHA1', mode: '12000' },
  { value: 'pbkdf2-sha512', label: '12100 - PBKDF2-HMAC-SHA512', mode: '12100' },
  { value: 'keepass', label: '13400 - KeePass 1 (AES/Twofish) and KeePass 2 (AES)', mode: '13400' },
  { value: 'veracrypt', label: '13711 - VeraCrypt', mode: '13711' },
  { value: 'luks', label: '14600 - LUKS', mode: '14600' },
  { value: 'ethereum', label: '15700 - Ethereum Wallet, PBKDF2-HMAC-SHA256', mode: '15700' },
  { value: 'keychain', label: '23100 - Mac OS X Keychain', mode: '23100' }
];

// Helper function to format storage values in human-readable format
const formatStorage = (sizeGB: number): string => {
  if (sizeGB >= 1024) {
    return `${(sizeGB / 1024).toFixed(1)}TB`;
  } else if (sizeGB >= 1) {
    return `${sizeGB}GB`;
  } else {
    return `${(sizeGB * 1024).toFixed(0)}MB`;
  }
};

export default function NewJobPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(0);
  const [formData, setFormData] = useState<JobFormData>({
    name: '',
    hash_type: 'md5'
  });
  
  // Data for dropdowns
  const [offersResponse, setOffersResponse] = useState<VastOffersResponse | null>(null);
  const [wordlists, setWordlists] = useState<StorageFile[]>([]);
  const [rules, setRules] = useState<StorageFile[]>([]);
  
  // Offer filtering and pagination
  const [offerFilters, setOfferFilters] = useState<VastOfferFilters>({
    page: 1,
    per_page: 10,
    search: '',
    min_gpus: 1,
    max_cost: 10.0,
    gpu_filter: '',
    location_filter: ''
  });
  
  // Loading states
  const [loadingOffers, setLoadingOffers] = useState(false);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  
  // Error handling
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadStorageFiles();
  }, []);

  // Refresh storage files when moving to the files & attack step
  useEffect(() => {
    if (currentStep === 1) {
      loadStorageFiles();
    }
  }, [currentStep]);

  const loadStorageFiles = async () => {
    setLoadingFiles(true);
    try {
      const [wordlistsData, rulesData] = await Promise.all([
        // Try enhanced wordlists first, fallback to regular if it fails
        storageApi.listEnhancedWordlists().catch(() => storageApi.listWordlists()),
        storageApi.listRules()
      ]);
      setWordlists(wordlistsData || []);
      setRules(rulesData || []);
    } catch (err) {
      console.error('Failed to load storage files:', err);
      // Reset to empty arrays on error to clear any stale data
      setWordlists([]);
      setRules([]);
    } finally {
      setLoadingFiles(false);
    }
  };

  const loadOffers = async (filters?: VastOfferFilters) => {
    setLoadingOffers(true);
    try {
      const finalFilters = { ...offerFilters, ...filters };
      const response = await vastApi.getOffers(finalFilters);
      setOffersResponse(response);
    } catch (err) {
      setError('Failed to load available instances');
    } finally {
      setLoadingOffers(false);
    }
  };

  const nextStep = () => {
    if (currentStep < WIZARD_STEPS.length - 1) {
      setCurrentStep(currentStep + 1);
      if (currentStep === 1) { // Moving to instance selection
        // Calculate required disk space based on selected wordlist
        let minDiskSpaceGB = 20; // Base minimum for OS and tools
        
        if (formData.word_list && wordlists.length > 0) {
          const selectedWordlist = wordlists.find((w: StorageFile) => w.key === formData.word_list);
          if (selectedWordlist) {
            if (selectedWordlist.has_metadata && selectedWordlist.uncompressed_size) {
              // Use catalog metadata for accurate calculation
              const compressedGB = selectedWordlist.size / (1024 * 1024 * 1024);
              const uncompressedGB = selectedWordlist.uncompressed_size / (1024 * 1024 * 1024);
              // Need space for: compressed file + uncompressed file + 20% buffer
              minDiskSpaceGB += compressedGB + (uncompressedGB * 1.2);
            } else {
              // Fallback to estimate based on file extension and size
              const sizeGB = selectedWordlist.size / (1024 * 1024 * 1024);
              let multiplier = 1.5; // Default for uncompressed
              
              if (selectedWordlist.name.endsWith('.7z')) {
                multiplier = 8; // 7z typically achieves 5-10x compression
              } else if (selectedWordlist.name.endsWith('.zip')) {
                multiplier = 5; // ZIP typically achieves 3-5x compression
              } else if (selectedWordlist.name.endsWith('.gz')) {
                multiplier = 3.5; // GZIP typically achieves 2-4x compression
              }
              
              minDiskSpaceGB += sizeGB * multiplier;
            }
          }
        }
        
        // Round up to nearest 10GB for safety
        minDiskSpaceGB = Math.ceil(minDiskSpaceGB / 10) * 10;
        
        // Load offers with disk space filter
        loadOffers({ min_disk_space_gb: minDiskSpaceGB });
      }
    }
  };

  const prevStep = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const updateFormData = (updates: Partial<JobFormData>) => {
    setFormData(prev => ({ ...prev, ...updates }));
  };

  const validateCurrentStep = (): boolean => {
    switch (currentStep) {
      case 0: // Basic details
        return formData.name.trim() !== '' && formData.hash_type !== '';
      case 1: // Files
        return formData.hash_file !== undefined;
      case 2: // Instance
        return formData.selected_offer !== undefined;
      case 3: // Timing
        return formData.hard_end_time !== undefined;
      default:
        return true;
    }
  };

  const calculateEstimatedCost = (): number => {
    if (!formData.selected_offer || !formData.hard_end_time) return 0;
    const hours = (formData.hard_end_time.getTime() - new Date().getTime()) / (1000 * 60 * 60);
    return Math.max(0, hours * formData.selected_offer.dph_total);
  };

  const submitJob = async () => {
    if (!formData.hash_file || !formData.selected_offer) return;

    setSubmitting(true);
    setError(null);

    try {
      // Create the job
      // Find the hash type details to get the mode number
      const selectedHashType = HASH_TYPES.find(type => type.value === formData.hash_type);
      
      // Calculate required disk space (same logic as instance selection)
      let requiredDiskGB = 20; // Base minimum for OS and tools
      if (formData.word_list && wordlists.length > 0) {
        const selectedWordlist = wordlists.find((w: StorageFile) => w.key === formData.word_list);
        if (selectedWordlist) {
          if (selectedWordlist.has_metadata && selectedWordlist.uncompressed_size) {
            // Use catalog metadata for accurate calculation
            const compressedGB = selectedWordlist.size / (1024 * 1024 * 1024);
            const uncompressedGB = selectedWordlist.uncompressed_size / (1024 * 1024 * 1024);
            // Need space for: compressed file + uncompressed file + 20% buffer
            requiredDiskGB += compressedGB + (uncompressedGB * 1.2);
          } else {
            // Fallback to estimate based on file extension and size
            const sizeGB = selectedWordlist.size / (1024 * 1024 * 1024);
            let multiplier = 1.5; // Default for uncompressed
            
            if (selectedWordlist.name.endsWith('.7z')) {
              multiplier = 8; // 7z typically achieves 5-10x compression for text
            } else if (selectedWordlist.name.endsWith('.zip')) {
              multiplier = 5; // ZIP typically achieves 3-5x compression for text
            } else if (selectedWordlist.name.endsWith('.gz')) {
              multiplier = 3.5; // GZIP typically achieves 2-4x compression for text
            }
            
            requiredDiskGB += sizeGB * multiplier;
          }
        }
      }
      // Round up to nearest 10GB for safety
      requiredDiskGB = Math.ceil(requiredDiskGB / 10) * 10;
      
      const jobData: JobCreateRequest = {
        name: formData.name,
        hash_type: selectedHashType?.mode || formData.hash_type, // Send mode number instead of hash type name
        word_list: formData.word_list,
        rule_files: formData.rule_files,
        custom_attack: formData.custom_attack,
        hard_end_time: formData.hard_end_time?.toISOString(),
        instance_type: formData.selected_offer.id.toString(),
        required_disk_gb: requiredDiskGB
      };

      console.log('Creating job with data:', jobData);
      const job = await jobApi.createJob(jobData);

      // Upload the hash file
      await uploadHashFile(job.id, formData.hash_file);

      // Redirect to job details
      router.push(`/jobs/${job.id}`);
    } catch (err: any) {
      console.error('Job creation error:', err);
      
      // Handle different error response formats
      let errorMessage = 'Failed to create job';
      
      if (err.response?.data) {
        const errorData = err.response.data;
        
        // Handle validation errors (array of error objects)
        if (Array.isArray(errorData)) {
          errorMessage = errorData.map(e => e.msg || e.message || String(e)).join(', ');
        }
        // Handle detail string
        else if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail;
          
          // Check if this is an instance availability error
          if (errorMessage.includes('no longer available') && errorMessage.includes('select a different instance')) {
            // Navigate back to instance selection step
            setCurrentStep(2); // Instance selection step
            setError('The selected instance is no longer available. Please choose a different instance.');
            return;
          }
        }
        // Handle direct error object
        else if (errorData.msg) {
          errorMessage = errorData.msg;
        }
        // Handle any other string response
        else if (typeof errorData === 'string') {
          errorMessage = errorData;
        }
      }
      // Handle network errors
      else if (err.message) {
        errorMessage = err.message;
      }
      
      setError(errorMessage);
    } finally {
      setSubmitting(false);
    }
  };

  const uploadHashFile = async (jobId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/jobs/${jobId}/upload-hash`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
      },
      body: formData
    });

    if (!response.ok) {
      throw new Error('Failed to upload hash file');
    }
  };

  if (!user) {
    return (
      <Layout>
        <div className="flex items-center justify-center min-h-64">
          <p className="text-muted-foreground">Please log in to create a new job.</p>
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
              <span className="text-blue-400 font-black">Create</span>
              <span className="text-slate-300 ml-3 font-normal">New Job</span>
            </h1>
            <p className="text-slate-400 mt-2 font-medium">
              Configure and launch a new password cracking job
            </p>
          </div>
        </div>

        {/* Progress Steps */}
        <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              {WIZARD_STEPS.map((step, index) => (
                <div key={step.id} className="flex items-center">
                  <div className={`flex items-center justify-center w-8 h-8 rounded-full border-2 transition-all duration-200 ${
                    index <= currentStep 
                      ? 'bg-gradient-to-r from-blue-600 to-blue-700 border-blue-500 text-white shadow-md' 
                      : 'border-slate-600 text-slate-400 bg-slate-800/50'
                  }`}>
                    {index + 1}
                  </div>
                  <div className="ml-3">
                    <div className={`text-sm font-medium transition-all duration-200 ${
                      index <= currentStep ? 'text-slate-200' : 'text-slate-500'
                    }`}>
                      {step.title}
                    </div>
                    <div className="text-xs text-slate-400">
                      {step.description}
                    </div>
                  </div>
                  {index < WIZARD_STEPS.length - 1 && (
                    <ChevronRight className="ml-6 h-4 w-4 text-slate-600" />
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Current Step Content */}
        <Card className="bg-white/5 border border-slate-700/60 rounded-lg shadow-lg backdrop-blur-sm">
          <CardHeader className="border-b border-slate-700/50">
            <CardTitle className="text-xl font-semibold text-slate-200">{WIZARD_STEPS[currentStep].title}</CardTitle>
            <CardDescription className="text-slate-400">{WIZARD_STEPS[currentStep].description}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6 pt-6">
            {currentStep === 0 && (
              <BasicDetailsStep 
                formData={formData} 
                updateFormData={updateFormData}
              />
            )}
            
            {currentStep === 1 && (
              <FilesAttackStep 
                formData={formData} 
                updateFormData={updateFormData}
                wordlists={wordlists}
                rules={rules}
                loadingFiles={loadingFiles}
                onRefreshFiles={loadStorageFiles}
              />
            )}
            
            {currentStep === 2 && (
              <InstanceSelectionStep 
                formData={formData} 
                updateFormData={updateFormData}
                offersResponse={offersResponse}
                loadingOffers={loadingOffers}
                offerFilters={offerFilters}
                setOfferFilters={setOfferFilters}
                loadOffers={loadOffers}
                wordlists={wordlists}
              />
            )}
            
            {currentStep === 3 && (
              <TimingCostStep 
                formData={formData} 
                updateFormData={updateFormData}
                estimatedCost={calculateEstimatedCost()}
              />
            )}
            
            {currentStep === 4 && (
              <ReviewSubmitStep 
                formData={formData}
                estimatedCost={calculateEstimatedCost()}
              />
            )}
          </CardContent>
        </Card>

        {/* Error Display */}
        {error && (
          <Alert variant="destructive" className="bg-red-900/20 border-red-500/50 text-red-400">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Navigation */}
        <div className="flex justify-between">
          <Button 
            variant="outline" 
            onClick={prevStep}
            disabled={currentStep === 0}
            className="border-slate-600 text-slate-300 hover:bg-white/10 hover:text-slate-100 hover:border-slate-500 bg-transparent rounded-lg font-semibold shadow-md transition-all duration-200"
          >
            <ChevronLeft className="mr-2 h-4 w-4" />
            Previous
          </Button>
          
          <div className="flex gap-2">
            {currentStep < WIZARD_STEPS.length - 1 ? (
              <Button 
                onClick={nextStep}
                disabled={!validateCurrentStep()}
                className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 text-white border-0 rounded-lg font-semibold shadow-lg transition-all duration-200"
              >
                Next
                <ChevronRight className="ml-2 h-4 w-4" />
              </Button>
            ) : (
              <Button 
                onClick={submitJob}
                disabled={!validateCurrentStep() || submitting}
                className="bg-gradient-to-r from-emerald-600 to-emerald-700 hover:from-emerald-500 hover:to-emerald-600 text-white border-0 rounded-lg font-semibold shadow-lg transition-all duration-200"
              >
                {submitting ? 'Creating...' : 'Create Job'}
              </Button>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}

// Step Components will be defined below...
function BasicDetailsStep({ formData, updateFormData }: any) {
  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium mb-2 text-slate-300">Job Name</label>
        <Input
          value={formData.name}
          onChange={(e) => updateFormData({ name: e.target.value })}
          placeholder="Enter a descriptive name for your job"
          className="bg-slate-800/50 border-slate-600/50 text-slate-200 placeholder:text-slate-500 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
        />
      </div>
      
      <div>
        <label className="block text-sm font-medium mb-2 text-slate-300">Hash Type</label>
        <select 
          value={formData.hash_type} 
          onChange={(e) => updateFormData({ hash_type: e.target.value })}
          className="flex h-10 w-full rounded-lg border bg-slate-800/50 border-slate-600/50 text-slate-200 px-3 py-2 text-sm focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {HASH_TYPES.map(type => (
            <option key={type.value} value={type.value}>
              {type.label} (Mode {type.mode})
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

function FilesAttackStep({ formData, updateFormData, wordlists, rules, loadingFiles, onRefreshFiles }: any) {
  const [countingHashes, setCountingHashes] = useState(false);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    updateFormData({ hash_file: file, hash_count: undefined });
    setCountingHashes(true);

    try {
      // Read file to count lines (hashes)
      const text = await file.text();
      const lines = text.split('\n').filter(line => line.trim() !== '');
      updateFormData({ hash_file: file, hash_count: lines.length });
    } catch (error) {
      console.error('Error counting hashes:', error);
      updateFormData({ hash_file: file, hash_count: undefined });
    } finally {
      setCountingHashes(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium mb-2 text-slate-300">Hash File *</label>
        <Input
          type="file"
          accept=".txt,.hash"
          onChange={handleFileChange}
          className="bg-slate-800/50 border-slate-600/50 text-slate-200 file:bg-slate-700/50 file:text-slate-300 file:border-slate-600/50 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
        />
        {formData.hash_file && (
          <div className="text-sm text-slate-400 mt-1">
            <p>Selected: {formData.hash_file.name}</p>
            {countingHashes && <p className="text-blue-400">Counting hashes...</p>}
            {formData.hash_count && !countingHashes && (
              <p className="text-emerald-400">Contains {formData.hash_count.toLocaleString()} hash{formData.hash_count !== 1 ? 'es' : ''}</p>
            )}
          </div>
        )}
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="block text-sm font-medium text-slate-300">Wordlist (Optional)</label>
          <Button
            variant="outline"
            size="sm"
            onClick={onRefreshFiles}
            disabled={loadingFiles}
            className="border-slate-600 text-slate-300 hover:bg-white/10 hover:text-slate-100 hover:border-slate-500 bg-transparent rounded-lg font-medium shadow-sm transition-all duration-200"
          >
            <RefreshCw className={`h-4 w-4 ${loadingFiles ? 'animate-spin' : ''}`} />
          </Button>
        </div>
        <select 
          value={formData.word_list || ''} 
          onChange={(e) => updateFormData({ word_list: e.target.value || undefined })}
          className="flex h-10 w-full rounded-lg border bg-slate-800/50 border-slate-600/50 text-slate-200 px-3 py-2 text-sm focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={loadingFiles}
        >
          <option value="">No wordlist (dictionary attack only)</option>
          {wordlists.map((wordlist: StorageFile) => (
            <option key={wordlist.key} value={wordlist.key}>
              {wordlist.name}
              {wordlist.line_count && ` (${wordlist.line_count.toLocaleString()} passwords)`}
            </option>
          ))}
        </select>
        {loadingFiles && (
          <p className="text-sm text-blue-400 mt-1 flex items-center gap-2">
            <RefreshCw className="h-3 w-3 animate-spin" />
            Loading storage files...
          </p>
        )}
        {!loadingFiles && wordlists.length === 0 && (
          <p className="text-sm text-amber-400 mt-1">
            No wordlists found. Check your S3 storage configuration.
          </p>
        )}
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="block text-sm font-medium text-slate-300">Rules (Optional)</label>
          {formData.rule_files && formData.rule_files.length > 0 && (
            <span className="text-xs text-slate-400">
              {formData.rule_files.length} rule{formData.rule_files.length !== 1 ? 's' : ''} selected
            </span>
          )}
        </div>
        
        {/* Selected Rules Display */}
        {formData.rule_files && formData.rule_files.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {formData.rule_files.map((ruleKey: string, index: number) => {
              const rule = rules.find((r: StorageFile) => r.key === ruleKey);
              return (
                <div
                  key={ruleKey}
                  className="inline-flex items-center gap-2 bg-blue-600/20 border border-blue-500/50 rounded-lg px-3 py-1 text-sm text-blue-300"
                >
                  <span className="text-xs text-blue-400">#{index + 1}</span>
                  <span>{rule?.name || ruleKey}</span>
                  {rule?.rule_count && (
                    <span className="text-xs text-blue-400">
                      ({rule.rule_count.toLocaleString()})
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      const newRules = formData.rule_files?.filter((_: string, i: number) => i !== index) || [];
                      updateFormData({ rule_files: newRules.length > 0 ? newRules : undefined });
                    }}
                    className="text-blue-400 hover:text-blue-300 transition-colors"
                  >
                    ×
                  </button>
                </div>
              );
            })}
            <button
              type="button"
              onClick={() => updateFormData({ rule_files: undefined })}
              className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-slate-300 transition-colors"
            >
              Clear all
            </button>
          </div>
        )}
        
        {/* Rule Selection Dropdown */}
        <select 
          value=""
          onChange={(e) => {
            if (e.target.value) {
              const currentRules = formData.rule_files || [];
              if (!currentRules.includes(e.target.value)) {
                updateFormData({ rule_files: [...currentRules, e.target.value] });
              }
            }
          }}
          className="flex h-10 w-full rounded-lg border bg-slate-800/50 border-slate-600/50 text-slate-200 px-3 py-2 text-sm focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={loadingFiles || !formData.word_list}
        >
          <option value="">
            {formData.rule_files && formData.rule_files.length > 0 
              ? 'Add another rule...' 
              : 'Select rules...'}
          </option>
          {rules
            .filter((rule: StorageFile) => !formData.rule_files?.includes(rule.key))
            .map((rule: StorageFile) => (
              <option key={rule.key} value={rule.key}>
                {rule.name}
                {rule.rule_count && ` (${rule.rule_count.toLocaleString()} rules)`}
              </option>
            ))}
        </select>
        
        {!formData.word_list && (
          <p className="text-sm text-slate-500 mt-1">
            Select a wordlist first to enable rules
          </p>
        )}
        {!loadingFiles && formData.word_list && rules.length === 0 && (
          <p className="text-sm text-amber-400 mt-1">
            No rules found. Check your S3 storage configuration.
          </p>
        )}
        {formData.rule_files && formData.rule_files.length > 0 && (
          <div className="mt-1 space-y-1">
            <p className="text-sm text-slate-400">
              Rules will be applied in the order shown above. Hashcat will use multiple -r flags.
            </p>
            {formData.rule_files.length > 1 && (
              <Alert className="border-amber-600/50 bg-amber-900/20">
                <AlertDescription className="text-amber-300 text-sm">
                  ⚠️ WARNING: Time estimates for multiple rule files are NOT accurate.
                  Rule interactions and amplification effects make reliable estimation impossible.
                  Large rule chains may exhaust system memory.
                  You must account for actual runtime yourself.
                </AlertDescription>
              </Alert>
            )}
          </div>
        )}
      </div>

      <div>
        <label className="block text-sm font-medium mb-2 text-slate-300">Custom Attack (Optional)</label>
        <Input
          value={formData.custom_attack || ''}
          onChange={(e) => updateFormData({ custom_attack: e.target.value || undefined })}
          placeholder="e.g., -a 3 ?l?l?l?l?d?d?d?d, -a 6 ?d?d?d?d, or -a 7 ?d?d?d?d"
          className="bg-slate-800/50 border-slate-600/50 text-slate-200 placeholder:text-slate-500 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
        />
        <p className="text-sm text-slate-500 mt-1">
          Advanced: Custom hashcat attack mode and mask. Hybrid attacks (-a 6/7) will use the selected wordlist above.
        </p>
        {formData.custom_attack && (
          <Alert className="border-amber-600/50 bg-amber-900/20 mt-2">
            <AlertDescription className="text-amber-300 text-sm">
              ⚠️ WARNING: Time estimates for custom attacks are NOT accurate.
              Actual runtime depends on mask complexity and cannot be reliably estimated.
              You must account for actual runtime yourself.
            </AlertDescription>
          </Alert>
        )}
      </div>
    </div>
  );
}

function InstanceSelectionStep({ 
  formData, 
  updateFormData, 
  offersResponse, 
  loadingOffers, 
  offerFilters, 
  setOfferFilters, 
  loadOffers,
  wordlists
}: any) {
  const handleFilterChange = (newFilters: Partial<VastOfferFilters>) => {
    const updatedFilters = { ...offerFilters, ...newFilters, page: 1 };
    setOfferFilters(updatedFilters);
    loadOffers(updatedFilters);
  };

  const handlePageChange = (newPage: number) => {
    const updatedFilters = { ...offerFilters, page: newPage };
    setOfferFilters(updatedFilters);
    loadOffers(updatedFilters);
  };

  const handleRefresh = () => {
    loadOffers(offerFilters);
  };

  if (loadingOffers && !offersResponse) {
    return <div className="text-center py-8 text-slate-400">Loading available instances...</div>;
  }

  const offers = offersResponse?.offers || [];
  const pagination = offersResponse?.pagination;

  // Calculate minimum disk space requirement
  let minDiskSpaceGB = 20; // Base minimum for OS and tools
  if (formData.word_list && wordlists.length > 0) {
    const selectedWordlist = wordlists.find((w: StorageFile) => w.key === formData.word_list);
    if (selectedWordlist) {
      if (selectedWordlist.has_metadata && selectedWordlist.uncompressed_size) {
        // Use catalog metadata for accurate calculation
        const compressedGB = selectedWordlist.size / (1024 * 1024 * 1024);
        const uncompressedGB = selectedWordlist.uncompressed_size / (1024 * 1024 * 1024);
        // Need space for: compressed file + uncompressed file + 20% buffer
        minDiskSpaceGB += compressedGB + (uncompressedGB * 1.2);
      } else {
        // Fallback to estimate based on file extension and size
        const sizeGB = selectedWordlist.size / (1024 * 1024 * 1024);
        let multiplier = 1.5; // Default for uncompressed
        
        if (selectedWordlist.name.endsWith('.7z')) {
          multiplier = 8; // 7z typically achieves 5-10x compression
        } else if (selectedWordlist.name.endsWith('.zip')) {
          multiplier = 5; // ZIP typically achieves 3-5x compression
        } else if (selectedWordlist.name.endsWith('.gz')) {
          multiplier = 3.5; // GZIP typically achieves 2-4x compression
        }
        
        minDiskSpaceGB += sizeGB * multiplier;
      }
    }
  }
  minDiskSpaceGB = Math.ceil(minDiskSpaceGB / 10) * 10;

  return (
    <div className="space-y-6">
      {/* Disk Space Requirement Notice */}
      {formData.word_list && (
        <Alert className="bg-blue-900/20 border-blue-500/50 text-blue-400">
          <Info className="h-4 w-4" />
          <AlertDescription>
            Minimum disk space requirement: <strong>{minDiskSpaceGB} GB</strong>
            <br />
            <span className="text-sm text-blue-400/80">
              Instances are filtered to ensure sufficient storage for your selected wordlist.
            </span>
          </AlertDescription>
        </Alert>
      )}
      
      {/* Search and Filters */}
      <div className="space-y-4">
        <div className="flex gap-4">
          <div className="flex-1">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-slate-400" />
              <Input
                placeholder="Search GPU models (e.g., RTX 4090, A100)"
                value={offerFilters.search || ''}
                onChange={(e) => handleFilterChange({ search: e.target.value })}
                className="pl-10 bg-slate-800/50 border-slate-600/50 text-slate-200 placeholder:text-slate-500 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
              />
            </div>
          </div>
          <Button
            variant="outline"
            onClick={handleRefresh}
            disabled={loadingOffers}
            className="border-slate-600 text-slate-300 hover:bg-white/10 hover:text-slate-100 hover:border-slate-500 bg-transparent rounded-lg font-medium shadow-sm transition-all duration-200"
          >
            <RefreshCw className={`h-4 w-4 ${loadingOffers ? 'animate-spin' : ''}`} />
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1 text-slate-300">Min GPUs</label>
            <Input
              type="number"
              min="1"
              max="8"
              value={offerFilters.min_gpus || 1}
              onChange={(e) => handleFilterChange({ min_gpus: parseInt(e.target.value) || 1 })}
              className="bg-slate-800/50 border-slate-600/50 text-slate-200 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-1 text-slate-300">Max Cost ($/hr)</label>
            <Input
              type="number"
              step="0.1"
              min="0.1"
              max="50"
              value={offerFilters.max_cost || 10}
              onChange={(e) => handleFilterChange({ max_cost: parseFloat(e.target.value) || 10 })}
              className="bg-slate-800/50 border-slate-600/50 text-slate-200 focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1 text-slate-300">GPU Type</label>
            <select
              value={offerFilters.gpu_filter || ''}
              onChange={(e) => handleFilterChange({ gpu_filter: e.target.value })}
              className="flex h-10 w-full rounded-lg border bg-slate-800/50 border-slate-600/50 text-slate-200 px-3 py-2 text-sm focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
            >
              <option value="">All GPU Types</option>
              <option value="RTX 4090">RTX 4090</option>
              <option value="RTX 4080">RTX 4080</option>
              <option value="RTX 4070">RTX 4070</option>
              <option value="RTX 3090">RTX 3090</option>
              <option value="RTX 3080">RTX 3080</option>
              <option value="A100">A100</option>
              <option value="H100">H100</option>
              <option value="V100">V100</option>
              <option value="T4">T4</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1 text-slate-300">Location</label>
            <select
              value={offerFilters.location_filter || ''}
              onChange={(e) => handleFilterChange({ location_filter: e.target.value })}
              className="flex h-10 w-full rounded-lg border bg-slate-800/50 border-slate-600/50 text-slate-200 px-3 py-2 text-sm focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20"
            >
              <option value="">All Locations</option>
              <option value="US">United States</option>
              <option value="EU">Europe</option>
              <option value="AS">Asia</option>
              <option value="CA">Canada</option>
            </select>
          </div>
        </div>
      </div>

      {/* Results Header */}
      {offersResponse && (
        <div className="flex justify-between items-center">
          <div className="text-sm text-muted-foreground">
            Showing {offers.length} of {pagination?.total || 0} instances
            {offerFilters.search && (
              <span> matching &quot;{offerFilters.search}&quot;</span>
            )}
          </div>
          {loadingOffers && (
            <div className="text-sm text-muted-foreground flex items-center gap-2">
              <RefreshCw className="h-3 w-3 animate-spin" />
              Updating...
            </div>
          )}
        </div>
      )}

      {/* Instance Grid */}
      <div className="grid gap-4">
        {offers.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            {loadingOffers ? (
              'Loading instances...'
            ) : (
              'No instances match your criteria. Try adjusting your filters.'
            )}
          </div>
        ) : (
          offers.map((offer: VastOffer) => (
            <div
              key={offer.id}
              className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                formData.selected_offer?.id === offer.id
                  ? 'border-primary bg-primary/5'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
              onClick={() => updateFormData({ selected_offer: offer })}
            >
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <Server className="h-4 w-4" />
                    <span className="font-medium">{offer.gpu_name}</span>
                    {offer.verified && <Badge variant="secondary">Verified</Badge>}
                    {offer.datacenter && <Badge variant="outline">Datacenter</Badge>}
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4 text-sm text-muted-foreground">
                    <div className="flex items-center gap-1">
                      <Zap className="h-3 w-3" />
                      {offer.num_gpus} GPU{offer.num_gpus > 1 ? 's' : ''}
                    </div>
                    <div className="flex items-center gap-1">
                      <Cpu className="h-3 w-3" />
                      {offer.cpu_cores} cores
                    </div>
                    <div className="flex items-center gap-1">
                      <HardDrive className="h-3 w-3" />
                      {formatStorage(offer.cpu_ram)} CPU RAM
                    </div>
                    <div className="flex items-center gap-1">
                      <Zap className="h-3 w-3" />
                      {formatStorage(offer.gpu_ram)} GPU RAM
                    </div>
                    <div className="flex items-center gap-1">
                      <HardDrive className="h-3 w-3" />
                      {formatStorage(offer.disk_space)} Storage
                    </div>
                    <div className="flex items-center gap-1">
                      <Shield className="h-3 w-3" />
                      {(offer.reliability * 100).toFixed(0)}% reliable
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="text-xs">
                        {offer.total_flops.toFixed(1)} TFLOPS
                      </span>
                    </div>
                  </div>
                </div>
                
                <div className="text-right">
                  <div className="text-lg font-bold">
                    ${offer.dph_total.toFixed(3)}/hr
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {offer.geolocation}
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {pagination && pagination.total_pages > 1 && (
        <div className="flex justify-center items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => handlePageChange(pagination.page - 1)}
            disabled={!pagination.has_prev || loadingOffers}
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </Button>
          
          <div className="flex items-center gap-1">
            {Array.from({ length: Math.min(5, pagination.total_pages) }, (_, i) => {
              let pageNum;
              if (pagination.total_pages <= 5) {
                pageNum = i + 1;
              } else if (pagination.page <= 3) {
                pageNum = i + 1;
              } else if (pagination.page >= pagination.total_pages - 2) {
                pageNum = pagination.total_pages - 4 + i;
              } else {
                pageNum = pagination.page - 2 + i;
              }

              return (
                <Button
                  key={pageNum}
                  variant={pageNum === pagination.page ? "default" : "outline"}
                  size="sm"
                  onClick={() => handlePageChange(pageNum)}
                  disabled={loadingOffers}
                >
                  {pageNum}
                </Button>
              );
            })}
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => handlePageChange(pagination.page + 1)}
            disabled={!pagination.has_next || loadingOffers}
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}

function TimingCostStep({ formData, updateFormData, estimatedCost }: any) {
  const [minutes, setMinutes] = useState(0);
  const [hours, setHours] = useState(1);
  const [days, setDays] = useState(0);
  const [timeEstimate, setTimeEstimate] = useState<JobTimeEstimate | null>(null);
  const [loadingEstimate, setLoadingEstimate] = useState(false);

  const updateEndTime = useCallback((newMinutes: number, newHours: number, newDays: number) => {
    const totalHours = newDays * 24 + newHours + newMinutes / 60;
    const endTime = new Date(Date.now() + totalHours * 60 * 60 * 1000);
    updateFormData({ hard_end_time: endTime });
  }, [updateFormData]);

  useEffect(() => {
    const totalHours = days * 24 + hours + minutes / 60;
    const endTime = new Date(Date.now() + totalHours * 60 * 60 * 1000);
    updateFormData({ hard_end_time: endTime });
  }, [minutes, hours, days, updateFormData]);

  useEffect(() => {
    const fetchEstimate = async () => {
      if (!formData.selected_offer || !formData.hash_count || !formData.hash_type) {
        return;
      }

      // Find the hash type mode
      const selectedHashType = HASH_TYPES.find(type => type.value === formData.hash_type);
      if (!selectedHashType) return;

      setLoadingEstimate(true);
      try {
        const estimate = await jobApi.estimateTime({
          hash_mode: selectedHashType.mode,
          gpu_model: formData.selected_offer.gpu_name,
          num_gpus: formData.selected_offer.num_gpus,
          num_hashes: formData.hash_count,
          wordlist: formData.word_list,
          rule_files: formData.rule_files,
          custom_attack: formData.custom_attack
        });
        setTimeEstimate(estimate);

        // If estimated time is reasonable, suggest it as the default
        if (estimate.estimated_seconds > 0 && estimate.estimated_seconds < 86400 * 14) {
          // Add 20% buffer to the estimate
          const bufferSeconds = estimate.estimated_seconds * 1.2;
          const bufferDays = Math.floor(bufferSeconds / 86400);
          const bufferHours = Math.floor((bufferSeconds % 86400) / 3600);
          const bufferMinutes = Math.floor((bufferSeconds % 3600) / 60);

          // Only update if user hasn't manually set values yet
          if (days === 0 && hours === 1 && minutes === 0) {
            setDays(bufferDays);
            setHours(bufferHours);
            setMinutes(bufferMinutes);
            updateEndTime(bufferMinutes, bufferHours, bufferDays);
          }
        }
      } catch (error) {
        console.error('Failed to fetch time estimate:', error);
      } finally {
        setLoadingEstimate(false);
      }
    };

    // Debounce the estimate call to prevent excessive requests
    const timeoutId = setTimeout(() => {
      fetchEstimate();
    }, 500); // 500ms debounce

    return () => clearTimeout(timeoutId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formData.selected_offer, formData.hash_count, formData.hash_type, formData.word_list, formData.rule_files, formData.custom_attack]); // Intentionally exclude time-related deps to prevent excessive API calls

  const getTotalDuration = () => {
    const totalMinutes = days * 24 * 60 + hours * 60 + minutes;
    const totalHours = totalMinutes / 60;
    
    if (totalHours < 1) {
      return `${minutes} minute${minutes !== 1 ? 's' : ''}`;
    } else if (totalHours < 24) {
      const displayHours = Math.floor(totalHours);
      const displayMinutes = Math.round((totalHours - displayHours) * 60);
      if (displayMinutes === 0) {
        return `${displayHours} hour${displayHours !== 1 ? 's' : ''}`;
      }
      return `${displayHours}h ${displayMinutes}m`;
    } else {
      const displayDays = Math.floor(totalHours / 24);
      const remainingHours = Math.floor(totalHours % 24);
      if (remainingHours === 0) {
        return `${displayDays} day${displayDays !== 1 ? 's' : ''}`;
      }
      return `${displayDays}d ${remainingHours}h`;
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium mb-4">Maximum Runtime *</label>
        
        {/* Setup time warning */}
        <Alert className="mb-4">
          <Info className="h-4 w-4" />
          <AlertDescription>
            <strong>Important:</strong> Instance setup can take up to 5 minutes. Jobs are automatically terminated when complete, so it&apos;s better to overestimate than underestimate your runtime. Consider adding extra time to your estimate to account for setup and any unexpected delays.
          </AlertDescription>
        </Alert>
        
        <div className="space-y-4">
          {/* Days Slider */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="text-sm text-muted-foreground">Days</label>
              <span className="text-sm font-medium min-w-[3ch] text-right">{days}</span>
            </div>
            <input
              type="range"
              min="0"
              max="14"
              value={days}
              onChange={(e) => {
                const newDays = parseInt(e.target.value);
                setDays(newDays);
                updateEndTime(minutes, hours, newDays);
              }}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 
                       [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 
                       [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary 
                       [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:shadow-sm
                       [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:rounded-full 
                       [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:cursor-pointer
                       [&::-moz-range-thumb]:shadow-sm"
            />
          </div>

          {/* Hours Slider */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="text-sm text-muted-foreground">Hours</label>
              <span className="text-sm font-medium min-w-[3ch] text-right">{hours}</span>
            </div>
            <input
              type="range"
              min="0"
              max="23"
              value={hours}
              onChange={(e) => {
                const newHours = parseInt(e.target.value);
                setHours(newHours);
                updateEndTime(minutes, newHours, days);
              }}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 
                       [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 
                       [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary 
                       [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:shadow-sm
                       [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:rounded-full 
                       [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:cursor-pointer
                       [&::-moz-range-thumb]:shadow-sm"
            />
          </div>

          {/* Minutes Slider */}
          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="text-sm text-muted-foreground">Minutes</label>
              <span className="text-sm font-medium min-w-[3ch] text-right">{minutes}</span>
            </div>
            <input
              type="range"
              min="0"
              max="59"
              value={minutes}
              onChange={(e) => {
                const newMinutes = parseInt(e.target.value);
                setMinutes(newMinutes);
                updateEndTime(newMinutes, hours, days);
              }}
              className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-gray-700 
                       [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 
                       [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary 
                       [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:shadow-sm
                       [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:rounded-full 
                       [&::-moz-range-thumb]:bg-primary [&::-moz-range-thumb]:border-0 [&::-moz-range-thumb]:cursor-pointer
                       [&::-moz-range-thumb]:shadow-sm"
            />
          </div>
        </div>

        <p className="text-sm text-muted-foreground mt-3">
          Job will be forcibly stopped after this time limit
        </p>
      </div>

      {/* Time Estimate Card */}
      {timeEstimate && (
        <div className="p-4 bg-blue-50 dark:bg-blue-950/20 rounded-lg border border-blue-200 dark:border-blue-800">
          <div className="flex items-start gap-3">
            <Info className="h-5 w-5 text-blue-600 dark:text-blue-400 mt-0.5" />
            <div className="flex-1 space-y-2">
              <h3 className="font-medium text-blue-900 dark:text-blue-100">
                Estimated Runtime: {timeEstimate.formatted_time} - These are estimates based on varying benchmarks, these may not be accurate.
              </h3>
              <p className="text-sm text-blue-700 dark:text-blue-300 whitespace-pre-line">
                {timeEstimate.explanation}
              </p>
              {timeEstimate.confidence !== 'high' && (
                <p className="text-sm text-blue-600 dark:text-blue-400 italic">
                  Note: This is an estimate based on generic benchmarks. Actual time may vary.
                </p>
              )}
              {timeEstimate.warning && (
                <p className="text-sm text-orange-600 dark:text-orange-400 font-medium mt-2">
                  ⚠️ {timeEstimate.warning}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {loadingEstimate && (
        <div className="p-4 bg-gray-50 dark:bg-gray-900/50 rounded-lg">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <RefreshCw className="h-4 w-4 animate-spin" />
            Calculating time estimate...
          </div>
        </div>
      )}

      {formData.hard_end_time && (
        <div className="p-4 bg-accent/20 rounded-lg">
          <h3 className="font-medium mb-2">Cost Estimation</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span>Instance:</span>
              <span>{formData.selected_offer?.gpu_name}</span>
            </div>
            <div className="flex justify-between">
              <span>Rate:</span>
              <span>${formData.selected_offer?.dph_total.toFixed(3)}/hour</span>
            </div>
            <div className="flex justify-between">
              <span>Duration:</span>
              <span>{getTotalDuration()}</span>
            </div>
            <div className="flex justify-between font-medium border-t pt-2">
              <span>Estimated Cost:</span>
              <span>${estimatedCost.toFixed(2)}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ReviewSubmitStep({ formData, estimatedCost }: any) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h3 className="font-medium mb-3">Job Configuration</h3>
          <div className="space-y-2 text-sm">
            <div><strong>Name:</strong> {formData.name}</div>
            <div><strong>Hash Type:</strong> {formData.hash_type.toUpperCase()}</div>
            <div><strong>Hash File:</strong> {formData.hash_file?.name}</div>
            {formData.word_list && <div><strong>Wordlist:</strong> {formData.word_list}</div>}
            {formData.rule_files && formData.rule_files.length > 0 && (
              <div><strong>Rules:</strong> {formData.rule_files.join(', ')} ({formData.rule_files.length} rule{formData.rule_files.length !== 1 ? 's' : ''})</div>
            )}
            {formData.custom_attack && <div><strong>Custom Attack:</strong> {formData.custom_attack}</div>}
          </div>
        </div>

        <div>
          <h3 className="font-medium mb-3">Instance & Timing</h3>
          <div className="space-y-2 text-sm">
            <div><strong>Instance:</strong> {formData.selected_offer?.gpu_name}</div>
            <div><strong>GPUs:</strong> {formData.selected_offer?.num_gpus}</div>
            <div><strong>Location:</strong> {formData.selected_offer?.geolocation}</div>
            <div><strong>Max Runtime:</strong> {formData.hard_end_time && (() => {
              const totalMinutes = Math.round((formData.hard_end_time.getTime() - Date.now()) / (1000 * 60));
              const days = Math.floor(totalMinutes / (24 * 60));
              const hours = Math.floor((totalMinutes % (24 * 60)) / 60);
              const minutes = totalMinutes % 60;
              
              if (days > 0) {
                return hours > 0 ? `${days}d ${hours}h` : `${days} day${days !== 1 ? 's' : ''}`;
              } else if (hours > 0) {
                return minutes > 0 ? `${hours}h ${minutes}m` : `${hours} hour${hours !== 1 ? 's' : ''}`;
              } else {
                return `${minutes} minute${minutes !== 1 ? 's' : ''}`;
              }
            })()}</div>
            <div><strong>Est. Cost:</strong> ${estimatedCost.toFixed(2)}</div>
          </div>
        </div>
      </div>

      <Alert>
        <AlertDescription>
          <strong>Important:</strong> Your job will be automatically stopped when the time limit is reached, 
          regardless of completion status. Make sure to set an appropriate runtime limit.
        </AlertDescription>
      </Alert>
    </div>
  );
}