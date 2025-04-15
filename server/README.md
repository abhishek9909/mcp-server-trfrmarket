A Model Context Protocol (MCP) server that provides any client access to helper functions using [WorldFootballR](https://github.com/JaseZiv/worldfootballR)

The server implements the protocol to allow any client to:
- Execute helper functions from transfermarket listed here.
- Execute python code properly based on file-paths (which would be stored in client's working directory)

The helper functions exposed are [based on this](https://jaseziv.github.io/worldfootballR/articles/extract-transfermarkt-data.html#transfermarkt-helper-functions)

# To Run the server:

## Prerequisites
Before setting up the project, ensure you have the following installed:

- [Docker](https://www.docker.com/products/docker-desktop) (latest version recommended)
- [Python 3.11](https://www.python.org/downloads/)
- [Poetry](https://python-poetry.org/docs/#installation) (for Python dependency management)

## Setup (unverified but quite simple)

### 1. Clone the Repository

```bash
git clone https://github.com/abhishek9909/mcp-server-trfrmarket.git
cd server
```

### 2. Build the Docker Image.

```bash
docker build -t mcp-server-app
```

### 3. Run the Docker Container

```bash
docker run --rm python-r-app
```
