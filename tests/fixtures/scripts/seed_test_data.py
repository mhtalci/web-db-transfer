#!/usr/bin/env python3
"""
Test data seeding script for the Migration Assistant.

This script generates comprehensive test data for various migration scenarios
including files, databases, and configuration data.
"""

import os
import json
import yaml
import random
import string
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any
import argparse


class TestDataGenerator:
    """Generate test data for migration testing."""
    
    def __init__(self, output_dir: str = "/data/test-files"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_text_files(self, count: int = 100, size_range: tuple = (1024, 10240)):
        """Generate text files of various sizes."""
        text_dir = self.output_dir / "text_files"
        text_dir.mkdir(exist_ok=True)
        
        print(f"Generating {count} text files...")
        
        for i in range(count):
            size = random.randint(*size_range)
            content = self._generate_random_text(size)
            
            file_path = text_dir / f"text_file_{i:03d}.txt"
            with open(file_path, "w") as f:
                f.write(content)
        
        print(f"Generated {count} text files in {text_dir}")
    
    def generate_binary_files(self, count: int = 20, size_range: tuple = (5120, 51200)):
        """Generate binary files for testing."""
        binary_dir = self.output_dir / "binary_files"
        binary_dir.mkdir(exist_ok=True)
        
        print(f"Generating {count} binary files...")
        
        for i in range(count):
            size = random.randint(*size_range)
            content = bytes([random.randint(0, 255) for _ in range(size)])
            
            file_path = binary_dir / f"binary_file_{i:03d}.bin"
            with open(file_path, "wb") as f:
                f.write(content)
        
        print(f"Generated {count} binary files in {binary_dir}")
    
    def generate_web_files(self):
        """Generate web application files (HTML, CSS, JS)."""
        web_dir = self.output_dir / "web_files"
        web_dir.mkdir(exist_ok=True)
        
        # Generate HTML files
        html_templates = [
            self._generate_html_page("Home", "Welcome to our website!"),
            self._generate_html_page("About", "Learn more about us."),
            self._generate_html_page("Contact", "Get in touch with us."),
            self._generate_html_page("Blog", "Read our latest posts."),
        ]
        
        for i, content in enumerate(html_templates):
            file_path = web_dir / f"page_{i}.html"
            with open(file_path, "w") as f:
                f.write(content)
        
        # Generate CSS files
        css_content = self._generate_css()
        with open(web_dir / "styles.css", "w") as f:
            f.write(css_content)
        
        # Generate JavaScript files
        js_content = self._generate_javascript()
        with open(web_dir / "script.js", "w") as f:
            f.write(js_content)
        
        # Generate config files
        config_data = {
            "database": {
                "host": "localhost",
                "port": 3306,
                "name": "webapp_db",
                "user": "webapp_user"
            },
            "cache": {
                "type": "redis",
                "host": "localhost",
                "port": 6379
            },
            "features": {
                "user_registration": True,
                "email_notifications": True,
                "analytics": True
            }
        }
        
        with open(web_dir / "config.json", "w") as f:
            json.dump(config_data, f, indent=2)
        
        with open(web_dir / "config.yaml", "w") as f:
            yaml.dump(config_data, f, default_flow_style=False)
        
        print(f"Generated web application files in {web_dir}")
    
    def generate_directory_structure(self):
        """Generate complex directory structure for testing."""
        structure_dir = self.output_dir / "directory_structure"
        structure_dir.mkdir(exist_ok=True)
        
        # Create nested directories
        directories = [
            "assets/images",
            "assets/css",
            "assets/js",
            "templates/pages",
            "templates/components",
            "data/uploads",
            "data/cache",
            "logs/application",
            "logs/access",
            "config/environments",
            "config/locales",
        ]
        
        for dir_path in directories:
            full_path = structure_dir / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            
            # Add some files to each directory
            for i in range(random.randint(1, 5)):
                file_name = f"file_{i}.txt"
                file_content = f"Content for {dir_path}/{file_name}"
                with open(full_path / file_name, "w") as f:
                    f.write(file_content)
        
        print(f"Generated directory structure in {structure_dir}")
    
    def generate_database_dumps(self):
        """Generate database dump files for testing."""
        db_dir = self.output_dir / "database_dumps"
        db_dir.mkdir(exist_ok=True)
        
        # Generate MySQL dump
        mysql_dump = self._generate_mysql_dump()
        with open(db_dir / "mysql_dump.sql", "w") as f:
            f.write(mysql_dump)
        
        # Generate PostgreSQL dump
        postgres_dump = self._generate_postgres_dump()
        with open(db_dir / "postgres_dump.sql", "w") as f:
            f.write(postgres_dump)
        
        # Generate MongoDB dump (JSON format)
        mongo_dump = self._generate_mongo_dump()
        with open(db_dir / "mongo_dump.json", "w") as f:
            json.dump(mongo_dump, f, indent=2, default=str)
        
        print(f"Generated database dumps in {db_dir}")
    
    def generate_migration_configs(self):
        """Generate migration configuration files for testing."""
        config_dir = self.output_dir / "migration_configs"
        config_dir.mkdir(exist_ok=True)
        
        configs = [
            self._generate_wordpress_config(),
            self._generate_static_site_config(),
            self._generate_database_only_config(),
            self._generate_cpanel_config(),
            self._generate_cloud_config(),
        ]
        
        for i, config in enumerate(configs):
            config_name = config.get("name", f"config_{i}").lower().replace(" ", "_")
            
            # Save as YAML
            with open(config_dir / f"{config_name}.yaml", "w") as f:
                yaml.dump(config, f, default_flow_style=False)
            
            # Save as JSON
            with open(config_dir / f"{config_name}.json", "w") as f:
                json.dump(config, f, indent=2)
        
        print(f"Generated migration configs in {config_dir}")
    
    def _generate_random_text(self, size: int) -> str:
        """Generate random text content."""
        words = [
            "lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing",
            "elit", "sed", "do", "eiusmod", "tempor", "incididunt", "ut", "labore",
            "et", "dolore", "magna", "aliqua", "enim", "ad", "minim", "veniam",
            "quis", "nostrud", "exercitation", "ullamco", "laboris", "nisi",
            "aliquip", "ex", "ea", "commodo", "consequat", "duis", "aute", "irure",
            "in", "reprehenderit", "voluptate", "velit", "esse", "cillum", "fugiat",
            "nulla", "pariatur", "excepteur", "sint", "occaecat", "cupidatat",
            "non", "proident", "sunt", "culpa", "qui", "officia", "deserunt",
            "mollit", "anim", "id", "est", "laborum"
        ]
        
        content = []
        current_size = 0
        
        while current_size < size:
            word = random.choice(words)
            if current_size + len(word) + 1 <= size:
                content.append(word)
                current_size += len(word) + 1
            else:
                break
        
        return " ".join(content)
    
    def _generate_html_page(self, title: str, content: str) -> str:
        """Generate HTML page content."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <header>
        <nav>
            <ul>
                <li><a href="page_0.html">Home</a></li>
                <li><a href="page_1.html">About</a></li>
                <li><a href="page_2.html">Contact</a></li>
                <li><a href="page_3.html">Blog</a></li>
            </ul>
        </nav>
    </header>
    <main>
        <h1>{title}</h1>
        <p>{content}</p>
        <p>This is a test page generated for migration testing purposes.</p>
    </main>
    <footer>
        <p>&copy; 2024 Test Website. All rights reserved.</p>
    </footer>
    <script src="script.js"></script>
</body>
</html>"""
    
    def _generate_css(self) -> str:
        """Generate CSS content."""
        return """/* Test CSS file for migration testing */
body {
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 0;
    line-height: 1.6;
    color: #333;
}

header {
    background-color: #007acc;
    color: white;
    padding: 1rem 0;
}

nav ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    justify-content: center;
}

nav li {
    margin: 0 1rem;
}

nav a {
    color: white;
    text-decoration: none;
    font-weight: bold;
}

nav a:hover {
    text-decoration: underline;
}

main {
    max-width: 800px;
    margin: 2rem auto;
    padding: 0 1rem;
}

h1 {
    color: #007acc;
    border-bottom: 2px solid #007acc;
    padding-bottom: 0.5rem;
}

footer {
    background-color: #f8f9fa;
    text-align: center;
    padding: 1rem 0;
    margin-top: 2rem;
    border-top: 1px solid #dee2e6;
}

@media (max-width: 768px) {
    nav ul {
        flex-direction: column;
        align-items: center;
    }
    
    nav li {
        margin: 0.5rem 0;
    }
}"""
    
    def _generate_javascript(self) -> str:
        """Generate JavaScript content."""
        return """// Test JavaScript file for migration testing
document.addEventListener('DOMContentLoaded', function() {
    console.log('Test website loaded successfully');
    
    // Add click tracking
    const links = document.querySelectorAll('a');
    links.forEach(link => {
        link.addEventListener('click', function(e) {
            console.log('Link clicked:', this.href);
        });
    });
    
    // Add form validation if forms exist
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            console.log('Form submitted');
            // Add validation logic here
        });
    });
    
    // Simple analytics tracking
    function trackPageView() {
        const data = {
            url: window.location.href,
            timestamp: new Date().toISOString(),
            userAgent: navigator.userAgent
        };
        console.log('Page view tracked:', data);
    }
    
    trackPageView();
});

// Utility functions
function formatDate(date) {
    return new Intl.DateTimeFormat('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    }).format(date);
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}"""
    
    def _generate_mysql_dump(self) -> str:
        """Generate MySQL dump content."""
        return """-- MySQL dump for migration testing
-- Generated on """ + datetime.now().isoformat() + """

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- Table structure for table `users`
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `email` varchar(100) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `is_active` tinyint(1) DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Dumping data for table `users`
INSERT INTO `users` VALUES 
(1,'admin','admin@example.com','$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx/L/jyG','2024-01-01 12:00:00','2024-01-01 12:00:00',1),
(2,'testuser','test@example.com','$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx/L/jyG','2024-01-01 12:00:00','2024-01-01 12:00:00',1);

-- Table structure for table `posts`
DROP TABLE IF EXISTS `posts`;
CREATE TABLE `posts` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `title` varchar(200) NOT NULL,
  `content` text,
  `slug` varchar(200) NOT NULL,
  `status` enum('draft','published','archived') DEFAULT 'draft',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `slug` (`slug`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `posts_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Dumping data for table `posts`
INSERT INTO `posts` VALUES 
(1,1,'Test Post','This is a test post for migration testing.','test-post','published','2024-01-01 12:00:00','2024-01-01 12:00:00');

SET FOREIGN_KEY_CHECKS = 1;"""
    
    def _generate_postgres_dump(self) -> str:
        """Generate PostgreSQL dump content."""
        return """-- PostgreSQL dump for migration testing
-- Generated on """ + datetime.now().isoformat() + """

SET statement_timeout = 0;
SET lock_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;

-- Table: users
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Data for table users
INSERT INTO users (username, email, password_hash) VALUES
('admin', 'admin@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx/L/jyG'),
('testuser', 'test@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx/L/jyG');

-- Table: posts
CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    content TEXT,
    slug VARCHAR(200) NOT NULL UNIQUE,
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data for table posts
INSERT INTO posts (user_id, title, content, slug, status) VALUES
(1, 'Test Post', 'This is a test post for migration testing.', 'test-post', 'published');

-- Indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_posts_user_id ON posts(user_id);
CREATE INDEX idx_posts_status ON posts(status);"""
    
    def _generate_mongo_dump(self) -> Dict[str, Any]:
        """Generate MongoDB dump content."""
        return {
            "users": [
                {
                    "_id": {"$oid": "507f1f77bcf86cd799439011"},
                    "username": "admin",
                    "email": "admin@example.com",
                    "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx/L/jyG",
                    "profile": {
                        "firstName": "Admin",
                        "lastName": "User"
                    },
                    "created_at": datetime.now(),
                    "is_active": True
                },
                {
                    "_id": {"$oid": "507f1f77bcf86cd799439012"},
                    "username": "testuser",
                    "email": "test@example.com",
                    "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx/L/jyG",
                    "profile": {
                        "firstName": "Test",
                        "lastName": "User"
                    },
                    "created_at": datetime.now(),
                    "is_active": True
                }
            ],
            "posts": [
                {
                    "_id": {"$oid": "507f1f77bcf86cd799439013"},
                    "title": "Test Post",
                    "content": "This is a test post for migration testing.",
                    "slug": "test-post",
                    "author": {
                        "username": "admin",
                        "email": "admin@example.com"
                    },
                    "status": "published",
                    "tags": ["test", "migration"],
                    "created_at": datetime.now()
                }
            ]
        }
    
    def _generate_wordpress_config(self) -> Dict[str, Any]:
        """Generate WordPress migration configuration."""
        return {
            "name": "WordPress Migration",
            "description": "Migrate WordPress site from shared hosting to cloud",
            "source": {
                "type": "wordpress",
                "host": "shared.hosting.com",
                "authentication": {
                    "type": "ssh_key",
                    "username": "wpuser",
                    "private_key_path": "/path/to/key"
                },
                "paths": {
                    "root_path": "/home/wpuser/public_html",
                    "wp_config": "/home/wpuser/public_html/wp-config.php"
                },
                "database": {
                    "type": "mysql",
                    "host": "localhost",
                    "port": 3306,
                    "database_name": "wpuser_wp",
                    "username": "wpuser",
                    "password": "wp_password"
                }
            },
            "destination": {
                "type": "aws_s3",
                "host": "s3.amazonaws.com",
                "cloud_config": {
                    "provider": "aws",
                    "region": "us-east-1",
                    "bucket": "wp-migration-bucket"
                },
                "database": {
                    "type": "aurora_mysql",
                    "host": "aurora.amazonaws.com",
                    "database_name": "wordpress_db",
                    "username": "aurora_user",
                    "password": "aurora_password"
                }
            },
            "transfer": {
                "method": "s3_sync",
                "parallel_transfers": 4,
                "compression_enabled": True
            },
            "options": {
                "maintenance_mode": True,
                "backup_before": True,
                "verify_after": True
            }
        }
    
    def _generate_static_site_config(self) -> Dict[str, Any]:
        """Generate static site migration configuration."""
        return {
            "name": "Static Site Migration",
            "description": "Migrate static HTML site to CDN",
            "source": {
                "type": "static",
                "host": "old-server.com",
                "authentication": {
                    "type": "password",
                    "username": "webuser",
                    "password": "web_password"
                },
                "paths": {
                    "root_path": "/var/www/html"
                }
            },
            "destination": {
                "type": "cloudflare_pages",
                "host": "pages.cloudflare.com",
                "cloud_config": {
                    "provider": "cloudflare",
                    "zone_id": "zone123",
                    "api_token": "cf_token"
                }
            },
            "transfer": {
                "method": "rsync",
                "compression_enabled": True,
                "exclude_patterns": ["*.log", "cache/*"]
            },
            "options": {
                "backup_before": False,
                "verify_after": True
            }
        }
    
    def _generate_database_only_config(self) -> Dict[str, Any]:
        """Generate database-only migration configuration."""
        return {
            "name": "Database Only Migration",
            "description": "Migrate database from MySQL to PostgreSQL",
            "source": {
                "type": "mysql",
                "database": {
                    "type": "mysql",
                    "host": "mysql.source.com",
                    "port": 3306,
                    "database_name": "source_db",
                    "username": "mysql_user",
                    "password": "mysql_password"
                }
            },
            "destination": {
                "type": "postgresql",
                "database": {
                    "type": "postgresql",
                    "host": "postgres.dest.com",
                    "port": 5432,
                    "database_name": "dest_db",
                    "username": "postgres_user",
                    "password": "postgres_password"
                }
            },
            "transfer": {
                "method": "direct_database",
                "batch_size": 1000
            },
            "options": {
                "convert_schema": True,
                "validate_data": True,
                "backup_before": True
            }
        }
    
    def _generate_cpanel_config(self) -> Dict[str, Any]:
        """Generate cPanel migration configuration."""
        return {
            "name": "cPanel Migration",
            "description": "Migrate from cPanel to cloud infrastructure",
            "source": {
                "type": "cpanel",
                "host": "shared.hosting.com",
                "authentication": {
                    "type": "api_key",
                    "username": "cpanel_user",
                    "api_key": "cpanel_api_token"
                },
                "control_panel_config": {
                    "type": "cpanel",
                    "port": 2083,
                    "ssl": True
                }
            },
            "destination": {
                "type": "digitalocean_droplet",
                "host": "droplet.digitalocean.com",
                "authentication": {
                    "type": "ssh_key",
                    "username": "root",
                    "private_key_path": "/path/to/do_key"
                }
            },
            "transfer": {
                "method": "ssh_scp",
                "parallel_transfers": 2
            },
            "options": {
                "preserve_email_accounts": True,
                "migrate_dns_records": True,
                "backup_before": True
            }
        }
    
    def _generate_cloud_config(self) -> Dict[str, Any]:
        """Generate cloud-to-cloud migration configuration."""
        return {
            "name": "Cloud Migration",
            "description": "Migrate from AWS to Google Cloud",
            "source": {
                "type": "aws_s3",
                "host": "s3.amazonaws.com",
                "cloud_config": {
                    "provider": "aws",
                    "region": "us-east-1",
                    "bucket": "source-bucket",
                    "access_key": "aws_access_key",
                    "secret_key": "aws_secret_key"
                }
            },
            "destination": {
                "type": "gcs",
                "host": "storage.googleapis.com",
                "cloud_config": {
                    "provider": "gcp",
                    "bucket": "dest-bucket",
                    "credentials_path": "/path/to/gcp_credentials.json"
                }
            },
            "transfer": {
                "method": "cloud_sync",
                "parallel_transfers": 8,
                "compression_enabled": False
            },
            "options": {
                "preserve_metadata": True,
                "verify_after": True
            }
        }


def main():
    """Main function to generate test data."""
    parser = argparse.ArgumentParser(description="Generate test data for migration testing")
    parser.add_argument("--output-dir", default="/data/test-files", help="Output directory for test data")
    parser.add_argument("--text-files", type=int, default=100, help="Number of text files to generate")
    parser.add_argument("--binary-files", type=int, default=20, help="Number of binary files to generate")
    parser.add_argument("--skip-web", action="store_true", help="Skip web files generation")
    parser.add_argument("--skip-db", action="store_true", help="Skip database dumps generation")
    parser.add_argument("--skip-configs", action="store_true", help="Skip migration configs generation")
    
    args = parser.parse_args()
    
    generator = TestDataGenerator(args.output_dir)
    
    print("Starting test data generation...")
    print(f"Output directory: {args.output_dir}")
    
    # Generate different types of test data
    generator.generate_text_files(args.text_files)
    generator.generate_binary_files(args.binary_files)
    
    if not args.skip_web:
        generator.generate_web_files()
    
    generator.generate_directory_structure()
    
    if not args.skip_db:
        generator.generate_database_dumps()
    
    if not args.skip_configs:
        generator.generate_migration_configs()
    
    print("Test data generation completed!")
    print(f"All files generated in: {args.output_dir}")


if __name__ == "__main__":
    main()