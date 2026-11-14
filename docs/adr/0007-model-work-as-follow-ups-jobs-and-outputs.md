# 0007. Model work as follow-ups, jobs and outputs

- **Status**: Accepted
- **Date**: 2026-11-14
- **Spec**: docs/reviews/review-3.txt, and the owner's description of how they work (below)

## Context

fu began as a safety net for context switching: park task A while switching to task B, then
find it and resume it later. Jobs were added soon after to group parked items, and later grew
into Jira-like work items with kinds such as idea, btw and guide, artifacts, and session
launching. By review 3 (projects, boards, configurable types) the owner had lost track of what
a job was for, because "job" was doing three things: a grouping label, a work item, and a
container for things produced.

The owner described how they actually work. While designing an epic or coding a story, ideas
come up: three in one session, ten across four sessions. Each is a semi-formed thought worth
parking so the current work can carry on. Some relate to the job at hand and some don't. The
job usually mirrors a Jira issue. Over its life it also produces many useful documents
(runbooks, explainers, cheatsheets, review notes), often kept in a gitignored `.temp/` folder
in the repo, that get used again and again and are easy to lose.

## Decision

We will model three things:

- **Follow-up**: a parked, semi-formed idea, captured mid-session in seconds with nothing to
  answer. The agent writes the one-line summary and the why from the session. It records the
  session it came from so the moment can be resumed. It belongs to a job when it relates to
  one: by default the job the session is working on, unless the user says it is unrelated.
  A follow-up can be promoted into a job of its own, as a child of the job it came from.
- **Job**: the container for a piece of work, usually mirroring a Jira issue (its ID is the
  Jira key). Its types describe work: epic, story, bug, spike and task, plus any the user adds.
  Jobs nest like Jira issues. A job collects its follow-ups, the sessions that worked on it,
  and its outputs.
- **Output** (called artifact in the code): something useful a session produced for the job.
  Documents are detected from what sessions wrote, including documents in gitignored folders
  inside a repo; code inside a repo collapses to the repo. The user adds and removes outputs;
  removing one asks first, and a removed detected output stays suppressed.

The idea, btw and guide kinds are retired: an idea is a follow-up, and a cheatsheet or a
runbook is an output. A **project** is the Jira project key in the job's ID (`ML` in `ML-12`),
or a project set by hand for a job without a Jira key. There is no separate board entity: the
Jobs screen lists jobs and the Follow-ups screen (formerly "Board") lists follow-ups.

The test for any new feature: does it make parking faster or surer, make what is parked easier
to find, or make resuming easier? If not, it belongs to a different tool.

## Consequences

Parking stays a zero-question action, which is the whole point of the tool. Jobs no longer
compete with follow-ups for "work I parked". Jira stays the system of record for the work
hierarchy; fu does not try to be a second Jira. Old boards load with retired kinds mapped to
task. Projects need no setup, but a job without a Jira key needs its project set by hand.

## Alternatives considered

- **Projects and boards as their own entities** (review 3 as written): more to manage at the
  moment of parking, and it duplicates Jira. Can be added later if one job list grows too long
  to scan.
- **Follow-ups as plain bookmarks** (where you stopped, how to resume): misses that a follow-up
  is usually a new idea, not the task you were on.
