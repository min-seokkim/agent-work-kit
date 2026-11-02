"""Validation of a check configuration (checks.toml) without running anything."""

from pathlib import PurePosixPath


def relative_file(value):
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or any(p.lower() in ("", ".", "..", ".git") for p in value.split("/"))
            or "\\" in value or ":" in value or "\x00" in value):
        raise ValueError(f"Use a relative path inside the project: {value}")
    return path


def relative_directory(value):
    if not isinstance(value, str):
        raise ValueError("cwd must be a string path relative to the worktree.")
    return PurePosixPath(".") if value == "." else relative_file(value)


def artifact_patterns(settings):
    """Validate `artifacts` and `required_artifacts`: glob patterns relative to the worktree."""
    patterns = {}
    for key in ("artifacts", "required_artifacts"):
        values = settings.get(key, [])
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
            raise ValueError(f"{key} must be an array of relative glob patterns.")
        for value in values:
            relative_file(value.replace("*", "x").replace("?", "x").replace("[", "x").replace("]", "x"))
        patterns[key] = values
    return patterns["artifacts"], patterns["required_artifacts"]


def validate_settings(settings):
    """Validate check configuration without executing commands or creating a worktree."""
    if type(settings.get("schema")) is not int or settings["schema"] != 1:
        raise ValueError("The check configuration needs schema = 1.")
    if settings.get("artifact_storage", "copy") not in ("copy", "shared"):
        raise ValueError('artifact_storage must be "copy" or "shared".')
    timeout = settings.get("timeout_seconds", 300)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 86400:
        raise ValueError("timeout_seconds must be above 0 and at most 86400.")
    checks, setup = settings.get("checks"), settings.get("setup", [])
    if not isinstance(checks, list) or not checks or not isinstance(setup, list):
        raise ValueError("checks must list at least one command.")
    names = set()
    for step in setup + checks:
        if not isinstance(step, dict):
            raise ValueError("Each step must be a table.")
        name, argv = step.get("name"), step.get("argv")
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("Each step needs a distinct name.")
        names.add(name)
        if not isinstance(argv, list) or not argv or any(not isinstance(s, str) for s in argv):
            raise ValueError("argv must be a non-empty array of strings.")
        relative_directory(step.get("cwd", "."))
    custom_env = settings.get("env", {})
    if not isinstance(custom_env, dict) or any(not isinstance(v, str) for v in custom_env.values()):
        raise ValueError("env values must be strings.")
    patterns, required = artifact_patterns(settings)
    return timeout, checks, setup, custom_env, patterns, required
