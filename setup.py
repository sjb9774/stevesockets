from setuptools import setup, find_packages

setup(
    name="stevesockets",
    version="0.0.2",
    description="A simple socket and websocket server package",
    long_description="",
    url="https://github.com/sjb9774/stevesockets",
    author="Stephen Biston",
    author_email="sjb9774@gmail.com",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    keywords="socket sockets websocket steve",
    packages=find_packages(exclude=["tests"]),
    install_requires=[],
    extras_require={},
    package_data={},
)
