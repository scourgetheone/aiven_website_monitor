import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="aiven-website-monitor", # Replace with your own username
    version="0.0.1",
    author="Viet Nguyen",
    author_email="vietnguyen92@hotmail.com",
    description="An app that monitors website online status using Aiven's Kafka and PostgreSQL",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/scourgetheone",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Linux",
    ],
    python_requires='>=3.6',
)
