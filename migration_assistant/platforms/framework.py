"""
Web framework platform adapters for Django, Laravel, Rails, Spring Boot, Next.js, and other frameworks.
"""

import json
import re
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
import xml.etree.ElementTree as ET

from .base import PlatformAdapter, PlatformInfo, DependencyInfo, EnvironmentConfig
from ..models.config import SystemConfig
from ..core.exceptions import PlatformError


class FrameworkAdapter(PlatformAdapter):
    """Base adapter for web frameworks."""
    
    @property
    def platform_type(self) -> str:
        return "framework"
    
    async def get_package_info(self, path: Path) -> Dict[str, Any]:
        """Get information about installed packages/dependencies."""
        return {}
    
    async def get_build_config(self, path: Path) -> Dict[str, Any]:
        """Get build configuration information."""
        return {}


class DjangoAdapter(FrameworkAdapter):
    """Adapter for Django framework."""
    
    @property
    def platform_type(self) -> str:
        return "django"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["2.0", "2.1", "2.2", "3.0", "3.1", "3.2", "4.0", "4.1", "4.2", "5.0"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect Django project."""
        # Check for manage.py
        manage_py = path / "manage.py"
        if manage_py.exists():
            try:
                content = manage_py.read_text()
                if "django" in content.lower() and "DJANGO_SETTINGS_MODULE" in content:
                    return True
            except Exception:
                pass
        
        # Check for requirements.txt with Django
        requirements = path / "requirements.txt"
        if requirements.exists():
            try:
                content = requirements.read_text()
                if re.search(r"^django[>=<]", content, re.MULTILINE | re.IGNORECASE):
                    return True
            except Exception:
                pass
        
        # Check for pyproject.toml with Django
        pyproject = path / "pyproject.toml"
        if pyproject.exists():
            try:
                import tomli
                content = tomli.loads(pyproject.read_text())
                dependencies = content.get("project", {}).get("dependencies", [])
                if any("django" in dep.lower() for dep in dependencies):
                    return True
            except Exception:
                pass
        
        return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze Django project."""
        if not await self.detect_platform(path):
            raise PlatformError(f"Django not detected at {path}")
        
        version = await self._get_django_version(path)
        settings_info = await self._analyze_django_settings(path)
        package_info = await self.get_package_info(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=version,
            framework="django",
            database_type=settings_info.get("database_type", "sqlite"),
            dependencies=list(package_info.keys()) if package_info else ["django"],
            config_files=["settings.py", "requirements.txt", "manage.py"],
            environment_variables=settings_info.get("env_vars", {})
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get Django dependencies."""
        return [
            DependencyInfo(
                name="python",
                version=">=3.8",
                required=True,
                install_command="apt-get install python3"
            ),
            DependencyInfo(
                name="pip",
                required=True,
                install_command="apt-get install python3-pip"
            ),
            DependencyInfo(
                name="django",
                required=True,
                install_command="pip install django"
            ),
            DependencyInfo(
                name="gunicorn",
                required=False,
                install_command="pip install gunicorn"
            ),
            DependencyInfo(
                name="nginx",
                required=False,
                install_command="apt-get install nginx"
            )
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract Django environment configuration."""
        env_files = []
        env_vars = {}
        
        # Check for .env files
        for env_file in [".env", ".env.local", ".env.production"]:
            env_path = path / env_file
            if env_path.exists():
                env_files.append(env_file)
                env_vars.update(self._extract_environment_variables(env_path.read_text()))
        
        # Check settings.py for environment variables
        settings_info = await self._analyze_django_settings(path)
        env_vars.update(settings_info.get("env_vars", {}))
        
        secrets = ["SECRET_KEY", "DATABASE_PASSWORD", "EMAIL_PASSWORD", "AWS_SECRET_ACCESS_KEY"]
        
        return EnvironmentConfig(
            variables=env_vars,
            files=env_files + ["settings.py"],
            secrets=secrets
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare Django migration."""
        platform_info = await self.analyze_platform(source_path)
        settings_info = await self._analyze_django_settings(source_path)
        package_info = await self.get_package_info(source_path)
        
        migration_steps = [
            "install_dependencies",
            "copy_project_files",
            "setup_virtual_environment",
            "run_migrations",
            "collect_static_files",
            "setup_web_server"
        ]
        
        return {
            "platform_info": platform_info.dict(),
            "settings_info": settings_info,
            "package_info": package_info,
            "migration_steps": migration_steps,
            "files_to_copy": [
                "manage.py",
                "requirements.txt",
                "pyproject.toml",
                "*.py",
                "static/",
                "media/",
                "templates/"
            ]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform Django post-migration setup."""
        try:
            # Install dependencies
            await self._install_django_dependencies(destination_path)
            
            # Run Django migrations
            await self._run_django_migrations(destination_path)
            
            # Collect static files
            await self._collect_static_files(destination_path)
            
            # Update settings for production
            await self._update_django_settings(destination_path, migration_info)
            
            return True
        except Exception as e:
            self.logger.error(f"Django post-migration setup failed: {e}")
            return False
    
    async def get_package_info(self, path: Path) -> Dict[str, Any]:
        """Get Django package information."""
        packages = {}
        
        # Check requirements.txt
        requirements = path / "requirements.txt"
        if requirements.exists():
            try:
                content = requirements.read_text()
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if "==" in line:
                            name, version = line.split("==", 1)
                            packages[name.strip()] = version.strip()
                        else:
                            packages[line] = "latest"
            except Exception:
                pass
        
        # Check pyproject.toml
        pyproject = path / "pyproject.toml"
        if pyproject.exists():
            try:
                import tomli
                content = tomli.loads(pyproject.read_text())
                dependencies = content.get("project", {}).get("dependencies", [])
                for dep in dependencies:
                    if ">=" in dep:
                        name, version = dep.split(">=", 1)
                        packages[name.strip()] = f">={version.strip()}"
                    elif "==" in dep:
                        name, version = dep.split("==", 1)
                        packages[name.strip()] = version.strip()
                    else:
                        packages[dep.strip()] = "latest"
            except Exception:
                pass
        
        return packages
    
    async def _get_django_version(self, path: Path) -> Optional[str]:
        """Get Django version from project."""
        # Try requirements.txt first
        requirements = path / "requirements.txt"
        if requirements.exists():
            try:
                content = requirements.read_text()
                match = re.search(r"^django==([^\s]+)", content, re.MULTILINE | re.IGNORECASE)
                if match:
                    return match.group(1)
            except Exception:
                pass
        
        # Try pyproject.toml
        pyproject = path / "pyproject.toml"
        if pyproject.exists():
            try:
                import tomli
                content = tomli.loads(pyproject.read_text())
                dependencies = content.get("project", {}).get("dependencies", [])
                for dep in dependencies:
                    if dep.lower().startswith("django"):
                        match = re.search(r"django[>=<]+([^\s,]+)", dep, re.IGNORECASE)
                        if match:
                            return match.group(1)
            except Exception:
                pass
        
        return None
    
    async def _analyze_django_settings(self, path: Path) -> Dict[str, Any]:
        """Analyze Django settings files."""
        settings_info = {
            "database_type": "sqlite",
            "env_vars": {},
            "installed_apps": [],
            "middleware": []
        }
        
        # Find settings files
        settings_files = []
        for settings_pattern in ["settings.py", "*/settings.py", "*/settings/*.py"]:
            settings_files.extend(path.glob(settings_pattern))
        
        for settings_file in settings_files:
            try:
                content = settings_file.read_text()
                
                # Extract database configuration
                if "DATABASES" in content:
                    db_match = re.search(r"'ENGINE':\s*'[^']*\.(\w+)'", content)
                    if db_match:
                        engine = db_match.group(1).lower()
                        if "postgresql" in engine:
                            settings_info["database_type"] = "postgresql"
                        elif "mysql" in engine:
                            settings_info["database_type"] = "mysql"
                        elif "sqlite" in engine:
                            settings_info["database_type"] = "sqlite"
                
                # Extract environment variables usage
                env_vars = re.findall(r"os\.environ\.get\(['\"]([^'\"]+)['\"]", content)
                for var in env_vars:
                    settings_info["env_vars"][var] = ""
                
                # Extract installed apps
                apps_match = re.search(r"INSTALLED_APPS\s*=\s*\[(.*?)\]", content, re.DOTALL)
                if apps_match:
                    apps_content = apps_match.group(1)
                    apps = re.findall(r"['\"]([^'\"]+)['\"]", apps_content)
                    settings_info["installed_apps"].extend(apps)
                
                break  # Use first settings file found
                
            except Exception:
                continue
        
        return settings_info
    
    async def _install_django_dependencies(self, path: Path) -> None:
        """Install Django dependencies."""
        import subprocess
        
        # Create virtual environment
        venv_path = path / "venv"
        if not venv_path.exists():
            subprocess.run(["python3", "-m", "venv", str(venv_path)], cwd=path)
        
        # Install requirements
        pip_path = venv_path / "bin" / "pip"
        requirements = path / "requirements.txt"
        if requirements.exists():
            subprocess.run([str(pip_path), "install", "-r", "requirements.txt"], cwd=path)
    
    async def _run_django_migrations(self, path: Path) -> None:
        """Run Django database migrations."""
        import subprocess
        
        manage_py = path / "manage.py"
        if manage_py.exists():
            python_path = path / "venv" / "bin" / "python"
            subprocess.run([str(python_path), "manage.py", "migrate"], cwd=path)
    
    async def _collect_static_files(self, path: Path) -> None:
        """Collect Django static files."""
        import subprocess
        
        manage_py = path / "manage.py"
        if manage_py.exists():
            python_path = path / "venv" / "bin" / "python"
            subprocess.run([str(python_path), "manage.py", "collectstatic", "--noinput"], cwd=path)
    
    async def _update_django_settings(self, path: Path, migration_info: Dict[str, Any]) -> None:
        """Update Django settings for production."""
        # This would update settings.py with production configurations
        # such as database settings, static files, security settings, etc.
        pass


class LaravelAdapter(FrameworkAdapter):
    """Adapter for Laravel framework."""
    
    @property
    def platform_type(self) -> str:
        return "laravel"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["6.0", "7.0", "8.0", "9.0", "10.0", "11.0"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect Laravel project."""
        # Check for artisan command
        artisan = path / "artisan"
        if artisan.exists():
            try:
                content = artisan.read_text()
                if "laravel" in content.lower():
                    return True
            except Exception:
                pass
        
        # Check for composer.json with Laravel
        composer_json = path / "composer.json"
        if composer_json.exists():
            try:
                content = json.loads(composer_json.read_text())
                require = content.get("require", {})
                if "laravel/framework" in require:
                    return True
            except Exception:
                pass
        
        return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze Laravel project."""
        if not await self.detect_platform(path):
            raise PlatformError(f"Laravel not detected at {path}")
        
        version = await self._get_laravel_version(path)
        env_config = await self._analyze_laravel_env(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=version,
            framework="laravel",
            database_type=env_config.get("DB_CONNECTION", "mysql"),
            dependencies=["php", "composer", "mysql"],
            config_files=[".env", "composer.json", "artisan"],
            environment_variables=env_config
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get Laravel dependencies."""
        return [
            DependencyInfo(name="php", version=">=8.0", required=True),
            DependencyInfo(name="composer", required=True),
            DependencyInfo(name="mysql", required=False),
            DependencyInfo(name="nginx", required=False)
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract Laravel environment configuration."""
        env_vars = await self._analyze_laravel_env(path)
        
        return EnvironmentConfig(
            variables=env_vars,
            files=[".env", ".env.example"],
            secrets=["APP_KEY", "DB_PASSWORD", "MAIL_PASSWORD"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare Laravel migration."""
        platform_info = await self.analyze_platform(source_path)
        
        return {
            "platform_info": platform_info.dict(),
            "migration_steps": ["install_dependencies", "copy_files", "run_migrations"],
            "files_to_copy": ["app/", "config/", "database/", "resources/", "routes/", "public/"]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform Laravel post-migration setup."""
        try:
            await self._install_laravel_dependencies(destination_path)
            await self._run_laravel_migrations(destination_path)
            return True
        except Exception as e:
            self.logger.error(f"Laravel post-migration setup failed: {e}")
            return False
    
    async def _get_laravel_version(self, path: Path) -> Optional[str]:
        """Get Laravel version."""
        composer_json = path / "composer.json"
        if composer_json.exists():
            try:
                content = json.loads(composer_json.read_text())
                laravel_version = content.get("require", {}).get("laravel/framework")
                if laravel_version:
                    return laravel_version.strip("^~")
            except Exception:
                pass
        return None
    
    async def _analyze_laravel_env(self, path: Path) -> Dict[str, str]:
        """Analyze Laravel .env file."""
        env_file = path / ".env"
        if not env_file.exists():
            return {}
        
        try:
            content = env_file.read_text()
            return self._extract_environment_variables(content)
        except Exception:
            return {}
    
    async def _install_laravel_dependencies(self, path: Path) -> None:
        """Install Laravel dependencies."""
        import subprocess
        subprocess.run(["composer", "install"], cwd=path)
    
    async def _run_laravel_migrations(self, path: Path) -> None:
        """Run Laravel database migrations."""
        import subprocess
        subprocess.run(["php", "artisan", "migrate"], cwd=path)


class RailsAdapter(FrameworkAdapter):
    """Adapter for Ruby on Rails framework."""
    
    @property
    def platform_type(self) -> str:
        return "rails"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["5.0", "5.1", "5.2", "6.0", "6.1", "7.0", "7.1"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect Rails application."""
        # Check for Gemfile with Rails
        gemfile = path / "Gemfile"
        if gemfile.exists():
            try:
                content = gemfile.read_text()
                if re.search(r"gem\s+['\"]rails['\"]", content):
                    return True
            except Exception:
                pass
        
        # Check for config/application.rb
        app_config = path / "config" / "application.rb"
        if app_config.exists():
            try:
                content = app_config.read_text()
                if "Rails::Application" in content:
                    return True
            except Exception:
                pass
        
        return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze Rails application."""
        if not await self.detect_platform(path):
            raise PlatformError(f"Rails not detected at {path}")
        
        version = await self._get_rails_version(path)
        db_config = await self._analyze_rails_database_config(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=version,
            framework="rails",
            database_type=db_config.get("adapter", "sqlite3"),
            dependencies=["ruby", "bundler", "rails"],
            config_files=["Gemfile", "config/database.yml", "config/application.rb"],
            environment_variables={}
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get Rails dependencies."""
        return [
            DependencyInfo(name="ruby", version=">=2.7", required=True),
            DependencyInfo(name="bundler", required=True),
            DependencyInfo(name="rails", required=True),
            DependencyInfo(name="sqlite3", required=False),
            DependencyInfo(name="postgresql", required=False)
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract Rails environment configuration."""
        return EnvironmentConfig(
            variables={},
            files=["config/database.yml", "config/secrets.yml", ".env"],
            secrets=["secret_key_base", "database_password"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare Rails migration."""
        platform_info = await self.analyze_platform(source_path)
        
        return {
            "platform_info": platform_info.dict(),
            "migration_steps": ["install_dependencies", "copy_files", "run_migrations"],
            "files_to_copy": ["app/", "config/", "db/", "public/", "Gemfile"]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform Rails post-migration setup."""
        try:
            await self._install_rails_dependencies(destination_path)
            await self._run_rails_migrations(destination_path)
            return True
        except Exception as e:
            self.logger.error(f"Rails post-migration setup failed: {e}")
            return False
    
    async def _get_rails_version(self, path: Path) -> Optional[str]:
        """Get Rails version."""
        gemfile = path / "Gemfile"
        if gemfile.exists():
            try:
                content = gemfile.read_text()
                match = re.search(r"gem\s+['\"]rails['\"]\s*,\s*['\"]([^'\"]+)['\"]", content)
                if match:
                    return match.group(1)
            except Exception:
                pass
        return None
    
    async def _analyze_rails_database_config(self, path: Path) -> Dict[str, Any]:
        """Analyze Rails database configuration."""
        db_config_file = path / "config" / "database.yml"
        if not db_config_file.exists():
            return {}
        
        try:
            content = yaml.safe_load(db_config_file.read_text())
            production_config = content.get("production", {})
            return production_config
        except Exception:
            return {}
    
    async def _install_rails_dependencies(self, path: Path) -> None:
        """Install Rails dependencies."""
        import subprocess
        subprocess.run(["bundle", "install"], cwd=path)
    
    async def _run_rails_migrations(self, path: Path) -> None:
        """Run Rails database migrations."""
        import subprocess
        subprocess.run(["rails", "db:migrate"], cwd=path)


class SpringBootAdapter(FrameworkAdapter):
    """Adapter for Spring Boot framework."""
    
    @property
    def platform_type(self) -> str:
        return "springboot"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["2.0", "2.1", "2.2", "2.3", "2.4", "2.5", "2.6", "2.7", "3.0", "3.1", "3.2"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect Spring Boot application."""
        # Check for pom.xml with Spring Boot
        pom_xml = path / "pom.xml"
        if pom_xml.exists():
            try:
                content = pom_xml.read_text()
                if "spring-boot" in content:
                    return True
            except Exception:
                pass
        
        # Check for build.gradle with Spring Boot
        build_gradle = path / "build.gradle"
        if build_gradle.exists():
            try:
                content = build_gradle.read_text()
                if "spring-boot" in content:
                    return True
            except Exception:
                pass
        
        return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze Spring Boot application."""
        if not await self.detect_platform(path):
            raise PlatformError(f"Spring Boot not detected at {path}")
        
        version = await self._get_springboot_version(path)
        app_config = await self._analyze_application_properties(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=version,
            framework="springboot",
            database_type=app_config.get("database_type", "h2"),
            dependencies=["java", "maven"],
            config_files=["pom.xml", "application.properties", "application.yml"],
            environment_variables=app_config.get("env_vars", {})
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get Spring Boot dependencies."""
        return [
            DependencyInfo(name="java", version=">=11", required=True),
            DependencyInfo(name="maven", required=True),
            DependencyInfo(name="mysql", required=False),
            DependencyInfo(name="postgresql", required=False)
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract Spring Boot environment configuration."""
        app_config = await self._analyze_application_properties(path)
        
        return EnvironmentConfig(
            variables=app_config.get("env_vars", {}),
            files=["application.properties", "application.yml"],
            secrets=["spring.datasource.password", "jwt.secret"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare Spring Boot migration."""
        platform_info = await self.analyze_platform(source_path)
        
        return {
            "platform_info": platform_info.dict(),
            "migration_steps": ["install_dependencies", "copy_files", "build_application"],
            "files_to_copy": ["src/", "pom.xml", "application.properties"]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform Spring Boot post-migration setup."""
        try:
            await self._build_springboot_application(destination_path)
            return True
        except Exception as e:
            self.logger.error(f"Spring Boot post-migration setup failed: {e}")
            return False
    
    async def _get_springboot_version(self, path: Path) -> Optional[str]:
        """Get Spring Boot version."""
        pom_xml = path / "pom.xml"
        if pom_xml.exists():
            try:
                tree = ET.parse(pom_xml)
                root = tree.getroot()
                
                # Look for Spring Boot parent version
                parent = root.find(".//{http://maven.apache.org/POM/4.0.0}parent")
                if parent is not None:
                    artifact_id = parent.find(".//{http://maven.apache.org/POM/4.0.0}artifactId")
                    if artifact_id is not None and "spring-boot" in artifact_id.text:
                        version = parent.find(".//{http://maven.apache.org/POM/4.0.0}version")
                        if version is not None:
                            return version.text
            except Exception:
                pass
        
        return None
    
    async def _analyze_application_properties(self, path: Path) -> Dict[str, Any]:
        """Analyze Spring Boot application properties."""
        config = {"env_vars": {}, "database_type": "h2"}
        
        # Check application.properties
        props_file = path / "src" / "main" / "resources" / "application.properties"
        if props_file.exists():
            try:
                content = props_file.read_text()
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        config["env_vars"][key.strip()] = value.strip()
                        
                        # Detect database type
                        if "spring.datasource.url" in key:
                            if "mysql" in value:
                                config["database_type"] = "mysql"
                            elif "postgresql" in value:
                                config["database_type"] = "postgresql"
                            elif "oracle" in value:
                                config["database_type"] = "oracle"
            except Exception:
                pass
        
        # Check application.yml
        yml_file = path / "src" / "main" / "resources" / "application.yml"
        if yml_file.exists():
            try:
                content = yaml.safe_load(yml_file.read_text())
                if isinstance(content, dict):
                    # Flatten YAML structure for environment variables
                    def flatten_dict(d, parent_key="", sep="."):
                        items = []
                        for k, v in d.items():
                            new_key = f"{parent_key}{sep}{k}" if parent_key else k
                            if isinstance(v, dict):
                                items.extend(flatten_dict(v, new_key, sep=sep).items())
                            else:
                                items.append((new_key, v))
                        return dict(items)
                    
                    flattened = flatten_dict(content)
                    config["env_vars"].update({k: str(v) for k, v in flattened.items()})
                    
                    # Detect database type from YAML
                    datasource_url = flattened.get("spring.datasource.url", "")
                    if "mysql" in datasource_url:
                        config["database_type"] = "mysql"
                    elif "postgresql" in datasource_url:
                        config["database_type"] = "postgresql"
            except Exception:
                pass
        
        return config
    
    async def _build_springboot_application(self, path: Path) -> None:
        """Build Spring Boot application."""
        import subprocess
        
        if (path / "pom.xml").exists():
            subprocess.run(["mvn", "clean", "package"], cwd=path)
        elif (path / "build.gradle").exists():
            subprocess.run(["./gradlew", "build"], cwd=path)


class NextJSAdapter(FrameworkAdapter):
    """Adapter for Next.js framework."""
    
    @property
    def platform_type(self) -> str:
        return "nextjs"
    
    @property
    def supported_versions(self) -> List[str]:
        return ["12.0", "12.1", "12.2", "12.3", "13.0", "13.1", "13.2", "13.3", "13.4", "13.5", 
                "14.0", "14.1", "14.2"]
    
    async def detect_platform(self, path: Path) -> bool:
        """Detect Next.js application."""
        package_json = path / "package.json"
        if not package_json.exists():
            return False
        
        try:
            content = json.loads(package_json.read_text())
            dependencies = {**content.get("dependencies", {}), **content.get("devDependencies", {})}
            return "next" in dependencies
        except Exception:
            return False
    
    async def analyze_platform(self, path: Path) -> PlatformInfo:
        """Analyze Next.js application."""
        if not await self.detect_platform(path):
            raise PlatformError(f"Next.js not detected at {path}")
        
        version = await self._get_nextjs_version(path)
        package_info = await self.get_package_info(path)
        env_config = await self._analyze_nextjs_env(path)
        
        return PlatformInfo(
            platform_type=self.platform_type,
            version=version,
            framework="nextjs",
            database_type=None,  # Next.js doesn't have a built-in database
            dependencies=list(package_info.keys()) if package_info else ["next", "react"],
            config_files=["package.json", "next.config.js", ".env.local"],
            environment_variables=env_config
        )
    
    async def get_dependencies(self) -> List[DependencyInfo]:
        """Get Next.js dependencies."""
        return [
            DependencyInfo(name="node", version=">=16", required=True),
            DependencyInfo(name="npm", required=True),
            DependencyInfo(name="next", required=True),
            DependencyInfo(name="react", required=True)
        ]
    
    async def get_environment_config(self, path: Path) -> EnvironmentConfig:
        """Extract Next.js environment configuration."""
        env_vars = await self._analyze_nextjs_env(path)
        
        env_files = []
        for env_file in [".env", ".env.local", ".env.production", ".env.development"]:
            if (path / env_file).exists():
                env_files.append(env_file)
        
        return EnvironmentConfig(
            variables=env_vars,
            files=env_files + ["next.config.js"],
            secrets=["NEXTAUTH_SECRET", "DATABASE_URL", "API_SECRET"]
        )
    
    async def prepare_migration(self, source_path: Path, destination_path: Path) -> Dict[str, Any]:
        """Prepare Next.js migration."""
        platform_info = await self.analyze_platform(source_path)
        package_info = await self.get_package_info(source_path)
        
        return {
            "platform_info": platform_info.dict(),
            "package_info": package_info,
            "migration_steps": ["install_dependencies", "copy_files", "build_application"],
            "files_to_copy": ["pages/", "components/", "public/", "styles/", "package.json", "next.config.js"]
        }
    
    async def post_migration_setup(self, destination_path: Path, migration_info: Dict[str, Any]) -> bool:
        """Perform Next.js post-migration setup."""
        try:
            await self._install_nextjs_dependencies(destination_path)
            await self._build_nextjs_application(destination_path)
            return True
        except Exception as e:
            self.logger.error(f"Next.js post-migration setup failed: {e}")
            return False
    
    async def get_package_info(self, path: Path) -> Dict[str, Any]:
        """Get Next.js package information."""
        package_json = path / "package.json"
        if not package_json.exists():
            return {}
        
        try:
            content = json.loads(package_json.read_text())
            dependencies = {**content.get("dependencies", {}), **content.get("devDependencies", {})}
            return dependencies
        except Exception:
            return {}
    
    async def _get_nextjs_version(self, path: Path) -> Optional[str]:
        """Get Next.js version."""
        package_json = path / "package.json"
        if package_json.exists():
            try:
                content = json.loads(package_json.read_text())
                dependencies = {**content.get("dependencies", {}), **content.get("devDependencies", {})}
                return dependencies.get("next", "").strip("^~")
            except Exception:
                pass
        return None
    
    async def _analyze_nextjs_env(self, path: Path) -> Dict[str, str]:
        """Analyze Next.js environment files."""
        env_vars = {}
        
        for env_file in [".env", ".env.local", ".env.production", ".env.development"]:
            env_path = path / env_file
            if env_path.exists():
                try:
                    content = env_path.read_text()
                    env_vars.update(self._extract_environment_variables(content))
                except Exception:
                    continue
        
        return env_vars
    
    async def _install_nextjs_dependencies(self, path: Path) -> None:
        """Install Next.js dependencies."""
        import subprocess
        subprocess.run(["npm", "install"], cwd=path)
    
    async def _build_nextjs_application(self, path: Path) -> None:
        """Build Next.js application."""
        import subprocess
        subprocess.run(["npm", "run", "build"], cwd=path)