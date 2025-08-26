"""
Platform-specific adapters for different system types.

This module provides adapters for various platforms including:
- CMS systems (WordPress, Drupal, Joomla)
- Web frameworks (Django, Laravel, Rails, Spring Boot, Next.js)
- Container platforms (Docker, Kubernetes)
- Cloud platforms (AWS, Azure, GCP, Netlify, Vercel)
- Control panels (cPanel, DirectAdmin, Plesk)
"""

from .base import PlatformAdapter
from .cms import CMSAdapter, WordPressAdapter, DrupalAdapter, JoomlaAdapter
from .framework import FrameworkAdapter, DjangoAdapter, LaravelAdapter, RailsAdapter, SpringBootAdapter, NextJSAdapter
from .container import ContainerAdapter, DockerAdapter, KubernetesAdapter
from .cloud import CloudAdapter, AWSAdapter, AzureAdapter, GCPAdapter, NetlifyAdapter, VercelAdapter
from .control_panel import ControlPanelAdapter, CPanelAdapter, DirectAdminAdapter, PleskAdapter
from .factory import PlatformAdapterFactory

__all__ = [
    'PlatformAdapter',
    'CMSAdapter', 'WordPressAdapter', 'DrupalAdapter', 'JoomlaAdapter',
    'FrameworkAdapter', 'DjangoAdapter', 'LaravelAdapter', 'RailsAdapter', 'SpringBootAdapter', 'NextJSAdapter',
    'ContainerAdapter', 'DockerAdapter', 'KubernetesAdapter',
    'CloudAdapter', 'AWSAdapter', 'AzureAdapter', 'GCPAdapter', 'NetlifyAdapter', 'VercelAdapter',
    'ControlPanelAdapter', 'CPanelAdapter', 'DirectAdminAdapter', 'PleskAdapter',
    'PlatformAdapterFactory'
]