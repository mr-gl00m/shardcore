"""shardcore/neuron@1.1 reference (draft, spec 1.12 section 8): a shard's brain.

    from shardcore.brain import Brain
    brain = Brain.build(soul, mind, seed=1)
    result = brain.deliberate("Dax is at the door", learn=False)   # a probe; she is unchanged
    document = brain.to_dict()                                      # neuronshard.json, version 1.1

Needs numpy. Nothing here reads or writes a bundle.
"""

from .engine import Engine
from .experience import EMOTIONS, Experience
from .wiring import IMPULSES, KINDS, SENSES, VERSION, Brain, Moment, Node, Result, errors

__all__ = ["EMOTIONS", "IMPULSES", "KINDS", "SENSES", "VERSION", "Brain", "Engine", "Experience", "Moment", "Node",
           "Result", "errors"]  # fmt: skip
