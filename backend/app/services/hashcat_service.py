from typing import Dict, List, Optional
import os
from enum import Enum

from app.models.job import Job


class HashcatMode(Enum):
    """Hashcat attack modes"""
    STRAIGHT = 0    # Dictionary attack
    COMBINATION = 1 # Combination attack
    BRUTE_FORCE = 3 # Brute-force attack
    HYBRID_WL_MASK = 6  # Hybrid Wordlist + Mask
    HYBRID_MASK_WL = 7  # Hybrid Mask + Wordlist


class HashType(Enum):
    """Common hash types with their hashcat mode numbers"""
    MD5 = 0
    SHA1 = 100
    SHA256 = 1400
    SHA512 = 1700
    NTLM = 1000
    LM = 3000
    MD4 = 900
    SHA224 = 1300
    SHA384 = 10800
    RIPEMD160 = 6000
    WHIRLPOOL = 6100


class HashcatService:
    def __init__(self):
        self.hashcat_binary = "hashcat"
        self.base_args = [
            "--force",           # Ignore warnings
            "--hwmon-disable",   # Disable hardware monitoring
            "--status",          # Enable status screen
            "--status-timer=5",  # Status update every 5 seconds
            "--machine-readable" # Machine readable output
        ]
    
    def get_hash_mode(self, hash_type: str) -> int:
        """Get hashcat mode number for hash type"""
        # If it's already a number, return it
        if hash_type.isdigit():
            return int(hash_type)
        
        hash_type_upper = hash_type.upper()
        try:
            return HashType[hash_type_upper].value
        except KeyError:
            hash_mappings = {
                # Basic hashes
                'MD5': 0,
                'SHA1': 100, 'SHA-1': 100,
                'SHA256': 1400, 'SHA-256': 1400,
                'SHA512': 1700, 'SHA-512': 1700,
                'MD4': 900,
                'SHA224': 1300, 'SHA-224': 1300,
                'SHA384': 10800, 'SHA-384': 10800,
                'RIPEMD160': 6000, 'RIPEMD-160': 6000,
                'WHIRLPOOL': 6100,
                
                # Windows/AD hashes
                'NTLM': 1000,
                'LM': 3000,
                'NTLMV2': 5600, 'NETNTLMV2': 5600,
                'NETNTLMV1': 5500, 'NTLMV1': 5500,
                'MSCASH': 1100, 'DCC': 1100,
                'MSCASH2': 2100, 'DCC2': 2100,
                
                # Kerberos
                'KERBEROS': 13100, 'KRB5TGS': 13100, 'KERBEROAST': 13100,
                'KRB5ASREP': 18200, 'ASREPROAST': 18200,
                
                # WiFi
                'WPA': 2500, 'WPA2': 22000, 'WPA3': 22000,
                
                # Other common
                'BCRYPT': 3200,
                'SHA512CRYPT': 1800,
                'OFFICE2013': 9600,
                
                # PostgreSQL hashes
                'POSTGRESQL': 12,
                'POSTGRESQL-MD5': 12,
                'POSTGRESQL-SCRAM-SHA-256': 28600
            }
            return hash_mappings.get(hash_type_upper, 0)  # Default to MD5
    
    def build_command(self, job: Job, wordlist_path: str = None, rules_paths: List[str] = None, skip_validation: bool = False) -> List[str]:
        """Build hashcat command for a job with support for multiple rule files"""
        if not skip_validation and (not job.hash_file_path or not os.path.exists(job.hash_file_path)):
            raise ValueError("Hash file not found")
        
        hash_mode = self.get_hash_mode(job.hash_type)
        
        # Base command
        cmd = [self.hashcat_binary] + self.base_args
        
        # Hash mode
        cmd.extend(["-m", str(hash_mode)])
        
        # Attack mode and parameters
        mask_parts = []  # Parts that go after hash file
        is_hybrid_attack = False
        attack_mode = None
        
        if job.custom_attack:
            # Custom attack - parse the command to separate flags from masks
            custom_parts = job.custom_attack.strip().split()
            attack_flags = []
            
            i = 0
            while i < len(custom_parts):
                if custom_parts[i] == '-a' and i + 1 < len(custom_parts):
                    # Attack mode flag with its value
                    attack_mode = custom_parts[i + 1]
                    attack_flags.extend(['-a', attack_mode])
                    # Check if this is a hybrid attack (mode 6 or 7)
                    if attack_mode in ['6', '7']:
                        is_hybrid_attack = True
                    i += 2
                elif '?' in custom_parts[i]:
                    # Mask pattern (contains ? character) - goes after hash file
                    mask_parts.append(custom_parts[i])
                    i += 1
                elif custom_parts[i].startswith('-'):
                    # Other flags (before hash file)
                    attack_flags.append(custom_parts[i])
                    # Check if this flag has a value
                    if i + 1 < len(custom_parts) and not custom_parts[i + 1].startswith('-'):
                        attack_flags.append(custom_parts[i + 1])
                        i += 2
                    else:
                        i += 1
                else:
                    # Non-flag, non-mask parts (could be wordlist for hybrid attacks)
                    if not (is_hybrid_attack and custom_parts[i].endswith('.txt')):
                        mask_parts.append(custom_parts[i])
                    i += 1
            
            # Add attack flags before hash file
            cmd.extend(attack_flags)
        else:
            # Standard dictionary attack
            cmd.extend(["-a", str(HashcatMode.STRAIGHT.value)])
        
        # Hash file
        cmd.append(job.hash_file_path)
        
        # Handle wordlist and mask positioning based on attack mode
        if is_hybrid_attack:
            if attack_mode == '6':
                # Mode 6: wordlist + mask (wordlist first, then mask)
                if wordlist_path:
                    cmd.append(wordlist_path)
                if mask_parts:
                    cmd.extend(mask_parts)
            elif attack_mode == '7':
                # Mode 7: mask + wordlist (mask first, then wordlist)
                if mask_parts:
                    cmd.extend(mask_parts)
                if wordlist_path:
                    cmd.append(wordlist_path)
        else:
            # Standard dictionary attack or non-hybrid custom attack
            if wordlist_path and not job.custom_attack:
                cmd.append(wordlist_path)
            # Add mask parts for non-hybrid custom attacks (like brute force)
            if mask_parts and not is_hybrid_attack:
                cmd.extend(mask_parts)
        
        # Rules files - support multiple rule files
        if rules_paths:
            for rules_path in rules_paths:
                if rules_path and (skip_validation or os.path.exists(rules_path)):
                    cmd.extend(["-r", rules_path])
        
        # Output files - use tmpfs paths for security (no disk persistence)
        pot_file = "/dev/shm/hashcat_secure/hashcat.pot"
        output_file = "/dev/shm/hashcat_secure/cracked.txt"
        
        cmd.extend([
            "--potfile-path", pot_file,
            "-o", output_file,  # Main output file for cracked passwords
            "--outfile-format", "2"  # Format: hash:password
        ])
        
        return cmd
    
    def build_benchmark_command(self, hash_mode: int) -> List[str]:
        """Build hashcat benchmark command"""
        cmd = [
            self.hashcat_binary,
            "--benchmark",
            "--machine-readable",
            "-m", str(hash_mode)
        ]
        return cmd
    
    def parse_status_output(self, output: str) -> Dict:
        """Parse hashcat status output"""
        lines = output.strip().split('\n')
        status = {}
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower().replace(' ', '_')
                value = value.strip()
                
                # Parse specific status fields
                if key == 'progress':
                    # Format: "123456/1000000 (12.35%)"
                    if '(' in value and ')' in value:
                        percentage = value.split('(')[1].split('%')[0]
                        try:
                            status['progress_percentage'] = float(percentage)
                        except ValueError:
                            status['progress_percentage'] = 0.0
                elif key == 'speed':
                    status['speed'] = value
                elif key == 'time':
                    status['elapsed_time'] = value
                elif key == 'eta':
                    status['estimated_time_remaining'] = value
                elif key == 'status':
                    status['current_status'] = value
                
                status[key] = value
        
        return status
    
    def validate_hash_file(self, file_path: str, hash_type: str) -> Dict:
        """Validate hash file format"""
        if not os.path.exists(file_path):
            return {"valid": False, "error": "File not found"}
        
        try:
            with open(file_path, 'r') as f:
                content = f.read().strip()
                lines = content.split('\n')
                
                if not lines or not lines[0]:
                    return {"valid": False, "error": "Empty file"}
                
                # Basic hash format validation
                hash_lengths = {
                    'md5': 32,
                    'sha1': 40,
                    'sha256': 64,
                    'sha512': 128,
                    'ntlm': 32,
                    'lm': 32,
                    'postgresql': 35,  # MD5 format: md5 + 32 hex chars
                    'postgresql-md5': 35,
                    'postgresql-scram-sha-256': None  # Variable length
                }
                
                expected_length = hash_lengths.get(hash_type.lower())
                if expected_length:
                    first_hash = lines[0].split(':')[0] if ':' in lines[0] else lines[0]
                    if len(first_hash) != expected_length:
                        return {
                            "valid": False, 
                            "error": f"Invalid hash length for {hash_type}. Expected {expected_length}, got {len(first_hash)}"
                        }
                
                return {
                    "valid": True,
                    "hash_count": len([line for line in lines if line.strip()]),
                    "has_usernames": ':' in lines[0] if lines else False
                }
                
        except Exception as e:
            return {"valid": False, "error": f"Error reading file: {str(e)}"}
    
    def estimate_completion_time(self, hash_count: int, hash_type: str, wordlist_size: int = None) -> Optional[int]:
        """Estimate job completion time in seconds"""
        # Base speeds (hashes per second) for different hash types on average GPU
        base_speeds = {
            'md5': 10000000000,      # 10 GH/s
            'sha1': 3000000000,      # 3 GH/s
            'sha256': 1000000000,    # 1 GH/s
            'sha512': 300000000,     # 300 MH/s
            'ntlm': 15000000000,     # 15 GH/s
            'lm': 20000000000,       # 20 GH/s
        }
        
        speed = base_speeds.get(hash_type.lower(), 1000000000)  # Default 1 GH/s
        
        if wordlist_size:
            total_attempts = wordlist_size * hash_count
        else:
            # Assume average wordlist size
            total_attempts = 14000000 * hash_count  # rockyou.txt size
        
        # Estimate time in seconds
        estimated_seconds = total_attempts / speed
        
        # Add some overhead (20%)
        return int(estimated_seconds * 1.2)