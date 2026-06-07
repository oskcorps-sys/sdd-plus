"""SDD+ CLI entrypoint."""

import typer
from sdd.cli.commands.status import status
from sdd.cli.commands.validate import validate
from sdd.cli.commands.transition import transition
from sdd.cli.commands.init import init
from sdd.cli.commands.audit import audit
from sdd.cli.commands.new_phase import new_phase
from sdd.cli.commands.projects import app as projects_app
from sdd.cli.commands.install_hooks import install_hooks
from sdd.cli.commands.check_patterns import check_patterns
from sdd.cli.commands.metrics import app as metrics_app
from sdd.cli.commands.dashboard import dashboard
from sdd.cli.commands.doctor import doctor

app = typer.Typer()

# Register commands
app.command()(status)
app.command()(validate)
app.command()(transition)
app.command()(init)
app.command()(audit)
app.command("new-phase")(new_phase)
app.add_typer(projects_app, name="projects")
app.command("install-hooks")(install_hooks)
app.command("check-patterns")(check_patterns)
app.add_typer(metrics_app, name="metrics")
app.command()(dashboard)
app.command()(doctor)


if __name__ == "__main__":
    app()
