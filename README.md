# GHR CLI

A Python utility for managing command-line tools from GitHub releases.

## Features

- Automatic download URL detection from GitHub releases
- Versioned installations with symbolic links
- Simple YAML configuration
- Clean old versions while keeping N most recent
- Standalone executable - no Python installation required
- Proper sudo privilege handling
- Built-in caching system for faster operations

## Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/m-d-nabeel/ghr-cli.git
   cd ghr-cli
   ```

2. Run the setup script to create the standalone executable:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

3. Use the generated executable:
   ```bash
   ./ghr-cli --help
   ```

4. (Optional) Move the executable to a location in your PATH:
   ```bash
   sudo cp ghr-cli /usr/local/bin/
   ```

   Or use the provided installation script:
   ```bash
   chmod +x install.sh
   ./install.sh  # Installs to current directory by default
   ```

   The install script accepts options:
   ```bash
   # Install to the current directory (default)
   ./install.sh
   
   # Install to a custom directory
   ./install.sh --dir ~/bin
   
   # Install to a custom location
   ./install.sh --config-dir ~/.config/ghr-cli
   
   # Install system-wide (requires sudo)
   sudo ./install.sh --system
   ```

## Standalone Executable

The setup script creates a standalone executable that:
- Doesn't require Python to be installed
- Has all dependencies bundled within it
- Only needs the `toolset.yaml` configuration file to be present

The executable will look for the configuration file in these locations (in order):
1. Path specified with `--config` option
2. Current working directory
3. Same directory as the executable
4. User config directory (~/.config/ghr-cli/toolset.yaml)
5. System-wide location: `/etc/ghr-cli/toolset.yaml`

This makes it easy to:
- Use a portable setup by keeping the executable and config file together
- Set up a system-wide installation with the provided install script

To deploy to another system, just copy:
- `ghr-cli` (the executable)
- `toolset.yaml` (your configuration)

## Configuration

Create or modify the `toolset.yaml` file to manage your tools:

```yaml
options:
  auto_cleanup: false
  keep_versions: 2
  cache_enabled: true
  cache_expiry: 3600
tools:
- repo: jesseduffield/lazydocker
  version: 0.24.1
- repo: jesseduffield/lazygit
  version: 0.48.0
```

### Configuration Options

- `auto_cleanup`: Automatically remove old versions when installing a new one
- `keep_versions`: Number of versions to keep (including the current one)
- `cache_enabled`: Enable or disable caching (default: true)
- `cache_expiry`: Cache expiry time in seconds (default: 3600 = 1 hour)

### Tool Options

- `repo`: GitHub repository in the format `owner/repo`
- `version`: Current version (will be updated when installing new versions)
- `install_path`: (Optional) Custom installation path (default: `/opt/reponame`)

## Usage

```bash
# List all configured tools
./ghr-cli --list

# Install all tools (will prompt before each installation)
./ghr-cli

# Install all tools without prompting
./ghr-cli --install

# Install a specific tool
./ghr-cli --install jesseduffield/lazygit

# Clean old versions
./ghr-cli --clean

# Rollback to a previous version
./ghr-cli --rollback jesseduffield/lazygit

# Check if sudo access is available
./ghr-cli --check-sudo

# Clear the download and API cache
./ghr-cli --clear-cache

# Show cache directory and statistics
./ghr-cli --cache-dir

# Disable caching for a single run
./ghr-cli --no-cache --install

# Force caching for a single run
./ghr-cli --force-cache --install
```

## Caching

The tool manager implements a caching system to improve performance:

- GitHub API responses are cached to reduce API requests
- Downloaded assets are cached to avoid re-downloading
- By default, cache is stored in `~/.cache/ghr-cli/`
- Cache expires after 1 hour (configurable in settings)

You can control caching behavior through:
- Command line options (`--clear-cache` and `--cache-dir`)
- Configuration settings in `toolset.yaml`

## Notes

- For system-wide installations (e.g., in `/opt`), you'll need sudo privileges.
- The tool manager will automatically detect when sudo is needed and prompt accordingly.

## Development

### Versioning

GHR CLI follows semantic versioning (MAJOR.MINOR.PATCH):
- MAJOR version for incompatible API changes
- MINOR version for backwards-compatible functionality additions
- PATCH version for backwards-compatible bug fixes

Version labels:
- `-alpha`: Alpha releases (for testing)
- `-beta`: Beta releases (for early user feedback)
- `-rc`: Release candidates (feature complete, testing for stability)

### Version Management

You can use the included `bump_version.py` script to manage versions:

```bash
# Bump patch version (0.1.0 -> 0.1.1)
./bump_version.py patch

# Bump minor version and set to beta (0.1.0 -> 0.2.0-beta)
./bump_version.py minor beta

# Set specific version
./bump_version.py set 1.0.0
```

### GitHub Releases

The project uses GitHub Actions to automatically build releases:

1. Pushing to `main` creates alpha builds
2. Creating a tag (v0.1.0) creates release builds
3. Using the workflow dispatch with parameters creates custom builds

For every build, GitHub Actions:
- Builds the ghr-cli for Linux, macOS, and Windows
- Creates distribution packages with documentation
- Uploads artifacts to the GitHub release