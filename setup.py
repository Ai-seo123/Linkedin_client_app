from setuptools import setup, find_packages

setup(
    name='KTinker_Client_bot',
    version='0.1.0',
    author='Your Name',
    author_email='your.email@example.com',
    description='A LinkedIn automation client using Flask and Gemini AI',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        'Flask',
        'requests',
        'pyngrok',
        'tkinter',
        'linkedin-automation',  # Replace with actual package name if available
        'gemini-ai'  # Replace with actual package name if available
    ],
    entry_points={
        'console_scripts': [
            'ktinker-client=KTinker_Client_bot:main',  # Adjust if main function is located elsewhere
        ],
    },
)