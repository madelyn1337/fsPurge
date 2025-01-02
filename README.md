# fsPurge

> A powerful multi purpose cleaning and scanning tool for mac

fsPurge is a tool designed to help users completely remove applications and their associated files from mac systems. fsPurge performs deep system scans to identify and remove all traces of an application, including preferences, caches, and hidden files.

## 🌟 Features

### 🔍 Intelligent Scanning
- **Deep System Analysis**: Recursively scans multiple system locations for application-related files
- **Pattern Matching**: Uses multiple different pattern matching to find related files
- **Smart Filtering**: Automatically bypasses system-critical files and directories as well as ones set by user in config
- **Resource-Efficient**: Has memory optimization and caching for increased performance while scanning

### 🧹 Multiple Uninstall Options

#### Standard Uninstall
- Safely uninstalles applications and associated files
- Has detailed progress and confirmation before removals

#### Quick Uninstall
- Targets the original .app bundle and common extra locations
- Has faster speeds than the forced and standard uninstall

#### Force Uninstall
- Uses root level to remove hard to delete apps
- Kills all running processes by itself at the highest level
- Gets through file locks and deals with permissions
- Also does high level system cleanup afterwards

### 📊 System Impact Analysis
- **Process Monitoring**: Scans and identifies running apps and background daemons
- **Resource Usage**: Monitors memory and CPU usage
- **Disk Space**: Indicates all disk space used
- **Dependencies**: Finds application dependencies and frameworks used/needed
- **Launch Agents**: Finds startup items easily

### 💾 Backup and Restore
- **Restore Points**: Creates a time snap and allows user to revert back to it in case of issues.
- **Compressed Storage**: Compresses backup to save more storage
- **Metadata Tracking**: Has a lot of info on the back ups

## 🛠️ Installation & Compiling

### fsPurge
- all in 1 cli menu
- bigger file but has all the tools in one place
- simple compiling
- requires more arguments
- more time consuming but overall simpler and easier for average users.

### Mini Versions
- easier to understand and use
- each tool does one thing only
- less arguments needed
- faster to use and can put into path
- requires compiling all tools individually

### How to Run:

Create a python virtual enviroment for ease of use (not needed but is recommended)

```bash
python3 -m venv venv
```
activate virtual environment

```bash
source venv/bin/activate
```
install python requirements to compile

```bash
pip install -r requirements.txt
```
Run the app using -h for instructions

```bash
python3 fspurge.py --help
```

### How to Compile:

Create a python virtual enviroment for ease of use (not needed but is recommended)

```bash
python3 -m venv venv
```
activate virtual environment

```bash
source venv/bin/activate
```
install python requirements to compile

```bash
pip install -r requirements.txt
```
compile into a binary

```bash
pyinstaller --onefile --clean --name scanner fspurge_scan.py
```
replace scanner with whatever you want the binary name called

replace fspurge_scan.py with whatever version you want to compile, if you want the all in one just use fspurge.py

## ⚠️ Important Notes

- App will need root privileges at certain times if needed, it will tell you why and what its doing
- Always recomended to create restore points on at least first run
- Do not start with force uninstall as it is slower and is at a higher privilege.
- All important files are protected by default unless stated by user.
- App is in alpha so feedback and ideas are appreciated.

---

*fsPurge was created to be feature-rich, powerful, and safe, allowing users to control their system.
