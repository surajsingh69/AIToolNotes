from setuptools import setup, find_packages

setup(
    name="aitoolnotes-ai-tool-finder",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[],
    author="Suraj Singh",
    author_email="surajjsingh0111@gmail.com",
    description="Find free AI tools by category. Data from AIToolNotes.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/surajsingh69/AIToolNotes",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
)
