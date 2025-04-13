import asyncio
import sys
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()
        self.file = None
    # methods will go here

    def assign_file(self):
        self.file = "logs.txt"

    def print_u(self, *args):
        if self.file:
            with open(self.file, 'a') as f:
                print(args, file=f)
        else:
            print(args)

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        self.print_u("\nConnected to server with tools:", [tool.name for tool in tools])

    def _check_if_message_is_termination(self, response) -> bool:
        """Check if the response is termination is a termination message"""
        if response is None:
            return False
        content_response = response.content
        for content in content_response:
            if content.type == 'text' and "STOP" in content.text:
                return True
        return False
    
    def _extract_final_text(self, response) -> str:
        if response is None:
            return ""
        content_response = response.content
        final_text = ""
        for content in content_response:
            if content.type == "text":
                final_text += content.text
        return final_text.replace("STOP:", "").strip()

    async def process_query(self, query: str) -> str:
        """Process a query using Claude and available tools"""
        response = await self.session.list_tools()
        available_tools = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]

        system_message = '''You are a helpful data analysis tool that can call tools and respond to user queries.
                    Some user queries may require multiple tool calls in sequence.
                    You can decide to a) call a tool, b) 'CONTINUE' the conversation or c) 'ANALYZE' the conversation and provide a final answer to the user.
                    Add CONTINUE:  or STOP:  as text at the beginning of the response to indicate your choice.
                '''

        messages = [
            {
                "role": "user",
                "content": query
            }
        ]

        response = None
        num_of_calls = 0
        while not self._check_if_message_is_termination(response) and num_of_calls < 10:
            self.print_u("\nSending query to Claude...")
            response = self.anthropic.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                system=system_message,
                messages=messages,
                tools=available_tools
            )
            num_of_calls += 1
            self.print_u("\nResponse received from Claude:")
            for content in response.content:
                if content.type == 'text':
                    self.print_u(content)
                    messages.append({
                        "role": "assistant",
                        "content": content.text
                    })
                elif content.type == 'tool_use':
                    self.print_u(content)
                    tool_name = content.name
                    tool_args = content.input

                    # Execute tool call
                    result = await self.session.call_tool(tool_name, tool_args)
                    messages.append({
                        "role": "assistant",
                        "content": [content]
                    })
                    messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": content.id,
                                "content": result.content
                            }
                        ]
                    })        
        
        final_text = self._extract_final_text(response)
        return final_text

    async def chat_loop(self):
        """Run an interactive chat loop"""
        self.print_u("\nMCP Client Started!")
        self.print_u("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\nQuery: ").strip()

                if query.lower() == 'quit':
                    break

                response = await self.process_query(query)
                self.print_u("\n" + response)

            except Exception as e:
                self.print_u(f"\nError: {str(e)}")

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

async def main():
    if len(sys.argv) < 2:
        self.print_u("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        if len(sys.argv) > 2:
            client.assign_file()
            await client.process_query(sys.argv[2])
        else:
            await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())