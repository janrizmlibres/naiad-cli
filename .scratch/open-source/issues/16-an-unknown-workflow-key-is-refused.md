# An unknown Workflow key is refused

Type: grilling
Mode: HITL
Status: resolved
Blocked by:

## Question

The Workflow loader ignores keys it does not know: a State declaring `questons = "human"` loads as if the key were absent, and its Questions stay with the default owner without a word. Once outside authors hand-edit these files, and once a file written for a newer Naiad can meet an older one, should an unknown key be refused, and does the file format need a version? Graduated from the map's "Not yet specified" (versioning the Workflow file format).

## Answer

Resolved 2026-09-27 by grilling, while clearing the map's fog.

- **An unknown key is refused at load**, at the top level, in a State and in `[answerer]` alike. The refusal names the key, where it sits (the file, or the State), and the keys allowed there. Refusing is the cheap form of versioning: a file written for a newer Naiad fails loudly on an older one instead of losing its new keys without a word.
- The one load path is used by every caller, so `naiad workflow check`, the writing verbs (which reload after writing and roll back), `queue add`, `run` and the Supervisor all refuse the same way.
- **No version key in this release.** One Naiad reads the file; a version returns only when the format has to break compatibility.
- No ADR: cheap to reverse.
