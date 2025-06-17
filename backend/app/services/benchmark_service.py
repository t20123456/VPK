"""Hashcat benchmark service for runtime estimation."""
from typing import Dict, Optional, Tuple
import math

class BenchmarkService:
    """Service for estimating hashcat job runtime based on hardware and attack parameters."""
    
    # GPU benchmark data: hash_mode -> gpu_model -> hashes_per_second
    # Based on hashcat benchmark mode (-b) results
    GPU_BENCHMARKS: Dict[str, Dict[str, int]] = {
        # MD5 (Mode 0)
        "0": {
            "RTX 5090": 210_000_000_000,  # 210 GH/s (estimated)
            "RTX 5080": 170_000_000_000,  # 170 GH/s (estimated)
            "RTX 5070 Ti": 140_000_000_000, # 140 GH/s (estimated)
            "RTX 5070": 110_000_000_000,  # 110 GH/s (estimated)
            "RTX 4090": 164_000_000_000,  # 164 GH/s
            "RTX 4080": 110_000_000_000,  # 110 GH/s
            "RTX 4070 Ti": 85_000_000_000,  # 85 GH/s
            "RTX 4070": 65_000_000_000,   # 65 GH/s
            "RTX 3090": 120_000_000_000,  # 120 GH/s
            "RTX 3080": 85_000_000_000,   # 85 GH/s
            "RTX 3070": 55_000_000_000,   # 55 GH/s
            "A100": 150_000_000_000,      # 150 GH/s
            "H100": 220_000_000_000,      # 220 GH/s
            "V100": 70_000_000_000,       # 70 GH/s
            "T4": 25_000_000_000,         # 25 GH/s
            "DEFAULT": 30_000_000_000,    # Conservative default
        },
        # SHA1 (Mode 100)
        "100": {
            "RTX 5090": 67_000_000_000,   # 67 GH/s (estimated)
            "RTX 5080": 54_000_000_000,   # 54 GH/s (estimated)
            "RTX 5070 Ti": 44_000_000_000, # 44 GH/s (estimated)
            "RTX 5070": 35_000_000_000,   # 35 GH/s (estimated)
            "RTX 4090": 52_000_000_000,   # 52 GH/s
            "RTX 4080": 35_000_000_000,   # 35 GH/s
            "RTX 4070 Ti": 27_000_000_000, # 27 GH/s
            "RTX 4070": 20_000_000_000,   # 20 GH/s
            "RTX 3090": 38_000_000_000,   # 38 GH/s
            "RTX 3080": 27_000_000_000,   # 27 GH/s
            "RTX 3070": 17_000_000_000,   # 17 GH/s
            "A100": 48_000_000_000,       # 48 GH/s
            "H100": 70_000_000_000,       # 70 GH/s
            "V100": 22_000_000_000,       # 22 GH/s
            "T4": 8_000_000_000,          # 8 GH/s
            "DEFAULT": 10_000_000_000,
        },
        # SHA256 (Mode 1400)
        "1400": {
            "RTX 5090": 30_000_000_000,   # 30 GH/s (estimated)
            "RTX 5080": 24_000_000_000,   # 24 GH/s (estimated)
            "RTX 5070 Ti": 19_000_000_000, # 19 GH/s (estimated)
            "RTX 5070": 15_000_000_000,   # 15 GH/s (estimated)
            "RTX 4090": 23_000_000_000,   # 23 GH/s
            "RTX 4080": 15_500_000_000,   # 15.5 GH/s
            "RTX 4070 Ti": 12_000_000_000, # 12 GH/s
            "RTX 4070": 9_000_000_000,    # 9 GH/s
            "RTX 3090": 17_000_000_000,   # 17 GH/s
            "RTX 3080": 12_000_000_000,   # 12 GH/s
            "RTX 3070": 7_500_000_000,    # 7.5 GH/s
            "A100": 21_000_000_000,       # 21 GH/s
            "H100": 31_000_000_000,       # 31 GH/s
            "V100": 10_000_000_000,       # 10 GH/s
            "T4": 3_500_000_000,          # 3.5 GH/s
            "DEFAULT": 5_000_000_000,
        },
        # SHA512 (Mode 1700)
        "1700": {
            "RTX 5090": 10_100_000_000,   # 10.1 GH/s (estimated)
            "RTX 5080": 8_200_000_000,    # 8.2 GH/s (estimated)
            "RTX 5070 Ti": 6_500_000_000,  # 6.5 GH/s (estimated)
            "RTX 5070": 5_200_000_000,    # 5.2 GH/s (estimated)
            "RTX 4090": 7_800_000_000,    # 7.8 GH/s
            "RTX 4080": 5_200_000_000,    # 5.2 GH/s
            "RTX 4070 Ti": 4_000_000_000,  # 4 GH/s
            "RTX 4070": 3_000_000_000,    # 3 GH/s
            "RTX 3090": 5_700_000_000,    # 5.7 GH/s
            "RTX 3080": 4_000_000_000,    # 4 GH/s
            "RTX 3070": 2_500_000_000,    # 2.5 GH/s
            "A100": 7_100_000_000,        # 7.1 GH/s
            "H100": 10_500_000_000,       # 10.5 GH/s
            "V100": 3_400_000_000,        # 3.4 GH/s
            "T4": 1_200_000_000,          # 1.2 GH/s
            "DEFAULT": 1_500_000_000,
        },
        # NTLM (Mode 1000)
        "1000": {
            "RTX 5090": 375_000_000_000,  # 375 GH/s (estimated)
            "RTX 5080": 300_000_000_000,  # 300 GH/s (estimated)
            "RTX 5070 Ti": 240_000_000_000, # 240 GH/s (estimated)
            "RTX 5070": 190_000_000_000,  # 190 GH/s (estimated)
            "RTX 4090": 288_000_000_000,  # 288 GH/s
            "RTX 4080": 193_000_000_000,  # 193 GH/s
            "RTX 4070 Ti": 150_000_000_000, # 150 GH/s
            "RTX 4070": 115_000_000_000,  # 115 GH/s
            "RTX 3090": 210_000_000_000,  # 210 GH/s
            "RTX 3080": 150_000_000_000,  # 150 GH/s
            "RTX 3070": 95_000_000_000,   # 95 GH/s
            "A100": 265_000_000_000,      # 265 GH/s
            "H100": 390_000_000_000,      # 390 GH/s
            "V100": 125_000_000_000,      # 125 GH/s
            "T4": 44_000_000_000,         # 44 GH/s
            "DEFAULT": 50_000_000_000,
        },
        # bcrypt (Mode 3200) - MUCH slower
        "3200": {
            "RTX 5090": 240_000,          # 240 KH/s (estimated)
            "RTX 5080": 195_000,          # 195 KH/s (estimated)
            "RTX 5070 Ti": 155_000,       # 155 KH/s (estimated)
            "RTX 5070": 120_000,          # 120 KH/s (estimated)
            "RTX 4090": 184_000,          # 184 KH/s
            "RTX 4080": 123_000,          # 123 KH/s
            "RTX 4070 Ti": 95_000,         # 95 KH/s
            "RTX 4070": 73_000,           # 73 KH/s
            "RTX 3090": 134_000,          # 134 KH/s
            "RTX 3080": 95_000,           # 95 KH/s
            "RTX 3070": 60_000,           # 60 KH/s
            "A100": 170_000,              # 170 KH/s
            "H100": 250_000,              # 250 KH/s
            "V100": 80_000,               # 80 KH/s
            "T4": 28_000,                 # 28 KH/s
            "DEFAULT": 30_000,
        },
        # WPA/WPA2 (Mode 2500/22000)
        "2500": {
            "RTX 5090": 2_600_000,        # 2.6 MH/s (estimated)
            "RTX 5080": 2_100_000,        # 2.1 MH/s (estimated)
            "RTX 5070 Ti": 1_700_000,     # 1.7 MH/s (estimated)
            "RTX 5070": 1_350_000,        # 1.35 MH/s (estimated)
            "RTX 4090": 2_000_000,        # 2 MH/s
            "RTX 4080": 1_350_000,        # 1.35 MH/s
            "RTX 4070 Ti": 1_050_000,      # 1.05 MH/s
            "RTX 4070": 800_000,          # 800 KH/s
            "RTX 3090": 1_470_000,        # 1.47 MH/s
            "RTX 3080": 1_050_000,        # 1.05 MH/s
            "RTX 3070": 660_000,          # 660 KH/s
            "A100": 1_850_000,            # 1.85 MH/s
            "H100": 2_750_000,            # 2.75 MH/s
            "V100": 880_000,              # 880 KH/s
            "T4": 310_000,                # 310 KH/s
            "DEFAULT": 400_000,
        },
        "22000": {  # Same as 2500 for WPA
            "RTX 5090": 2_600_000,
            "RTX 5080": 2_100_000,
            "RTX 5070 Ti": 1_700_000,
            "RTX 5070": 1_350_000,
            "RTX 4090": 2_000_000,
            "RTX 4080": 1_350_000,
            "RTX 4070 Ti": 1_050_000,
            "RTX 4070": 800_000,
            "RTX 3090": 1_470_000,
            "RTX 3080": 1_050_000,
            "RTX 3070": 660_000,
            "A100": 1_850_000,
            "H100": 2_750_000,
            "V100": 880_000,
            "T4": 310_000,
            "DEFAULT": 400_000,
        },
        
        # Active Directory Hash Types
        
        # Domain Cached Credentials (DCC) - Mode 1100
        "1100": {
            "RTX 5090": 45_000_000_000,   # 45 GH/s (estimated)
            "RTX 5080": 36_000_000_000,   # 36 GH/s (estimated)
            "RTX 5070 Ti": 29_000_000_000, # 29 GH/s (estimated)
            "RTX 5070": 23_000_000_000,   # 23 GH/s (estimated)
            "RTX 4090": 35_000_000_000,   # 35 GH/s
            "RTX 4080": 23_500_000_000,   # 23.5 GH/s
            "RTX 4070 Ti": 18_000_000_000, # 18 GH/s
            "RTX 4070": 14_000_000_000,   # 14 GH/s
            "RTX 3090": 25_500_000_000,   # 25.5 GH/s
            "RTX 3080": 18_000_000_000,   # 18 GH/s
            "RTX 3070": 11_500_000_000,   # 11.5 GH/s
            "A100": 32_000_000_000,       # 32 GH/s
            "H100": 47_000_000_000,       # 47 GH/s
            "V100": 15_000_000_000,       # 15 GH/s
            "T4": 5_200_000_000,          # 5.2 GH/s
            "DEFAULT": 7_500_000_000,
        },
        
        # Domain Cached Credentials 2 (DCC2) - Mode 2100
        "2100": {
            "RTX 5090": 1_300_000,        # 1.3 MH/s (estimated)
            "RTX 5080": 1_050_000,        # 1.05 MH/s (estimated)
            "RTX 5070 Ti": 850_000,       # 850 KH/s (estimated)
            "RTX 5070": 680_000,          # 680 KH/s (estimated)
            "RTX 4090": 1_000_000,        # 1 MH/s
            "RTX 4080": 670_000,          # 670 KH/s
            "RTX 4070 Ti": 520_000,       # 520 KH/s
            "RTX 4070": 400_000,          # 400 KH/s
            "RTX 3090": 730_000,          # 730 KH/s
            "RTX 3080": 520_000,          # 520 KH/s
            "RTX 3070": 330_000,          # 330 KH/s
            "A100": 920_000,              # 920 KH/s
            "H100": 1_380_000,            # 1.38 MH/s
            "V100": 440_000,              # 440 KH/s
            "T4": 155_000,                # 155 KH/s
            "DEFAULT": 200_000,
        },
        
        # NetNTLMv1 - Mode 5500
        "5500": {
            "RTX 5090": 150_000_000_000,  # 150 GH/s (estimated)
            "RTX 5080": 120_000_000_000,  # 120 GH/s (estimated)
            "RTX 5070 Ti": 96_000_000_000, # 96 GH/s (estimated)
            "RTX 5070": 76_000_000_000,   # 76 GH/s (estimated)
            "RTX 4090": 115_000_000_000,  # 115 GH/s
            "RTX 4080": 77_000_000_000,   # 77 GH/s
            "RTX 4070 Ti": 60_000_000_000, # 60 GH/s
            "RTX 4070": 46_000_000_000,   # 46 GH/s
            "RTX 3090": 84_000_000_000,   # 84 GH/s
            "RTX 3080": 60_000_000_000,   # 60 GH/s
            "RTX 3070": 38_000_000_000,   # 38 GH/s
            "A100": 106_000_000_000,      # 106 GH/s
            "H100": 156_000_000_000,      # 156 GH/s
            "V100": 50_000_000_000,       # 50 GH/s
            "T4": 17_600_000_000,         # 17.6 GH/s
            "DEFAULT": 20_000_000_000,
        },
        
        # NetNTLMv2 - Mode 5600
        "5600": {
            "RTX 5090": 6_500_000_000,    # 6.5 GH/s (estimated)
            "RTX 5080": 5_200_000_000,    # 5.2 GH/s (estimated)
            "RTX 5070 Ti": 4_200_000_000,  # 4.2 GH/s (estimated)
            "RTX 5070": 3_300_000_000,    # 3.3 GH/s (estimated)
            "RTX 4090": 5_000_000_000,    # 5 GH/s
            "RTX 4080": 3_350_000_000,    # 3.35 GH/s
            "RTX 4070 Ti": 2_600_000_000,  # 2.6 GH/s
            "RTX 4070": 2_000_000_000,    # 2 GH/s
            "RTX 3090": 3_650_000_000,    # 3.65 GH/s
            "RTX 3080": 2_600_000_000,    # 2.6 GH/s
            "RTX 3070": 1_650_000_000,    # 1.65 GH/s
            "A100": 4_600_000_000,        # 4.6 GH/s
            "H100": 6_800_000_000,        # 6.8 GH/s
            "V100": 2_170_000_000,        # 2.17 GH/s
            "T4": 770_000_000,            # 770 MH/s
            "DEFAULT": 1_000_000_000,
        },
        
        # LM Hash - Mode 3000
        "3000": {
            "RTX 5090": 385_000_000_000,  # 385 GH/s (estimated)
            "RTX 5080": 310_000_000_000,  # 310 GH/s (estimated)
            "RTX 5070 Ti": 250_000_000_000, # 250 GH/s (estimated)
            "RTX 5070": 195_000_000_000,  # 195 GH/s (estimated)
            "RTX 4090": 296_000_000_000,  # 296 GH/s
            "RTX 4080": 198_000_000_000,  # 198 GH/s
            "RTX 4070 Ti": 154_000_000_000, # 154 GH/s
            "RTX 4070": 118_000_000_000,  # 118 GH/s
            "RTX 3090": 216_000_000_000,  # 216 GH/s
            "RTX 3080": 154_000_000_000,  # 154 GH/s
            "RTX 3070": 98_000_000_000,   # 98 GH/s
            "A100": 272_000_000_000,      # 272 GH/s
            "H100": 400_000_000_000,      # 400 GH/s
            "V100": 128_000_000_000,      # 128 GH/s
            "T4": 45_000_000_000,         # 45 GH/s
            "DEFAULT": 50_000_000_000,
        },
        
        # Kerberos 5 AS-REP etype 23 - Mode 18200
        "18200": {
            "RTX 5090": 13_000_000_000,   # 13 GH/s (estimated)
            "RTX 5080": 10_400_000_000,   # 10.4 GH/s (estimated)
            "RTX 5070 Ti": 8_400_000_000,  # 8.4 GH/s (estimated)
            "RTX 5070": 6_700_000_000,    # 6.7 GH/s (estimated)
            "RTX 4090": 10_000_000_000,   # 10 GH/s
            "RTX 4080": 6_700_000_000,    # 6.7 GH/s
            "RTX 4070 Ti": 5_200_000_000,  # 5.2 GH/s
            "RTX 4070": 4_000_000_000,    # 4 GH/s
            "RTX 3090": 7_300_000_000,    # 7.3 GH/s
            "RTX 3080": 5_200_000_000,    # 5.2 GH/s
            "RTX 3070": 3_300_000_000,    # 3.3 GH/s
            "A100": 9_200_000_000,        # 9.2 GH/s
            "H100": 13_600_000_000,       # 13.6 GH/s
            "V100": 4_340_000_000,        # 4.34 GH/s
            "T4": 1_540_000_000,          # 1.54 GH/s
            "DEFAULT": 2_000_000_000,
        },
        
        # Kerberos 5 TGS-REP etype 23 - Mode 13100
        "13100": {
            "RTX 5090": 4_550_000_000,    # 4.55 GH/s (estimated)
            "RTX 5080": 3_650_000_000,    # 3.65 GH/s (estimated)
            "RTX 5070 Ti": 2_950_000_000,  # 2.95 GH/s (estimated)
            "RTX 5070": 2_350_000_000,    # 2.35 GH/s (estimated)
            "RTX 4090": 3_500_000_000,    # 3.5 GH/s
            "RTX 4080": 2_350_000_000,    # 2.35 GH/s
            "RTX 4070 Ti": 1_820_000_000,  # 1.82 GH/s
            "RTX 4070": 1_400_000_000,    # 1.4 GH/s
            "RTX 3090": 2_560_000_000,    # 2.56 GH/s
            "RTX 3080": 1_820_000_000,    # 1.82 GH/s
            "RTX 3070": 1_155_000_000,    # 1.155 GH/s
            "A100": 3_220_000_000,        # 3.22 GH/s
            "H100": 4_760_000_000,        # 4.76 GH/s
            "V100": 1_520_000_000,        # 1.52 GH/s
            "T4": 539_000_000,            # 539 MH/s
            "DEFAULT": 700_000_000,
        },
    }
    
    # Average wordlist sizes (in millions of passwords)
    WORDLIST_SIZES = {
        "rockyou.txt": 14_344_392,
        "crackstation.txt": 1_493_677_782,  # 1.5 billion
        "weakpass_3a": 987_054_321,
        "top-passwords.txt": 10_000_000,
        "common-passwords.txt": 1_000_000,
        "default": 100_000_000,  # 100M as default
    }
    
    # Common rule counts
    RULE_COUNTS = {
        "best64.rule": 64,
        "dive.rule": 99092,
        "d3ad0ne.rule": 34324,
        "rockyou-30000.rule": 30000,
        "OneRuleToRuleThemAll.rule": 52014,
        "OneRuleToRuleThemStill.rule": 48414,  # Actual rule count from the file
        "T0XlC-insert_space_and_special_0_F.rule": 480,  # Add T0XlC rule
        "leetspeak.rule": 256,
        "combinator.rule": 1024,
        "default": 10000,  # Increased default for better estimates
    }
    
    @classmethod
    def get_gpu_benchmark(cls, hash_mode: str, gpu_model: str, num_gpus: int = 1) -> int:
        """
        Get benchmark speed for given GPU and hash mode.
        Returns hashes per second.
        """
        # Normalize GPU model name
        gpu_model = gpu_model.upper()
        for key in cls.GPU_BENCHMARKS.get(hash_mode, {}).keys():
            if key.upper() in gpu_model or gpu_model in key.upper():
                base_speed = cls.GPU_BENCHMARKS[hash_mode][key]
                # Scale linearly with GPU count (slight efficiency loss)
                return int(base_speed * num_gpus * 0.95)  # 95% efficiency for multi-GPU
        
        # Fallback to default if GPU not found
        default_speed = cls.GPU_BENCHMARKS.get(hash_mode, {}).get("DEFAULT", 1_000_000_000)
        return int(default_speed * num_gpus * 0.95)
    
    @classmethod
    def get_wordlist_size(cls, wordlist_name: Optional[str]) -> int:
        """Get estimated wordlist size."""
        if not wordlist_name:
            return 0
        
        # First try to get line count from wordlist service (catalog + S3 metadata)
        try:
            from app.services.wordlist_service import get_wordlist_service
            from app.core.database import SessionLocal
            
            db = SessionLocal()
            try:
                wordlist_service = get_wordlist_service(db)
                enhanced_wordlists = wordlist_service.list_wordlists_with_metadata()
                
                # Find matching wordlist by key or name
                for wordlist in enhanced_wordlists:
                    if wordlist.get("key") == wordlist_name or wordlist.get("name") == wordlist_name.split('/')[-1]:
                        line_count = wordlist.get("line_count")
                        if line_count and isinstance(line_count, (int, float)):
                            print(f"Found line count for {wordlist_name}: {line_count:,}")
                            return int(line_count)
            finally:
                db.close()
        except Exception as e:
            print(f"Warning: Could not get line count from wordlist service: {e}")
        
        # Fallback to filename-based lookup
        filename = wordlist_name.split('/')[-1].lower()
        
        for key, size in cls.WORDLIST_SIZES.items():
            if key.lower() in filename:
                return size
        
        return cls.WORDLIST_SIZES["default"]
    
    @classmethod
    def get_rule_count(cls, rule_name: Optional[str]) -> int:
        """Get rule count for given rule file."""
        if not rule_name:
            return 1  # No rules = 1x multiplier
        
        # First try to get the actual count from S3 metadata
        try:
            from app.services.s3_client import S3Client
            s3_client = S3Client()
            file_info = s3_client.get_file_info(rule_name)
            
            if file_info and 'rule_count' in file_info.get('metadata', {}):
                rule_count = int(file_info['metadata']['rule_count'])
                print(f"Using S3 metadata rule count for {rule_name}: {rule_count:,}")
                return rule_count
        except Exception as e:
            print(f"Warning: Could not get rule count from S3 metadata: {e}")
        
        # Fallback to filename-based lookup
        filename = rule_name.split('/')[-1].lower()
        
        # First try exact match
        for key, count in cls.RULE_COUNTS.items():
            if key.lower() == filename:
                print(f"Using hardcoded rule count for {filename}: {count:,}")
                return count
        
        # Then try partial matching for common patterns
        if "onerule" in filename:
            if "still" in filename:
                return cls.RULE_COUNTS["OneRuleToRuleThemStill.rule"]
            else:
                return cls.RULE_COUNTS["OneRuleToRuleThemAll.rule"]
        
        if "t0xlc" in filename or "toxic" in filename:
            return cls.RULE_COUNTS["T0XlC-insert_space_and_special_0_F.rule"]
        
        if "dive" in filename:
            return cls.RULE_COUNTS["dive.rule"]
        
        if "best64" in filename:
            return cls.RULE_COUNTS["best64.rule"]
        
        # Finally try substring matching
        for key, count in cls.RULE_COUNTS.items():
            if key.lower() in filename:
                return count
        
        return cls.RULE_COUNTS["default"]
    
    @classmethod
    def estimate_runtime(
        cls,
        hash_mode: str,
        gpu_model: str,
        num_gpus: int,
        num_hashes: int,
        wordlist: Optional[str] = None,
        rule_files: Optional[list] = None,
        custom_attack: Optional[str] = None
    ) -> Tuple[int, str]:
        """
        Estimate runtime in seconds and return explanation.
        
        Returns:
            Tuple of (estimated_seconds, explanation_string)
        """
        # Get GPU benchmark speed
        hashes_per_second = cls.get_gpu_benchmark(hash_mode, gpu_model, num_gpus)
        
        # Calculate total candidates
        if custom_attack:
            # For custom attacks, estimate based on mask complexity
            # This is a rough estimate
            if "?l?l?l?l" in custom_attack:  # 4 lowercase
                total_candidates = 26 ** 4  # 456,976
            elif "?l?l?l?l?l" in custom_attack:  # 5 lowercase
                total_candidates = 26 ** 5  # 11,881,376
            elif "?l?l?l?l?l?l" in custom_attack:  # 6 lowercase
                total_candidates = 26 ** 6  # 308,915,776
            elif "?a?a?a?a?a?a" in custom_attack:  # 6 all chars
                total_candidates = 95 ** 6  # 735,091,890,625
            elif "?a?a?a?a?a?a?a?a" in custom_attack:  # 8 all chars
                total_candidates = 95 ** 8  # 6,634,204,312,890,625
            else:
                # Default estimate for unknown masks
                total_candidates = 1_000_000_000
            
            explanation = f"Custom attack with ~{total_candidates:,} candidates"
            explanation += "\n\n⚠️ WARNING: Time estimates for custom attacks are NOT accurate."
            explanation += "\nActual runtime depends on mask complexity and cannot be reliably estimated."
            explanation += "\nYou must account for actual runtime yourself."
        else:
            # Dictionary attack
            wordlist_size = cls.get_wordlist_size(wordlist)
            
            # Calculate total rule count from multiple rule files
            # Mathematical model: Total Candidates = |W| × ∏(i=1 to n) |Ri|
            # Multiple -r flags in hashcat create rule chains, where each word gets
            # processed through all combinations of rules across files sequentially
            # Example: 2 rule files with 48,414 and 480 rules = 48,414 × 480 = 23,238,720 combinations
            if rule_files and len(rule_files) > 0:
                total_rule_count = 1  # Start with 1 for multiplication
                rule_details = []
                for rule_file in rule_files:
                    file_rule_count = cls.get_rule_count(rule_file)
                    total_rule_count *= file_rule_count  # Multiplicative for rule chaining
                    rule_details.append(f"{rule_file}: {file_rule_count:,}")
                rule_count = total_rule_count
                
                # Add safety check for exponential growth
                if rule_count > 1_000_000_000:  # 1 billion rule combinations
                    print(f"WARNING: Very large rule combination count: {rule_count:,}")
                    print("This may result in extremely long runtime!")
            else:
                rule_count = cls.get_rule_count(None)  # Default single rule count
            
            # If no wordlist is specified, assume a default dictionary attack
            if wordlist_size == 0:
                wordlist_size = 100_000_000  # 100M default wordlist size
                explanation = f"Dictionary attack: ~{wordlist_size:,} passwords (default wordlist)"
            else:
                explanation = f"Dictionary attack: {wordlist_size:,} passwords"
            
            total_candidates = wordlist_size * rule_count
            
            if rule_files and len(rule_files) > 1:
                # Show the multiplicative nature of multiple rule files
                individual_counts = [cls.get_rule_count(rf) for rf in rule_files]
                rule_multiplication = " × ".join([f"{count:,}" for count in individual_counts])
                explanation += f" × ({rule_multiplication} rule combinations) = {total_candidates:,} candidates"
                
                # Add strong warning for multiple rules
                explanation += "\n\n⚠️ WARNING: Time estimates for multiple rule files are NOT accurate."
                explanation += "\nRule interactions and amplification effects make reliable estimation impossible."
                explanation += "\nLarge rule chains may exhaust system memory."
                explanation += "\nYou must account for actual runtime yourself."
            elif rule_count > 1:
                explanation += f" × {rule_count:,} rules = {total_candidates:,} candidates"
        
        # Calculate time
        # Time = (total_candidates * num_hashes) / hashes_per_second
        if num_hashes > 1:
            # Hashcat processes multiple hashes efficiently
            # Time doesn't scale linearly with hash count
            efficiency_factor = min(1.0, 1.0 / math.log10(num_hashes + 1))
            effective_hashes = 1 + (num_hashes - 1) * efficiency_factor
        else:
            effective_hashes = num_hashes
        
        total_operations = total_candidates * effective_hashes
        cracking_time_seconds = max(1, int(total_operations / hashes_per_second))  # Minimum 1 second
        
        # Cap extremely long estimates (more than 30 days) and add warning
        max_reasonable_time = 30 * 24 * 3600  # 30 days in seconds
        if cracking_time_seconds > max_reasonable_time:
            explanation += f"\n⚠️  EXTREME WARNING: Estimated time exceeds 30 days! Consider reducing rule files or using smaller wordlists."
            cracking_time_seconds = max_reasonable_time  # Cap the estimate
        
        # Add buffer for initialization, file transfers, instance setup, etc.
        # Instance setup can take up to 5 minutes, this may vary massivley depending on wordlist downloaded but 5 mins is pretty safe given data transfer speeds.
        overhead_seconds = 300  # 5 minutes overhead for setup
        estimated_seconds = cracking_time_seconds + overhead_seconds
        
        # Format explanation with performance info
        explanation += f"\nGPU Performance: {hashes_per_second:,} H/s ({gpu_model} × {num_gpus})"
        explanation += f"\nHash count: {num_hashes:,} hashes"
        explanation += f"\nCracking time: {cls.format_time(cracking_time_seconds)}"
        explanation += f"\nSetup overhead: ~5 minutes"
        
        return estimated_seconds, explanation
    
    @classmethod
    def format_time(cls, seconds: int) -> str:
        """Format seconds into human-readable time."""
        if seconds < 60:
            return f"{seconds} seconds"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif seconds < 86400:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if minutes > 0:
                return f"{hours}h {minutes}m"
            return f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            if hours > 0:
                return f"{days}d {hours}h"
            return f"{days} day{'s' if days != 1 else ''}"


# Export service
benchmark_service = BenchmarkService()