from setuptools import setup, find_packages
import os

# Read requirements.txt
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

# Read README.md for long description
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

# Ensure cache directory exists
cache_dir = 'cache'
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

setup(
    name='ld-cleanup-report',
    version='1.0.0',
    description='LaunchDarkly Feature Flag Cleanup Report Generator',
    long_description='A tool for generating cleanup reports for LaunchDarkly feature flags. ',
    long_description_content_type='text/markdown',
    author='Benedicto Tan',
    author_email='btan@launchdarkly.com',
    url='',
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'ld-cleanup-report=src.ld_cleanup_report:main',
        ],
    },
    python_requires='>=3.6',
    package_data={
        '': ['README.md', 'requirements.txt'],
    },
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