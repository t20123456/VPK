import asyncio
import subprocess
import json
import os
import re
from typing import List, Dict, Optional, Any
from datetime import datetime

from app.services.settings_service import get_settings_service


class VastAIClient:
    def __init__(self, api_key: str = None):
        if api_key:
            self.api_key = api_key
        else:
            settings_service = get_settings_service()
            self.api_key = settings_service.get_vast_api_key()
        
        # SSH stderr patterns to filter out
        self.ssh_noise_patterns = [
            r"Warning: Permanently added '[^']+' \([^)]+\) to the list of known hosts\.",
            r"Welcome to vast\.ai\.",
            r"If authentication fails, try again after a few seconds",
            r"and double check your ssh key",
            r"Have fun!",
        ]
    
    async def _run_vastai_command(self, command: List[str]) -> Dict[str, Any]:
        """Run a vastai CLI command and return parsed JSON result"""
        # Set API key as environment variable if provided
        env = {}
        if self.api_key:
            env["VAST_API_KEY"] = self.api_key
        
        try:
            # Run the command
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**dict(os.environ), **env} if env else None
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"Vast.ai CLI error: {stderr.decode().strip()}")
            
            # Parse JSON output
            output = stdout.decode().strip()
            if output:
                return json.loads(output)
            return {}
            
        except json.JSONDecodeError as e:
            # Some commands might not return JSON or return empty output
            if output.strip():
                # Try to return the raw output if it's not empty
                print(f"Non-JSON output from vastai command: {output}")
                return {"raw_output": output}
            else:
                # Check if command succeeded but returned no output
                if process.returncode == 0:
                    print("Command succeeded but returned no output")
                    return {"success": True}
                else:
                    raise Exception(f"Failed to parse Vast.ai CLI output (empty): {stderr.decode()}")
        except Exception as e:
            raise Exception(f"Vast.ai CLI error: {str(e)}")
    
    async def get_offers(self, 
                        secure_cloud: bool = True,
                        verified: bool = True,
                        max_cost_per_hour: float = None,
                        region: str = "global") -> List[Dict[str, Any]]:
        """Get available GPU instances using vastai CLI"""
        
        # Build the search query according to Vast.ai CLI syntax
        query_parts = []
        
        if verified:
            query_parts.append("verified=true")
        
        if secure_cloud:
            query_parts.append("reliability>0.9")  # High reliability for secure cloud
        
        if max_cost_per_hour:
            query_parts.append(f"dph_total<={max_cost_per_hour}")
        else:
            # Set a reasonable default max cost
            query_parts.append("dph_total<=10.0")
        
        # Add geographical filter using correct vast.ai CLI syntax
        if region and region.lower() == "europe":
            # Comprehensive list of European countries including Iceland
            european_countries = [
                "DE", "FR", "NL", "GB", "SE", "NO", "FI", "IT", "ES", "AT",
                "BE", "DK", "IE", "PT", "CH", "PL", "CZ", "HU", "RO", "BG",
                "HR", "SI", "SK", "EE", "LV", "LT", "LU", "MT", "CY", "IS",
                "GR", "RS", "BA", "ME", "MK", "AL", "XK", "MD", "UA", "BY"
            ]
            query_parts.append(f"geolocation in [{','.join(european_countries)}]")
        elif region and region.lower() == "us":
            # US country code only
            query_parts.append("geolocation=US")
        elif region and region.lower() == "global":
            # Include comprehensive EU list + US + Canada
            all_countries = [
                # European countries including Iceland and other Nordic countries
                "DE", "FR", "NL", "GB", "SE", "NO", "FI", "IT", "ES", "AT",
                "BE", "DK", "IE", "PT", "CH", "PL", "HU", "RO", "BG",
                "HR", "SI", "SK", "EE", "LV", "LT", "LU", "MT", "CY", "IS",
                "GR", "RS", "BA", "ME", "MK", "AL", "XK", "MD", "UA", "BY",
                # North America
                "US", "CA"
            ]
            query_parts.append(f"geolocation in [{','.join(all_countries)}]")
        
        # Add CUDA compatibility, GPU requirements, and datacenter filters
        query_parts.extend([
            "cuda_max_good>=12.8",  # Ensure CUDA 12.8+ compatibility
            "datacenter=true",      # Only datacenter instances
            "rentable=true",
            "num_gpus>=1",
            "num_gpus<=8"           # Allow instances with 1-8 GPUs for big rigs
        ])
        
        # Join query parts with spaces
        query_string = " ".join(query_parts)
        
        try:
            # Build CLI command
            command = ["vastai", "search", "offers", query_string, "--raw"]
            
            # Run the CLI command
            result = await self._run_vastai_command(command)
            
            # Handle different response formats
            if isinstance(result, list):
                offers = result
            elif isinstance(result, dict):
                offers = result.get("offers", [])
            else:
                offers = []
            
            return offers
            
        except Exception as e:
            print(f"Vast.ai CLI error in get_offers: {str(e)}")
            return []
    
    async def create_instance(self, 
                             offer_id: int,
                             image: str = "dizcza/docker-hashcat:cuda",
                             disk: int = 20,
                             label: str = None) -> Dict[str, Any]:
        """Create a new instance using vastai CLI"""
        label = label or f"vpk-job-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Build CLI command
        command = [
            "vastai", "create", "instance", str(offer_id),
            "--image", image,
            "--disk", str(disk),
            "--label", label,
            "--ssh",
            "--direct",
            "--raw"
        ]
        
        result = await self._run_vastai_command(command)
        
        # Handle different response formats
        if isinstance(result, dict):
            if 'new_contract' in result:
                return result
            elif 'raw_output' in result:
                # Try to extract instance ID from raw output
                output = result['raw_output']
                print(f"Raw create instance output: {output}")
                # Look for instance ID patterns in the output
                import re
                match = re.search(r'(\d+)', output)
                if match:
                    return {"new_contract": int(match.group(1))}
                else:
                    return result
            else:
                return result
        return result
    
    async def get_instances(self) -> List[Dict[str, Any]]:
        """Get list of user's instances using vastai CLI"""
        command = ["vastai", "show", "instances", "--raw"]
        result = await self._run_vastai_command(command)
        
        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return result.get("instances", [])
        return []
    
    async def get_instance(self, instance_id: int) -> Dict[str, Any]:
        """Get details of a specific instance"""
        instances = await self.get_instances()
        for instance in instances:
            if instance.get("id") == instance_id:
                return instance
        raise Exception(f"Instance {instance_id} not found")
    
    async def show_instance(self, instance_id: int) -> Optional[Dict[str, Any]]:
        """Get information about a specific instance using vastai show instance command"""
        try:
            command = ["vastai", "show", "instance", str(instance_id), "--raw"]
            result = await self._run_vastai_command(command)
            return result
        except Exception as e:
            # Check if instance not found
            error_msg = str(e).lower()
            if "not found" in error_msg or "404" in error_msg:
                return None
            raise e
    
    async def destroy_instance(self, instance_id: int) -> Dict[str, Any]:
        """Destroy an instance using vastai CLI"""
        command = ["vastai", "destroy", "instance", str(instance_id), "--raw"]
        return await self._run_vastai_command(command)
    
    async def get_ssh_url(self, instance_id: int) -> str:
        """Get SSH connection details for an instance"""
        try:
            cli_command = ["vastai", "ssh-url", str(instance_id), "--api-key", self.api_key]
            result = await self._run_vastai_command(cli_command)
            
            if isinstance(result, dict) and 'raw_output' in result:
                ssh_url = result['raw_output'].strip()
            else:
                ssh_url = str(result).strip()
                
            return ssh_url
        except Exception as e:
            raise Exception(f"Failed to get SSH URL: {str(e)}")
    
    def _filter_ssh_stderr(self, stderr: str) -> str:
        """Filter out common SSH noise from stderr while preserving actual errors"""
        if not stderr:
            return ""
        
        lines = stderr.strip().split('\n')
        filtered_lines = []
        
        for line in lines:
            # Check if line matches any noise pattern
            is_noise = False
            for pattern in self.ssh_noise_patterns:
                if re.search(pattern, line.strip()):
                    is_noise = True
                    break
            
            # Keep the line if it's not noise
            if not is_noise and line.strip():
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)

    async def execute_command(self, 
                             instance_id: int, 
                             command: str,
                             ssh_key_path: str = None) -> Dict[str, Any]:
        """Execute a command on an instance via SSH"""
        try:
            # Get SSH connection details
            ssh_url = await self.get_ssh_url(instance_id)
            
            # Parse SSH URL: ssh://root@host:port
            import re
            match = re.match(r'ssh://([^@]+)@([^:]+):(\d+)', ssh_url)
            if not match:
                raise Exception(f"Invalid SSH URL format: {ssh_url}")
            
            user, host, port = match.groups()
            
            # Build SSH command
            ssh_command = [
                "ssh",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=10",
                "-p", port
            ]
            
            # Add SSH key if provided
            if ssh_key_path and os.path.exists(ssh_key_path):
                ssh_command.extend(["-i", ssh_key_path])
            
            ssh_command.extend([f"{user}@{host}", command])
            
            process = await asyncio.create_subprocess_exec(
                *ssh_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Filter SSH noise from stderr
            filtered_stderr = self._filter_ssh_stderr(stderr.decode() if stderr else "")
            
            return {
                "stdout": stdout.decode() if stdout else "",
                "stderr": filtered_stderr,
                "returncode": process.returncode
            }
            
        except Exception as e:
            return {
                "stdout": "",
                "stderr": str(e),
                "returncode": 1
            }
    
    async def upload_file(self, 
                         instance_id: int,
                         local_path: str,
                         remote_path: str) -> Dict[str, Any]:
        """Upload a file to an instance"""
        # Note: Tried using Vasts own upload functionality but it was a bit shit, so fell back to just using SCP....
        # scp/rsync commands through execute_command
        raise NotImplementedError("File upload via API not yet implemented")
    
    async def download_file(self, 
                           instance_id: int,
                           remote_path: str,
                           local_path: str) -> Dict[str, Any]:
        """Download a file from an instance"""
        # use scp/rsync commands through execute_command
        raise NotImplementedError("File download via API not yet implemented")
    
    async def get_instance_logs(self, instance_id: int) -> str:
        """Get logs from an instance using vastai CLI"""
        command = ["vastai", "logs", str(instance_id), "--raw"]
        try:
            result = await self._run_vastai_command(command)
            if isinstance(result, dict):
                return result.get("logs", "")
            elif isinstance(result, str):
                return result
            return ""
        except Exception as e:
            return f"Error getting logs: {str(e)}"
    
    async def wait_for_instance_ready(self, 
                                     instance_id: int, 
                                     timeout: int = 300) -> bool:
        """Wait for instance to be ready"""
        start_time = datetime.now()
        
        while (datetime.now() - start_time).seconds < timeout:
            try:
                instance = await self.get_instance(instance_id)
                if instance.get("actual_status") == "running":
                    return True
                await asyncio.sleep(10)
            except Exception:
                await asyncio.sleep(10)
        
        return False
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test the CLI connection"""
        try:
            # Try a simple CLI call to test authentication
            instances = await self.get_instances()
            return {
                "status": "success",
                "api_accessible": True,
                "user_instances": len(instances)
            }
        except Exception as e:
            return {
                "status": "error",
                "api_accessible": False,
                "error": str(e)
            }
    
    async def get_machine_benchmarks(self, gpu_name: str) -> Dict[str, Any]:
        """Get benchmark data for a specific GPU type"""
        # This would integrate with hashcat benchmark data
        # For now, return basic structure
        return {
            "gpu_name": gpu_name,
            "hashcat_benchmarks": {
                "md5": 0,
                "sha1": 0,
                "sha256": 0,
                "ntlm": 0
            }
        }