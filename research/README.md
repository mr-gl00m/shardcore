# Research Grounding

This folder documents the published research that grounds SHARDCORE's
design decisions. Each entry names the paper, summarizes what
architectural choice it informs, and points at the spec section that
cites it.

**We do not redistribute third-party papers in this repo.** Readers
should retrieve each source from its canonical publisher. Links below
are the intended canonical sources; if a link is broken or missing,
search the title + authors.

Grounding is citation of influence, not proof of behavior. The way a
shard behaves is whatever its runtime computes; these papers explain
*why the choices were made*.

---

## 1. Drosophila connectome + LIF dynamics

**What it grounds:** Neuronshard's leaky-integrate-and-fire substrate
(§6), including the choice of `V_REST = -52 mV`, `V_THRESHOLD = -45 mV`,
`TAU_MEMBRANE = 20 ms`, `TAU_SYNAPSE = 5 ms`, `T_REFRACTORY = 2.2 ms`,
and Poisson-noise injection on identity-anchor nodes.

**Why it's relevant:** The fly connectome demonstrates that
biologically-plausible behavior can emerge from a sparse weighted graph
of LIF neurons with no explicit rule machinery, the substrate we want
for shards. A shard's personality is not a rule set; it is topology +
dynamics over that topology.

**Internal notes:** See `proj_cortex/What the Fly Brain Actually Teaches.txt`
(not in this public release) for the working notes that translated the
connectome model's constants into SHARDCORE's spec numbers.

**Canonical source:** Scheffer et al., "A connectome and analysis of the
adult Drosophila central brain" (eLife, 2020), and subsequent
connectome releases by the FlyEM / Janelia team. Pair with the
FlyWire whole-brain connectome (Dorkenwald et al., 2024).

---

## 2. Reservoir computing with memristors

**What it grounds:** The viability argument for a small recurrent system
holding continuous spatiotemporal state, and the long-term roadmap
entry (ROADMAP §2.3) for swappable reservoir-style back-ends behind
the stable Neuronshard I/O interface.

**Why it's relevant:** Reservoir computing shows that a sparsely-connected
recurrent network with fixed random internal weights can compute useful
transformations without training the internal recurrence, exactly the
regime where SHARDCORE's per-shard derived topology operates. The
memristor hardware work demonstrates this is not just theoretical.

**Canonical source:** "Scalable platform enabling reservoir computing
with nanoporous oxide memristors for image recognition and time series
prediction." Locate via the authors' publication venue (search title
on the publisher or on arXiv).

---

## 3. Neuromorphic bridge from biological hearing

**What it grounds:** The philosophical commitment to event-driven sparse
computation over dense feed-forward evaluation, and why Neuronshard emits
spikes on threshold crossings instead of producing continuous activations
every tick.

**Why it's relevant:** Biological audition achieves extraordinary
efficiency through spike timing and sparsity. The paper's framing of
when event-based computation wins over dense computation is directly
applicable to a system that expects to tick forever on modest hardware.

**Canonical source:** "Bridging Biological Hearing and Neuromorphic
Computing." Locate via the authors' publication venue.

---

## 4. Neuro-symbolic AI (Amazon Nova 2 Lite)

**What it grounds:** §14 (Neuro-Symbolic Validation Rules,
EXPERIMENTAL). The idea that LLM fluid reasoning should be paired with
a symbolic layer that produces *verifiable* outputs directly motivates
the AST-whitelisted rule evaluator slated for v1.1.

**Why it's relevant:** A shard runtime is a neuro-symbolic system by
construction: the LLM supplies fluid reasoning, the shard's structured
pillars (stat_block, interest_graph, validation_rules) supply the
symbolic constraints. This paper describes the pattern we are building
toward.

**Canonical source:** "How Neuro-Symbolic AI Breaks the Limits of LLMs"
(Amazon Science / Amazon Nova 2 Lite announcement). Locate via the
Amazon Science blog or the Nova 2 Lite technical announcement.

---

## 5. Functional introspection in language models

**What it grounds:** §13 (Introspection Surface, EXPERIMENTAL). The
claim is that capable LLMs have meaningful functional introspective
access to their own activations. SHARDCORE's introspection surface is
designed so that when an LLM running a shard reports on its internal
state, the statements can be grounded in **actual** data structures
(drives, chemistry, firing nodes) rather than in templated self-talk.

**Why it's relevant:** If introspection reports are sourced causally
from the shard's real state, the accuracy / grounding / internality
criteria from this research line are satisfied by construction.

**Canonical source:** Anthropic research publication on introspection /
activation steering / circuit-level self-reports. Locate via
anthropic.com/research.

---

## 6. Generative agents (Smallville)

**What it grounds:** The tiered memory design (§5 short-term /
long-term / core / archive) and the dream-consolidation pass (§12).
Park et al. demonstrated that a memory-stream with reflection and
importance-weighted retrieval produces persistent-seeming characters.
SHARDCORE's mindshard is a statically-checkable, file-portable
evolution of that architecture.

**Why it's relevant:** The memory tiers, the consolidation pass, and
the notion that recent activity biases future retrieval all trace
back to this paper's demonstrated patterns. SHARDCORE fixes them in a
portable file format so different runtimes can reproduce the same
character behavior.

**Canonical source:** Park et al., "Generative Agents: Interactive
Simulacra of Human Behavior," [arXiv:2304.03442](https://arxiv.org/abs/2304.03442).

---

## How to add to this folder

When a new paper meaningfully grounds a design decision:

1. Add an entry here with the same shape: *what it grounds*, *why it
   matters*, *canonical source*.
2. Add a `[N]` citation in the corresponding spec section.
3. Do **not** commit PDFs or article text unless the paper is under a
   license that explicitly permits redistribution (e.g., arXiv papers
   under CC-BY are fine; publisher PDFs generally are not).
