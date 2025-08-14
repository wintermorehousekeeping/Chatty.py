# tools.py
import asyncio
import os
from typing import Dict, Any

# Assuming google_search is a module with a search function
import google_search

class BaseTool:
    """
    A base class for all tools.
    This provides a common interface for name and description,
    and defines the run() method that all subclasses must implement.
    """
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    async def run(self, **kwargs: Any) -> str:
        """
        Executes the tool's core functionality.
        This method must be implemented by all concrete tool classes.
        """
        raise NotImplementedError("Subclasses must implement the 'run' method.")

class GoogleSearchTool(BaseTool):
    """
    A tool for performing Google searches.
    """
    def __init__(self):
        super().__init__(
            name="google_search",
            description="Searches for information on Google. Arguments: 'query' (str)."
        )

    async def run(self, query: str) -> str:
        """
        Performs a Google search using the provided query.
        """
        print(f"Searching Google for: '{query}'")
        try:
            # The google_search.search function is assumed to be an external
            # library or module that needs to be run in a separate thread.
            search_results_list = await asyncio.to_thread(google_search.search, queries=[query])

            if not search_results_list or not search_results_list[0].results:
                return "No search results found."

            context_snippets = [r.snippet for r in search_results_list[0].results if r.snippet]
            if not context_snippets:
                return "I found results, but no useful snippets to answer your question."
            
            # Join the snippets for a coherent response.
            return "\n".join(context_snippets)
        except Exception as e:
            return f"An error occurred while executing the Google Search tool: {e}"

class FileTool(BaseTool):
    """
    A tool for performing file operations like reading and writing.
    """
    def __init__(self):
        super().__init__(
            name="file_tool",
            description="Performs file operations. Arguments: 'action' (str), 'filename' (str), 'content' (str)."
        )

    async def run(self, action: str, filename: str, content: str = None) -> str:
        """
        Executes a file operation (read or write) based on the 'action'.
        """
        if action == "read":
            return await self._read_file(filename)
        elif action == "write":
            if content is None:
                return "Error: 'content' argument is required for 'write' action."
            return await self._write_file(filename, content)
        else:
            return f"Error: Invalid action '{action}'. Use 'read' or 'write'."

    async def _read_file(self, filename: str) -> str:
        """
        Reads a file from the local file system in a separate thread.
        """
        try:
            def sync_read():
                with open(filename, 'r') as f:
                    return f.read()
            
            content = await asyncio.to_thread(sync_read)
            return f"File '{filename}' content:\n---\n{content}\n---"
        except FileNotFoundError:
            return f"Error: File not found at '{filename}'."
        except Exception as e:
            return f"Error reading file '{filename}': {e}"

    async def _write_file(self, filename: str, content: str) -> str:
        """
        Writes content to a file on the local file system in a separate thread.
        """
        try:
            def sync_write():
                with open(filename, 'w') as f:
                    f.write(content)

            await asyncio.to_thread(sync_write)
            return f"Content successfully written to '{filename}'."
        except Exception as e:
            return f"Error writing to file '{filename}': {e}"


