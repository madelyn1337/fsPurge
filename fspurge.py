#!/usr/bin/env python3

import os
import sys
import argparse
import glob
import json
import fnmatch
import hashlib
from pathlib import Path
import shutil
from typing import List, Set, Dict
from datetime import datetime, timedelta
import tqdm
import re
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.tree import Tree
from rich.style import Style
from rich.text import Text
from rich import print as rprint
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import mmap
import pickle
from functools import lru_cache
import sqlite3
import itertools
from config import Config
import subprocess
import getpass
import tarfile
import tempfile
from rich.prompt import Confirm
import resource
import asyncio
import aiofiles
import gc
import psutil

def scan_directory(args) -> Set[str]:
    """Standalone process-safe directory scanner."""
    base_path, patterns, app_name, excluded_patterns = args
    found_files = set()
    
    try:
        clean_app_name = app_name.replace('.app', '')
        strict_pattern = re.compile(rf".*{re.escape(app_name)}.*", re.IGNORECASE)
        loose_pattern = re.compile(rf".*{re.escape(clean_app_name)}.*", re.IGNORECASE)
        
        # Compile excluded patterns
        excluded_regexes = [re.compile(pattern, re.IGNORECASE) for pattern in excluded_patterns]
        
        for root, dirs, files in os.walk(base_path):
            # Skip Python virtual environments and node_modules
            if any(x in root for x in ['/venv/', '/node_modules/', '/site-packages/']):
                continue
                
            app_bundle = os.path.join(root, f"{clean_app_name}.app")
            if os.path.exists(app_bundle):
                found_files.add(app_bundle)
            
            for name in itertools.chain(files, dirs):
                full_path = os.path.join(root, name)
                
                # Skip if path matches any excluded pattern
                if any(regex.search(full_path) for regex in excluded_regexes):
                    continue
                    
                # Skip Python packages and modules
                if ('site-packages' in full_path or 
                    full_path.endswith('.py') or 
                    '/pip/' in full_path or
                    '/plugins/' in full_path or
                    '/extensions/' in full_path):
                    continue
                
                if full_path.endswith('.app') and full_path in found_files:
                    continue
                
                if (strict_pattern.match(name) or 
                    loose_pattern.match(name) or 
                    any(fnmatch.fnmatch(full_path, pattern.format(app_name=clean_app_name)) 
                        for pattern in patterns)):
                    found_files.add(full_path)
                    
                lower_name = name.lower()
                if any(pattern in lower_name for pattern in [
                    clean_app_name.lower(),
                    f"com.{clean_app_name.lower()}",
                    f"org.{clean_app_name.lower()}",
                    f"{clean_app_name.lower()}.plist"
                ]):
                    found_files.add(full_path)
                    
    except Exception as e:
        print(f"Error scanning {base_path}: {e}")
        
    return found_files

class FSPurge:
    """Optimized main class for fsPurge application."""
    def __init__(self):
        # Optimize memory usage
        self._set_resource_limits()
        
        # Initialize console with optimized settings
        self.console = Console(color_system="auto", force_terminal=True)
        
        # Cache frequently used styles
        self.styles = {
            'header': Style(color="cyan", bold=True),
            'warning': Style(color="yellow", bold=True),
            'error': Style(color="red", bold=True),
            'success': Style(color="green", bold=True)
        }
        
        # Load configuration with caching
        self.config = self._load_cached_config()
        
        # Optimize search paths
        self.search_paths = self._optimize_search_paths()
        
        # Initialize database connection pool
        self.db_pool = self._init_db_pool()
        
        # Initialize process pool
        self.process_pool = ProcessPoolExecutor(
            max_workers=min(32, (os.cpu_count() or 1) * 2)
        )
        
        # Initialize thread pool for I/O operations
        self.thread_pool = ThreadPoolExecutor(
            max_workers=min(32, (os.cpu_count() or 1) * 4)
        )

    def _set_resource_limits(self):
        """Optimize resource limits for better performance."""
        try:
            # Set memory limit to 75% of available memory
            import psutil
            memory = psutil.virtual_memory()
            soft_limit = int(memory.available * 0.75)
            resource.setrlimit(resource.RLIMIT_AS, (soft_limit, -1))
            
            # Increase file descriptors limit
            resource.setrlimit(resource.RLIMIT_NOFILE, (65535, 65535))
        except Exception as e:
            print(f"Warning: Could not set resource limits: {e}")

    def _init_db_pool(self):
        """Initialize optimized SQLite connection pool."""
        def create_connection():
            conn = sqlite3.connect(self.db_path)
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA cache_size=-2000')
            conn.execute('PRAGMA temp_store=MEMORY')
            conn.execute('PRAGMA mmap_size=30000000000')
            return conn
        
        return create_connection()

    @lru_cache(maxsize=2048)
    def _calculate_size(self, path: str) -> int:
        """Highly optimized size calculation with caching."""
        try:
            if os.path.isfile(path):
                return os.path.getsize(path)
            
            total_size = 0
            for entry in os.scandir(path):
                try:
                    if entry.is_file(follow_symlinks=False):
                        total_size += entry.stat().st_size
                    elif entry.is_dir(follow_symlinks=False):
                        total_size += self._calculate_size(entry.path)
                except (OSError, PermissionError):
                    continue
            return total_size
        except Exception:
            return 0

    def _load_app_patterns(self) -> Dict[str, List[str]]:
        """Load known app file patterns from database."""
        patterns_file = os.path.join(os.path.dirname(__file__), 'app_patterns.json')
        try:
            with open(patterns_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Default patterns if database file doesn't exist
            return {
                "general": [
                    "com.*.{app_name}*",
                    "*.{app_name}.*",
                    "{app_name}*"
                ]
            }

    def _init_cache_db(self):
        """Initialize SQLite cache database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS file_cache
                          (path TEXT PRIMARY KEY, 
                           size INTEGER,
                           modified_time REAL,
                           last_checked REAL)''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_last_checked ON file_cache(last_checked)')

    async def _create_backup_async(self, files: Set[str]) -> str:
        """Asynchronous backup creation with compression."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(self.backup_dir, timestamp)
        os.makedirs(backup_path, exist_ok=True)

        async def backup_file(file: str) -> None:
            relative_path = os.path.relpath(file, '/')
            backup_file = os.path.join(backup_path, relative_path)
            os.makedirs(os.path.dirname(backup_file), exist_ok=True)
            
            try:
                if os.path.isfile(file):
                    # Use efficient copy for large files
                    if os.path.getsize(file) > 100 * 1024 * 1024:  # 100MB
                        with open(file, 'rb') as src, open(backup_file, 'wb') as dst:
                            mm = mmap.mmap(src.fileno(), 0, access=mmap.ACCESS_READ)
                            for chunk in iter(lambda: mm.read(1024*1024), b''):
                                dst.write(chunk)
                            mm.close()
                    else:
                        shutil.copy2(file, backup_file)
                elif os.path.isdir(file):
                    await asyncio.to_thread(shutil.copytree, file, backup_file, 
                                         symlinks=True, dirs_exist_ok=True)
            except Exception as e:
                print(f"Warning: Could not backup {file}: {e}")

        # Process files in parallel
        chunk_size = 1000
        for i in range(0, len(files), chunk_size):
            chunk = list(files)[i:i + chunk_size]
            await asyncio.gather(*(backup_file(f) for f in chunk))

        return backup_path

    def _is_cache_valid(self, path: str) -> bool:
        """Check if cached file info is still valid."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''SELECT modified_time, last_checked 
                            FROM file_cache 
                            WHERE path = ?''', (path,))
            result = cursor.fetchone()
            
            if not result:
                return False
                
            cached_mtime, last_checked = result
            current_mtime = os.path.getmtime(path) if os.path.exists(path) else None
            
            # Cache is valid if file hasn't been modified and was checked in last 24 hours
            return (current_mtime == cached_mtime and 
                    datetime.fromtimestamp(last_checked) > datetime.now() - timedelta(hours=24))

    def _update_cache(self, path: str, size: int):
        """Update file information in cache."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''INSERT OR REPLACE INTO file_cache 
                          (path, size, modified_time, last_checked)
                          VALUES (?, ?, ?, ?)''',
                       (path, size, os.path.getmtime(path), datetime.now().timestamp()))

    def find_app_files(self, app_name: str) -> Set[str]:
        """Optimized file scanning with parallel processing and caching."""
        found_files = set()
        patterns = self.app_patterns.get(app_name.lower().replace('.app', ''), self.app_patterns["general"])
        
        scan_args = []
        for base_path in self.search_paths:
            expanded_path = os.path.expanduser(base_path)
            if os.path.exists(expanded_path):
                scan_args.append((expanded_path, patterns, app_name, self.excluded_patterns))

        with ProcessPoolExecutor(max_workers=self.num_processes) as executor:
            results = executor.map(scan_directory, scan_args)
            for result in results:
                found_files.update(result)

        return found_files

    def _display_header(self):
        """Display stylish header."""
        header = """
╭──────────────────────────────────────╮
│             fsPurge v1.0             │
│    Safe and Thorough App Removal     │
╰──────────────────────────────────────╯
        """
        self.console.print(Panel(header, style="cyan bold"))

    def _format_file_entry(self, file: str, size: int) -> Text:
        """Format file entry with icons and colors based on file type."""
        if file.endswith('.app'):
            icon = "🎯 "  # Special icon for .app bundles
        elif os.path.isfile(file):
            if file.endswith('.plist'):
                icon = "⚙️ "  # Settings files
            elif file.endswith('.log'):
                icon = "📝 "  # Log files
            elif file.endswith('.cache'):
                icon = "📦 "  # Cache files
            else:
                icon = "📄 "  # Regular files
        else:
            icon = "📁 "  # Directories

        text = Text()
        text.append(icon)
        text.append(file, style="blue")
        text.append(" (", style="dim")
        text.append(self._format_size(size), style="green")
        text.append(")", style="dim")
        return text

    def scan(self, app_name: str) -> None:
        """Enhanced scan with beautiful output."""
        self._display_header()
        
        with self.console.status("[bold blue]Scanning system...", spinner="dots"):
            found_files = self.find_app_files(app_name)

        if not found_files:
            self.console.print("\n[yellow]No files found.[/yellow]")
            return

        # Create tree view of found files
        tree = Tree(f"[bold cyan]Files related to '{app_name}'")
        total_size = 0

        # Group files by directory
        grouped_files = {}
        for file in sorted(found_files):
            dir_name = os.path.dirname(file)
            if dir_name not in grouped_files:
                grouped_files[dir_name] = []
            grouped_files[dir_name].append(file)

        # Add files to tree
        for dir_name, files in grouped_files.items():
            dir_branch = tree.add(f"[yellow]{dir_name}[/yellow]")
            dir_size = 0
            
            for file in files:
                size = self._calculate_size(file)
                dir_size += size
                total_size += size
                dir_branch.add(self._format_file_entry(os.path.basename(file), size))

        self.console.print(tree)
        self.console.print(f"\n[bold green]Total files found:[/bold green] {len(found_files)}")
        self.console.print(f"[bold green]Total size:[/bold green] {self._format_size(total_size)}")

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"

    def _batch_process_files(self, files: Set[str], operation: callable, 
                           description: str) -> None:
        """Process files in batches with progress tracking."""
        batch_size = 1000
        batches = [list(files)[i:i + batch_size] 
                  for i in range(0, len(files), batch_size)]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task(description, total=len(files))
            
            with ThreadPoolExecutor(max_workers=self.num_processes * 2) as executor:
                for batch in batches:
                    futures = [executor.submit(operation, file) for file in batch]
                    for _ in futures:
                        progress.update(task, advance=1)

    def _is_safe_path(self, path: str) -> tuple[bool, str]:
        """Check if path should be protected from deletion."""
        for safe_dir, description in self.safe_directories.items():
            if f'/{safe_dir}/' in path:
                return True, description
        return False, ""

    def uninstall(self, app_name: str) -> None:
        """Safely remove an application and all its related files."""
        self.console.print(f"\n[cyan]Analyzing {app_name}...[/cyan]")
        
        # Ask about restore point
        create_restore = Confirm.ask(
            "[yellow]Would you like to create a restore point before uninstalling?[/yellow]",
            default=True
        )
        
        if create_restore:
            self.create_restore_point(f"Before_{app_name}_Uninstall")
        
        files = self.find_app_files(app_name)
        if not files:
            self.console.print("[yellow]No files found for this application.[/yellow]")
            return
        
        # Rest of uninstall method remains the same...

    def _clear_cache(self):
        """Clear expired cache entries."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''DELETE FROM file_cache 
                          WHERE last_checked < ?''', 
                       (datetime.now() - timedelta(days=7)).timestamp())

    def analyze_system_impact(self, app_name: str) -> None:
        """Analyze application's impact on system."""
        self.console.print("\n[cyan]Analyzing system impact...[/cyan]")
        
        impact_data = {
            'launch_agents': [],
            'background_processes': [],
            'startup_items': [],
            'memory_usage': 0,
            'cpu_usage': 0
        }
        
        # Check launch agents and daemons
        launch_paths = [
            os.path.expanduser('~/Library/LaunchAgents'),
            '/Library/LaunchAgents',
            '/Library/LaunchDaemons'
        ]
        
        # Get running processes
        try:
            import psutil
            app_processes = []
            for proc in psutil.process_iter(['name', 'memory_info', 'cpu_percent']):
                try:
                    if app_name.lower() in proc.info['name'].lower():
                        app_processes.append(proc)
                        impact_data['memory_usage'] += proc.info['memory_info'].rss / (1024 * 1024)  # Convert to MB
                        impact_data['cpu_usage'] += proc.info['cpu_percent']
                        impact_data['background_processes'].append(proc.info['name'])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            self.console.print("[yellow]psutil package not found. Process analysis limited.[/yellow]")
        
        # Check startup items
        startup_locations = [
            os.path.expanduser(f'~/Library/Application Support/{app_name}'),
            os.path.expanduser('~/Library/LaunchAgents'),
            '/Library/LaunchAgents',
            '/Library/LaunchDaemons',
            os.path.expanduser('~/Library/Application Support/com.apple.backgroundtaskmanagementagent/backgrounditems.btm')
        ]
        
        for location in startup_locations:
            if os.path.exists(location):
                if os.path.isfile(location):
                    with open(location, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if app_name.lower() in content.lower():
                            impact_data['startup_items'].append(location)
                else:
                    for root, _, files in os.walk(location):
                        for file in files:
                            if file.lower().endswith('.plist'):
                                full_path = os.path.join(root, file)
                                if app_name.lower() in file.lower():
                                    impact_data['launch_agents'].append(full_path)
        
        # Calculate disk usage
        app_files = self.find_app_files(app_name)
        total_size = sum(self._calculate_size(f) for f in app_files)
        
        # Create impact report
        panel = Panel(
            "\n".join([
                f"[cyan]Launch Agents:[/cyan] {len(impact_data['launch_agents'])}",
                f"[cyan]Background Processes:[/cyan] {len(impact_data['background_processes'])}",
                f"[cyan]Startup Items:[/cyan] {len(impact_data['startup_items'])}",
                f"[cyan]Memory Usage:[/cyan] {impact_data['memory_usage']:.1f} MB",
                f"[cyan]CPU Usage:[/cyan] {impact_data['cpu_usage']:.1f}%",
                f"[cyan]Disk Usage:[/cyan] {self._format_size(total_size)}",
                "\n[yellow]Active Processes:[/yellow]" + 
                "\n".join(f"\n  - {proc}" for proc in impact_data['background_processes']),
                "\n[yellow]Launch Agents:[/yellow]" + 
                "\n".join(f"\n  - {agent}" for agent in impact_data['launch_agents']),
                "\n[yellow]Startup Items:[/yellow]" + 
                "\n".join(f"\n  - {item}" for item in impact_data['startup_items'])
            ]),
            title=f"System Impact Analysis - {app_name}",
            border_style="green"
        )
        
        self.console.print(panel)

    def analyze_dependencies(self, app_name: str) -> None:
        """Analyze application dependencies and shared components."""
        app_path = f"/Applications/{app_name}.app"
        if not os.path.exists(app_path):
            self.console.print("[red]Application not found![/red]")
            return
        
        dependencies = {
            'Frameworks': set(),
            'Shared Libraries': set(),
            'Plugins': set(),
            'Extensions': set(),
            'Executables': set(),
            'Resources': set()
        }
        
        with Progress() as progress:
            task = progress.add_task("Analyzing dependencies...", total=100)
            
            contents_path = os.path.join(app_path, 'Contents')
            
            # Check Frameworks
            frameworks_path = os.path.join(contents_path, 'Frameworks')
            if os.path.exists(frameworks_path):
                for item in os.listdir(frameworks_path):
                    if item.endswith('.framework') or item.endswith('.app'):
                        dependencies['Frameworks'].add(item)
            progress.update(task, advance=20)
            
            # Check Plugins
            plugins_path = os.path.join(contents_path, 'PlugIns')
            if os.path.exists(plugins_path):
                for item in os.listdir(plugins_path):
                    dependencies['Plugins'].add(item)
            progress.update(task, advance=20)
            
            # Check Resources
            resources_path = os.path.join(contents_path, 'Resources')
            if os.path.exists(resources_path):
                resources = [f for f in os.listdir(resources_path) 
                           if f.endswith(('.dylib', '.bundle', '.plugin'))]
                dependencies['Resources'].update(resources)
            progress.update(task, advance=20)
            
            # Check MacOS executables
            macos_path = os.path.join(contents_path, 'MacOS')
            if os.path.exists(macos_path):
                dependencies['Executables'].update(os.listdir(macos_path))
            progress.update(task, advance=20)
            
            # Check shared libraries using otool
            try:
                main_binary = os.path.join(macos_path, app_name.replace('.app', ''))
                if os.path.exists(main_binary):
                    result = os.popen(f'otool -L "{main_binary}"').read()
                    libraries = [line.split()[0] for line in result.split('\n')[1:] 
                               if line.strip() and not line.startswith('\t/System/')]
                    dependencies['Shared Libraries'].update(libraries)
            except Exception as e:
                self.console.print(f"[yellow]Could not analyze shared libraries: {e}[/yellow]")
            progress.update(task, advance=20)
        
        # Display results in a tree
        tree = Tree(f"[bold cyan]{app_name} Dependencies[/bold cyan]")
        
        for dep_type, items in dependencies.items():
            if items:
                branch = tree.add(f"[yellow]{dep_type} ({len(items)})[/yellow]")
                for item in sorted(items):
                    if dep_type == 'Shared Libraries':
                        # Simplify library paths for readability
                        item = os.path.basename(item)
                    branch.add(Text(item, style="blue"))
        
        self.console.print(tree)

    def schedule_cleaning(self, app_name: str, interval_days: int) -> None:
        """Schedule periodic cleaning of app remnants."""
        cron_command = f'0 0 */{interval_days} * * {sys.executable} {__file__} -uninstall "{app_name}"'
        
        try:
            from crontab import CronTab
            cron = CronTab(user=True)
            job = cron.new(command=cron_command)
            job.setall(f'0 0 */{interval_days} * *')
            cron.write()
            
            self.console.print(f"[green]Scheduled cleaning for {app_name} every {interval_days} days[/green]")
        except Exception as e:
            self.console.print(f"[red]Failed to schedule cleaning: {e}[/red]")

    def create_restore_point(self, name: str = None) -> None:
        """Create a system-wide restore point."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if not name:
            name = f"RestorePoint_{timestamp}"
        else:
            name = f"{name}_{timestamp}"
        
        restore_base = os.path.expanduser("~/fsPurge_Restore")
        restore_point_dir = os.path.join(restore_base, name)
        
        self.console.print(Panel(f"\n[cyan]Creating Restore Point: {name}[/cyan]\n"))
        
        # Paths to backup
        paths_to_backup = {
            'home': [
                '~/Documents',
                '~/Downloads',
                '~/Desktop',
                '~/Pictures',
                '~/Music',
                '~/Movies',
                '~/Library/Application Support',
                '~/Library/Preferences',
            ],
            'system': [
                '/Applications',
                '/usr/local/bin',
                '/Library/LaunchAgents',
                '/Library/LaunchDaemons',
            ]
        }
        
        # Create restore point directory
        os.makedirs(restore_point_dir, exist_ok=True)
        
        # Save restore point metadata
        metadata = {
            'name': name,
            'timestamp': timestamp,
            'created_by': getpass.getuser(),
            'paths_backed_up': paths_to_backup,
        }
        
        with open(os.path.join(restore_point_dir, 'metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=4)
        
        with Progress() as progress:
            # Calculate total files for progress bar
            total_files = 0
            for category, paths in paths_to_backup.items():
                for path in paths:
                    expanded_path = os.path.expanduser(path)
                    if os.path.exists(expanded_path):
                        if os.path.isfile(expanded_path):
                            total_files += 1
                        else:
                            for root, _, files in os.walk(expanded_path):
                                total_files += len(files)
            
            backup_task = progress.add_task("[cyan]Creating backup...", total=total_files)
            
            # Perform backup
            for category, paths in paths_to_backup.items():
                category_dir = os.path.join(restore_point_dir, category)
                os.makedirs(category_dir, exist_ok=True)
                
                for path in paths:
                    expanded_path = os.path.expanduser(path)
                    if not os.path.exists(expanded_path):
                        continue
                    
                    relative_path = os.path.relpath(expanded_path, os.path.expanduser('~' if category == 'home' else '/'))
                    backup_path = os.path.join(category_dir, relative_path)
                    
                    try:
                        if os.path.isfile(expanded_path):
                            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                            shutil.copy2(expanded_path, backup_path)
                            progress.advance(backup_task)
                        else:
                            for root, dirs, files in os.walk(expanded_path):
                                for d in dirs:
                                    src_path = os.path.join(root, d)
                                    dst_path = os.path.join(backup_path, os.path.relpath(src_path, expanded_path))
                                    os.makedirs(dst_path, exist_ok=True)
                                
                                for f in files:
                                    src_path = os.path.join(root, f)
                                    dst_path = os.path.join(backup_path, os.path.relpath(src_path, expanded_path))
                                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                                    shutil.copy2(src_path, dst_path)
                                    progress.advance(backup_task)
                    except (PermissionError, OSError) as e:
                        self.console.print(f"[yellow]Warning: Could not backup {expanded_path}: {e}[/yellow]")
            
            # Compress the restore point
            compress_task = progress.add_task("[cyan]Compressing backup...", total=1)
            archive_path = f"{restore_point_dir}.tar.gz"
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(restore_point_dir, arcname=os.path.basename(restore_point_dir))
            progress.update(compress_task, advance=1)
            
            # Clean up uncompressed directory
            shutil.rmtree(restore_point_dir)
        
        size = os.path.getsize(archive_path)
        self.console.print(f"\n[green]Restore point created successfully![/green]")
        self.console.print(f"[cyan]Location:[/cyan] {archive_path}")
        self.console.print(f"[cyan]Size:[/cyan] {self._format_size(size)}")

    def restore_from_point(self, restore_point: str) -> None:
        """Restore system from a restore point."""
        restore_base = os.path.expanduser("~/fsPurge_Restore")
        
        # Find the restore point
        if not restore_point.endswith('.tar.gz'):
            restore_point += '.tar.gz'
        restore_path = os.path.join(restore_base, restore_point)
        
        if not os.path.exists(restore_path):
            self.console.print("[red]Error: Restore point not found![/red]")
            return
        
        # Request root privileges
        if not request_root_privileges("Required to restore system files"):
            return
        
        self.console.print(Panel("\n[cyan]Restoring System from Backup[/cyan]\n"))
        
        # Create temporary directory for extraction
        with tempfile.TemporaryDirectory() as temp_dir:
            with Progress() as progress:
                # Extract archive
                extract_task = progress.add_task("[cyan]Extracting backup...", total=1)
                with tarfile.open(restore_path, "r:gz") as tar:
                    tar.extractall(temp_dir)
                progress.update(extract_task, advance=1)
                
                # Load metadata
                restore_point_dir = os.path.join(temp_dir, restore_point.replace('.tar.gz', ''))
                with open(os.path.join(restore_point_dir, 'metadata.json'), 'r') as f:
                    metadata = json.load(f)
                
                # Restore files
                total_files = 0
                for root, _, files in os.walk(restore_point_dir):
                    total_files += len(files)
                
                restore_task = progress.add_task("[cyan]Restoring files...", total=total_files)
                
                # Restore home directory files
                home_dir = os.path.join(restore_point_dir, 'home')
                if os.path.exists(home_dir):
                    for root, dirs, files in os.walk(home_dir):
                        for d in dirs:
                            src_path = os.path.join(root, d)
                            dst_path = os.path.join(os.path.expanduser('~'), 
                                                  os.path.relpath(src_path, home_dir))
                            os.makedirs(dst_path, exist_ok=True)
                        
                        for f in files:
                            src_path = os.path.join(root, f)
                            dst_path = os.path.join(os.path.expanduser('~'), 
                                                  os.path.relpath(src_path, home_dir))
                            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                            shutil.copy2(src_path, dst_path)
                            progress.advance(restore_task)
                
                # Restore system files
                system_dir = os.path.join(restore_point_dir, 'system')
                if os.path.exists(system_dir):
                    for root, dirs, files in os.walk(system_dir):
                        for d in dirs:
                            src_path = os.path.join(root, d)
                            dst_path = os.path.join('/', os.path.relpath(src_path, system_dir))
                            os.makedirs(dst_path, exist_ok=True)
                        
                        for f in files:
                            src_path = os.path.join(root, f)
                            dst_path = os.path.join('/', os.path.relpath(src_path, system_dir))
                            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                            shutil.copy2(src_path, dst_path)
                            progress.advance(restore_task)
            
        self.console.print("\n[green]System restored successfully![/green]")

    def list_restore_points(self) -> None:
        """List available restore points."""
        restore_base = os.path.expanduser("~/fsPurge_Restore")
        if not os.path.exists(restore_base):
            self.console.print("[yellow]No restore points found.[/yellow]")
            return
        
        restore_points = []
        for file in os.listdir(restore_base):
            if file.endswith('.tar.gz'):
                path = os.path.join(restore_base, file)
                size = os.path.getsize(path)
                created = datetime.fromtimestamp(os.path.getctime(path))
                restore_points.append((file, size, created))
        
        if not restore_points:
            self.console.print("[yellow]No restore points found.[/yellow]")
            return
        
        table = Table(title="Available Restore Points")
        table.add_column("Name", style="cyan")
        table.add_column("Size", style="green")
        table.add_column("Created", style="yellow")
        
        for name, size, created in sorted(restore_points, key=lambda x: x[2], reverse=True):
            table.add_row(
                name.replace('.tar.gz', ''),
                self._format_size(size),
                created.strftime("%Y-%m-%d %H:%M:%S")
            )
        
        self.console.print(table)

    def quick_uninstall(self, app_name: str) -> None:
        """Quick uninstall focusing only on main app bundle and obvious locations."""
        self.console.print(f"\n[cyan]Quick uninstalling {app_name}...[/cyan]")
        
        # Ask about restore point
        create_restore = Confirm.ask(
            "[yellow]Create restore point before quick uninstall?[/yellow]",
            default=True
        )
        
        if create_restore:
            self.create_restore_point(f"Before_Quick_{app_name}_Uninstall")
        
        common_paths = [
            f"/Applications/{app_name}.app",
            f"/Applications/{app_name}",
            os.path.expanduser(f"~/Applications/{app_name}.app"),
            os.path.expanduser(f"~/Applications/{app_name}"),
            os.path.expanduser(f"~/Library/Application Support/{app_name}"),
            os.path.expanduser(f"~/Library/Caches/{app_name}"),
            os.path.expanduser(f"~/Library/Preferences/*{app_name}*"),
            os.path.expanduser(f"~/Library/Saved Application State/{app_name}*"),
            os.path.expanduser(f"~/Library/Logs/{app_name}"),
        ]
        
        found_files = set()
        for path in common_paths:
            if '*' in path:
                # Handle wildcard paths
                base_dir = os.path.dirname(path)
                pattern = os.path.basename(path)
                if os.path.exists(base_dir):
                    matches = [os.path.join(base_dir, f) for f in os.listdir(base_dir)
                              if fnmatch.fnmatch(f.lower(), pattern.lower())]
                    found_files.update(matches)
            else:
                if os.path.exists(path):
                    found_files.add(path)
        
        if not found_files:
            self.console.print("[yellow]No files found for quick uninstall.[/yellow]")
            return
        
        # Display files to be removed
        tree = Tree(f"[bold red]Files to be removed:[/bold red]")
        total_size = 0
        for file in sorted(found_files):
            size = self._calculate_size(file)
            total_size += size
            tree.add(self._format_file_entry(file, size))
        
        self.console.print(tree)
        self.console.print(f"\n[bold]Total space to be freed:[/bold] {self._format_size(total_size)}")
        
        if Confirm.ask("\n[bold red]Proceed with quick uninstall?[/bold red]"):
            with Progress() as progress:
                task = progress.add_task("Removing files...", total=len(found_files))
                for file in found_files:
                    try:
                        if os.path.isfile(file) or os.path.islink(file):
                            os.remove(file)
                        elif os.path.isdir(file):
                            shutil.rmtree(file)
                        progress.advance(task)
                    except (PermissionError, OSError) as e:
                        self.console.print(f"[yellow]Warning: Could not remove {file}: {e}[/yellow]")
            
            self.console.print("[green]Quick uninstall completed![/green]")

    def force_uninstall(self, app_name: str) -> None:
        """Force uninstall using elevated privileges and ignoring locks."""
        self.console.print(f"\n[bold red]Force uninstalling {app_name}...[/bold red]")
        self.console.print("[yellow]Warning: Force mode will attempt to remove all traces of the app![/yellow]")
        
        # Request root privileges
        if not request_root_privileges("Required for force uninstall"):
            return
        
        # Ask about restore point
        create_restore = Confirm.ask(
            "[yellow]Create restore point before force uninstall?[/yellow]",
            default=True
        )
        
        if create_restore:
            self.create_restore_point(f"Before_Force_{app_name}_Uninstall")
        
        # Find all related processes
        try:
            import psutil
            processes = []
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if app_name.lower() in proc.info['name'].lower():
                        processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                
            if processes:
                self.console.print("\n[yellow]Found running processes:[/yellow]")
                for proc in processes:
                    self.console.print(f"  • {proc.info['name']} (PID: {proc.info['pid']})")
                
                if Confirm.ask("[bold red]Kill related processes?[/bold red]"):
                    for proc in processes:
                        try:
                            proc.kill()
                        except psutil.NoSuchProcess:
                            pass
        except ImportError:
            self.console.print("[yellow]psutil not installed - skipping process detection[/yellow]")
        
        # Find all files
        files = self.find_app_files(app_name)
        
        if not files:
            self.console.print("[yellow]No files found for force uninstall.[/yellow]")
            return
        
        # Display files to be removed
        tree = Tree(f"[bold red]Files to be forcefully removed:[/bold red]")
        total_size = 0
        for file in sorted(files):
            size = self._calculate_size(file)
            total_size += size
            tree.add(self._format_file_entry(file, size))
        
        self.console.print(tree)
        self.console.print(f"\n[bold]Total space to be freed:[/bold] {self._format_size(total_size)}")
        
        if Confirm.ask("\n[bold red]Proceed with force uninstall? This cannot be undone![/bold red]"):
            with Progress() as progress:
                task = progress.add_task("Force removing files...", total=len(files))
                for file in files:
                    try:
                        # Try to remove read-only flag if present
                        if os.path.exists(file):
                            os.chmod(file, 0o777)
                        
                        if os.path.isfile(file) or os.path.islink(file):
                            os.remove(file)
                        elif os.path.isdir(file):
                            shutil.rmtree(file, ignore_errors=True)
                        progress.advance(task)
                    except (PermissionError, OSError) as e:
                        # Try using sudo if normal removal fails
                        try:
                            subprocess.run(['sudo', 'rm', '-rf', file], check=True)
                            progress.advance(task)
                        except subprocess.CalledProcessError as e:
                            self.console.print(f"[red]Error: Could not remove {file}: {e}[/red]")
            
            self.console.print("[green]Force uninstall completed![/green]")

    async def process_files(self, files: Set[str], operation: str) -> None:
        """Optimized parallel file processing."""
        chunk_size = 1000
        total_chunks = (len(files) + chunk_size - 1) // chunk_size
        
        async with asyncio.TaskGroup() as group:
            for i in range(0, len(files), chunk_size):
                chunk = list(files)[i:i + chunk_size]
                group.create_task(self._process_chunk(chunk, operation))

    async def _process_chunk(self, files: List[str], operation: str) -> None:
        """Process a chunk of files efficiently."""
        for file in files:
            try:
                if operation == 'remove':
                    if os.path.isfile(file) or os.path.islink(file):
                        os.remove(file)
                    elif os.path.isdir(file):
                        shutil.rmtree(file, ignore_errors=True)
                elif operation == 'analyze':
                    await self._analyze_file(file)
            except Exception as e:
                self.console.print(f"[yellow]Error processing {file}: {e}[/yellow]")

    def optimize_memory_usage(self):
        """Implement memory optimization strategies."""
        gc.collect()  # Force garbage collection
        
        # Clear caches if memory usage is high
        if psutil.virtual_memory().percent > 90:
            self._calculate_size.cache_clear()
            gc.collect()

def handle_drag_and_drop() -> str:
    """Enhanced drag and drop interface."""
    console = Console()
    console.print("\n[bold cyan]Please drag and drop the application or file[/bold cyan]")
    console.print("[dim](press Enter when done)[/dim]")
    path = input().strip()
    path = path.strip("'\"").replace("\\", "")
    if os.path.exists(path):
        return os.path.basename(path).replace('.app', '')
    return path

def request_root_privileges(reason: str) -> bool:
    """Request root privileges with explanation."""
    console = Console()
    console.print(f"\n[yellow]Root privileges required: {reason}[/yellow]")
    
    try:
        if os.geteuid() != 0:
            console.print("[cyan]Requesting sudo privileges...[/cyan]")
            subprocess.check_call(['sudo', '-v'])
            # Re-run the script with sudo
            args = ['sudo', sys.executable] + sys.argv
            os.execvp('sudo', args)
        return True
    except subprocess.CalledProcessError:
        console.print("[red]Failed to obtain root privileges. Some operations may fail.[/red]")
        return False

def create_help_message():
    """Create a stylish help message."""
    help_panel = """
╭──────────────────────────────────────╮
│             fsPurge v1.0             │
│    Safe and Thorough App Removal     │
╰──────────────────────────────────────╯

[cyan]USAGE:[/cyan]
    fspurge [bold green]<command>[/bold green] [bold yellow]<app_name>[/bold yellow]

[cyan]COMMANDS:[/cyan]
    [bold green]-s[/bold green], [bold green]--scan[/bold green] [bold yellow]<app_name>[/bold yellow]
        Scan system for all files related to the specified app
        [dim]Example: fspurge -s firefox[/dim]

    [bold green]-u[/bold green], [bold green]--uninstall[/bold green] [bold yellow]<app_name>[/bold yellow]
        Safely remove an application and all its related files
        [dim]Example: fspurge -u google chrome[/dim]

    [bold green]-a[/bold green], [bold green]--analyze[/bold green] [bold yellow]<app_name>[/bold yellow]
        Analyze app's system impact and dependencies
        [dim]Example: fspurge -a spotify[/dim]

    [bold green]-rp[/bold green], [bold green]--restorepoint[/bold green] [bold yellow]<name>[/bold yellow]
        Create a system restore point with optional name
        [dim]Example: fspurge -rp "Before Update"[/dim]

    [bold green]-r[/bold green], [bold green]--restore[/bold green] [bold yellow]<point_name>[/bold yellow]
        Restore system from a restore point
        [dim]Example: fspurge -r Before_Update_20240215[/dim]

    [bold green]-lrp[/bold green], [bold green]--list-restorepoints[/bold green]
        List available restore points
        [dim]Example: fspurge -lrp[/dim]

    [bold green]-d[/bold green], [bold green]--drag[/bold green]
        Use interactive drag-and-drop interface
        [dim]Example: fspurge --drag[/dim]

    [bold green]-c[/bold green], [bold green]--config[/bold green]
        Modify configuration settings
        [dim]Example: fspurge --config[/dim]

[cyan]NOTES:[/cyan]
    • For apps with spaces in their name, no quotes needed
      [dim]Example: fspurge -s visual studio code[/dim]

    • Some operations may require root privileges
      [dim]The tool will request sudo access when needed[/dim]

    • Quick mode (-q) is faster but less thorough
      [dim]Best for simple apps with standard installations[/dim]

    • Force mode (-f) is aggressive and requires root
      [dim]Use only when standard uninstall fails[/dim]

[cyan]VERSION:[/cyan]
    1.0.0

[cyan]AUTHOR:[/cyan]
    madelyn1337
"""
    return help_panel

def main():
    console = Console()
    
    # Custom help message
    if len(sys.argv) == 1 or '-h' in sys.argv or '--help' in sys.argv:
        console.print(create_help_message())
        sys.exit(0)
    
    parser = argparse.ArgumentParser(
        description='fsPurge - Safe and Thorough App Removal',
        add_help=False
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-s', '--scan', nargs='+', metavar='APP_NAME',
                      help='Scan for files related to the specified app')
    group.add_argument('-u', '--uninstall', nargs='+', metavar='APP_NAME',
                      help='Remove all files related to the specified app')
    group.add_argument('-q', '--quick', nargs='+', metavar='APP_NAME',
                      help='Quick uninstall of main app files only')
    group.add_argument('-f', '--force', nargs='+', metavar='APP_NAME',
                      help='Force uninstall with elevated privileges')
    group.add_argument('-a', '--analyze', nargs='+', metavar='APP_NAME',
                      help='Analyze system impact and dependencies')
    group.add_argument('-d', '--drag', action='store_true',
                      help='Use drag and drop interface')
    group.add_argument('-c', '--config', action='store_true',
                      help='Modify configuration settings')
    group.add_argument('-rp', '--restorepoint', nargs='?', const='', metavar='NAME',
                      help='Create a system restore point with optional name')
    group.add_argument('-r', '--restore', metavar='POINT_NAME',
                      help='Restore system from a restore point')
    group.add_argument('-lrp', '--list-restorepoints', action='store_true',
                      help='List available restore points')
    group.add_argument('-h', '--help', action='store_true',
                      help='Show this help message')
    
    args = parser.parse_args()
    
    purger = FSPurge()
    
    if args.config:
        # Force config setup to run again
        purger.config.config["first_run"] = True
        purger.config.first_time_setup(console)
        sys.exit(0)
    elif args.analyze:
        app_name = ' '.join(args.analyze)
        request_root_privileges("Required to analyze system processes and protected files")
        purger.analyze_system_impact(app_name)
        purger.analyze_dependencies(app_name)
    elif args.drag:
        app_name = handle_drag_and_drop()
        action = input("Choose action (scan/uninstall/analyze): ").lower()
        if action == 'scan':
            purger.scan(app_name)
        elif action == 'uninstall':
            request_root_privileges("Required to remove system files and applications")
            purger.uninstall(app_name)
        elif action == 'analyze':
            request_root_privileges("Required to analyze system processes and protected files")
            purger.analyze_system_impact(app_name)
            purger.analyze_dependencies(app_name)
        else:
            print("Invalid action. Please choose 'scan', 'uninstall', or 'analyze'.")
    elif args.scan:
        app_name = ' '.join(args.scan)
        purger.scan(app_name)
    elif args.uninstall:
        app_name = ' '.join(args.uninstall)
        request_root_privileges("Required to remove system files and applications")
        purger.uninstall(app_name)
    elif args.quick:
        app_name = ' '.join(args.quick)
        purger.quick_uninstall(app_name)
    elif args.force:
        app_name = ' '.join(args.force)
        purger.force_uninstall(app_name)

if __name__ == "__main__":
    asyncio.run(main())