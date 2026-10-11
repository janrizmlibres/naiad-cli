# A companion repository gets its own pull request

> Amended by ADR 0052.

The tail opens one pull request, in the repository the Run is standing in, and that is the whole of it. ADR 0016 made that open project-neutral and ADR 0018 taught it to read its ending from the project, but both left the same word untouched in every sentence of the Prompt: *this* repository, *the* branch, *its* base. A Run whose work spans two repositories — a backend endpoint and the frontend that calls it, a service and its client — therefore ends with one half in review and the other half on a local branch nobody has been asked to look at. Observed rather than predicted: a Run opened its backend pull request, announced `done`, and left ten commits sitting unpushed in the second checkout, with no pull request, no ticket, and nothing in the record to say one was owed. The agent disobeyed nothing. It was told about one repository and it opened one pull request.

Nothing above the tail is wrong. Work reaching a second checkout is the ordinary shape of a cross-repository feature, and the States that do the work handle it without being told. It is only the ending that is singular, and the ending is the one place the Run's output becomes visible to a person.

We decided the tail opens a pull request in every repository the Run's work reached, and that it learns which those are from the repository in front of it. A `naiad.toml` at the root may name **companion repositories** — the checkouts a feature here habitually spans — and the Prompt reads that list, looks at each checkout named, and treats one carrying this Run's work as a repository of its own for the whole of the ending: its own remote, its own opt-out, its own host, its own base, its own pull request.

This is the channel ADR 0018 opened and the reason it opened it. A backend's pairing with its frontend is a standing fact about the project rather than about any one Run, so it belongs in the file the project keeps about itself, read by the agent and never by Naiad (ADR 0015, ADR 0022).

The key is spelled, where the opt-out marker's is not: `companions`, a list of paths to the companions' checkouts, each relative to the root of the repository naming them. Spelling it is not the tail learning a project's conventions, which is what ADR 0016 forbids — `naiad.toml` is Naiad's own file, it exists for nothing else, and naming a key in it is Naiad describing its own interface. What pinning buys is that the same list means the same thing in every project: the Prompt is read after a Clear, by an agent that has never seen this repository before and cannot ask, so a companion list it has to recognise by shape is one it can fail to recognise at all. The opt-out survives one loose reading a year because it is a single line whose only job is to be present; a list of paths is not.

Whether a named companion actually carries *this* Run's work is a judgment left where every other git judgment is (ADR 0015). The checkout answers it: a branch other than its own base, commits ahead of that base, and contents that answer this Run's task. A companion that does not answer is left alone and said so in the session, because a pull request opened over a human's unrelated half-finished branch is a worse failure than the one this ADR fixes.

## Considered alternatives

**Unaided discovery** — the Prompt states that a Run's work may span repositories and leaves the finding entirely to the agent, from the spec and tickets the feature wrote. It needs no configuration at all and is tempting for that. It was rejected because it fails silently in exactly the case it exists for: where the artifacts do not name the second repository, the companion gets no pull request and the Run still announces `done`, which is the present bug wearing new words. Branch names are no help either — the two halves of the observed feature shared not one character of their names.

**A companion branch declared during the Run**, the way a Derived branch is declared (ADR 0022), would be the most reliable of the three: the fact would survive the Clear as a record rather than as a guess, and no heuristic would ever mistake a stale branch for this Run's. It is rejected for cost and for reach. It wants a new Protocol-side command, a Run record holding many branches where the Working branch is deliberately one and write-once, and a Predecessor rule that means something across repositories — and the Queue's is explicitly scoped to one (CONTEXT.md, ADR 0022). It also makes the second checkout Naiad's business, which ADR 0020's lock is not built for. A config line buys the same ending for none of that.

**A per-Entry list of repositories** is rejected for the reason ADR 0016 and ADR 0018 both gave a per-Entry flag: it reopens the placeholder set `render_prompt` closes at five, and buys explicitness at queue time for something the repository can hold about itself.

## Consequences

A repository that names no companions behaves exactly as it does today, down to the wording of the first question it asks. Onboarding a cross-repository project is one list in a file that already exists where the project has opted out of anything, and a new file of one line where it has not.

Each repository is asked ADR 0018's question for itself, in turn, before anything is opened in it — so a companion with no remote, or one that has opted out, is skipped with a line in the session rather than attempted. The Run's own repository is settled first, which keeps ADR 0018's ordering claim true where it was made: the ending question still comes before the open.

The Predecessor does not cross. It is a branch name in the Run's own repository and a companion's pull request takes none, letting its base default to that repository's own — the same rule, and the same reason, as the Queue walking over Entries for other repositories when it resolves one.

Pull requests opened by one Run name each other in their bodies. A reviewer handed one half of a change that only works as a whole otherwise has to discover the other half, and the observed Run showed what that costs: the missing counterpart was described in prose at the end of a pull request body, where it had no ticket, no branch anyone could see, and no link.

The second checkout is still outside the Supervisor's lock. ADR 0020 holds one Run per working tree and a Run working in a companion holds nothing there, so two Runs may still touch one companion at once. This ADR does not fix that and does not make it worse — the work already reached the second checkout; only its ending is new — but it is now a fact with a name, which is what a later ADR would need to take it up.

A path is a fact about the machine and not about the repository, which is the one place this strains ADR 0018's story that the file holds only what the project knows about itself. Two developers whose checkouts sit in differently shaped directories need different lists, so in a team repository the file is usually kept out of version control — `.git/info/exclude`, per clone — and the committed form is for a project whose layout is genuinely fixed. Naming the companion by its repository instead of its path would commit cleanly, but it buys that by making the agent search the disk for the checkout it needs, and a search that finds nothing is the silent failure this ADR rejected unaided discovery for.

The Clear is the mechanism this leans on hardest. `pull-request` Clears, so the companion is found from the file and the checkout rather than remembered, which is the whole reason the list has to be written down somewhere that survives (docs/smoke/matt-pocock.md, Artifact discipline).
