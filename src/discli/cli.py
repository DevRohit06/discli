import click


@click.group()
@click.option("--token", envvar="DISCORD_BOT_TOKEN", default=None, help="Discord bot token.")
@click.option("--json", "use_json", is_flag=True, default=False, help="Output as JSON.")
@click.pass_context
def main(ctx, token, use_json):
    """discli — Discord CLI for AI agents."""
    ctx.ensure_object(dict)
    ctx.obj["token"] = token
    ctx.obj["use_json"] = use_json
