# fsPurge

> A powerful multi purpose cleaning and scanning tool for mac

fsPurge is a tool designed to help users completely remove applications and their associated files from mac systems. fsPurge performs deep system scans to identify and remove all traces of an application, including preferences, caches, and hidden files.

## 🌟 Features

### 🔍 Intelligent Scanning
- **Deep System Analysis**: Recursively scans multiple system locations for application-related files
- **Pattern Matching**: Uses both strict and loose pattern matching to find related files
- **Smart Filtering**: Automatically excludes system-critical files and directories
- **Resource-Efficient**: Implements memory optimization and caching for better performance

### 🧹 Multiple Uninstall Options

#### Standard Uninstall
- Safely removes applications and associated files
- Creates automatic backup before removal
- Shows detailed progress and confirmation prompts
- Handles permissions and locked files appropriately

#### Quick Uninstall
- Focuses on main application bundle and common locations
- Perfect for simple applications with standard installations
- Faster than full uninstall while still being thorough

#### Force Uninstall
- Uses elevated privileges to remove stubborn applications
- Terminates running processes automatically
- Bypasses file locks and permission issues
- Includes additional system cleanup

### 📊 System Impact Analysis
- **Process Monitoring**: Identifies running processes and background services
- **Resource Usage**: Tracks memory and CPU usage
- **Disk Space**: Calculates total disk space used
- **Dependencies**: Maps application dependencies and shared components
- **Launch Agents**: Identifies startup items and scheduled tasks

### 💾 Backup and Restore
- **System Restore Points**: Creates comprehensive system backups
- **Selective Restoration**: Ability to restore specific files or entire systems
- **Compressed Storage**: Efficient backup storage using compression
- **Metadata Tracking**: Maintains detailed backup information

### 🔄 Background Services
- **Launch Agent Detection**: Identifies and removes startup items
- **Service Management**: Handles background processes and daemons
- **Scheduled Tasks**: Manages periodic cleanup tasks
- **System Integration**: Proper handling of system services

### 🛡️ Safety Features
- **Protected Path Detection**: Prevents removal of system-critical files
- **Automatic Backups**: Creates restore points before major operations
- **Confirmation Prompts**: Requires user confirmation for dangerous operations
- **Error Handling**: Graceful handling of errors and permissions issues

### 🎯 Additional Features
- **Drag and Drop Interface**: Simple drag-and-drop functionality
- **Progress Tracking**: Real-time progress indicators
- **Rich Console Output**: Beautiful and informative console interface
- **Multi-threading**: Parallel processing for better performance
- **Memory Optimization**: Efficient memory usage and garbage collection
- **Cache Management**: Smart caching for repeated operations

## 🔧 Technical Details

### Advanced File Detection
fsPurge uses multiple methods to identify application-related files:
- Regular expression pattern matching
- Fuzzy name matching
- Bundle identifier tracking
- File system monitoring
- Metadata analysis

### Performance Optimization
- Implements multiprocessing for CPU-intensive tasks
- Uses asynchronous I/O for file operations
- Maintains an SQLite cache for faster scanning
- Employs memory management strategies
- Implements efficient file system traversal

### System Integration
- Integrates with macOS system services
- Handles system permissions appropriately
- Manages process termination safely
- Provides proper cleanup of system resources

## 🎯 Use Cases

### Perfect for:
- Complete application removal
- System cleanup and optimization
- Application analysis and troubleshooting
- System maintenance and monitoring
- Backup and restore operations

### Ideal when:
- Standard uninstallers leave remnants
- Applications have deep system integration
- You need to track application impact
- System resources need optimization
- Complete removal is required

## ⚠️ Important Notes

- Some operations require root privileges
- Creating restore points before major operations is recommended
- Force uninstall should be used as a last resort
- System files are protected from accidental removal
- Some operations may require system restart

---

*fsPurge is designed to be powerful yet safe, providing users with complete control over their system while maintaining system integrity.*
