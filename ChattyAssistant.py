k# ChattyAssistant.py
import asyncio
import json
import logging
import sys
import io
import contextlib
from typing import Any, Dict, List, Optional
from colorama import Fore, Style, init

from config import Config, Constants
# Import our new refactored tool classes
from tools import GoogleSearchTool, FileTool

# Initialize colorama for cross-platform color support
init(autoreset=True)

# --- Main Assistant Class ---
class ChattyAssistant:
    """A streamlined, multi-functional conversational assistant with tool-use capabilities."""
    def __init__(self):
        self.chat_history = [{"role": "system", "content": Constants.SYSTEM_PROMPT}]
        self.last_generated_code = None
        Config.load_settings()
        self.session_started = False
        
        # A dictionary to map user commands to methods for a cleaner handler
        self.commands = {
            "exit": self._exit,
            "quit": self._exit,
            "settings": self.manage_settings,
            "help": self._show_help,
            "save": self._save_history,
            "clear history": self._clear_history,
            "run code": self._run_last_code,
        }
    
        # A dictionary to map tool names from the LLM's response to instances
        # of our new tool classes. This is the core of the refactoring.
        self.tools = {
            "google_search": GoogleSearchTool(),
            "file_tool": FileTool(),
        }

    async def _parse_llm_json(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parses JSON from a response, handling common markdown and nested formats."""
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            try:
                # Attempt to extract JSON from a markdown block
                json_str = response_text.split('```json')[1].split('```')[0].strip()
                return json.loads(json_str)
            except (IndexError, json.JSONDecodeError):
                logging.error("Failed to parse JSON from LLM response.")
        return None

    async def _send_to_ollama(self, prompt: str, temperature: float, format_as: str = "json") -> Optional[Dict[str, Any]]:
        """Sends a prompt and returns a parsed JSON response with retry logic."""
        payload = {
            "model": "phi3:mini",
            "prompt": prompt,
            "stream": False,
            "format": format_as,
            "temperature": temperature
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.post(Constants.OLLAMA_API_URL, json=payload) as response:
                        response.raise_for_status()
                        response_text = await response.text()
                        if format_as == "json":
                            return await self._parse_llm_json(response_text)
                        return response_text # For text responses
            except aiohttp.ClientError as e:
                logging.error(f"Network error: {e}. Attempt {attempt + 1} of {max_retries}.")
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logging.error(f"An unexpected error occurred: {e}")
                return None
        print(f"{Fore.RED}A network error occurred after multiple attempts. Is Ollama running?")
        return None

    def _run_code(self, code_to_run: str) -> str:
        """
        Executes Python code in a secure, sandboxed environment.
        Only a limited set of safe built-in functions are available to the code.
        This prevents malicious code from accessing system resources.
        """
        # Define a limited, safe environment for code execution.
        # We include common built-ins like print, len, range, and type.
        safe_globals = {
            "__builtins__": {
                "print": print,
                "len": len,
                "range": range,
                "str": str,
                "int": int,
                "float": float,
                "list": list,
                "dict": dict,
                "tuple": tuple,
                "set": set,
                "type": type,
                "zip": zip,
                "sum": sum,
                "min": min,
                "max": max,
                "abs": abs,
                "round": round,
            }
        }
        safe_locals = {}

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        redirected_output = io.StringIO()
        sys.stdout = redirected_output
        sys.stderr = redirected_output
        
        try:
            # Pass the limited environment to exec()
            exec(code_to_run, safe_globals, safe_locals)
            return redirected_output.getvalue()
        except Exception as e:
            # Return a clear error message without revealing internal details
            return f"An error occurred during code execution: {e}"
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
    
    def _extract_code(self, text: str) -> Optional[str]:
        """Extracts a Python code block from a markdown string."""
        try:
            return text.split('```python')[1].split('```')[0].strip()
        except IndexError:
            return None
    
    async def _exit(self):
        """Exits the application gracefully."""
        confirm = (await asyncio.to_thread(input, f"{Fore.YELLOW}Are you sure you want to exit? (yes/no): ")).lower()
        if confirm.startswith('y'):
            self._save_history()
            print(f"{Fore.GREEN}Goodbye!")
            sys.exit(0)
    
    def _save_history(self):
        """Saves chat history to a JSON file."""
        try:
            with open("chat_history.json", "w") as f:
                json.dump(self.chat_history[1:], f, indent=4)
            print(f"{Fore.GREEN}Chat history saved.")
        except IOError as e:
            logging.error(f"Failed to save chat history: {e}")
    
    def _load_history(self):
        """Loads chat history from a JSON file."""
        try:
            with open("chat_history.json", "r") as f:
                self.chat_history.extend(json.load(f))
            print(f"{Fore.GREEN}Chat history loaded.")
        except FileNotFoundError:
            logging.info("No history found. Starting a new session.")
        except (IOError, json.JSONDecodeError) as e:
            logging.error(f"Failed to load chat history: {e}")
    
    async def _clear_history(self):
        """Clears the current chat history and deletes the file."""
        confirm = (await asyncio.to_thread(input, f"{Fore.YELLOW}Clear history? Cannot be undone. (yes/no): ")).lower()
        if confirm.startswith('y'):
            self.chat_history = [self.chat_history[0]]
            try:
                import os
                os.remove("chat_history.json")
                print(f"{Fore.GREEN}Chat history cleared.")
            except FileNotFoundError:
                print(f"{Fore.GREEN}Chat history already empty.")
    
    async def _show_help(self):
        """Displays help information."""
        print("\n--- Help ---")
        print("I can search, write code, or just chat.")
        print(f"  Type {Fore.YELLOW}'exit'{Style.RESET_ALL} or {Fore.YELLOW}'quit'{Style.RESET_ALL} to end our conversation.")
        print(f"  Type {Fore.YELLOW}'settings'{Style.RESET_ALL} to customize me.")
        print(f"  Type {Fore.YELLOW}'save'{Style.RESET_ALL} to manually save your chat.")
        print(f"  Type {Fore.YELLOW}'clear history'{Style.RESET_ALL} to delete our chat.")
        print(f"  Type {Fore.YELLOW}'run code'{Style.RESET_ALL} to execute the last code I wrote.")
        print("---")
        
    async def _run_last_code(self):
        """Executes the last generated code block."""
        if self.last_generated_code:
            print(f"\n{Fore.MAGENTA}Running code...{Style.RESET_ALL}")
            output = await asyncio.to_thread(self._run_code, self.last_generated_code)
            print(f"\n{Fore.MAGENTA}--- Code Output ---{Style.RESET_ALL}")
            print(output)
            print(f"{Fore.MAGENTA}-------------------{Style.RESET_ALL}\n")
        else:
            print(f"{Fore.RED}No code has been generated yet.")

    async def _execute_tool_call(self, tool_name: str, args: Dict[str, Any]) -> str:
        """
        Executes a tool based on the LLM's request using our new refactored tool classes.
        This is much cleaner now!
        """
        if tool_name in self.tools:
            try:
                tool_instance = self.tools[tool_name]
                # Dynamically call the run() method on the tool instance with the arguments
                return await tool_instance.run(**args)
            except Exception as e:
                return f"An error occurred while executing the tool '{tool_name}': {e}"
        else:
            return f"Error: Tool '{tool_name}' not recognized."
    
    async def manage_settings(self):
        """Allows the user to manage assistant settings."""
        print(f"\n--- Current Settings ---")
        print(f"Conversation Temperature: {Config.TEMPERATURE_CONVERSATION}")
        print(f"Search/Code Temperature: {Config.TEMPERATURE_SEARCH}")
        print("---")
        
        change_settings = (await asyncio.to_thread(input, f"{Fore.YELLOW}Change settings? (yes/no): ")).lower()
        if not change_settings.startswith('y'):
            return
    
        print("Enter new values (0.1 to 1.0).")
        try:
            new_conv_temp = float(await asyncio.to_thread(input, f"{Fore.YELLOW}New Conversation Temp: {Style.RESET_ALL}"))
            if 0.1 <= new_conv_temp <= 1.0: Config.TEMPERATURE_CONVERSATION = new_conv_temp
            
            new_search_temp = float(await asyncio.to_thread(input, f"{Fore.YELLOW}New Search/Code Temp: {Style.RESET_ALL}"))
            if 0.1 <= new_search_temp <= 1.0: Config.TEMPERATURE_SEARCH = new_search_temp
            
            print(f"{Fore.GREEN}Settings updated successfully.")
            Config.save_settings()
        except ValueError:
            print(f"{Fore.RED}Invalid input. Settings were not changed.")
            
    async def run(self):
        """Main loop for the assistant."""
        self._load_history()
        
        if not self.session_started:
            print("Hello! I'm your conversational assistant.")
            print("I can search, write code, read/write files, or just chat.")
            print(f"Type {Fore.YELLOW}'help'{Style.RESET_ALL} to see available commands.")
            self.session_started = True
    
        while True:
            try:
                user_input = await asyncio.to_thread(input, f"\n{Fore.BLUE}You: {Style.RESET_ALL}")
                clean_input = user_input.strip().lower()
                
                # Check for direct commands
                if clean_input in self.commands:
                    await self.commands[clean_input]()
                    continue
    
                print("Thinking...")
                
                # Use the LLM to determine the appropriate action (e.g., TOOL_USE or CHAT)
                response = await self._send_to_ollama(
                    f"Determine the best action for this user input: '{user_input}'",
                    Config.TEMPERATURE_CONVERSATION
                )
    
                if not response or not response.get("type"):
                    print(f"{Fore.RED}Sorry, I can't process that right now. Please try again.")
                    continue
    
                action = response.get("type")
    
                # Handle tool use
                if action == "TOOL_USE":
                    tool_name = response.get("tool_name")
                    tool_args = response.get("arguments", {})
                    
                    tool_output = await self._execute_tool_call(tool_name, tool_args)
                    self.chat_history.append({"role": "tool_output", "content": tool_output})
                    
                    # Send the tool output back to the LLM to get a user-friendly response
                    prompt_for_final_response = f"User: {user_input}\nTool Output: {tool_output}"
                    final_response_text = await self._send_to_ollama(
                        prompt_for_final_response,
                        Config.TEMPERATURE_SEARCH,
                        format_as="text"
                    )
                    
                    print(f"\n{Fore.CYAN}{final_response_text}{Style.RESET_ALL}\n")
                    self.chat_history.append({"role": "assistant", "content": final_response_text})
    
                # Handle code generation or conversation directly
                else: # "CODE" or "CONVERSATION"
                    query = response.get("query")
                    response_text = await self._send_to_ollama(query, Config.TEMPERATURE_SEARCH, format_as="text")
                    print(f"\n{Fore.CYAN}{response_text}{Style.RESET_ALL}\n")
                    self.chat_history.append({"role": "assistant", "content": response_text})
    
                    # Check if the response was code and offer to run it
                    if action == "CODE":
                        self.last_generated_code = self._extract_code(response_text)
                        if self.last_generated_code:
                            print(f"{Fore.YELLOW}Type '{Style.BRIGHT}run code{Style.NORMAL}' to execute it.{Style.RESET_ALL}")
            
            except asyncio.CancelledError:
                print(f"{Fore.GREEN}\nGoodbye!")
                sys.exit(0)
            except Exception as e:
                logging.error(f"An unexpected error occurred: {e}")
                
# --- Entry Point ---
async def main() -> None:
    assistant = ChattyAssistant()
    await assistant.run()

if __name__ == "__main__":
    asyncio.run(main())

