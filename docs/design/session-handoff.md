# Handing a job to a new session

When you start a new session from the board (shift+R on a job, then New Session), `fu` gives the
agent what the board knows about the job. This page explains what it sends, how, and why.

## The problem

A new session starts with no memory of earlier ones. The board knows things worth passing on: why
the job exists, what is still open, which sessions worked on it and what they produced. Pasting all
of that into the first message gives the agent a wall of text, and it can't tell background from
instructions. It also uses up context on files the task may never need.

## What gets handed over

You tick sections in the dialog. List sections also let you pick single entries (→ on the section).

| Section | What the agent gets | Why it helps |
|---|---|---|
| Why | The job's description | The goal behind the job, so choices fit it |
| Notes | The job's notes, up to 4,000 characters | Decisions and gotchas you wrote down |
| Open follow-ups | Each todo/doing task: summary, why, notes, last worked, folder | The work that is actually unfinished, most active first |
| Parent job | The parent's id, kind, title, status, why, notes, home folder | The bigger goal this piece serves |
| Child jobs | The same for each picked child | What the job is split into, and where each part stands |
| Earlier sessions | Agent, name, last worked, folder, the tasks it carried, and its transcript path | Where to look for detail without replaying old conversations |
| Artifacts | Kind, label and path of each picked deliverable | Runbooks, explainers, skills and repos to build on rather than redo |

The brief also always says:

- which board task the new session is, so it can keep the board current through `fu`
  (`fu add ... --job <id>` to park something, `fu done <id>` to finish a task);
- that it is background, not instructions, and that it was true when the session started.

## How the brief is written

- **Paths, not contents.** Files, folders and transcripts are named by path. The agent opens one
  only when the task needs it, and is told to search long transcripts rather than read them whole.
  This keeps the brief short and avoids stale copies of files.
- **Background first, the task separate.** The brief is labelled as background. Your prompt is
  the task, so the agent doesn't act on old details as if they were orders.
- **Newest first.** Open tasks put the ones you are doing first, and sessions are newest first, so
  the most relevant lines come first.
- **Nothing about itself.** The new session's own task and session are left out of the lists.
- **Saved to disk.** Each brief is written to `<data dir>/briefs/<session id>.md` and linked from
  the task (`brief`), so you can see exactly what the agent was given.

## How it reaches the agent

- **Claude Code**: the brief goes in through `--append-system-prompt-file`. It stays in the system
  prompt, so it survives compaction. The first message is your prompt alone, so a leading `/skill`
  still runs as a skill.
- **Copilot CLI** has no system-prompt option. Its first message (`-i`) is the brief, then a
  `## Your task` heading, then your prompt. A leading `/name` becomes "Use the name skill."
  because a slash command can't follow the brief.
- Both get `--session-id` (so `fu` knows the session before it starts, and can resume it later)
  and `--name "<job id> <title>"` (so the agent's own session list shows the job).

## With no prompt

An empty prompt sends a default task: read the brief, say where the job stands (done, open,
blocked) and suggest a next step, then wait before changing files. This lets the session get its
bearings without editing anything you haven't seen.

## Where the session starts

The folder defaults to the first of these that exists:

1. the job's home folder (set in the job form or with `fu job edit --home`);
2. a repo the job's sessions produced;
3. the parent's home or repo, if the parent is handed over;
4. a child's home or repo, if child jobs are handed over;
5. the folder of the job's latest session;
6. the folder `fu` was started from.

Paths under your home folder are shown with `~`.

## While it runs

The board steps aside (it suspends itself), the agent runs in the same terminal, and the board
comes back when the agent exits. Resuming an earlier session works the same way.

## Limits

- Live Claude Code and Copilot sessions started this way have not been checked end to end. What
  has been checked is that the flags exist (Claude reads the brief file and rejects unknown flags)
  and that the board runs the command and comes back, using a stand-in agent.
- Copilot gets the brief as a message, not a system prompt, so it can lose the brief when the
  conversation is compacted.
- A brief is a snapshot. If the board changes during the session, the agent only sees it through
  `fu`.
