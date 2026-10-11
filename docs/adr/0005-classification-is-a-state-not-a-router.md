# Classification is a State, not a router

A Workflow may branch — a bug is diagnosed and fixed, a feature is grilled, specced and ticketed — and something must decide which way a given task goes. Naiad v1 answered this with a routing step it owned: a headless call made before any session existed, whose verdict selected one of four built-in branches.

We decided instead that classification is simply the first State of the Workflow. Its prompt reads the task and announces the head of the appropriate branch, exactly as any other State announces its successor. Choosing a branch is a judgment about the work, and ADR 0001 puts those with the agent; a Workflow that can already send the agent to any of its States can express a branch without Naiad learning anything.

## Consequences

A Workflow is no longer necessarily a straight line. The declared order still supplies the expected next State and defines what gate-skipping steps over, but a branching State declares its candidate successors explicitly, and the branches converge on a shared tail. This is a field on the one or two States that branch — deliberately not a transition graph over all of them, which would put Workflow semantics back inside Naiad.

Because the classifier is an ordinary State it runs in the Run's own interactive session with full access to the codebase, rather than as a one-shot headless call. When the branch is already known, starting the Run at a later State skips classification entirely.
