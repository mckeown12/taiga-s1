## Option A (single tweet)

Taiga-S1: a 1.2M-param model, trained from scratch, that drives FreeCAD. No LLM, no screenshots: it reads the feature tree and picks the next command in ~1ms.

Trained on parts with ≤5 features, it builds 11-feature parts (~55 commands) at 100%, and 17-feature parts at 95%. My previous version: 0%.

🤗 https://huggingface.co/shhivv/taiga-s1

## Option B (thread)

1/ Meet Taiga-S1, a tiny "System 1" model for CAD: 1.2M params, from scratch, no LLM, no vision. It reads FreeCAD's structured state and scores the valid commands in ~1ms.

🤗 https://huggingface.co/shhivv/taiga-s1

2/ v1 looked perfect, at 100% on test goals. Then I checked: 99% of those goals reused recipes it had already seen. On longer parts it scored 0%.

3/ So I built held-out tests: longer parts (up to 11 features vs ≤5 in training) and feature combinations it never saw. Then I ran ~12 ablations.

4/ What worked:
- randomized position IDs (Ruoss et al.)
- "coupled ordinals" linking each goal item to the tree
- a modular policy: each goal item asks "am I built yet?", and the model acts on the first that isn't

→ 11-feature parts: 0% → 100%

5/ What didn't: a progress-pointer head, length-invariant features, and a softmax pointer, which has to learn "next = built + 1" and broke past the trained length.

6/ It also drives the real FreeCAD app live. Fastest way to see it: FreeCAD on one side, the model building parts on the other.

Code + full eval: GITHUB_LINK
