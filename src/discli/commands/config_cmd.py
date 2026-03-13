import click

from discli.config import load_config, save_config


@click.group("config")
def config_group():
    """Manage discli configuration."""


@config_group.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    """Set a config value (e.g. discli config set token YOUR_TOKEN)."""
    save_config({key: value})
    click.echo(f"Set {key}.")


@config_group.command("show")
@click.pass_context
def config_show(ctx):
    """Show current configuration."""
    import json as json_mod

    data = load_config()
    use_json = ctx.obj.get("use_json", False)
    if use_json:
        click.echo(json_mod.dumps(data, indent=2))
    else:
        if not data:
            click.echo("No configuration set.")
        else:
            for k, v in data.items():
                display = v[:8] + "..." if k == "token" and len(v) > 8 else v
                click.echo(f"{k}: {display}")
