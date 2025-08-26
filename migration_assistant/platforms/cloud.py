"""
Cloud platform adapters for AWS, Azure, GCP, Netlify, Vercel, and other cloud services.
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
import asyncio
import subprocess

from .base import PlatformAdapter, PlatformInfo, DependencyInfo, EnvironmentConfig
from ..models.config import SystemConfig
from ..core.exceptions import PlatformError


class CloudAdapter(PlatformAdapter):
    """Base adapter for cloud platforms."""
    
    @property
    def platform_type(self) -> str:
        return "cloud"
    
    async def get_cloud_resources(self, path: Path) -> Dict[str, Any]:
        """Get information about cloud resources."""
        return {}
    
    async def get_deployment_config(self, path: Path) -> Dict[str, Any]:
        """Get deployment configuration."""
        return {}


class AWSAdapter(CloudAdapter):
    """Adapter for AWS (Amazon Web Services) deployments."""
    
    @property
    def platform_type(self) -> str:
        return "aws"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["v1", "v2"]  # AWS CLI versions
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect AWS deployment configuration."""
        # Check for AWS-specific files
        aws_files = [
            "template.yaml",  # SAM template
            "template.yml",
            "serverless.yml",  # Serverless framework
            "serverless.yaml",
            "cloudformation.yaml",  # CloudFormation
            "cloudformation.yml",
            "cdk.json",  # AWS CDK
            ".aws-sam",  # SAM build directory
            "samconfig.toml"  # SAM configuration
        ]
        
        for aws_file in aws_files:
            if (path / aws_file).exists():
                return True
        
        # Check for AWS configuration in package.json (for Node.js projects)
        package_json = path / "package.json"
        if package_json.exists():
            try:
                content = json.loads(package_json.read_text())
                scripts = content.get("scripts", {})
                if any("aws" in script for script in scripts.values()):
                    return True
            except Exception:
                pass
        
        return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze AWS deployment."""
        if not await self.detect_platform(path):
            raise PlatformError(f"AWS not detected at {path}")
        
        aws_config = await self._analyze_aws_config(path)
        sam_config = await self._analyze_sam_config(path)
        serverless_config = await self._analyze_serverless_config(path)
        
        # Determine the primary AWS service
        services = []
        if sam_config:
            services.extend(sam_config.get("services", []))
        if serverless_config:
            services.extend(serverless_config.get("services", []))
        if aws_config:
            services.extend(aws_config.get("services", []))
        
        config_files = []
        for config_file in ["template.yaml", "template.yml", "serverless.yml", "cdk.json", "samconfig.toml"]:
            if (path / config_file).exists():
                config_files.append(config_file)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=await self._get_aws_cli_version(),
            framework="aws",
            database_type=self._detect_database_from_services(services),
            dependencies=["aws-cli", "sam-cli"],
            config_files=config_files,
            environment_variables=self._extract_env_vars_from_configs(aws_config, sam_config, serverless_config)
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get AWS dependencies."""
        return [
            DependencyInfo(
                name="aws-cli",
                version=">=2.0",
                required=True,
                install_command="curl 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o 'awscliv2.zip' && unzip awscliv2.zip && sudo ./aws/install"
            ),
            DependencyInfo(
                name="sam-cli",
                required=False,
                install_command="pip install aws-sam-cli"
            ),
            DependencyInfo(
                name="serverless",
                required=False,
                install_command="npm install -g serverless"
            ),
            DependencyInfo(
                name="aws-cdk",
                required=False,
                install_command="npm install -g aws-cdk"
            )
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract AWS environment configuration."""
        env_vars = {}
        
        # Check for AWS credentials and config
        aws_credentials = [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "AWS_REGION",
            "AWS_PROFILE"
        ]
        
        # Extract from various config files
        configs = [
            await self._analyze_aws_config(path),
            await self._analyze_sam_config(path),
            await self._analyze_serverless_config(path)
        ]
        
        for config in configs:
            if config and "environment" in config:
                env_vars.update(config["environment"])
        
        config_files = []
        for config_file in ["template.yaml", "serverless.yml", "samconfig.toml", ".env"]:
            if (path / config_file).exists():
                config_files.append(config_file)
        
        return EnvironmentConfig(
            variables=env_vars,
            files=config_files,
            secrets=aws_credentials + ["DATABASE_PASSWORD", "API_KEY"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare AWS migration."""
        platform_info = await self.analyze_platform(source_path)
        aws_config = await self._analyze_aws_config(source_path)
        
        migration_steps = [
            "backup_resources",
            "export_configuration",
            "copy_code",
            "deploy_infrastructure",
            "deploy_application",
            "verify_deployment"
        ]
        
        return {
            "platform_info": platform_info.dict(),
            "aws_config": aws_config,
            "migration_steps": migration_steps,
            "files_to_copy": [
                "template.yaml",
                "serverless.yml",
                "cdk.json",
                "samconfig.toml",
                "src/",
                "lambda/",
                ".env"
            ]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform AWS post-migration setup."""
        try:
            # Deploy SAM application if template exists
            if (destination_path / "template.yaml").exists() or (destination_path / "template.yml").exists():
                await self._deploy_sam_application(destination_path)
            
            # Deploy Serverless application if config exists
            elif (destination_path / "serverless.yml").exists():
                await self._deploy_serverless_application(destination_path)
            
            # Deploy CDK application if config exists
            elif (destination_path / "cdk.json").exists():
                await self._deploy_cdk_application(destination_path)
            
            return True
        except Exception as e:
            self.logger.error(f"AWS post-migration setup failed: {e}")
            return False
    
    async def _analyze_aws_config(self, path: Path) -> Dict[str, Any]:
        """Analyze general AWS configuration."""
        config = {"services": [], "environment": {}}
        
        # Check CloudFormation templates
        cf_files = ["cloudformation.yaml", "cloudformation.yml"]
        for cf_file in cf_files:
            cf_path = path / cf_file
            if cf_path.exists():
                try:
                    cf_content = yaml.safe_load(cf_path.read_text())
                    resources = cf_content.get("Resources", {})
                    for resource_name, resource_config in resources.items():
                        resource_type = resource_config.get("Type", "")
                        config["services"].append({
                            "name": resource_name,
                            "type": resource_type,
                            "service": self._aws_resource_to_service(resource_type)
                        })
                except Exception as e:
                    self.logger.warning(f"Failed to parse {cf_file}: {e}")
        
        return config
    
    async def _analyze_sam_config(self, path: Path) -> Dict[str, Any]:
        """Analyze SAM (Serverless Application Model) configuration."""
        template_files = ["template.yaml", "template.yml"]
        
        for template_file in template_files:
            template_path = path / template_file
            if template_path.exists():
                try:
                    template_content = yaml.safe_load(template_path.read_text())
                    
                    config = {
                        "services": [],
                        "environment": {},
                        "globals": template_content.get("Globals", {})
                    }
                    
                    resources = template_content.get("Resources", {})
                    for resource_name, resource_config in resources.items():
                        resource_type = resource_config.get("Type", "")
                        if resource_type.startswith("AWS::Serverless::"):
                            config["services"].append({
                                "name": resource_name,
                                "type": resource_type,
                                "properties": resource_config.get("Properties", {})
                            })
                    
                    # Extract environment variables from globals
                    function_globals = config["globals"].get("Function", {})
                    if "Environment" in function_globals:
                        env_vars = function_globals["Environment"].get("Variables", {})
                        config["environment"].update(env_vars)
                    
                    return config
                except Exception as e:
                    self.logger.warning(f"Failed to parse {template_file}: {e}")
        
        return {}
    
    async def _analyze_serverless_config(self, path: Path) -> Dict[str, Any]:
        """Analyze Serverless Framework configuration."""
        serverless_files = ["serverless.yml", "serverless.yaml"]
        
        for serverless_file in serverless_files:
            serverless_path = path / serverless_file
            if serverless_path.exists():
                try:
                    serverless_content = yaml.safe_load(serverless_path.read_text())
                    
                    config = {
                        "services": [],
                        "environment": {},
                        "provider": serverless_content.get("provider", {}),
                        "functions": serverless_content.get("functions", {})
                    }
                    
                    # Extract functions as services
                    for function_name, function_config in config["functions"].items():
                        config["services"].append({
                            "name": function_name,
                            "type": "AWS::Lambda::Function",
                            "handler": function_config.get("handler"),
                            "runtime": function_config.get("runtime")
                        })
                    
                    # Extract environment variables
                    provider_env = config["provider"].get("environment", {})
                    config["environment"].update(provider_env)
                    
                    return config
                except Exception as e:
                    self.logger.warning(f"Failed to parse {serverless_file}: {e}")
        
        return {}
    
    async def _get_aws_cli_version(self) -> Optional[str]:
        """Get AWS CLI version."""
        try:
            result = await asyncio.create_subprocess_exec(
                "aws", "--version",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                version_line = stdout.decode().strip()
                # Extract version from "aws-cli/2.13.25 Python/3.11.5 ..."
                if "aws-cli/" in version_line:
                    version = version_line.split("aws-cli/")[1].split()[0]
                    return version
            return None
        except Exception:
            return None
    
    def _aws_resource_to_service(self, resource_type: str) -> str:
        """Map AWS resource type to service name."""
        service_mapping = {
            "AWS::Lambda::Function": "lambda",
            "AWS::S3::Bucket": "s3",
            "AWS::RDS::DBInstance": "rds",
            "AWS::DynamoDB::Table": "dynamodb",
            "AWS::ApiGateway::RestApi": "apigateway",
            "AWS::CloudFormation::Stack": "cloudformation",
            "AWS::EC2::Instance": "ec2",
            "AWS::ECS::Service": "ecs",
            "AWS::EKS::Cluster": "eks"
        }
        return service_mapping.get(resource_type, "unknown")
    
    def _detect_database_from_services(self, services: List[Dict[str, Any]]) -> Optional[str]:
        """Detect database type from AWS services."""
        for service in services:
            service_type = service.get("service", "")
            if service_type == "rds":
                return "mysql"  # Default, could be PostgreSQL
            elif service_type == "dynamodb":
                return "dynamodb"
        return None
    
    def _extract_env_vars_from_configs(self, *configs) -> Dict[str, str]:
        """Extract environment variables from multiple configs."""
        env_vars = {}
        for config in configs:
            if config and "environment" in config:
                env_vars.update(config["environment"])
        return env_vars
    
    async def _deploy_sam_application(self, path: Path) -> None:
        """Deploy SAM application."""
        try:
            # Build the application
            result = await asyncio.create_subprocess_exec(
                "sam", "build",
                cwd=path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                raise Exception(f"SAM build failed: {stderr.decode()}")
            
            # Deploy the application
            result = await asyncio.create_subprocess_exec(
                "sam", "deploy", "--guided",
                cwd=path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                raise Exception(f"SAM deploy failed: {stderr.decode()}")
                
        except Exception as e:
            self.logger.error(f"Failed to deploy SAM application: {e}")
            raise
    
    async def _deploy_serverless_application(self, path: Path) -> None:
        """Deploy Serverless Framework application."""
        try:
            result = await asyncio.create_subprocess_exec(
                "serverless", "deploy",
                cwd=path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                raise Exception(f"Serverless deploy failed: {stderr.decode()}")
                
        except Exception as e:
            self.logger.error(f"Failed to deploy Serverless application: {e}")
            raise
    
    async def _deploy_cdk_application(self, path: Path) -> None:
        """Deploy AWS CDK application."""
        try:
            # Install dependencies
            result = await asyncio.create_subprocess_exec(
                "npm", "install",
                cwd=path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                raise Exception(f"CDK npm install failed: {stderr.decode()}")
            
            # Deploy the stack
            result = await asyncio.create_subprocess_exec(
                "cdk", "deploy", "--require-approval", "never",
                cwd=path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                raise Exception(f"CDK deploy failed: {stderr.decode()}")
                
        except Exception as e:
            self.logger.error(f"Failed to deploy CDK application: {e}")
            raise


class AzureAdapter(CloudAdapter):
    """Adapter for Microsoft Azure deployments."""
    
    @property
    def platform_type(self) -> str:
        return "azure"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["2.0"]  # Azure CLI version
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect Azure deployment configuration."""
        azure_files = [
            "azure-pipelines.yml",
            "azuredeploy.json",
            "azuredeploy.parameters.json",
            "bicep.json",
            "main.bicep",
            "host.json",  # Azure Functions
            "function.json"
        ]
        
        for azure_file in azure_files:
            if (path / azure_file).exists():
                return True
        
        return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze Azure deployment."""
        if not await self.detect_platform(path):
            raise PlatformError(f"Azure not detected at {path}")
        
        azure_config = await self._analyze_azure_config(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=await self._get_azure_cli_version(),
            framework="azure",
            database_type=self._detect_database_from_config(azure_config),
            dependencies=["azure-cli"],
            config_files=azure_config.get("config_files", []),
            environment_variables=azure_config.get("environment", {})
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get Azure dependencies."""
        return [
            DependencyInfo(
                name="azure-cli",
                version=">=2.0",
                required=True,
                install_command="curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash"
            ),
            DependencyInfo(
                name="azure-functions-core-tools",
                required=False,
                install_command="npm install -g azure-functions-core-tools@4 --unsafe-perm true"
            )
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract Azure environment configuration."""
        return EnvironmentConfig(
            variables={},
            files=["local.settings.json", ".env"],
            secrets=["AZURE_CLIENT_SECRET", "AZURE_TENANT_ID", "CONNECTION_STRING"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare Azure migration."""
        platform_info = await self.analyze_platform(source_path)
        
        return {
            "platform_info": platform_info.dict(),
            "migration_steps": ["backup_resources", "deploy_infrastructure", "deploy_application"],
            "files_to_copy": ["*.json", "*.bicep", "*.yml"]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform Azure post-migration setup."""
        return True
    
    async def _analyze_azure_config(self, path: Path) -> Dict[str, Any]:
        """Analyze Azure configuration files."""
        return {"config_files": [], "environment": {}}
    
    async def _get_azure_cli_version(self) -> Optional[str]:
        """Get Azure CLI version."""
        try:
            result = await asyncio.create_subprocess_exec(
                "az", "--version",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                version_line = stdout.decode().strip()
                if "azure-cli" in version_line:
                    # Extract version from output
                    for line in version_line.split('\n'):
                        if "azure-cli" in line:
                            version = line.split()[1]
                            return version
            return None
        except Exception:
            return None
    
    def _detect_database_from_config(self, config: Dict[str, Any]) -> Optional[str]:
        """Detect database type from Azure configuration."""
        return None


class GCPAdapter(CloudAdapter):
    """Adapter for Google Cloud Platform deployments."""
    
    @property
    def platform_type(self) -> str:
        return "gcp"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["400.0", "450.0"]  # gcloud CLI versions
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect GCP deployment configuration."""
        gcp_files = [
            "app.yaml",  # App Engine
            "cloudbuild.yaml",  # Cloud Build
            "deployment.yaml",  # Kubernetes on GKE
            "function.yaml",  # Cloud Functions
            "main.py",  # Cloud Functions (Python)
            "requirements.txt"  # Often used with GCP Python apps
        ]
        
        # Check for app.yaml (App Engine)
        if (path / "app.yaml").exists():
            return True
        
        # Check for Cloud Build
        if (path / "cloudbuild.yaml").exists():
            return True
        
        return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze GCP deployment."""
        if not await self.detect_platform(path):
            raise PlatformError(f"GCP not detected at {path}")
        
        gcp_config = await self._analyze_gcp_config(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=await self._get_gcloud_version(),
            framework="gcp",
            database_type=None,
            dependencies=["gcloud"],
            config_files=gcp_config.get("config_files", []),
            environment_variables=gcp_config.get("environment", {})
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get GCP dependencies."""
        return [
            DependencyInfo(
                name="gcloud",
                required=True,
                install_command="curl https://sdk.cloud.google.com | bash"
            )
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract GCP environment configuration."""
        return EnvironmentConfig(
            variables={},
            files=["app.yaml", ".env"],
            secrets=["GOOGLE_APPLICATION_CREDENTIALS", "DATABASE_URL"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare GCP migration."""
        platform_info = await self.analyze_platform(source_path)
        
        return {
            "platform_info": platform_info.dict(),
            "migration_steps": ["backup_resources", "deploy_application"],
            "files_to_copy": ["app.yaml", "cloudbuild.yaml", "*.py", "requirements.txt"]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform GCP post-migration setup."""
        return True
    
    async def _analyze_gcp_config(self, path: Path) -> Dict[str, Any]:
        """Analyze GCP configuration files."""
        return {"config_files": [], "environment": {}}
    
    async def _get_gcloud_version(self) -> Optional[str]:
        """Get gcloud CLI version."""
        try:
            result = await asyncio.create_subprocess_exec(
                "gcloud", "version",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                version_line = stdout.decode().strip()
                if "Google Cloud SDK" in version_line:
                    for line in version_line.split('\n'):
                        if "Google Cloud SDK" in line:
                            version = line.split()[3]
                            return version
            return None
        except Exception:
            return None


class NetlifyAdapter(CloudAdapter):
    """Adapter for Netlify deployments."""
    
    @property
    def platform_type(self) -> str:
        return "netlify"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["15.0", "16.0", "17.0"]  # Netlify CLI versions
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect Netlify deployment configuration."""
        netlify_files = [
            "netlify.toml",
            "_redirects",
            "_headers",
            "netlify"
        ]
        
        for netlify_file in netlify_files:
            if (path / netlify_file).exists():
                return True
        
        # Check package.json for Netlify scripts
        package_json = path / "package.json"
        if package_json.exists():
            try:
                content = json.loads(package_json.read_text())
                scripts = content.get("scripts", {})
                if any("netlify" in script for script in scripts.values()):
                    return True
            except Exception:
                pass
        
        return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze Netlify deployment."""
        if not await self.detect_platform(path):
            raise PlatformError(f"Netlify not detected at {path}")
        
        netlify_config = await self._analyze_netlify_config(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=await self._get_netlify_cli_version(),
            framework="netlify",
            database_type=None,
            dependencies=["netlify-cli"],
            config_files=netlify_config.get("config_files", []),
            environment_variables=netlify_config.get("environment", {})
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get Netlify dependencies."""
        return [
            DependencyInfo(
                name="netlify-cli",
                required=True,
                install_command="npm install -g netlify-cli"
            )
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract Netlify environment configuration."""
        return EnvironmentConfig(
            variables={},
            files=["netlify.toml", ".env"],
            secrets=["NETLIFY_AUTH_TOKEN", "API_KEY"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare Netlify migration."""
        platform_info = await self.analyze_platform(source_path)
        
        return {
            "platform_info": platform_info.dict(),
            "migration_steps": ["build_site", "deploy_site"],
            "files_to_copy": ["netlify.toml", "_redirects", "_headers", "public/", "dist/"]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform Netlify post-migration setup."""
        return True
    
    async def _analyze_netlify_config(self, path: Path) -> Dict[str, Any]:
        """Analyze Netlify configuration."""
        return {"config_files": [], "environment": {}}
    
    async def _get_netlify_cli_version(self) -> Optional[str]:
        """Get Netlify CLI version."""
        try:
            result = await asyncio.create_subprocess_exec(
                "netlify", "--version",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                version_line = stdout.decode().strip()
                if "netlify-cli/" in version_line:
                    version = version_line.split("netlify-cli/")[1].split()[0]
                    return version
            return None
        except Exception:
            return None


class VercelAdapter(CloudAdapter):
    """Adapter for Vercel deployments."""
    
    @property
    def platform_type(self) -> str:
        return "vercel"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["32.0", "33.0", "34.0"]  # Vercel CLI versions
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect Vercel deployment configuration."""
        vercel_files = [
            "vercel.json",
            ".vercel",
            "now.json"  # Legacy Vercel (Zeit Now)
        ]
        
        for vercel_file in vercel_files:
            if (path / vercel_file).exists():
                return True
        
        return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze Vercel deployment."""
        if not await self.detect_platform(path):
            raise PlatformError(f"Vercel not detected at {path}")
        
        vercel_config = await self._analyze_vercel_config(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=await self._get_vercel_cli_version(),
            framework="vercel",
            database_type=None,
            dependencies=["vercel"],
            config_files=vercel_config.get("config_files", []),
            environment_variables=vercel_config.get("environment", {})
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get Vercel dependencies."""
        return [
            DependencyInfo(
                name="vercel",
                required=True,
                install_command="npm install -g vercel"
            )
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract Vercel environment configuration."""
        return EnvironmentConfig(
            variables={},
            files=["vercel.json", ".env.local"],
            secrets=["VERCEL_TOKEN", "DATABASE_URL"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare Vercel migration."""
        platform_info = await self.analyze_platform(source_path)
        
        return {
            "platform_info": platform_info.dict(),
            "migration_steps": ["build_application", "deploy_application"],
            "files_to_copy": ["vercel.json", "package.json", "src/", "public/"]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform Vercel post-migration setup."""
        return True
    
    async def _analyze_vercel_config(self, path: Path) -> Dict[str, Any]:
        """Analyze Vercel configuration."""
        return {"config_files": [], "environment": {}}
    
    async def _get_vercel_cli_version(self) -> Optional[str]:
        """Get Vercel CLI version."""
        try:
            result = await asyncio.create_subprocess_exec(
                "vercel", "--version",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                version_line = stdout.decode().strip()
                return version_line
            return None
        except Exception:
            return None