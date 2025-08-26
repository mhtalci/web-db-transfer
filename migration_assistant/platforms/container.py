"""
Container platform adapters for Docker and Kubernetes migrations.
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
import subprocess
import asyncio

from .base import PlatformAdapter, PlatformInfo, DependencyInfo, EnvironmentConfig
from ..models.config import SystemConfig
from ..core.exceptions import PlatformError


class ContainerAdapter(PlatformAdapter):
    """Base adapter for container platforms."""
    
    @property
    def platform_type(self) -> str:
        return "container"
    
    async def get_container_info(self, path: Path) -> Dict[str, Any]:
        """Get information about containers."""
        return {}
    
    async def get_volume_info(self, path: Path) -> Dict[str, Any]:
        """Get information about volumes."""
        return {}
    
    async def get_network_info(self, path: Path) -> Dict[str, Any]:
        """Get information about networks."""
        return {}


class DockerAdapter(ContainerAdapter):
    """Adapter for Docker containers and Docker Compose applications."""
    
    @property
    def platform_type(self) -> str:
        return "docker"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["20.10", "23.0", "24.0", "25.0"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect Docker application."""
        # Check for Dockerfile
        dockerfile = path / "Dockerfile"
        if dockerfile.exists():
            return True
        
        # Check for docker-compose files
        compose_files = [
            "docker-compose.yml",
            "docker-compose.yaml", 
            "compose.yml",
            "compose.yaml"
        ]
        
        for compose_file in compose_files:
            if (path / compose_file).exists():
                return True
        
        return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze Docker application."""
        if not await self.detect_platform(path):
            raise PlatformError(f"Docker not detected at {path}")
        
        docker_info = await self._analyze_docker_config(path)
        compose_info = await self._analyze_compose_config(path)
        
        # Combine information from Dockerfile and docker-compose
        services = compose_info.get("services", {})
        if not services and docker_info:
            services = {"app": docker_info}
        
        dependencies = ["docker"]
        if compose_info:
            dependencies.append("docker-compose")
        
        config_files = []
        if (path / "Dockerfile").exists():
            config_files.append("Dockerfile")
        
        for compose_file in ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]:
            if (path / compose_file).exists():
                config_files.append(compose_file)
                break
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=await self._get_docker_version(),
            framework="docker",
            database_type=self._detect_database_from_services(services),
            dependencies=dependencies,
            config_files=config_files,
            environment_variables=self._extract_env_vars_from_services(services)
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get Docker dependencies."""
        return [
            DependencyInfo(
                name="docker",
                version=">=20.10",
                required=True,
                install_command="curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh"
            ),
            DependencyInfo(
                name="docker-compose",
                version=">=2.0",
                required=False,
                install_command="pip install docker-compose"
            )
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract Docker environment configuration."""
        env_vars = {}
        env_files = []
        
        # Check for .env files
        for env_file in [".env", ".env.local", ".env.production"]:
            env_path = path / env_file
            if env_path.exists():
                env_files.append(env_file)
                env_vars.update(self._extract_environment_variables(env_path.read_text()))
        
        # Extract from docker-compose files
        compose_info = await self._analyze_compose_config(path)
        if compose_info:
            for service_name, service_config in compose_info.get("services", {}).items():
                service_env = service_config.get("environment", {})
                if isinstance(service_env, list):
                    for env_var in service_env:
                        if "=" in env_var:
                            key, value = env_var.split("=", 1)
                            env_vars[f"{service_name}_{key}"] = value
                elif isinstance(service_env, dict):
                    for key, value in service_env.items():
                        env_vars[f"{service_name}_{key}"] = str(value)
        
        secrets = ["DATABASE_PASSWORD", "API_KEY", "SECRET_KEY", "JWT_SECRET"]
        
        return EnvironmentConfig(
            variables=env_vars,
            files=env_files,
            secrets=secrets
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare Docker migration."""
        platform_info = await self.analyze_platform(source_path)
        docker_info = await self._analyze_docker_config(source_path)
        compose_info = await self._analyze_compose_config(source_path)
        
        migration_steps = [
            "export_images",
            "backup_volumes",
            "copy_configuration",
            "import_images",
            "restore_volumes",
            "start_containers"
        ]
        
        return {
            "platform_info": platform_info.dict(),
            "docker_info": docker_info,
            "compose_info": compose_info,
            "migration_steps": migration_steps,
            "files_to_copy": [
                "Dockerfile",
                "docker-compose.yml",
                "docker-compose.yaml",
                ".env",
                ".dockerignore"
            ]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform Docker post-migration setup."""
        try:
            # Build images if Dockerfile exists
            if (destination_path / "Dockerfile").exists():
                await self._build_docker_image(destination_path)
            
            # Start services if docker-compose exists
            compose_files = ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]
            for compose_file in compose_files:
                if (destination_path / compose_file).exists():
                    await self._start_compose_services(destination_path, compose_file)
                    break
            
            return True
        except Exception as e:
            self.logger.error(f"Docker post-migration setup failed: {e}")
            return False
    
    async def get_container_info(self, path: Path) -> Dict[str, Any]:
        """Get Docker container information."""
        try:
            # Get running containers
            result = await asyncio.create_subprocess_exec(
                "docker", "ps", "--format", "json",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                containers = []
                for line in stdout.decode().strip().split('\n'):
                    if line:
                        containers.append(json.loads(line))
                return {"containers": containers}
            else:
                self.logger.warning(f"Failed to get container info: {stderr.decode()}")
                return {}
        except Exception as e:
            self.logger.error(f"Error getting container info: {e}")
            return {}
    
    async def get_volume_info(self, path: Path) -> Dict[str, Any]:
        """Get Docker volume information."""
        try:
            result = await asyncio.create_subprocess_exec(
                "docker", "volume", "ls", "--format", "json",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                volumes = []
                for line in stdout.decode().strip().split('\n'):
                    if line:
                        volumes.append(json.loads(line))
                return {"volumes": volumes}
            else:
                self.logger.warning(f"Failed to get volume info: {stderr.decode()}")
                return {}
        except Exception as e:
            self.logger.error(f"Error getting volume info: {e}")
            return {}
    
    async def _analyze_docker_config(self, path: Path) -> Dict[str, Any]:
        """Analyze Dockerfile configuration."""
        dockerfile = path / "Dockerfile"
        if not dockerfile.exists():
            return {}
        
        try:
            content = dockerfile.read_text()
            config = {
                "base_image": None,
                "exposed_ports": [],
                "volumes": [],
                "environment": {},
                "commands": []
            }
            
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("FROM "):
                    config["base_image"] = line.split()[1]
                elif line.startswith("EXPOSE "):
                    ports = line.split()[1:]
                    config["exposed_ports"].extend(ports)
                elif line.startswith("VOLUME "):
                    volumes = line.split()[1:]
                    config["volumes"].extend(volumes)
                elif line.startswith("ENV "):
                    env_parts = line.split()[1:]
                    for env_part in env_parts:
                        if "=" in env_part:
                            key, value = env_part.split("=", 1)
                            config["environment"][key] = value
                elif line.startswith(("RUN ", "CMD ", "ENTRYPOINT ")):
                    config["commands"].append(line)
            
            return config
        except Exception as e:
            self.logger.error(f"Failed to analyze Dockerfile: {e}")
            return {}
    
    async def _analyze_compose_config(self, path: Path) -> Dict[str, Any]:
        """Analyze docker-compose configuration."""
        compose_files = ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]
        
        for compose_file in compose_files:
            compose_path = path / compose_file
            if compose_path.exists():
                try:
                    content = yaml.safe_load(compose_path.read_text())
                    return content
                except Exception as e:
                    self.logger.error(f"Failed to parse {compose_file}: {e}")
                    continue
        
        return {}
    
    async def _get_docker_version(self) -> Optional[str]:
        """Get Docker version."""
        try:
            result = await asyncio.create_subprocess_exec(
                "docker", "--version",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                version_line = stdout.decode().strip()
                # Extract version from "Docker version 24.0.6, build ed223bc"
                if "version" in version_line:
                    parts = version_line.split()
                    for i, part in enumerate(parts):
                        if part == "version" and i + 1 < len(parts):
                            version = parts[i + 1].rstrip(",")
                            return version
            return None
        except Exception:
            return None
    
    def _detect_database_from_services(self, services: Dict[str, Any]) -> Optional[str]:
        """Detect database type from services."""
        for service_name, service_config in services.items():
            image = service_config.get("image", "")
            if "mysql" in image.lower():
                return "mysql"
            elif "postgres" in image.lower():
                return "postgresql"
            elif "mongo" in image.lower():
                return "mongodb"
            elif "redis" in image.lower():
                return "redis"
        return None
    
    def _extract_env_vars_from_services(self, services: Dict[str, Any]) -> Dict[str, str]:
        """Extract environment variables from services."""
        env_vars = {}
        
        for service_name, service_config in services.items():
            service_env = service_config.get("environment", {})
            if isinstance(service_env, list):
                for env_var in service_env:
                    if "=" in env_var:
                        key, value = env_var.split("=", 1)
                        env_vars[key] = value
            elif isinstance(service_env, dict):
                env_vars.update({k: str(v) for k, v in service_env.items()})
        
        return env_vars
    
    async def _build_docker_image(self, path: Path) -> None:
        """Build Docker image."""
        try:
            result = await asyncio.create_subprocess_exec(
                "docker", "build", "-t", f"migrated-app", ".",
                cwd=path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                raise Exception(f"Docker build failed: {stderr.decode()}")
        except Exception as e:
            self.logger.error(f"Failed to build Docker image: {e}")
            raise
    
    async def _start_compose_services(self, path: Path, compose_file: str) -> None:
        """Start docker-compose services."""
        try:
            result = await asyncio.create_subprocess_exec(
                "docker-compose", "-f", compose_file, "up", "-d",
                cwd=path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                raise Exception(f"Docker compose up failed: {stderr.decode()}")
        except Exception as e:
            self.logger.error(f"Failed to start compose services: {e}")
            raise


class KubernetesAdapter(ContainerAdapter):
    """Adapter for Kubernetes applications."""
    
    @property
    def platform_type(self) -> str:
        return "kubernetes"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["1.24", "1.25", "1.26", "1.27", "1.28", "1.29"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect Kubernetes application."""
        # Check for Kubernetes manifest files
        k8s_files = list(path.glob("*.yaml")) + list(path.glob("*.yml"))
        
        for k8s_file in k8s_files:
            try:
                content = yaml.safe_load(k8s_file.read_text())
                if isinstance(content, dict) and "apiVersion" in content and "kind" in content:
                    return True
            except Exception:
                continue
        
        # Check for kustomization files
        kustomization_files = ["kustomization.yaml", "kustomization.yml", "Kustomization"]
        for kustomization_file in kustomization_files:
            if (path / kustomization_file).exists():
                return True
        
        # Check for Helm charts
        if (path / "Chart.yaml").exists():
            return True
        
        return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze Kubernetes application."""
        if not await self.detect_platform(path):
            raise PlatformError(f"Kubernetes not detected at {path}")
        
        k8s_resources = await self._analyze_k8s_resources(path)
        helm_info = await self._analyze_helm_chart(path)
        
        dependencies = ["kubectl"]
        if helm_info:
            dependencies.append("helm")
        
        config_files = []
        for yaml_file in path.glob("*.yaml"):
            config_files.append(yaml_file.name)
        for yml_file in path.glob("*.yml"):
            config_files.append(yml_file.name)
        
        if helm_info:
            config_files.append("Chart.yaml")
            config_files.append("values.yaml")
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=await self._get_kubernetes_version(),
            framework="kubernetes",
            database_type=self._detect_database_from_resources(k8s_resources),
            dependencies=dependencies,
            config_files=config_files,
            environment_variables=self._extract_env_vars_from_resources(k8s_resources)
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get Kubernetes dependencies."""
        return [
            DependencyInfo(
                name="kubectl",
                required=True,
                install_command="curl -LO https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
            ),
            DependencyInfo(
                name="helm",
                required=False,
                install_command="curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"
            ),
            DependencyInfo(
                name="kustomize",
                required=False,
                install_command="curl -s https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh | bash"
            )
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract Kubernetes environment configuration."""
        env_vars = {}
        k8s_resources = await self._analyze_k8s_resources(path)
        
        # Extract environment variables from ConfigMaps and Secrets
        for resource in k8s_resources:
            if resource.get("kind") == "ConfigMap":
                data = resource.get("data", {})
                env_vars.update(data)
            elif resource.get("kind") == "Secret":
                # Note: Secret data is base64 encoded
                data = resource.get("data", {})
                for key in data.keys():
                    env_vars[key] = "[SECRET]"
        
        config_files = [f.name for f in path.glob("*.yaml")] + [f.name for f in path.glob("*.yml")]
        secrets = ["database-secret", "api-secret", "tls-secret"]
        
        return EnvironmentConfig(
            variables=env_vars,
            files=config_files,
            secrets=secrets
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare Kubernetes migration."""
        platform_info = await self.analyze_platform(source_path)
        k8s_resources = await self._analyze_k8s_resources(source_path)
        helm_info = await self._analyze_helm_chart(source_path)
        
        migration_steps = [
            "backup_resources",
            "export_persistent_volumes",
            "copy_manifests",
            "apply_manifests",
            "restore_persistent_volumes",
            "verify_deployment"
        ]
        
        return {
            "platform_info": platform_info.dict(),
            "k8s_resources": k8s_resources,
            "helm_info": helm_info,
            "migration_steps": migration_steps,
            "files_to_copy": ["*.yaml", "*.yml", "Chart.yaml", "values.yaml"]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform Kubernetes post-migration setup."""
        try:
            # Apply Kubernetes manifests
            await self._apply_k8s_manifests(destination_path)
            
            # Install Helm chart if present
            helm_info = migration_info.get("helm_info")
            if helm_info:
                await self._install_helm_chart(destination_path)
            
            return True
        except Exception as e:
            self.logger.error(f"Kubernetes post-migration setup failed: {e}")
            return False
    
    async def _analyze_k8s_resources(self, path: Path) -> List[Dict[str, Any]]:
        """Analyze Kubernetes resource files."""
        resources = []
        
        yaml_files = list(path.glob("*.yaml")) + list(path.glob("*.yml"))
        
        for yaml_file in yaml_files:
            try:
                content = yaml_file.read_text()
                # Handle multiple documents in one file
                for doc in yaml.safe_load_all(content):
                    if doc and isinstance(doc, dict) and "apiVersion" in doc and "kind" in doc:
                        resources.append(doc)
            except Exception as e:
                self.logger.warning(f"Failed to parse {yaml_file}: {e}")
                continue
        
        return resources
    
    async def _analyze_helm_chart(self, path: Path) -> Optional[Dict[str, Any]]:
        """Analyze Helm chart if present."""
        chart_yaml = path / "Chart.yaml"
        if not chart_yaml.exists():
            return None
        
        try:
            chart_info = yaml.safe_load(chart_yaml.read_text())
            
            # Also read values.yaml if present
            values_yaml = path / "values.yaml"
            if values_yaml.exists():
                values = yaml.safe_load(values_yaml.read_text())
                chart_info["values"] = values
            
            return chart_info
        except Exception as e:
            self.logger.error(f"Failed to analyze Helm chart: {e}")
            return None
    
    async def _get_kubernetes_version(self) -> Optional[str]:
        """Get Kubernetes cluster version."""
        try:
            result = await asyncio.create_subprocess_exec(
                "kubectl", "version", "--client", "--output=json",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                version_info = json.loads(stdout.decode())
                client_version = version_info.get("clientVersion", {})
                return client_version.get("gitVersion", "").lstrip("v")
            return None
        except Exception:
            return None
    
    def _detect_database_from_resources(self, resources: List[Dict[str, Any]]) -> Optional[str]:
        """Detect database type from Kubernetes resources."""
        for resource in resources:
            if resource.get("kind") == "Deployment":
                containers = resource.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
                for container in containers:
                    image = container.get("image", "")
                    if "mysql" in image.lower():
                        return "mysql"
                    elif "postgres" in image.lower():
                        return "postgresql"
                    elif "mongo" in image.lower():
                        return "mongodb"
                    elif "redis" in image.lower():
                        return "redis"
        return None
    
    def _extract_env_vars_from_resources(self, resources: List[Dict[str, Any]]) -> Dict[str, str]:
        """Extract environment variables from Kubernetes resources."""
        env_vars = {}
        
        for resource in resources:
            if resource.get("kind") == "ConfigMap":
                data = resource.get("data", {})
                env_vars.update(data)
            elif resource.get("kind") == "Deployment":
                containers = resource.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
                for container in containers:
                    env = container.get("env", [])
                    for env_var in env:
                        name = env_var.get("name")
                        value = env_var.get("value")
                        if name and value:
                            env_vars[name] = value
        
        return env_vars
    
    async def _apply_k8s_manifests(self, path: Path) -> None:
        """Apply Kubernetes manifests."""
        try:
            result = await asyncio.create_subprocess_exec(
                "kubectl", "apply", "-f", ".",
                cwd=path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                raise Exception(f"kubectl apply failed: {stderr.decode()}")
        except Exception as e:
            self.logger.error(f"Failed to apply Kubernetes manifests: {e}")
            raise
    
    async def _install_helm_chart(self, path: Path) -> None:
        """Install Helm chart."""
        try:
            chart_yaml = path / "Chart.yaml"
            if chart_yaml.exists():
                chart_info = yaml.safe_load(chart_yaml.read_text())
                chart_name = chart_info.get("name", "migrated-chart")
                
                result = await asyncio.create_subprocess_exec(
                    "helm", "install", chart_name, ".",
                    cwd=path,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                
                if result.returncode != 0:
                    raise Exception(f"helm install failed: {stderr.decode()}")
        except Exception as e:
            self.logger.error(f"Failed to install Helm chart: {e}")
            raise