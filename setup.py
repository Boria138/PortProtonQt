from setuptools import setup, find_packages

setup(
    name='PortProtonQt',
    version='0.1.0',
    packages=find_packages(),
    install_requires=open('requirements.txt').read(),
    entry_points={
        'console_scripts': [
            'portprotonqt=portprotonqt.app:main',
        ],
    },
    author='Boria138, BlackSnaker, Castro-Fidel',
    author_email='?',
    description='A project to rewrite PortProton (PortWINE) using PySide',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/BlackSnaker/PortProtonQt',
    license='MIT',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Linux',
    ],
    python_requires='>=3.6',
)
