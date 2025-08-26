"""
Tests for platform adapters (CMS and framework adapters).
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from migration_assistant.platforms.factory import PlatformAdapterFactory
from migration_assistant.platforms.cms import WordPressAdapter, DrupalAdapter, JoomlaAdapter
from migration_assistant.platforms.framework import DjangoAdapter, LaravelAdapter, NextJSAdapter
from migration_assistant.platforms.container import DockerAdapter, KubernetesAdapter
from migration_assistant.platforms.cloud import AWSAdapter, NetlifyAdapter, VercelAdapter
from migration_assistant.platforms.control_panel import CPanelAdapter, DirectAdminAdapter, PleskAdapter, HostingAccount, DatabaseInfo, EmailAccount, DNSRecord
from migration_assistant.models.config import SystemConfig
from migration_assistant.core.exceptions import PlatformError


class TestPlatformAdapterFactory:
    """Test platform adapter factory."""
    
    def test_get_available_platforms(self):
        """Test getting available platforms."""
        platforms = PlatformAdapterFactory.get_available_platforms()
        
        expected_platforms = [
            "wordpress", "drupal", "joomla",
            "django", "laravel", "rails", "springboot", "nextjs"
        ]
        
        for platform in expected_platforms:
            assert platform in platforms
    
    def test_create_adapter(self):
        """Test creating platform adapters."""
        config = SystemConfig(type="wordpress", host="localhost")
        
        adapter = PlatformAdapterFactory.create_adapter("wordpress", config)
        assert isinstance(adapter, WordPressAdapter)
        assert adapter.platform_type == "wordpress"
    
    def test_create_adapter_invalid_platform(self):
        """Test creating adapter for invalid platform."""
        config = SystemConfig(type="invalid", host="localhost")
        
        with pytest.raises(PlatformError):
            PlatformAdapterFactory.create_adapter("invalid", config)
    
    def test_validate_platform_compatibility(self):
        """Test platform compatibility validation."""
        # Same platform should be compatible
        assert PlatformAdapterFactory.validate_platform_compatibility("wordpress", "wordpress")
        
        # CMS to CMS should be compatible
        assert PlatformAdapterFactory.validate_platform_compatibility("wordpress", "drupal")
        
        # Framework to different framework should not be compatible
        assert not PlatformAdapterFactory.validate_platform_compatibility("django", "laravel")
    
    def test_get_migration_complexity(self):
        """Test migration complexity assessment."""
        # Same platform should be simple
        assert PlatformAdapterFactory.get_migration_complexity("wordpress", "wordpress") == "simple"
        
        # CMS to different CMS should be complex
        assert PlatformAdapterFactory.get_migration_complexity("wordpress", "drupal") == "complex"
        
        # Unsupported migration
        assert PlatformAdapterFactory.get_migration_complexity("django", "laravel") == "unsupported"


class TestWordPressAdapter:
    """Test WordPress adapter."""
    
    @pytest.fixture
    def wordpress_adapter(self):
        """Create WordPress adapter for testing."""
        config = SystemConfig(type="wordpress", host="localhost")
        return WordPressAdapter(config)
    
    @pytest.fixture
    def wordpress_site(self):
        """Create temporary WordPress site structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            site_path = Path(temp_dir)
            
            # Create WordPress structure
            (site_path / "wp-config.php").write_text("""
<?php
define('DB_NAME', 'wordpress_db');
define('DB_USER', 'wp_user');
define('DB_PASSWORD', 'wp_pass');
define('DB_HOST', 'localhost');
define('DB_CHARSET', 'utf8');
$table_prefix = 'wp_';
""")
            
            (site_path / "wp-includes").mkdir()
            (site_path / "wp-admin").mkdir()
            
            # Create version file
            version_file = site_path / "wp-includes" / "version.php"
            version_file.write_text("<?php $wp_version = '6.3.1';")
            
            # Create themes directory
            themes_dir = site_path / "wp-content" / "themes" / "twentytwentythree"
            themes_dir.mkdir(parents=True)
            (themes_dir / "style.css").write_text("""
/*
Theme Name: Twenty Twenty-Three
Version: 1.2
Description: Default WordPress theme
Author: WordPress Team
*/
""")
            
            # Create plugins directory
            plugins_dir = site_path / "wp-content" / "plugins" / "hello-dolly"
            plugins_dir.mkdir(parents=True)
            (plugins_dir / "hello.php").write_text("""
<?php
/*
Plugin Name: Hello Dolly
Version: 1.7.2
Description: This is not just a plugin
Author: Matt Mullenweg
*/
""")
            
            yield site_path
    
    @pytest.mark.asyncio
    async def test_detect_wordpress(self, wordpress_adapter, wordpress_site):
        """Test WordPress detection."""
        assert await wordpress_adapter.detect_platform(wordpress_site)
        
        # Test non-WordPress directory
        with tempfile.TemporaryDirectory() as temp_dir:
            non_wp_path = Path(temp_dir)
            assert not await wordpress_adapter.detect_platform(non_wp_path)
    
    @pytest.mark.asyncio
    async def test_analyze_wordpress(self, wordpress_adapter, wordpress_site):
        """Test WordPress analysis."""
        platform_info = await wordpress_adapter.analyze_platform(wordpress_site)
        
        assert platform_info.platform_type == "wordpress"
        assert platform_info.version == "6.3.1"
        assert platform_info.framework == "wordpress"
        assert platform_info.database_type == "mysql"
        assert "php" in platform_info.dependencies
    
    @pytest.mark.asyncio
    async def test_get_database_config(self, wordpress_adapter, wordpress_site):
        """Test WordPress database configuration extraction."""
        db_config = await wordpress_adapter.get_database_config(wordpress_site)
        
        assert db_config["name"] == "wordpress_db"
        assert db_config["user"] == "wp_user"
        assert db_config["password"] == "wp_pass"
        assert db_config["host"] == "localhost"
        assert db_config["prefix"] == "wp_"
    
    @pytest.mark.asyncio
    async def test_get_theme_info(self, wordpress_adapter, wordpress_site):
        """Test WordPress theme information extraction."""
        themes = await wordpress_adapter.get_theme_info(wordpress_site)
        
        assert "twentytwentythree" in themes
        theme_info = themes["twentytwentythree"]
        assert theme_info["name"] == "Twenty Twenty-Three"
        assert theme_info["version"] == "1.2"
    
    @pytest.mark.asyncio
    async def test_get_plugin_info(self, wordpress_adapter, wordpress_site):
        """Test WordPress plugin information extraction."""
        plugins = await wordpress_adapter.get_plugin_info(wordpress_site)
        
        assert "hello-dolly" in plugins
        plugin_info = plugins["hello-dolly"]
        assert plugin_info["name"] == "Hello Dolly"
        assert plugin_info["version"] == "1.7.2"
    
    @pytest.mark.asyncio
    async def test_prepare_migration(self, wordpress_adapter, wordpress_site):
        """Test WordPress migration preparation."""
        destination_path = Path("/tmp/destination")
        migration_info = await wordpress_adapter.prepare_migration(wordpress_site, destination_path)
        
        assert "platform_info" in migration_info
        assert "database_config" in migration_info
        assert "themes" in migration_info
        assert "plugins" in migration_info
        assert "migration_steps" in migration_info
        
        expected_steps = ["backup_database", "export_content", "copy_themes", "copy_plugins", "copy_uploads", "update_config", "update_urls"]
        assert migration_info["migration_steps"] == expected_steps


class TestDjangoAdapter:
    """Test Django adapter."""
    
    @pytest.fixture
    def django_adapter(self):
        """Create Django adapter for testing."""
        config = SystemConfig(type="django", host="localhost")
        return DjangoAdapter(config)
    
    @pytest.fixture
    def django_project(self):
        """Create temporary Django project structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # Create manage.py
            (project_path / "manage.py").write_text("""
#!/usr/bin/env python
import os
import sys

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError("Django is not installed") from exc
    execute_from_command_line(sys.argv)
""")
            
            # Create requirements.txt
            (project_path / "requirements.txt").write_text("""
Django==4.2.5
psycopg2-binary==2.9.7
gunicorn==21.2.0
""")
            
            # Create settings.py
            settings_dir = project_path / "myproject"
            settings_dir.mkdir()
            (settings_dir / "settings.py").write_text("""
import os

SECRET_KEY = os.environ.get('SECRET_KEY', 'default-secret-key')
DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'myproject'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'myapp',
]
""")
            
            # Create .env file
            (project_path / ".env").write_text("""
SECRET_KEY=my-secret-key
DB_NAME=myproject_db
DB_USER=myuser
DB_PASSWORD=mypassword
DB_HOST=localhost
""")
            
            yield project_path
    
    @pytest.mark.asyncio
    async def test_detect_django(self, django_adapter, django_project):
        """Test Django detection."""
        assert await django_adapter.detect_platform(django_project)
        
        # Test non-Django directory
        with tempfile.TemporaryDirectory() as temp_dir:
            non_django_path = Path(temp_dir)
            assert not await django_adapter.detect_platform(non_django_path)
    
    @pytest.mark.asyncio
    async def test_analyze_django(self, django_adapter, django_project):
        """Test Django analysis."""
        platform_info = await django_adapter.analyze_platform(django_project)
        
        assert platform_info.platform_type == "django"
        assert platform_info.version == "4.2.5"
        assert platform_info.framework == "django"
        assert platform_info.database_type == "postgresql"
        assert "Django" in platform_info.dependencies
    
    @pytest.mark.asyncio
    async def test_get_package_info(self, django_adapter, django_project):
        """Test Django package information extraction."""
        packages = await django_adapter.get_package_info(django_project)
        
        assert "Django" in packages
        assert packages["Django"] == "4.2.5"
        assert "psycopg2-binary" in packages
        assert packages["psycopg2-binary"] == "2.9.7"
    
    @pytest.mark.asyncio
    async def test_get_environment_config(self, django_adapter, django_project):
        """Test Django environment configuration extraction."""
        env_config = await django_adapter.get_environment_config(django_project)
        
        assert "SECRET_KEY" in env_config.variables
        assert "DB_NAME" in env_config.variables
        assert env_config.variables["SECRET_KEY"] == "my-secret-key"
        assert ".env" in env_config.files
        assert "SECRET_KEY" in env_config.secrets


class TestNextJSAdapter:
    """Test Next.js adapter."""
    
    @pytest.fixture
    def nextjs_adapter(self):
        """Create Next.js adapter for testing."""
        config = SystemConfig(type="nextjs", host="localhost")
        return NextJSAdapter(config)
    
    @pytest.fixture
    def nextjs_project(self):
        """Create temporary Next.js project structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # Create package.json
            package_json = {
                "name": "my-nextjs-app",
                "version": "0.1.0",
                "private": True,
                "scripts": {
                    "dev": "next dev",
                    "build": "next build",
                    "start": "next start"
                },
                "dependencies": {
                    "next": "14.0.0",
                    "react": "18.2.0",
                    "react-dom": "18.2.0"
                },
                "devDependencies": {
                    "@types/node": "20.5.0",
                    "@types/react": "18.2.0",
                    "typescript": "5.1.0"
                }
            }
            (project_path / "package.json").write_text(json.dumps(package_json, indent=2))
            
            # Create next.config.js
            (project_path / "next.config.js").write_text("""
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
}

module.exports = nextConfig
""")
            
            # Create .env.local
            (project_path / ".env.local").write_text("""
NEXTAUTH_SECRET=my-nextauth-secret
DATABASE_URL=postgresql://user:pass@localhost:5432/mydb
API_SECRET=my-api-secret
""")
            
            # Create pages directory
            pages_dir = project_path / "pages"
            pages_dir.mkdir()
            (pages_dir / "index.js").write_text("""
export default function Home() {
  return <div>Hello Next.js!</div>
}
""")
            
            yield project_path
    
    @pytest.mark.asyncio
    async def test_detect_nextjs(self, nextjs_adapter, nextjs_project):
        """Test Next.js detection."""
        assert await nextjs_adapter.detect_platform(nextjs_project)
        
        # Test non-Next.js directory
        with tempfile.TemporaryDirectory() as temp_dir:
            non_nextjs_path = Path(temp_dir)
            assert not await nextjs_adapter.detect_platform(non_nextjs_path)
    
    @pytest.mark.asyncio
    async def test_analyze_nextjs(self, nextjs_adapter, nextjs_project):
        """Test Next.js analysis."""
        platform_info = await nextjs_adapter.analyze_platform(nextjs_project)
        
        assert platform_info.platform_type == "nextjs"
        assert platform_info.version == "14.0.0"
        assert platform_info.framework == "nextjs"
        assert platform_info.database_type is None
        assert "next" in platform_info.dependencies
    
    @pytest.mark.asyncio
    async def test_get_package_info(self, nextjs_adapter, nextjs_project):
        """Test Next.js package information extraction."""
        packages = await nextjs_adapter.get_package_info(nextjs_project)
        
        assert "next" in packages
        assert packages["next"] == "14.0.0"
        assert "react" in packages
        assert packages["react"] == "18.2.0"
    
    @pytest.mark.asyncio
    async def test_get_environment_config(self, nextjs_adapter, nextjs_project):
        """Test Next.js environment configuration extraction."""
        env_config = await nextjs_adapter.get_environment_config(nextjs_project)
        
        assert "NEXTAUTH_SECRET" in env_config.variables
        assert "DATABASE_URL" in env_config.variables
        assert env_config.variables["NEXTAUTH_SECRET"] == "my-nextauth-secret"
        assert ".env.local" in env_config.files
        assert "NEXTAUTH_SECRET" in env_config.secrets


class TestPlatformDetection:
    """Test automatic platform detection."""
    
    @pytest.mark.asyncio
    async def test_detect_multiple_platforms(self):
        """Test detecting multiple platforms in a directory."""
        config = SystemConfig(type="auto", host="localhost")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            
            # Create WordPress structure
            wp_path = base_path / "wordpress"
            wp_path.mkdir()
            (wp_path / "wp-config.php").write_text("<?php // WordPress config")
            (wp_path / "wp-includes").mkdir()
            (wp_path / "wp-admin").mkdir()
            
            # Create Django structure
            django_path = base_path / "django"
            django_path.mkdir()
            (django_path / "manage.py").write_text("#!/usr/bin/env python\n# Django manage.py")
            (django_path / "requirements.txt").write_text("Django==4.2.0")
            
            # Test WordPress detection
            wp_adapter = await PlatformAdapterFactory.detect_platform(wp_path, config)
            assert wp_adapter is not None
            assert wp_adapter.platform_type == "wordpress"
            
            # Test Django detection
            django_adapter = await PlatformAdapterFactory.detect_platform(django_path, config)
            assert django_adapter is not None
            assert django_adapter.platform_type == "django"
    
    @pytest.mark.asyncio
    async def test_no_platform_detected(self):
        """Test when no platform is detected."""
        config = SystemConfig(type="auto", host="localhost")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_path = Path(temp_dir)
            
            adapter = await PlatformAdapterFactory.detect_platform(empty_path, config)
            assert adapter is None


@pytest.mark.integration
class TestPlatformAdapterIntegration:
    """Integration tests for platform adapters."""
    
    @pytest.mark.asyncio
    async def test_wordpress_full_workflow(self):
        """Test complete WordPress migration workflow."""
        config = SystemConfig(type="wordpress", host="localhost")
        adapter = WordPressAdapter(config)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "source"
            destination_path = Path(temp_dir) / "destination"
            
            # Create minimal WordPress structure
            source_path.mkdir()
            (source_path / "wp-config.php").write_text("<?php // WordPress config")
            (source_path / "wp-includes").mkdir()
            (source_path / "wp-admin").mkdir()
            
            # Test detection
            assert await adapter.detect_platform(source_path)
            
            # Test analysis
            platform_info = await adapter.analyze_platform(source_path)
            assert platform_info.platform_type == "wordpress"
            
            # Test migration preparation
            migration_info = await adapter.prepare_migration(source_path, destination_path)
            assert "migration_steps" in migration_info
            
            # Test dependencies
            dependencies = await adapter.get_dependencies()
            assert len(dependencies) > 0
            assert any(dep.name == "php" for dep in dependencies)
    
    @pytest.mark.asyncio
    async def test_django_full_workflow(self):
        """Test complete Django migration workflow."""
        config = SystemConfig(type="django", host="localhost")
        adapter = DjangoAdapter(config)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "source"
            destination_path = Path(temp_dir) / "destination"
            
            # Create minimal Django structure
            source_path.mkdir()
            (source_path / "manage.py").write_text("#!/usr/bin/env python\n# Django manage.py")
            (source_path / "requirements.txt").write_text("Django==4.2.0")
            
            # Test detection
            assert await adapter.detect_platform(source_path)
            
            # Test analysis
            platform_info = await adapter.analyze_platform(source_path)
            assert platform_info.platform_type == "django"
            
            # Test migration preparation
            migration_info = await adapter.prepare_migration(source_path, destination_path)
            assert "migration_steps" in migration_info
            
            # Test dependencies
            dependencies = await adapter.get_dependencies()
            assert len(dependencies) > 0
            assert any(dep.name == "python" for dep in dependencies)


class TestDockerAdapter:
    """Test Docker adapter."""
    
    @pytest.fixture
    def docker_adapter(self):
        """Create Docker adapter for testing."""
        config = SystemConfig(type="docker", host="localhost")
        return DockerAdapter(config)
    
    @pytest.fixture
    def docker_project(self):
        """Create temporary Docker project structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # Create Dockerfile
            (project_path / "Dockerfile").write_text("""
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 3000
CMD ["npm", "start"]
""")
            
            # Create docker-compose.yml
            compose_content = {
                "version": "3.8",
                "services": {
                    "web": {
                        "build": ".",
                        "ports": ["3000:3000"],
                        "environment": {
                            "NODE_ENV": "production",
                            "DATABASE_URL": "postgresql://user:pass@db:5432/myapp"
                        },
                        "depends_on": ["db"]
                    },
                    "db": {
                        "image": "postgres:15",
                        "environment": {
                            "POSTGRES_DB": "myapp",
                            "POSTGRES_USER": "user",
                            "POSTGRES_PASSWORD": "pass"
                        },
                        "volumes": ["postgres_data:/var/lib/postgresql/data"]
                    }
                },
                "volumes": {
                    "postgres_data": {}
                }
            }
            (project_path / "docker-compose.yml").write_text(yaml.dump(compose_content))
            
            # Create .env file
            (project_path / ".env").write_text("""
NODE_ENV=development
DATABASE_URL=postgresql://user:pass@localhost:5432/myapp_dev
API_KEY=secret-api-key
""")
            
            yield project_path
    
    @pytest.mark.asyncio
    async def test_detect_docker(self, docker_adapter, docker_project):
        """Test Docker detection."""
        assert await docker_adapter.detect_platform(docker_project)
        
        # Test directory with only Dockerfile
        with tempfile.TemporaryDirectory() as temp_dir:
            dockerfile_only = Path(temp_dir)
            (dockerfile_only / "Dockerfile").write_text("FROM node:18")
            assert await docker_adapter.detect_platform(dockerfile_only)
        
        # Test directory with only docker-compose
        with tempfile.TemporaryDirectory() as temp_dir:
            compose_only = Path(temp_dir)
            (compose_only / "docker-compose.yml").write_text("version: '3.8'")
            assert await docker_adapter.detect_platform(compose_only)
    
    @pytest.mark.asyncio
    async def test_analyze_docker(self, docker_adapter, docker_project):
        """Test Docker analysis."""
        platform_info = await docker_adapter.analyze_platform(docker_project)
        
        assert platform_info.platform_type == "docker"
        assert platform_info.framework == "docker"
        assert platform_info.database_type == "postgresql"
        assert "docker" in platform_info.dependencies
        assert "docker-compose" in platform_info.dependencies
    
    @pytest.mark.asyncio
    async def test_get_environment_config(self, docker_adapter, docker_project):
        """Test Docker environment configuration extraction."""
        env_config = await docker_adapter.get_environment_config(docker_project)
        
        assert "NODE_ENV" in env_config.variables
        assert "DATABASE_URL" in env_config.variables
        assert ".env" in env_config.files


class TestKubernetesAdapter:
    """Test Kubernetes adapter."""
    
    @pytest.fixture
    def k8s_adapter(self):
        """Create Kubernetes adapter for testing."""
        config = SystemConfig(type="kubernetes", host="localhost")
        return KubernetesAdapter(config)
    
    @pytest.fixture
    def k8s_project(self):
        """Create temporary Kubernetes project structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # Create deployment.yaml
            deployment = {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": "web-app"},
                "spec": {
                    "replicas": 3,
                    "selector": {"matchLabels": {"app": "web-app"}},
                    "template": {
                        "metadata": {"labels": {"app": "web-app"}},
                        "spec": {
                            "containers": [{
                                "name": "web",
                                "image": "nginx:1.20",
                                "ports": [{"containerPort": 80}],
                                "env": [
                                    {"name": "NODE_ENV", "value": "production"},
                                    {"name": "DATABASE_URL", "valueFrom": {"secretKeyRef": {"name": "db-secret", "key": "url"}}}
                                ]
                            }]
                        }
                    }
                }
            }
            (project_path / "deployment.yaml").write_text(yaml.dump(deployment))
            
            # Create service.yaml
            service = {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {"name": "web-service"},
                "spec": {
                    "selector": {"app": "web-app"},
                    "ports": [{"port": 80, "targetPort": 80}],
                    "type": "LoadBalancer"
                }
            }
            (project_path / "service.yaml").write_text(yaml.dump(service))
            
            # Create configmap.yaml
            configmap = {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {"name": "app-config"},
                "data": {
                    "NODE_ENV": "production",
                    "LOG_LEVEL": "info"
                }
            }
            (project_path / "configmap.yaml").write_text(yaml.dump(configmap))
            
            yield project_path
    
    @pytest.mark.asyncio
    async def test_detect_kubernetes(self, k8s_adapter, k8s_project):
        """Test Kubernetes detection."""
        assert await k8s_adapter.detect_platform(k8s_project)
        
        # Test non-Kubernetes directory
        with tempfile.TemporaryDirectory() as temp_dir:
            non_k8s_path = Path(temp_dir)
            assert not await k8s_adapter.detect_platform(non_k8s_path)
    
    @pytest.mark.asyncio
    async def test_analyze_kubernetes(self, k8s_adapter, k8s_project):
        """Test Kubernetes analysis."""
        platform_info = await k8s_adapter.analyze_platform(k8s_project)
        
        assert platform_info.platform_type == "kubernetes"
        assert platform_info.framework == "kubernetes"
        assert "kubectl" in platform_info.dependencies
        assert len(platform_info.config_files) > 0


class TestAWSAdapter:
    """Test AWS adapter."""
    
    @pytest.fixture
    def aws_adapter(self):
        """Create AWS adapter for testing."""
        config = SystemConfig(type="aws", host="localhost")
        return AWSAdapter(config)
    
    @pytest.fixture
    def aws_project(self):
        """Create temporary AWS project structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # Create SAM template
            sam_template = {
                "AWSTemplateFormatVersion": "2010-09-09",
                "Transform": "AWS::Serverless-2016-10-31",
                "Globals": {
                    "Function": {
                        "Timeout": 30,
                        "Environment": {
                            "Variables": {
                                "NODE_ENV": "production",
                                "LOG_LEVEL": "info"
                            }
                        }
                    }
                },
                "Resources": {
                    "HelloWorldFunction": {
                        "Type": "AWS::Serverless::Function",
                        "Properties": {
                            "CodeUri": "hello-world/",
                            "Handler": "app.lambdaHandler",
                            "Runtime": "nodejs18.x",
                            "Events": {
                                "HelloWorld": {
                                    "Type": "Api",
                                    "Properties": {
                                        "Path": "/hello",
                                        "Method": "get"
                                    }
                                }
                            }
                        }
                    }
                }
            }
            (project_path / "template.yaml").write_text(yaml.dump(sam_template))
            
            # Create serverless.yml
            serverless_config = {
                "service": "my-serverless-app",
                "provider": {
                    "name": "aws",
                    "runtime": "nodejs18.x",
                    "region": "us-east-1",
                    "environment": {
                        "NODE_ENV": "production",
                        "DATABASE_URL": "${env:DATABASE_URL}"
                    }
                },
                "functions": {
                    "hello": {
                        "handler": "handler.hello",
                        "events": [{"http": {"path": "/hello", "method": "get"}}]
                    }
                }
            }
            (project_path / "serverless.yml").write_text(yaml.dump(serverless_config))
            
            yield project_path
    
    @pytest.mark.asyncio
    async def test_detect_aws(self, aws_adapter, aws_project):
        """Test AWS detection."""
        assert await aws_adapter.detect_platform(aws_project)
        
        # Test directory with only SAM template
        with tempfile.TemporaryDirectory() as temp_dir:
            sam_only = Path(temp_dir)
            (sam_only / "template.yaml").write_text("AWSTemplateFormatVersion: '2010-09-09'")
            assert await aws_adapter.detect_platform(sam_only)
    
    @pytest.mark.asyncio
    async def test_analyze_aws(self, aws_adapter, aws_project):
        """Test AWS analysis."""
        platform_info = await aws_adapter.analyze_platform(aws_project)
        
        assert platform_info.platform_type == "aws"
        assert platform_info.framework == "aws"
        assert "aws-cli" in platform_info.dependencies
        assert "sam-cli" in platform_info.dependencies


class TestCloudAdapterIntegration:
    """Integration tests for cloud adapters."""
    
    @pytest.mark.asyncio
    async def test_netlify_detection(self):
        """Test Netlify detection."""
        config = SystemConfig(type="netlify", host="localhost")
        adapter = NetlifyAdapter(config)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # Create netlify.toml
            (project_path / "netlify.toml").write_text("""
[build]
  publish = "dist"
  command = "npm run build"

[build.environment]
  NODE_VERSION = "18"
""")
            
            assert await adapter.detect_platform(project_path)
            
            platform_info = await adapter.analyze_platform(project_path)
            assert platform_info.platform_type == "netlify"
    
    @pytest.mark.asyncio
    async def test_vercel_detection(self):
        """Test Vercel detection."""
        config = SystemConfig(type="vercel", host="localhost")
        adapter = VercelAdapter(config)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # Create vercel.json
            vercel_config = {
                "version": 2,
                "builds": [
                    {"src": "package.json", "use": "@vercel/node"}
                ],
                "routes": [
                    {"src": "/(.*)", "dest": "/"}
                ]
            }
            (project_path / "vercel.json").write_text(json.dumps(vercel_config, indent=2))
            
            assert await adapter.detect_platform(project_path)
            
            platform_info = await adapter.analyze_platform(project_path)
            assert platform_info.platform_type == "vercel"


@pytest.mark.integration
class TestContainerCloudAdapterIntegration:
    """Integration tests for container and cloud platform adapters."""
    
    @pytest.mark.asyncio
    async def test_docker_full_workflow(self):
        """Test complete Docker migration workflow."""
        config = SystemConfig(type="docker", host="localhost")
        adapter = DockerAdapter(config)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "source"
            destination_path = Path(temp_dir) / "destination"
            
            # Create minimal Docker structure
            source_path.mkdir()
            (source_path / "Dockerfile").write_text("FROM node:18\nWORKDIR /app")
            (source_path / "docker-compose.yml").write_text("version: '3.8'\nservices:\n  web:\n    build: .")
            
            # Test detection
            assert await adapter.detect_platform(source_path)
            
            # Test analysis
            platform_info = await adapter.analyze_platform(source_path)
            assert platform_info.platform_type == "docker"
            
            # Test migration preparation
            migration_info = await adapter.prepare_migration(source_path, destination_path)
            assert "migration_steps" in migration_info
            
            # Test dependencies
            dependencies = await adapter.get_dependencies()
            assert len(dependencies) > 0
            assert any(dep.name == "docker" for dep in dependencies)
    
    @pytest.mark.asyncio
    async def test_kubernetes_full_workflow(self):
        """Test complete Kubernetes migration workflow."""
        config = SystemConfig(type="kubernetes", host="localhost")
        adapter = KubernetesAdapter(config)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "source"
            destination_path = Path(temp_dir) / "destination"
            
            # Create minimal Kubernetes structure
            source_path.mkdir()
            deployment = {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": "test-app"},
                "spec": {"replicas": 1}
            }
            (source_path / "deployment.yaml").write_text(yaml.dump(deployment))
            
            # Test detection
            assert await adapter.detect_platform(source_path)
            
            # Test analysis
            platform_info = await adapter.analyze_platform(source_path)
            assert platform_info.platform_type == "kubernetes"
            
            # Test migration preparation
            migration_info = await adapter.prepare_migration(source_path, destination_path)
            assert "migration_steps" in migration_info
            
            # Test dependencies
            dependencies = await adapter.get_dependencies()
            assert len(dependencies) > 0
            assert any(dep.name == "kubectl" for dep in dependencies)


class TestCPanelAdapter:
    """Test cPanel adapter."""
    
    @pytest.fixture
    def cpanel_adapter(self):
        """Create cPanel adapter for testing."""
        config = SystemConfig(type="cpanel", host="cpanel.example.com")
        config.username = "testuser"
        config.api_token = "test_token"
        return CPanelAdapter(config)
    
    @pytest.fixture
    def cpanel_site(self):
        """Create temporary cPanel site structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            site_path = Path(temp_dir)
            
            # Create cPanel structure
            (site_path / ".cpanel").mkdir()
            (site_path / "public_html").mkdir()
            (site_path / "mail").mkdir()
            (site_path / "logs").mkdir()
            
            # Create cpanel.yml
            cpanel_config = {
                "---": None,
                "api_version": 3,
                "configuration": {
                    "domains": ["example.com", "subdomain.example.com"],
                    "databases": ["example_db", "test_db"]
                }
            }
            (site_path / "cpanel.yml").write_text(yaml.dump(cpanel_config))
            
            yield site_path
    
    @pytest.mark.asyncio
    async def test_detect_cpanel(self, cpanel_adapter, cpanel_site):
        """Test cPanel detection."""
        assert await cpanel_adapter.detect_platform(cpanel_site)
        
        # Test non-cPanel directory
        with tempfile.TemporaryDirectory() as temp_dir:
            non_cpanel_path = Path(temp_dir)
            assert not await cpanel_adapter.detect_platform(non_cpanel_path)
    
    @pytest.mark.asyncio
    async def test_analyze_cpanel(self, cpanel_adapter, cpanel_site):
        """Test cPanel analysis."""
        with patch.object(cpanel_adapter, '_get_cpanel_info', return_value={"version": "11.6"}):
            with patch.object(cpanel_adapter, 'get_accounts', return_value=[]):
                platform_info = await cpanel_adapter.analyze_platform(cpanel_site)
                
                assert platform_info.platform_type == "cpanel"
                assert platform_info.framework == "cpanel"
                assert platform_info.database_type == "mysql"
                assert "curl" in platform_info.dependencies
    
    @pytest.mark.asyncio
    async def test_get_environment_config(self, cpanel_adapter, cpanel_site):
        """Test cPanel environment configuration extraction."""
        env_config = await cpanel_adapter.get_environment_config(cpanel_site)
        
        assert "CPANEL_HOST" in env_config.variables
        assert "CPANEL_USER" in env_config.variables
        assert "CPANEL_API_TOKEN" in env_config.secrets
        assert ".cpanel" in env_config.files or "cpanel.yml" in env_config.files


class TestDirectAdminAdapter:
    """Test DirectAdmin adapter."""
    
    @pytest.fixture
    def directadmin_adapter(self):
        """Create DirectAdmin adapter for testing."""
        config = SystemConfig(type="directadmin", host="da.example.com")
        config.username = "admin"
        config.password = "password"
        return DirectAdminAdapter(config)
    
    @pytest.fixture
    def directadmin_site(self):
        """Create temporary DirectAdmin site structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            site_path = Path(temp_dir)
            
            # Create DirectAdmin structure
            (site_path / ".directadmin").mkdir()
            (site_path / "domains").mkdir()
            (site_path / "public_html").mkdir()
            
            # Create directadmin.conf
            (site_path / "directadmin.conf").write_text("""
# DirectAdmin Configuration
version=1.65
mysql=ON
php=ON
""")
            
            yield site_path
    
    @pytest.mark.asyncio
    async def test_detect_directadmin(self, directadmin_adapter, directadmin_site):
        """Test DirectAdmin detection."""
        assert await directadmin_adapter.detect_platform(directadmin_site)
        
        # Test non-DirectAdmin directory
        with tempfile.TemporaryDirectory() as temp_dir:
            non_da_path = Path(temp_dir)
            assert not await directadmin_adapter.detect_platform(non_da_path)
    
    @pytest.mark.asyncio
    async def test_analyze_directadmin(self, directadmin_adapter, directadmin_site):
        """Test DirectAdmin analysis."""
        with patch.object(directadmin_adapter, '_get_directadmin_info', return_value={"version": "1.65"}):
            platform_info = await directadmin_adapter.analyze_platform(directadmin_site)
            
            assert platform_info.platform_type == "directadmin"
            assert platform_info.framework == "directadmin"
            assert platform_info.database_type == "mysql"


class TestPleskAdapter:
    """Test Plesk adapter."""
    
    @pytest.fixture
    def plesk_adapter(self):
        """Create Plesk adapter for testing."""
        config = SystemConfig(type="plesk", host="plesk.example.com")
        config.api_key = "test_api_key"
        return PleskAdapter(config)
    
    @pytest.fixture
    def plesk_site(self):
        """Create temporary Plesk site structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            site_path = Path(temp_dir)
            
            # Create Plesk structure
            (site_path / ".plesk").mkdir()
            (site_path / "httpdocs").mkdir()
            (site_path / "vhosts").mkdir()
            
            # Create plesk.conf
            (site_path / "plesk.conf").write_text("""
# Plesk Configuration
version=21.0
mysql_support=true
php_support=true
""")
            
            yield site_path
    
    @pytest.mark.asyncio
    async def test_detect_plesk(self, plesk_adapter, plesk_site):
        """Test Plesk detection."""
        assert await plesk_adapter.detect_platform(plesk_site)
        
        # Test non-Plesk directory
        with tempfile.TemporaryDirectory() as temp_dir:
            non_plesk_path = Path(temp_dir)
            assert not await plesk_adapter.detect_platform(non_plesk_path)
    
    @pytest.mark.asyncio
    async def test_analyze_plesk(self, plesk_adapter, plesk_site):
        """Test Plesk analysis."""
        with patch.object(plesk_adapter, '_get_plesk_info', return_value={"version": "21.0"}):
            platform_info = await plesk_adapter.analyze_platform(plesk_site)
            
            assert platform_info.platform_type == "plesk"
            assert platform_info.framework == "plesk"
            assert platform_info.database_type == "mysql"


@pytest.mark.integration
class TestControlPanelAdapterIntegration:
    """Integration tests for control panel adapters."""
    
    @pytest.mark.asyncio
    async def test_cpanel_full_workflow(self):
        """Test complete cPanel migration workflow."""
        config = SystemConfig(type="cpanel", host="cpanel.example.com")
        config.username = "testuser"
        config.api_token = "test_token"
        adapter = CPanelAdapter(config)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "source"
            destination_path = Path(temp_dir) / "destination"
            
            # Create minimal cPanel structure
            source_path.mkdir()
            (source_path / ".cpanel").mkdir()
            (source_path / "public_html").mkdir()
            (source_path / "cpanel.yml").write_text("api_version: 3")
            
            # Test detection
            assert await adapter.detect_platform(source_path)
            
            # Test analysis (with mocked API calls)
            with patch.object(adapter, '_get_cpanel_info', return_value={"version": "11.6"}):
                with patch.object(adapter, 'get_accounts', return_value=[]):
                    platform_info = await adapter.analyze_platform(source_path)
                    assert platform_info.platform_type == "cpanel"
            
            # Test migration preparation
            with patch.object(adapter, 'get_accounts', return_value=[]):
                migration_info = await adapter.prepare_migration(source_path, destination_path)
                assert "migration_steps" in migration_info
            
            # Test dependencies
            dependencies = await adapter.get_dependencies()
            assert len(dependencies) > 0
            assert any(dep.name == "curl" for dep in dependencies)
    
    @pytest.mark.asyncio
    async def test_control_panel_factory_integration(self):
        """Test control panel adapters through factory."""
        # Test cPanel
        config = SystemConfig(type="cpanel", host="localhost")
        cpanel_adapter = PlatformAdapterFactory.create_adapter("cpanel", config)
        assert isinstance(cpanel_adapter, CPanelAdapter)
        assert cpanel_adapter.platform_type == "cpanel"
        
        # Test DirectAdmin
        config = SystemConfig(type="directadmin", host="localhost")
        da_adapter = PlatformAdapterFactory.create_adapter("directadmin", config)
        assert isinstance(da_adapter, DirectAdminAdapter)
        assert da_adapter.platform_type == "directadmin"
        
        # Test Plesk
        config = SystemConfig(type="plesk", host="localhost")
        plesk_adapter = PlatformAdapterFactory.create_adapter("plesk", config)
        assert isinstance(plesk_adapter, PleskAdapter)
        assert plesk_adapter.platform_type == "plesk"
    
    @pytest.mark.asyncio
    async def test_control_panel_compatibility(self):
        """Test control panel migration compatibility."""
        # Control panels should be compatible with each other
        assert PlatformAdapterFactory.validate_platform_compatibility("cpanel", "directadmin")
        assert PlatformAdapterFactory.validate_platform_compatibility("cpanel", "plesk")
        assert PlatformAdapterFactory.validate_platform_compatibility("directadmin", "plesk")
        
        # Control panels should be compatible with cloud platforms
        assert PlatformAdapterFactory.validate_platform_compatibility("cpanel", "aws")
        assert PlatformAdapterFactory.validate_platform_compatibility("plesk", "azure")
        assert PlatformAdapterFactory.validate_platform_compatibility("directadmin", "gcp")
    
    @pytest.mark.asyncio
    async def test_control_panel_migration_complexity(self):
        """Test control panel migration complexity assessment."""
        # Same control panel should be simple
        assert PlatformAdapterFactory.get_migration_complexity("cpanel", "cpanel") == "simple"
        
        # Different control panels should be moderate to complex
        complexity = PlatformAdapterFactory.get_migration_complexity("cpanel", "directadmin")
        assert complexity in ["moderate", "complex"]
        
        # Control panel to cloud should be moderate to complex
        complexity = PlatformAdapterFactory.get_migration_complexity("cpanel", "aws")
        assert complexity in ["moderate", "complex"]


class TestControlPanelDataModels:
    """Test control panel data models."""
    
    def test_hosting_account_model(self):
        """Test HostingAccount model."""
        account = HostingAccount(
            username="testuser",
            domain="example.com",
            email="admin@example.com",
            databases=["db1", "db2"],
            subdomains=["sub1.example.com"],
            email_accounts=["user@example.com"]
        )
        
        assert account.username == "testuser"
        assert account.domain == "example.com"
        assert account["username"] == "testuser"  # Dict-like access
        assert len(account.databases) == 2
    
    def test_database_info_model(self):
        """Test DatabaseInfo model."""
        db = DatabaseInfo(
            name="example_db",
            user="db_user",
            host="localhost",
            type="mysql",
            size=1024000
        )
        
        assert db.name == "example_db"
        assert db.type == "mysql"
        assert db["size"] == 1024000
    
    def test_email_account_model(self):
        """Test EmailAccount model."""
        email = EmailAccount(
            email="user@example.com",
            quota=1000000,
            usage=500000
        )
        
        assert email.email == "user@example.com"
        assert email.quota == 1000000
        assert email["usage"] == 500000
    
    def test_dns_record_model(self):
        """Test DNSRecord model."""
        dns = DNSRecord(
            name="www",
            type="A",
            value="192.168.1.1",
            ttl=3600
        )
        
        assert dns.name == "www"
        assert dns.type == "A"
        assert dns["value"] == "192.168.1.1"