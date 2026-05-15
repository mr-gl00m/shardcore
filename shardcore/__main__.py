"""Dispatch `python -m shardcore <subcommand>`.

Subcommands:
    verify   Validate a .shard bundle against the spec (manifest SHA-256, pillar schemas).
    neuron   Run the Neuronshard reference tick engine on a bundle.
"""
import sys


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m shardcore <verify|neuron> [args...]", file=sys.stderr)
        return 2
    cmd, rest = argv[1], argv[2:]
    if cmd == "verify":
        from shardcore import verify
        return verify.main(rest)
    if cmd == "neuron":
        from shardcore import neuron
        return neuron.main(rest)
    print(f"unknown subcommand: {cmd}", file=sys.stderr)
    return 2


def _cli_entry() -> None:
    sys.exit(main(sys.argv))


if __name__ == "__main__":
    _cli_entry()
