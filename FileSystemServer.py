import asyncio
import datetime
import logging
import os
import shutil
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# Configure logging for auditing and debugging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = Server("filesystem")

# Set the root directory Claude is allowed to access.
# Use the FS_ALLOWED_ROOT environment variable, or fall back to the user's home directory.
ALLOWED_ROOT = Path(os.environ.get("FS_ALLOWED_ROOT", str(Path.home()))).resolve()
logger.info(f"Filesystem server started. Allowed root: {ALLOWED_ROOT}")


def safe_path(path_str: str) -> Path:
    """Ensure the path is within the allowed root using is_relative_to() for robustness."""
    path = Path(path_str).resolve()
    if not path.is_relative_to(ALLOWED_ROOT):
        raise PermissionError(f"Access denied: '{path}' is outside allowed root '{ALLOWED_ROOT}'")
    return path


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_directory",
            description="List files and folders in a directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list. Defaults to allowed root if not provided."
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="read_file",
            description="Read the contents of a text file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Full path to the file to read."
                    }
                },
                "required": ["path"]
            }
        ),
        types.Tool(
            name="write_file",
            description="Write or overwrite a text file with given content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Full path to the file."},
                    "content": {"type": "string", "description": "Text content to write."}
                },
                "required": ["path", "content"]
            }
        ),
        types.Tool(
            name="delete_file",
            description="Delete a file from the filesystem.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Full path to the file to delete."}
                },
                "required": ["path"]
            }
        ),
        types.Tool(
            name="delete_directory",
            description="Delete an empty or non-empty directory from the filesystem.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Full path to the directory to delete."},
                    "recursive": {"type": "boolean", "description": "If true, deletes non-empty directories. Default is false."}
                },
                "required": ["path"]
            }
        ),
        types.Tool(
            name="create_directory",
            description="Create a new directory (including parent directories).",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Full path of the directory to create."}
                },
                "required": ["path"]
            }
        ),
        types.Tool(
            name="copy_file",
            description="Copy a file from one location to another.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Source file path."},
                    "destination": {"type": "string", "description": "Destination file path."}
                },
                "required": ["source", "destination"]
            }
        ),
        types.Tool(
            name="move_file",
            description="Move or rename a file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Source file path."},
                    "destination": {"type": "string", "description": "Destination file path."}
                },
                "required": ["source", "destination"]
            }
        ),
        types.Tool(
            name="search_files",
            description="Search for files by name pattern in a directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory to search in."},
                    "pattern": {"type": "string", "description": "Filename pattern e.g. '*.py', '*.txt', 'report*'"}
                },
                "required": ["directory", "pattern"]
            }
        ),
        types.Tool(
            name="get_file_info",
            description="Get metadata about a file (size, modified date, type).",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Full path to the file."}
                },
                "required": ["path"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        if name == "list_directory":
            path = safe_path(arguments.get("path", str(ALLOWED_ROOT)))
            logger.info(f"list_directory: {path}")
            if not path.exists():
                return [types.TextContent(type="text", text=f"Path does not exist: {path}")]
            if not path.is_dir():
                return [types.TextContent(type="text", text=f"Not a directory: {path}")]

            items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            lines = []
            for item in items:
                icon = "📄" if item.is_file() else "📁"
                size = f"  ({item.stat().st_size:,} bytes)" if item.is_file() else ""
                lines.append(f"{icon} {item.name}{size}")

            result = f"Contents of {path}:\n" + "\n".join(lines) if lines else f"{path} is empty."
            return [types.TextContent(type="text", text=result)]

        elif name == "read_file":
            path = safe_path(arguments["path"])
            logger.info(f"read_file: {path}")
            if not path.is_file():
                return [types.TextContent(type="text", text=f"File not found: {path}")]

            if path.stat().st_size > 1_000_000:
                return [types.TextContent(type="text", text=f"File too large to read (>1MB): {path}")]

            content = path.read_text(encoding="utf-8", errors="replace")
            return [types.TextContent(type="text", text=f"Contents of {path}:\n\n{content}")]

        elif name == "write_file":
            path = safe_path(arguments["path"])
            logger.info(f"write_file: {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(arguments["content"], encoding="utf-8")
            return [types.TextContent(type="text", text=f"Successfully wrote to {path}")]

        elif name == "delete_file":
            path = safe_path(arguments["path"])
            logger.info(f"delete_file: {path}")
            if not path.exists():
                return [types.TextContent(type="text", text=f"File not found: {path}")]
            if path.is_dir():
                return [types.TextContent(type="text", text=f"'{path}' is a directory. Use delete_directory instead.")]
            path.unlink()
            return [types.TextContent(type="text", text=f"Deleted: {path}")]

        elif name == "delete_directory":
            path = safe_path(arguments["path"])
            recursive = arguments.get("recursive", False)
            logger.info(f"delete_directory: {path} (recursive={recursive})")
            if not path.exists():
                return [types.TextContent(type="text", text=f"Directory not found: {path}")]
            if not path.is_dir():
                return [types.TextContent(type="text", text=f"'{path}' is not a directory. Use delete_file instead.")]
            if recursive:
                shutil.rmtree(str(path))
            else:
                path.rmdir()  # Raises if non-empty
            return [types.TextContent(type="text", text=f"Deleted directory: {path}")]

        elif name == "create_directory":
            path = safe_path(arguments["path"])
            logger.info(f"create_directory: {path}")
            path.mkdir(parents=True, exist_ok=True)
            return [types.TextContent(type="text", text=f"Directory created: {path}")]

        elif name == "copy_file":
            src = safe_path(arguments["source"])
            dst = safe_path(arguments["destination"])
            logger.info(f"copy_file: {src} → {dst}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            return [types.TextContent(type="text", text=f"Copied {src} → {dst}")]

        elif name == "move_file":
            src = safe_path(arguments["source"])
            dst = safe_path(arguments["destination"])
            logger.info(f"move_file: {src} → {dst}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return [types.TextContent(type="text", text=f"Moved {src} → {dst}")]

        elif name == "search_files":
            directory = safe_path(arguments["directory"])
            pattern = arguments["pattern"]
            logger.info(f"search_files: pattern='{pattern}' in {directory}")
            matches = list(directory.rglob(pattern))
            if not matches:
                return [types.TextContent(type="text", text=f"No files found matching '{pattern}' in {directory}")]
            lines = [str(m) for m in sorted(matches)[:100]]  # limit to 100 results
            return [types.TextContent(type="text", text=f"Found {len(matches)} match(es):\n" + "\n".join(lines))]

        elif name == "get_file_info":
            path = safe_path(arguments["path"])
            logger.info(f"get_file_info: {path}")
            if not path.exists():
                return [types.TextContent(type="text", text=f"Path not found: {path}")]
            stat = path.stat()
            modified = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            info = (
                f"Path     : {path}\n"
                f"Type     : {'File' if path.is_file() else 'Directory'}\n"
                f"Size     : {stat.st_size:,} bytes\n"
                f"Modified : {modified}"
            )
            return [types.TextContent(type="text", text=info)]

        else:
            logger.warning(f"Unknown tool called: {name}")
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except PermissionError as e:
        logger.warning(f"Permission denied: {e}")
        return [types.TextContent(type="text", text=str(e))]
    except Exception as e:
        logger.error(f"Error in tool '{name}': {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
