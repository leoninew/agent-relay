import click

from conflua.interfaces.client import ConfluaClient


@click.command("mcp", help="启动 stdio MCP 服务，连接同一 Conflua HTTP 服务")
@click.pass_obj
def mcp_server(client: ConfluaClient) -> None:
    from conflua.interfaces.mcp import create_mcp_server

    create_mcp_server(client).run(transport="stdio")
