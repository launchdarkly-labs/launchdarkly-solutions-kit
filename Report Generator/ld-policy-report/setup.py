from setuptools import setup, find_packages
import os
"""
:license: MIT see LICENSE for more details.
"""
# Read README.md for long description
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

# Ensure cache directory exists
cache_dir = 'cache'
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

setup(
    name="launchdarkly-policy-report",
    version="0.1.0",
    description='LaunchDarkly Policy Report Generator',
    long_description="",
    long_description_content_type='text/markdown',
    author='Benedicto Tan',
    author_email='btan@launchdarkly.com',
    url='',
    packages=[
        'launchdarkly_api_client',
        'launchdarkly_policy_similarity',
        'launchdarkly_reports',
        'src'
    ],
    package_data={
        'launchdarkly_reports': ['reports_styles.css', 'reports.js'],
    },
    install_requires=[
        'requests',
        'python-dotenv',
        'tqdm',
        'chromadb',
        'sentence-transformers'
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ],
    },
    entry_points={
        'console_scripts': [
            'ld-policy-report=src.ld_policy_report:main',
        ],
    },
    python_requires='>=3.6',
    data_files=[
        ('cache', []),  # Create empty cache directory in installation
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
    keywords='launchdarkly feature-flags cleanup report',
) 