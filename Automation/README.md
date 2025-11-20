# LaunchDarkly Automation Scripts

A collection of CLI tools designed to help LaunchDarkly administrators, DevOps teams, and developers manage policies, teams, and documentation more efficiently.

## Available Tools

### 1. **Policy Linter** (`policy-linter`)
A powerful CLI tool for validating, exporting, and fixing LaunchDarkly custom roles to ensure they use only valid actions and follow best practices.

**Key Features:**
- **Policy Validation**: Check custom roles against LaunchDarkly's official resource actions
- **Issue Detection**: Find invalid, deprecated, or problematic actions
- **Auto-Fix**: Generate corrected versions with invalid actions removed
- **Bulk Export**: Export all policies for backup, audit, or migration

**Use Cases:**
- Managing multiple custom roles across your organization
- Ensuring role-based access control follows security best practices
- Auditing and remediating access control issues
- Moving policies between LaunchDarkly accounts

**Quick Usage:**
```bash
# Validate all policies
policy-linter --validate

# Fix invalid policies
policy-linter --fix

# Export all policies
policy-linter --export
```

### 2. **TeamManager** (`team-manager`)
Comprehensive LaunchDarkly team management tool for analyzing, optimizing, and managing team role assignments.

**Key Features:**
- **Team Analysis**: Coverage reports and role distribution insights
- **Assignment Suggestions**: Recommendations for optimizing role assignments
- **Template Analysis**: Discover role attribute patterns and placeholders in role scoped policy
- **Patch Generation**: Automated patch creation and application
- **Batch Processing**: Apply changes to multiple teams simultaneously
- **Export Capabilities**: Generate detailed JSON reports

**Use Cases:**
- Analyzing team role coverage and distribution
- Optimizing role assignments across teams
- Managing template-based(role-scoped policy) role deployments
- Bulk updating team roles and permissions

**Quick Usage:**
```bash
# Analyze team coverage
team-manager --analyze-teams

# Generate role assignment patches
team-manager --generate-patch

# Apply patches to teams
team-manager --apply-patch
```

## Installation & Setup

### Prerequisites
- **Python 3.6+** (Python 3.7+ recommended)
- **LaunchDarkly API Key** with appropriate permissions


### Quick Setup
```bash
# 1. Navigate to the Automation directory
cd "Automation"

# 2. Run the setup script (creates virtual environment and installs dependencies)
./setup.sh

# 3. Activate the virtual environment
source venv/bin/activate

# 4. Configure your LaunchDarkly API key
echo "LAUNCHDARKLY_API_KEY=your-api-key-here" > .env
```

### Manual Installation
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install the package and all dependencies
pip install -e .
```

## Configuration

### Environment Variables
Create a `.env` file in the Automation directory:

```bash
# Required for Policy Linter and TeamManager
LAUNCHDARKLY_API_KEY=your-api-key-here

# Optional: Override default LaunchDarkly API endpoint
LAUNCHDARKLY_API_ENDPOINT=https://app.launchdarkly.com
```

### API Permissions Required

| Tool | Required Permissions |
|------|---------------------|
| **Policy Linter** | `reader` (validation), `updatePolicy` (fixing) |
| **TeamManager** | `reader`, `updateTeamCustomRoles` |

## Directory Structure

```
Automation/
├── api_client/           # Shared LaunchDarkly API client library
├── config/              # Configuration files and schemas
├── policy_linter/       # Policy validation and fixing tool
├── team_manager/         # Team management and analysis tool
├── output/              # Generated reports, exports, and patches
├── setup.py            # Package configuration
├── setup.sh            # Quick setup script
└── env-example         # Environment variables template
```

## Output Files

All tools generate output in the `output/` directory:
- **Reports**: Analysis and validation reports
- **Exported Roles**: Policy exports and backups
- **Patches**: Team role update patches
- **Converted Docs**: Markdown and JSON conversions

## Workflow Examples

### Policy Management Workflow
```bash
# 1. Validate current policies
policy-linter --validate

# 2. Export for backup
policy-linter --export

# 3. Fix any issues found
policy-linter --fix
```

### Team Role Optimization Workflow
```bash
# 1. Analyze current team structure
team-manager --report

# 2. Generate  patches for role scoped policy
team-manager --generate-patches < Sample role scoped policy JSON >

# 3. Apply patches to teams
team-manager --apply-patches  <[team1 team2 team-N]>
team-manager --apply-patches  <team> --patch-dir <patch directory> --comment "applying patches"
```


## Getting Help

Each tool provides detailed help and usage information:

```bash
policy-linter --help
team-manager --help
```

For detailed documentation and advanced usage, see the individual README files in each tool's directory:
- [Policy Linter README](./policy_linter/README.md)
- [TeamManager README](./team_manager/README.md)

## Troubleshooting

### Common Issues

**Virtual Environment Issues:**
```bash
# Deactivate and recreate if needed
deactivate
rm -rf venv
./setup.sh
```

**API Permission Errors:**
- Ensure your API key has the required permissions for the tool you're using
- Check that your API key is correctly set in the `.env` file

