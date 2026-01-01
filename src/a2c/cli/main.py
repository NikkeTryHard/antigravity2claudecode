"""
a2c CLI - Main entry point.

Provides commands for:
- serve: Start the proxy server
- code: Launch Claude Code with a2c proxy
- status: Show status dashboard
- config: Manage configuration
"""

import typer
from rich.console import Console

app = typer.Typer(
    name="a2c",
    help="AI API Router - Route requests to multiple AI providers",
    add_completion=True,
)
console = Console()


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Bind host"),
    port: int = typer.Option(8080, "--port", "-p", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable hot reload"),
    log_level: str = typer.Option("INFO", "--log-level", "-l", help="Log level"),
) -> None:
    """Start the a2c proxy server."""
    import logging
    import os

    import uvicorn

    # Set environment variables for settings
    os.environ["A2C_HOST"] = host
    os.environ["A2C_PORT"] = str(port)
    os.environ["A2C_LOG_LEVEL"] = log_level

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    console.print(f"[bold green]Starting a2c server on {host}:{port}[/bold green]")
    console.print(f"[dim]Log level: {log_level}[/dim]")
    console.print(f"[dim]Reload: {reload}[/dim]")
    console.print()

    uvicorn.run(
        "a2c.server.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level.lower(),
    )


@app.command()
def code(
    provider: str = typer.Option("antigravity", "--provider", "-p", help="Provider to use"),
    model: str = typer.Option(None, "--model", "-m", help="Model to use"),
    thinking: bool = typer.Option(
        True, "--thinking/--no-thinking", help="Enable extended thinking"
    ),
) -> None:
    """Launch Claude Code with a2c as proxy."""
    import os
    import subprocess
    import sys

    from a2c.server.config import get_settings

    settings = get_settings()
    proxy_url = f"http://{settings.server.host}:{settings.server.port}"

    console.print("[bold]Launching Claude Code with a2c proxy[/bold]")
    console.print(f"[dim]Proxy URL: {proxy_url}[/dim]")
    console.print(f"[dim]Provider: {provider}[/dim]")
    if model:
        console.print(f"[dim]Model: {model}[/dim]")
    console.print()

    # Set environment for Claude Code
    env = os.environ.copy()
    env["ANTHROPIC_BASE_URL"] = proxy_url
    env["ANTHROPIC_API_KEY"] = "a2c-proxy"  # Dummy key, real key is in provider

    # Add agent type header
    env["X_AGENT_TYPE"] = "code"

    # Build claude command
    cmd = ["claude"]
    if model:
        cmd.extend(["--model", model])

    try:
        subprocess.run(cmd, env=env, check=True)
    except FileNotFoundError:
        console.print("[red]Error: 'claude' command not found.[/red]")
        console.print(
            "[dim]Make sure Claude Code is installed: npm install -g @anthropic-ai/claude-code[/dim]"
        )
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)


@app.command()
def status(
    live: bool = typer.Option(False, "--live", "-l", help="Enable live updates"),
    interval: float = typer.Option(2.0, "--interval", "-i", help="Update interval in seconds"),
) -> None:
    """Show server status dashboard."""
    import time

    import httpx
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table

    from a2c.server.config import get_settings

    settings = get_settings()
    base_url = f"http://{settings.server.host}:{settings.server.port}"

    def make_layout() -> Layout:
        """Create the dashboard layout."""
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3),
        )
        layout["main"].split_row(
            Layout(name="left"),
            Layout(name="right"),
        )
        layout["left"].split_column(
            Layout(name="providers"),
            Layout(name="routing", size=10),
        )
        layout["right"].split_column(
            Layout(name="stats"),
            Layout(name="recent", size=12),
        )
        return layout

    def get_server_status() -> dict:
        """Fetch server status."""
        try:
            with httpx.Client(timeout=5.0) as client:
                health = client.get(f"{base_url}/health").json()
                providers = client.get(f"{base_url}/health/providers").json()
                # Try to get debug stats if available
                try:
                    debug_stats = client.get(f"{base_url}/debug/stats", params={"hours": 1}).json()
                    recent_requests = client.get(
                        f"{base_url}/debug/requests", params={"limit": 5}
                    ).json()
                except Exception:
                    debug_stats = None
                    recent_requests = None
                return {
                    "health": health,
                    "providers": providers,
                    "debug_stats": debug_stats,
                    "recent_requests": recent_requests,
                    "error": None,
                }
        except Exception as e:
            return {
                "health": None,
                "providers": None,
                "debug_stats": None,
                "recent_requests": None,
                "error": str(e),
            }

    def render_providers(data: dict) -> Panel:
        """Render providers panel."""
        table = Table(show_header=True, header_style="bold", expand=True)
        table.add_column("Provider")
        table.add_column("Status")
        table.add_column("Latency")
        table.add_column("Features")

        if data.get("error"):
            return Panel(f"[red]Error: {data['error']}[/red]", title="Providers")

        providers = data.get("providers", {}).get("providers", {})
        for name, info in providers.items():
            health_status = info.get("health", {}).get("status", "unknown")
            status_color = {"healthy": "green", "degraded": "yellow", "unhealthy": "red"}.get(
                health_status, "dim"
            )

            latency = info.get("health", {}).get("latency_ms")
            latency_str = f"{latency:.0f}ms" if latency else "-"

            caps = info.get("capabilities", {})
            features = []
            if caps.get("thinking"):
                features.append("think")
            if caps.get("streaming"):
                features.append("stream")
            if caps.get("tools"):
                features.append("tools")

            table.add_row(
                name,
                f"[{status_color}]{health_status}[/{status_color}]",
                latency_str,
                ", ".join(features) if features else "-",
            )

        return Panel(table, title="Providers")

    def render_routing(data: dict) -> Panel:
        """Render routing info panel."""
        content = f"""[bold]Default:[/bold] {settings.routing.default_provider}
[bold]Background:[/bold] {settings.routing.background_provider}
[bold]Think:[/bold] {settings.routing.think_provider}
[bold]Long Context:[/bold] {settings.routing.long_context_provider}"""
        return Panel(content, title="Routing")

    def render_stats(data: dict) -> Panel:
        """Render stats panel."""
        if data.get("error"):
            return Panel(f"[red]Error: {data['error']}[/red]", title="Stats")

        health = data.get("health", {})
        providers_info = health.get("providers", {})
        debug_stats = data.get("debug_stats", {}) or {}

        # Format stats
        total_requests = debug_stats.get("total_requests", 0)
        total_errors = debug_stats.get("total_errors", 0)
        error_rate = debug_stats.get("error_rate", 0)
        avg_latency = debug_stats.get("avg_latency_ms")
        input_tokens = debug_stats.get("total_input_tokens", 0)
        output_tokens = debug_stats.get("total_output_tokens", 0)

        error_color = "green" if error_rate < 0.01 else "yellow" if error_rate < 0.05 else "red"
        latency_str = f"{avg_latency:.0f}ms" if avg_latency else "-"

        content = f"""[bold]Server[/bold]
Status: [green]running[/green]
Port: {settings.server.port}

[bold]Providers[/bold]
Total: {providers_info.get("total", 0)}
Healthy: [green]{providers_info.get("healthy", 0)}[/green]

[bold]Last Hour[/bold]
Requests: {total_requests}
Errors: [{error_color}]{total_errors}[/{error_color}] ({error_rate:.1%})
Avg Latency: {latency_str}
Tokens: {input_tokens:,} in / {output_tokens:,} out"""

        return Panel(content, title="Stats")

    def render_recent(data: dict) -> Panel:
        """Render recent requests panel."""
        table = Table(show_header=True, header_style="bold", expand=True)
        table.add_column("Time", width=8)
        table.add_column("Provider")
        table.add_column("Status", width=6)
        table.add_column("Latency", width=8)

        recent = data.get("recent_requests", {}) or {}
        items = recent.get("items", [])

        if not items:
            return Panel("[dim]No recent requests[/dim]", title="Recent Requests")

        for req in items[:5]:
            time_str = req.get("created_at", "")[-8:]  # Just time portion
            provider = req.get("provider", "-")
            status_code = req.get("status_code")
            latency = req.get("latency_ms")

            status_color = "green" if status_code and 200 <= status_code < 300 else "red"
            latency_str = f"{latency}ms" if latency else "-"

            table.add_row(
                time_str,
                provider,
                f"[{status_color}]{status_code or '-'}[/{status_color}]",
                latency_str,
            )

        return Panel(table, title="Recent Requests")

    def render_dashboard(data: dict) -> Layout:
        """Render the full dashboard."""
        layout = make_layout()
        mode_str = "[green]LIVE[/green]" if live else "[dim]STATIC[/dim]"
        layout["header"].update(
            Panel(
                f"[bold blue]a2c Status Dashboard[/bold blue] - {base_url} {mode_str}",
                style="blue",
            )
        )
        layout["providers"].update(render_providers(data))
        layout["routing"].update(render_routing(data))
        layout["stats"].update(render_stats(data))
        layout["recent"].update(render_recent(data))
        footer_text = (
            "[dim]Press Ctrl+C to exit[/dim]"
            if live
            else "[dim]Use --live for continuous updates[/dim]"
        )
        layout["footer"].update(Panel(footer_text))
        return layout

    if live:
        # Live mode with continuous updates
        try:
            with Live(
                render_dashboard(get_server_status()), refresh_per_second=1, console=console
            ) as live_display:
                while True:
                    time.sleep(interval)
                    data = get_server_status()
                    live_display.update(render_dashboard(data))
        except KeyboardInterrupt:
            console.print("\n[dim]Dashboard stopped[/dim]")
    else:
        # Static mode - just print once
        data = get_server_status()
        console.print(render_dashboard(data))


@app.command()
def config(
    action: str = typer.Argument("show", help="Action: show, init, path"),
) -> None:
    """Manage configuration."""
    from pathlib import Path

    from a2c.server.config import get_settings, get_settings_dict

    if action == "show":
        settings = get_settings_dict()
        console.print_json(data=settings)

    elif action == "init":
        config_path = Path("config.yaml")
        if config_path.exists():
            console.print(f"[yellow]Config file already exists: {config_path}[/yellow]")
            return

        default_config = """# a2c Configuration
server:
  host: 127.0.0.1
  port: 8080
  log_level: INFO
  debug_enabled: true

routing:
  long_context_threshold: 100000
  default_provider: anthropic
  background_provider: antigravity
  think_provider: antigravity
  long_context_provider: gemini
  websearch_provider: gemini

# Provider credentials are set via environment variables:
# ANTHROPIC_API_KEY=sk-ant-...
# GOOGLE_API_KEY=...
# OPENAI_API_KEY=sk-...
"""
        config_path.write_text(default_config)
        console.print(f"[green]Created config file: {config_path}[/green]")

    elif action == "path":
        settings = get_settings()
        if settings.server.config_path:
            console.print(str(settings.server.config_path))
        else:
            console.print("[dim]No config file specified[/dim]")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("[dim]Available actions: show, init, path[/dim]")


@app.command()
def version() -> None:
    """Show version information."""
    from a2c import __version__

    console.print(f"a2c version {__version__}")


@app.command()
def route(
    action: str = typer.Argument("list", help="Action: list, show, test"),
    name: str | None = typer.Option(None, "--name", "-n", help="Rule name"),
    agent_type: str | None = typer.Option(None, "--agent", "-a", help="Agent type for test"),
    model: str | None = typer.Option(None, "--model", "-m", help="Model for test"),
) -> None:
    """Manage routing rules."""
    import httpx

    from a2c.server.config import get_settings

    settings = get_settings()
    base_url = f"http://{settings.server.host}:{settings.server.port}"

    if action == "list":
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{base_url}/admin/routing/rules")
                if response.status_code == 200:
                    rules = response.json().get("rules", [])
                    if not rules:
                        console.print("[dim]No routing rules configured[/dim]")
                        return

                    from rich.table import Table

                    table = Table(show_header=True, header_style="bold")
                    table.add_column("Priority")
                    table.add_column("Name")
                    table.add_column("Condition")
                    table.add_column("Provider")

                    for rule in rules:
                        table.add_row(
                            str(rule.get("priority", 0)),
                            rule.get("name", "-"),
                            rule.get("condition", "-"),
                            rule.get("provider", "-"),
                        )

                    console.print(table)
                else:
                    console.print(f"[red]Error: {response.text}[/red]")
        except Exception as e:
            console.print(f"[red]Error connecting to server: {e}[/red]")

    elif action == "show":
        if not name:
            console.print("[red]Error: --name is required for show action[/red]")
            return

        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{base_url}/admin/routing/rules/{name}")
                if response.status_code == 200:
                    console.print_json(data=response.json())
                else:
                    console.print(f"[red]Rule not found: {name}[/red]")
        except Exception as e:
            console.print(f"[red]Error connecting to server: {e}[/red]")

    elif action == "test":
        # Test which provider would be selected for given conditions
        try:
            with httpx.Client(timeout=5.0) as client:
                params = {}
                if agent_type:
                    params["agent_type"] = agent_type
                if model:
                    params["model"] = model

                response = client.get(f"{base_url}/admin/routing/test", params=params)
                if response.status_code == 200:
                    result = response.json()
                    console.print(
                        f"[bold]Selected Provider:[/bold] {result.get('provider', 'unknown')}"
                    )
                    if result.get("matched_rule"):
                        console.print(f"[dim]Matched Rule: {result.get('matched_rule')}[/dim]")
                else:
                    console.print(f"[red]Error: {response.text}[/red]")
        except Exception as e:
            console.print(f"[red]Error connecting to server: {e}[/red]")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("[dim]Available actions: list, show, test[/dim]")


@app.command()
def provider(
    action: str = typer.Argument("list", help="Action: list, show, health"),
    name: str | None = typer.Option(None, "--name", "-n", help="Provider name"),
) -> None:
    """Manage providers."""
    import httpx

    from a2c.server.config import get_settings

    settings = get_settings()
    base_url = f"http://{settings.server.host}:{settings.server.port}"

    if action == "list":
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{base_url}/health/providers")
                if response.status_code == 200:
                    providers = response.json().get("providers", {})

                    from rich.table import Table

                    table = Table(show_header=True, header_style="bold")
                    table.add_column("Provider")
                    table.add_column("Status")
                    table.add_column("Configured")
                    table.add_column("Latency")

                    for pname, info in providers.items():
                        health = info.get("health", {})
                        status = health.get("status", "unknown")
                        status_color = {
                            "healthy": "green",
                            "degraded": "yellow",
                            "unhealthy": "red",
                        }.get(status, "dim")
                        configured = (
                            "[green]Yes[/green]" if info.get("configured") else "[red]No[/red]"
                        )
                        latency = health.get("latency_ms")
                        latency_str = f"{latency:.0f}ms" if latency else "-"

                        table.add_row(
                            pname,
                            f"[{status_color}]{status}[/{status_color}]",
                            configured,
                            latency_str,
                        )

                    console.print(table)
                else:
                    console.print(f"[red]Error: {response.text}[/red]")
        except Exception as e:
            console.print(f"[red]Error connecting to server: {e}[/red]")

    elif action == "show":
        if not name:
            console.print("[red]Error: --name is required for show action[/red]")
            return

        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{base_url}/health/providers")
                if response.status_code == 200:
                    providers = response.json().get("providers", {})
                    if name in providers:
                        console.print_json(data=providers[name])
                    else:
                        console.print(f"[red]Provider not found: {name}[/red]")
                else:
                    console.print(f"[red]Error: {response.text}[/red]")
        except Exception as e:
            console.print(f"[red]Error connecting to server: {e}[/red]")

    elif action == "health":
        # Refresh health checks
        try:
            with httpx.Client(timeout=10.0) as client:
                console.print("[dim]Checking provider health...[/dim]")
                response = client.get(f"{base_url}/health/providers")
                if response.status_code == 200:
                    providers = response.json().get("providers", {})

                    for pname, info in providers.items():
                        health = info.get("health", {})
                        status = health.get("status", "unknown")
                        if status == "healthy":
                            console.print(f"[green]✓[/green] {pname}: {status}")
                        elif status == "degraded":
                            console.print(f"[yellow]![/yellow] {pname}: {status}")
                        else:
                            console.print(f"[red]✗[/red] {pname}: {status}")
                else:
                    console.print(f"[red]Error: {response.text}[/red]")
        except Exception as e:
            console.print(f"[red]Error connecting to server: {e}[/red]")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("[dim]Available actions: list, show, health[/dim]")


@app.command()
def logs(
    action: str = typer.Argument("tail", help="Action: tail, show"),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    level: str = typer.Option("INFO", "--level", "-l", help="Minimum log level"),
) -> None:
    """View server logs."""
    import time

    import httpx

    from a2c.server.config import get_settings

    settings = get_settings()
    base_url = f"http://{settings.server.host}:{settings.server.port}"

    if action == "tail":
        try:
            with httpx.Client(timeout=5.0) as client:
                # Fetch recent requests as a proxy for logs
                response = client.get(f"{base_url}/debug/requests", params={"limit": lines})
                if response.status_code == 200:
                    requests = response.json().get("items", [])

                    if not requests:
                        console.print("[dim]No recent requests[/dim]")
                        if follow:
                            console.print("[dim]Waiting for requests... (Ctrl+C to exit)[/dim]")

                    for req in reversed(requests):
                        _print_log_entry(req, console)

                    if follow:
                        last_id = requests[0]["id"] if requests else None
                        while True:
                            time.sleep(1)
                            response = client.get(
                                f"{base_url}/debug/requests", params={"limit": 10}
                            )
                            if response.status_code == 200:
                                new_requests = response.json().get("items", [])
                                for req in reversed(new_requests):
                                    if req["id"] != last_id:
                                        _print_log_entry(req, console)
                                        last_id = req["id"]
                else:
                    console.print(f"[red]Error: {response.text}[/red]")
        except KeyboardInterrupt:
            console.print("\n[dim]Stopped[/dim]")
        except Exception as e:
            console.print(f"[red]Error connecting to server: {e}[/red]")

    elif action == "show":
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{base_url}/debug/requests", params={"limit": lines})
                if response.status_code == 200:
                    requests = response.json().get("items", [])

                    from rich.table import Table

                    table = Table(show_header=True, header_style="bold")
                    table.add_column("Time")
                    table.add_column("Request ID")
                    table.add_column("Provider")
                    table.add_column("Model")
                    table.add_column("Status")
                    table.add_column("Latency")

                    for req in requests:
                        status = req.get("status_code", "-")
                        status_color = "green" if status and 200 <= status < 300 else "red"
                        latency = req.get("latency_ms")
                        latency_str = f"{latency}ms" if latency else "-"

                        table.add_row(
                            req.get("created_at", "-")[:19],
                            req.get("request_id", "-"),
                            req.get("provider", "-"),
                            req.get("model", "-") or "-",
                            f"[{status_color}]{status}[/{status_color}]",
                            latency_str,
                        )

                    console.print(table)
                else:
                    console.print(f"[red]Error: {response.text}[/red]")
        except Exception as e:
            console.print(f"[red]Error connecting to server: {e}[/red]")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("[dim]Available actions: tail, show[/dim]")


def _print_log_entry(req: dict, console: Console) -> None:
    """Print a single log entry."""
    time_str = req.get("created_at", "")[:19]
    request_id = req.get("request_id", "")
    provider = req.get("provider", "")
    model = req.get("model", "") or ""
    status = req.get("status_code")
    latency = req.get("latency_ms")

    status_color = "green" if status and 200 <= status < 300 else "red"
    latency_str = f"{latency}ms" if latency else "-"

    console.print(
        f"[dim]{time_str}[/dim] [{status_color}]{status}[/{status_color}] "
        f"{request_id} → {provider} ({model}) [{latency_str}]"
    )


@app.command()
def debug(
    action: str = typer.Argument("list", help="Action: list, show, stats, cleanup"),
    request_id: str | None = typer.Option(None, "--id", "-i", help="Request ID"),
    limit: int = typer.Option(20, "--limit", "-n", help="Number of items"),
    hours: int = typer.Option(24, "--hours", help="Hours for stats"),
) -> None:
    """Debug stored requests."""
    import httpx

    from a2c.server.config import get_settings

    settings = get_settings()
    base_url = f"http://{settings.server.host}:{settings.server.port}"

    if action == "list":
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{base_url}/debug/requests", params={"limit": limit})
                if response.status_code == 200:
                    data = response.json()
                    requests = data.get("items", [])
                    total = data.get("total", 0)

                    from rich.table import Table

                    table = Table(
                        show_header=True,
                        header_style="bold",
                        title=f"Requests ({len(requests)}/{total})",
                    )
                    table.add_column("Request ID")
                    table.add_column("Time")
                    table.add_column("Provider")
                    table.add_column("Model")
                    table.add_column("Status")
                    table.add_column("Latency")
                    table.add_column("Tokens")

                    for req in requests:
                        status = req.get("status_code", "-")
                        status_color = "green" if status and 200 <= status < 300 else "red"
                        latency = req.get("latency_ms")
                        latency_str = f"{latency}ms" if latency else "-"

                        input_tokens = req.get("input_tokens")
                        output_tokens = req.get("output_tokens")
                        if input_tokens and output_tokens:
                            tokens = f"{input_tokens}/{output_tokens}"
                        else:
                            tokens = "-"

                        table.add_row(
                            req.get("request_id", "-"),
                            req.get("created_at", "-")[:19],
                            req.get("provider", "-"),
                            req.get("model", "-") or "-",
                            f"[{status_color}]{status}[/{status_color}]",
                            latency_str,
                            tokens,
                        )

                    console.print(table)
                else:
                    console.print(f"[red]Error: {response.text}[/red]")
        except Exception as e:
            console.print(f"[red]Error connecting to server: {e}[/red]")

    elif action == "show":
        if not request_id:
            console.print("[red]Error: --id is required for show action[/red]")
            return

        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{base_url}/debug/requests/{request_id}")
                if response.status_code == 200:
                    console.print_json(data=response.json())
                else:
                    console.print(f"[red]Request not found: {request_id}[/red]")
        except Exception as e:
            console.print(f"[red]Error connecting to server: {e}[/red]")

    elif action == "stats":
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{base_url}/debug/stats", params={"hours": hours})
                if response.status_code == 200:
                    stats = response.json()

                    console.print(f"\n[bold]Stats for last {hours} hours[/bold]\n")
                    console.print(f"Total Requests: {stats.get('total_requests', 0)}")
                    console.print(f"Total Errors: {stats.get('total_errors', 0)}")

                    error_rate = stats.get("error_rate", 0)
                    error_color = (
                        "green" if error_rate < 0.01 else "yellow" if error_rate < 0.05 else "red"
                    )
                    console.print(f"Error Rate: [{error_color}]{error_rate:.1%}[/{error_color}]")

                    avg_latency = stats.get("avg_latency_ms")
                    if avg_latency:
                        console.print(f"Avg Latency: {avg_latency:.0f}ms")

                    input_tokens = stats.get("total_input_tokens", 0)
                    output_tokens = stats.get("total_output_tokens", 0)
                    console.print(f"Total Tokens: {input_tokens:,} in / {output_tokens:,} out")

                    by_provider = stats.get("by_provider", {})
                    if by_provider:
                        console.print("\n[bold]By Provider:[/bold]")
                        for pname, count in by_provider.items():
                            console.print(f"  {pname}: {count}")
                else:
                    console.print(f"[red]Error: {response.text}[/red]")
        except Exception as e:
            console.print(f"[red]Error connecting to server: {e}[/red]")

    elif action == "cleanup":
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.delete(f"{base_url}/debug/cleanup")
                if response.status_code == 200:
                    result = response.json()
                    console.print(f"[green]{result.get('message', 'Cleanup complete')}[/green]")
                else:
                    console.print(f"[red]Error: {response.text}[/red]")
        except Exception as e:
            console.print(f"[red]Error connecting to server: {e}[/red]")

    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("[dim]Available actions: list, show, stats, cleanup[/dim]")


if __name__ == "__main__":
    app()
