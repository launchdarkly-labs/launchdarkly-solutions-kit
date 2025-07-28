from setuptools import setup, find_packages
import os


# Ensure cache directory exists
output_dir = 'output'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

setup(
    name="automation-scripts",
    version="0.1.0",
    description='LaunchDarkly CLI Tools',
    long_description="A collection of CLI tools for managing LaunchDarkly resources.",
    long_description_content_type='text/markdown',
    author='LaunchDarkly-Labs',
    author_email='',
    url='https://github.com/launchdarkly-labs/launchdarkly-solutions-kit',
    packages=[
        'api_client',
        'policy_linter',
        'team_manager'
        
    ],
    package_data={
        'config': ['resource_actions.json'],
    },
    install_requires=[
        'python-dotenv',
        'tqdm',
        "selenium>=4.10.0",
        "beautifulsoup4>=4.12.0",
        "html2text>=2020.1.16",
        "webdriver-manager>=3.8.6",
        "requests>=2.28.0",
        "jsonpatch>=1.32",
    ],
    extras_require={
        "dev": [
            "black>=23.0.0",
            "flake8>=6.0.0",
        ],
    },
    entry_points={
        'console_scripts': [
            'policy-linter=policy_linter.main:main',
            'team-manager=team_manager.main:main',
        ],
    },
    python_requires='>=3.6',
    data_files=[
        ('output', []),  # Create empty cache directory in installation
        ('output/reports', []),
        ('output/exported_roles', []),
        ('output/patches', []),
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    keywords='launchdarkly policy linter role policy validation team management role assignment',
) 