# LaunchDarkly Solutions Kit
A collection of scripts, extensions, and helper tools developed by the LaunchDarkly Professional Services team.

This repository contains a variety of resources designed to help teams streamline their LaunchDarkly implementations, automate common tasks, and extend LaunchDarkly's capabilities. These tools are provided as-is, without formal support, but you're welcome to use, modify, and adapt them to fit your needs.

## What's Inside?
- [**Automation**](./Automation) – CLI tools for policy management, team administration, and documentation conversion
- [**Integrations & Extensions**](./Integrations%20and%20Extensions) – Code snippets and utilities to connect LaunchDarkly with other platforms
- [**Helper Tools**](./Helper%20Tools) – Utilities to enhance productivity when working with LaunchDarkly
- [**Report Generators**](./Report%20Generator) – Applications for generating comprehensive LaunchDarkly analysis reports
- [**Examples & Best Practices**](./Examples%20and%20Best%20Practices) – Sample implementations and guidelines for common use cases

## Need Help Customizing These Solutions?
If you require assistance in tailoring these solutions to your specific needs, our LaunchDarkly Professional Services team is available for paid engagements to help you integrate, optimize, and extend your feature flagging strategy. Reach out to us to discuss how we can support your use case!

## Disclaimer
This repository is maintained by the LaunchDarkly Professional Services team, but the tools provided here are not officially supported by LaunchDarkly. Use them at your own discretion!

## Automation
| Name  | Description | Key Features |
|-------|-------------|--------------|
| [**Policy Linter**](./Automation#1-policy-linter-policy-linter) | CLI tool for validating, exporting, and fixing LaunchDarkly custom roles | Policy validation, auto-fix capability, bulk export, schema compliance |
| [**TeamManager**](./Automation#2-teammanager-teammanager) | Team management tool for analyzing and optimizing role assignments | Team analysis, role distribution insights, patch generation, template processing |
| **API Client Library** | Shared LaunchDarkly API client with intelligent caching and rate limiting | Automatic caching, progress tracking, error handling, data enrichment |

## Report Generators
| Name  | Description | Use Cases |
|-------|-------------|-----------|
| [**Flag Cleanup Report**](./Report%20Generator/flag-cleanup-report) | Bulk analysis and offline reporting tool that complements Launch Insights | Multi-project analysis, automated CSV exports, cached data processing, cleanup initiatives |
| [**Policy Report Generator**](./Report%20Generator/ld-policy-report) | Analysis tool for custom role policies with similarity detection and team visualization | Policy similarity analysis, role assignment tracking, team access visualization, invalid action detection |

## Integrations & Extensions
| Status | Description |
|--------|-------------|
| 🚧 **Coming Soon** | Code snippets and utilities for connecting LaunchDarkly with popular platforms |
| 📋 **Planned Integrations** | CI/CD pipelines, monitoring tools, notification systems, and workflow automation |

## Helper Tools
| Status | Description |
|--------|-------------|
| 🚧 **Coming Soon** | Utilities to enhance productivity when working with LaunchDarkly |
| 📋 **Planned Tools** | SDK helpers, configuration validators, migration utilities, and development aids |

## Examples & Best Practices
| Status | Description |
|--------|-------------|
| 🚧 **Coming Soon** | Sample implementations and guidelines for common LaunchDarkly use cases |
| 📋 **Planned Content** | Feature flag patterns, SDK integration examples, testing strategies, and architecture guides |

## Getting Started

### Quick Setup for Automation
```bash
# Navigate to Automation
cd "Automation"

# Run setup script
./setup.sh

# Activate virtual environment
source venv/bin/activate

# Configure your API key
echo "LAUNCHDARKLY_API_KEY=your-api-key-here" > .env
```

### Quick Setup for Report Generators
```bash
# For Flag Cleanup Report
cd "Report Generator/flag-cleanup-report"
./setup.sh

# For Policy Report Generator  
cd "Report Generator/ld-policy-report"
./setup.sh
```

## Repository Structure
```
launchdarkly-solutions-kit/
├── Automation/          # CLI automation tools
│   ├── policy_linter/          # Policy validation and management
│   ├── team_manager/            # TeamManager - Team and role management
│   ├── api_client/             # Shared API client library
│   └── README.md               # Detailed automation documentation
├── Report Generator/            # Analysis and reporting tools
│   ├── flag-cleanup-report/    # Feature flag cleanup analysis
│   ├── ld-policy-report/       # Custom role policy analysis
│   └── README.md               # Report generation documentation
├── Helper Tools/                # Development and productivity utilities
├── Integrations and Extensions/ # Platform integration utilities
├── Examples and Best Practices/ # Implementation guides and samples
└── README.md                   # This file
```

## Contributing & License
We welcome contributions! Please feel free to submit a PR or open an issue to suggest improvements or new features.

### Contributing Guidelines
- Fork the repository and create a feature branch
- Add comprehensive documentation for new tools
- Include setup scripts and dependency management
- Follow existing code style and structure conventions
- Test your changes thoroughly before submitting

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Support & Community
- **Documentation**: Each tool includes detailed README files with usage examples
- **Issues**: Report bugs or request features through GitHub Issues
- **Ideas**: Share suggestions for new tools or improvements
- **Professional Services**: Contact LaunchDarkly for paid customization and integration support