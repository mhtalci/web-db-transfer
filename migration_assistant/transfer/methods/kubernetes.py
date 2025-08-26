"""
Kubernetes transfer implementation using kubernetes client.

This module provides Kubernetes pod and volume transfer capabilities
with support for copying files to/from pods and persistent volumes.
"""

import asyncio
import base64
import tempfile
from pathlib import Path
from typing import Dict, Any, Union, Optional, List
import logging

try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException
    from kubernetes.stream import stream
    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False

from ..base import TransferMethod, TransferResult, TransferStatus
from ..factory import register_transfer_method

logger = logging.getLogger(__name__)


@register_transfer_method('kubernetes')
class KubernetesTransfer(TransferMethod):
    """
    Kubernetes transfer implementation using kubernetes client.
    
    Supports copying files to/from Kubernetes pods and persistent volumes
    with various authentication and connection options.
    """
    
    SUPPORTED_SCHEMES = ['k8s://', 'kubernetes://']
    REQUIRED_CONFIG = ['pod_name']
    OPTIONAL_CONFIG = [
        'namespace', 'container_name', 'kubeconfig_path', 'context',
        'pod_path', 'create_pod', 'image', 'command', 'service_account',
        'node_selector', 'tolerations', 'resources'
    ]
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Kubernetes transfer method.
        
        Args:
            config: Configuration dictionary with Kubernetes parameters
        """
        if not KUBERNETES_AVAILABLE:
            raise ImportError(
                "kubernetes is required for Kubernetes transfers. "
                "Install with: pip install kubernetes"
            )
        
        super().__init__(config)
        
        # Parse URL if provided
        if 'url' in config:
            self._parse_url(config['url'])
        
        # Kubernetes connection parameters
        self.kubeconfig_path = config.get('kubeconfig_path')
        self.context = config.get('context')
        
        # Pod parameters
        self.namespace = config.get('namespace', 'default')
        self.pod_name = config.get('pod_name', '')
        self.container_name = config.get('container_name')
        self.pod_path = config.get('pod_path', '/tmp')
        
        # Pod creation options
        self.create_pod = config.get('create_pod', False)
        self.image = config.get('image')  # No default, required when creating pod
        self.command = config.get('command', ['sleep', '3600'])
        self.service_account = config.get('service_account')
        self.node_selector = config.get('node_selector', {})
        self.tolerations = config.get('tolerations', [])
        self.resources = config.get('resources', {})
        
        # Kubernetes clients
        self._core_v1_api: Optional[client.CoreV1Api] = None
        self._created_pod: Optional[str] = None
    
    def _parse_url(self, url: str) -> None:
        """Parse Kubernetes URL and update configuration."""
        # Example: k8s://namespace/pod_name/container_name/path/to/file
        if url.startswith(('k8s://', 'kubernetes://')):
            scheme_len = 6 if url.startswith('k8s://') else 13  # k8s:// is 6 chars, not 5
            parts = url[scheme_len:].split('/')
            
            if len(parts) >= 2:
                self.config['namespace'] = parts[0]
                self.config['pod_name'] = parts[1]
                
                if len(parts) >= 3:
                    self.config['container_name'] = parts[2]
                    
                    if len(parts) >= 4:
                        self.config['pod_path'] = '/' + '/'.join(parts[3:])
    
    async def validate_config(self) -> bool:
        """
        Validate Kubernetes configuration.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Check required parameters
            if not self.pod_name:
                self.logger.error("Pod name is required")
                return False
            
            if not self.namespace:
                self.logger.error("Namespace is required")
                return False
            
            # If creating pod, image is required
            if self.create_pod and not self.image:
                self.logger.error("Image is required when creating pod")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """
        Test Kubernetes connection.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            await self._connect()
            
            # Test cluster connection by listing namespaces
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._core_v1_api.list_namespace
            )
            
            self.logger.info("Kubernetes connection test successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Kubernetes connection test failed: {e}")
            return False
    
    async def _connect(self) -> None:
        """Establish Kubernetes connection."""
        if self._core_v1_api:
            return
        
        # Load kubeconfig
        if self.kubeconfig_path:
            config.load_kube_config(config_file=self.kubeconfig_path, context=self.context)
        else:
            try:
                # Try in-cluster config first
                config.load_incluster_config()
            except config.ConfigException:
                # Fall back to default kubeconfig
                config.load_kube_config(context=self.context)
        
        # Create API client
        self._core_v1_api = client.CoreV1Api()
        
        self.logger.info("Kubernetes connection established")
    
    async def _ensure_pod_exists(self) -> str:
        """Ensure pod exists, create if needed."""
        if self._created_pod:
            return self._created_pod
        
        loop = asyncio.get_event_loop()
        
        try:
            # Try to get existing pod
            pod = await loop.run_in_executor(
                None,
                self._core_v1_api.read_namespaced_pod,
                self.pod_name,
                self.namespace
            )
            
            # Check if pod is running
            if pod.status.phase != 'Running':
                # Wait for pod to be running
                await self._wait_for_pod_running()
            
            return self.pod_name
            
        except ApiException as e:
            if e.status != 404:
                raise
            
            if not self.create_pod:
                raise Exception(f"Pod {self.pod_name} not found in namespace {self.namespace}")
            
            # Create new pod
            await self._create_pod()
            return self.pod_name
    
    async def _create_pod(self) -> None:
        """Create a new pod."""
        self.logger.info(f"Creating pod {self.pod_name} in namespace {self.namespace}")
        
        # Prepare pod specification
        pod_spec = client.V1PodSpec(
            containers=[
                client.V1Container(
                    name=self.container_name or 'main',
                    image=self.image,
                    command=self.command,
                    resources=client.V1ResourceRequirements(**self.resources) if self.resources else None
                )
            ],
            restart_policy='Never',
            service_account_name=self.service_account,
            node_selector=self.node_selector if self.node_selector else None,
            tolerations=[
                client.V1Toleration(**toleration) for toleration in self.tolerations
            ] if self.tolerations else None
        )
        
        pod = client.V1Pod(
            api_version='v1',
            kind='Pod',
            metadata=client.V1ObjectMeta(
                name=self.pod_name,
                namespace=self.namespace
            ),
            spec=pod_spec
        )
        
        # Create pod
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._core_v1_api.create_namespaced_pod,
            self.namespace,
            pod
        )
        
        self._created_pod = self.pod_name
        
        # Wait for pod to be running
        await self._wait_for_pod_running()
    
    async def _wait_for_pod_running(self, timeout: int = 300) -> None:
        """Wait for pod to be in running state."""
        self.logger.info(f"Waiting for pod {self.pod_name} to be running...")
        
        start_time = asyncio.get_event_loop().time()
        
        while True:
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise Exception(f"Timeout waiting for pod {self.pod_name} to be running")
            
            loop = asyncio.get_event_loop()
            pod = await loop.run_in_executor(
                None,
                self._core_v1_api.read_namespaced_pod,
                self.pod_name,
                self.namespace
            )
            
            if pod.status.phase == 'Running':
                self.logger.info(f"Pod {self.pod_name} is now running")
                break
            elif pod.status.phase == 'Failed':
                raise Exception(f"Pod {self.pod_name} failed to start")
            
            await asyncio.sleep(2)
    
    async def _copy_to_pod(self, source_path: Path, destination_path: str) -> None:
        """Copy file to pod using kubectl cp equivalent."""
        # Read source file
        with open(source_path, 'rb') as f:
            file_content = f.read()
        
        # Encode file content
        encoded_content = base64.b64encode(file_content).decode('utf-8')
        
        # Create command to write file in pod
        command = [
            'sh', '-c',
            f'echo "{encoded_content}" | base64 -d > {destination_path}'
        ]
        
        # Execute command in pod
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            stream,
            self._core_v1_api.connect_get_namespaced_pod_exec,
            self.pod_name,
            self.namespace,
            command=command,
            container=self.container_name,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False
        )
    
    async def _copy_from_pod(self, source_path: str, destination_path: Path) -> None:
        """Copy file from pod using kubectl cp equivalent."""
        # Create command to read file from pod
        command = ['cat', source_path]
        
        # Execute command in pod
        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(
            None,
            stream,
            self._core_v1_api.connect_get_namespaced_pod_exec,
            self.pod_name,
            self.namespace,
            command=command,
            container=self.container_name,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False
        )
        
        # Write output to destination file
        with open(destination_path, 'wb') as f:
            f.write(output.encode('utf-8'))
    
    async def transfer_file(
        self, 
        source: Union[str, Path], 
        destination: Union[str, Path],
        **kwargs
    ) -> TransferResult:
        """
        Transfer a single file to/from Kubernetes pod.
        
        Args:
            source: Source file path
            destination: Destination file path
            **kwargs: Additional transfer options
            
        Returns:
            TransferResult with operation details
        """
        source_path = Path(source)
        
        if not source_path.exists():
            return TransferResult(
                success=False,
                status=TransferStatus.FAILED,
                progress=self._progress,
                transferred_files=[],
                failed_files=[str(source)],
                error_message=f"Source file not found: {source}"
            )
        
        try:
            await self._connect()
            
            # Get file size for progress tracking
            file_size = source_path.stat().st_size
            self._update_progress(
                total_bytes=file_size,
                total_files=1,
                current_file=str(source)
            )
            
            # Ensure pod exists
            await self._ensure_pod_exists()
            
            # Determine transfer direction
            is_to_pod = kwargs.get('to_pod', True)
            
            if is_to_pod:
                # Transfer to pod
                pod_file_path = f"{self.pod_path}/{Path(destination).name}"
                await self._copy_to_pod(source_path, pod_file_path)
            else:
                # Transfer from pod
                await self._copy_from_pod(str(destination), source_path)
            
            self._update_progress(
                transferred_files=1,
                transferred_bytes=file_size,
                status=TransferStatus.COMPLETED
            )
            
            return TransferResult(
                success=True,
                status=TransferStatus.COMPLETED,
                progress=self._progress,
                transferred_files=[str(source)],
                failed_files=[]
            )
            
        except Exception as e:
            self.logger.error(f"Kubernetes file transfer failed: {e}")
            self._update_progress(status=TransferStatus.FAILED, error_message=str(e))
            
            return TransferResult(
                success=False,
                status=TransferStatus.FAILED,
                progress=self._progress,
                transferred_files=[],
                failed_files=[str(source)],
                error_message=str(e)
            )
    
    async def transfer_directory(
        self,
        source: Union[str, Path],
        destination: Union[str, Path],
        recursive: bool = True,
        **kwargs
    ) -> TransferResult:
        """
        Transfer a directory to/from Kubernetes pod.
        
        Args:
            source: Source directory path
            destination: Destination directory path
            recursive: Whether to transfer subdirectories
            **kwargs: Additional transfer options
            
        Returns:
            TransferResult with operation details
        """
        source_path = Path(source)
        
        if not source_path.exists():
            return TransferResult(
                success=False,
                status=TransferStatus.FAILED,
                progress=self._progress,
                transferred_files=[],
                failed_files=[str(source)],
                error_message=f"Source directory not found: {source}"
            )
        
        if not source_path.is_dir():
            return TransferResult(
                success=False,
                status=TransferStatus.FAILED,
                progress=self._progress,
                transferred_files=[],
                failed_files=[str(source)],
                error_message=f"Source is not a directory: {source}"
            )
        
        try:
            await self._connect()
            await self._ensure_pod_exists()
            
            # Collect all files to transfer
            files_to_transfer = []
            if recursive:
                for file_path in source_path.rglob('*'):
                    if file_path.is_file():
                        files_to_transfer.append(file_path)
            else:
                for file_path in source_path.iterdir():
                    if file_path.is_file():
                        files_to_transfer.append(file_path)
            
            # Calculate total size
            total_size = sum(f.stat().st_size for f in files_to_transfer)
            self._update_progress(
                total_bytes=total_size,
                total_files=len(files_to_transfer)
            )
            
            transferred_files = []
            failed_files = []
            
            # Determine transfer direction
            is_to_pod = kwargs.get('to_pod', True)
            
            # Transfer each file
            for file_path in files_to_transfer:
                if self.is_cancelled():
                    break
                
                try:
                    self._update_progress(current_file=str(file_path))
                    
                    if is_to_pod:
                        # Calculate relative path and pod path
                        relative_path = file_path.relative_to(source_path)
                        pod_file_path = f"{self.pod_path}/{destination}/{relative_path}".replace('\\', '/')
                        
                        # Create directory in pod if needed
                        pod_dir = '/'.join(pod_file_path.split('/')[:-1])
                        mkdir_command = ['mkdir', '-p', pod_dir]
                        
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(
                            None,
                            stream,
                            self._core_v1_api.connect_get_namespaced_pod_exec,
                            self.pod_name,
                            self.namespace,
                            command=mkdir_command,
                            container=self.container_name,
                            stderr=True,
                            stdin=False,
                            stdout=True,
                            tty=False
                        )
                        
                        await self._copy_to_pod(file_path, pod_file_path)
                    else:
                        # Transfer from pod
                        relative_path = file_path.relative_to(source_path)
                        pod_file_path = f"{destination}/{relative_path}".replace('\\', '/')
                        local_file_path = source_path / relative_path
                        
                        # Create local directory if needed
                        local_file_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        await self._copy_from_pod(pod_file_path, local_file_path)
                    
                    transferred_files.append(str(file_path))
                    self._update_progress(transferred_files=len(transferred_files))
                    
                except Exception as e:
                    self.logger.error(f"Failed to transfer {file_path}: {e}")
                    failed_files.append(str(file_path))
            
            success = len(failed_files) == 0 and not self.is_cancelled()
            status = TransferStatus.COMPLETED if success else TransferStatus.FAILED
            
            self._update_progress(status=status)
            
            return TransferResult(
                success=success,
                status=status,
                progress=self._progress,
                transferred_files=transferred_files,
                failed_files=failed_files
            )
            
        except Exception as e:
            self.logger.error(f"Kubernetes directory transfer failed: {e}")
            self._update_progress(status=TransferStatus.FAILED, error_message=str(e))
            
            return TransferResult(
                success=False,
                status=TransferStatus.FAILED,
                progress=self._progress,
                transferred_files=[],
                failed_files=[str(source)],
                error_message=str(e)
            )
    
    async def cleanup(self) -> None:
        """Clean up Kubernetes resources."""
        if self._created_pod and self._core_v1_api:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    self._core_v1_api.delete_namespaced_pod,
                    self._created_pod,
                    self.namespace
                )
                self.logger.info(f"Cleaned up created pod: {self._created_pod}")
            except Exception as e:
                self.logger.warning(f"Failed to cleanup pod: {e}")
        
        self._core_v1_api = None