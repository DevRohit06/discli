import click

from discli.config import load_config
from discli.commands.config_cmd import config_group


@click.group()
@click.option("--token", envvar="DISCORD_BOT_TOKEN", default=None, help="Discord bot token.")
@click.option("--json", "use_json", is_flag=True, default=False, help="Output as JSON.")
@click.pass_context
def main(ctx, token, use_json):
    """discli — Discord CLI for AI agents."""
    ctx.ensure_object(dict)
    if token is None:
        config = load_config()
        token = config.get("token")
    ctx.obj["token"] = token
    ctx.obj["use_json"] = use_json


main.add_command(config_group)
