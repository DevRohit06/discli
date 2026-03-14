import click

from discli.config import load_config
from discli.commands.channel import channel_group
from discli.commands.config_cmd import config_group
from discli.commands.listen import listen_cmd
from discli.commands.member import member_group
from discli.commands.message import message_group
from discli.commands.reaction import reaction_group
from discli.commands.role import role_group
from discli.commands.server import server_group
from discli.commands.typing_cmd import typing_cmd


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


main.add_command(channel_group)
main.add_command(config_group)
main.add_command(listen_cmd)
main.add_command(member_group)
main.add_command(message_group)
main.add_command(reaction_group)
main.add_command(role_group)
main.add_command(server_group)
main.add_command(typing_cmd)
