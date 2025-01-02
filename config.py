import json
import os
from typing import Dict, List
from rich.prompt import Confirm

DEFAULT_CONFIG = {
    "excluded_locations": {
        "development": {
            "enabled": True,
            "paths": [
                "site-packages",
                "node_modules",
                "venv",
                "env",
                ".virtualenv",
                "pip",
                "npm",
                "yarn",
                "composer",
                "gradle",
                "maven"
            ]
        },
        "plugins_extensions": {
            "enabled": True,
            "paths": [
                "plugins",
                "extensions",
                "addons",
                "modules",
                "plug-ins"
            ]
        },
        "system": {
            "enabled": True,
            "paths": [
                "System",
                "Private",
                "bin",
                "sbin",
                "usr/bin",
                "usr/sbin",
                "usr/local/bin"
            ]
        },
        "custom": {
            "enabled": True,
            "paths": []
        }
    },
    "backup_enabled": True,
    "backup_location": "~/fsPurge_Backups/",
    "first_run": True
}

class Config:
    """Configuration manager for fsPurge."""
    def __init__(self):
        self.config_dir = os.path.expanduser('~/fsPurge_Config/')
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_file = os.path.join(self.config_dir, 'config.json')
        self.load_config()

    def load_config(self):
        """Load or create configuration file."""
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)

        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = DEFAULT_CONFIG

    def save_config(self):
        """Save current configuration to file."""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)

    def first_time_setup(self, console):
        """Run first-time setup and configuration."""
        console.print("\n[cyan]First-time setup[/cyan]")
        
        # Initialize default configuration
        self.config = {
            "first_run": False,
            "excluded_patterns": [
                "*.app",
                ".DS_Store",
                ".localized",
                "Icon\r"
            ],
            "safe_directories": {
                "System": "Critical system files",
                "Library": "System library files",
                "Users": "User home directories",
                "Applications": "Core applications"
            }
        }
        
        # Ask about initial restore point
        if Confirm.ask(
            "[yellow]Would you like to create an initial system restore point?[/yellow]",
            default=True
        ):
            from .fspurge import FSPurge  # Import here to avoid circular import
            purger = FSPurge()
            purger.create_restore_point("Initial_Setup")
        
        # Save configuration
        self.save_config()
        console.print("[green]Configuration saved successfully![/green]")

    def get_excluded_patterns(self) -> List[str]:
        """Generate excluded patterns based on configuration."""
        patterns = []
        for category, details in self.config["excluded_locations"].items():
            if details["enabled"]:
                for path in details["paths"]:
                    patterns.append(f".*/{path}/.*")
        return patterns 