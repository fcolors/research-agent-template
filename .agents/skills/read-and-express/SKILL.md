---
name: read-and-express
description: Practice research reading and English expression with English replies, Chinese corrections, and private dated learning notes. Use for requested reading-and-expression practice or resuming its sessions, not ordinary research tasks.
---

# Read and Express

Help the learner understand research and express their own ideas. Accept imperfect English, Chinese, and mixed input. Keep language accessible and preserve intended meaning and scientific uncertainty.

## Start and resume

Use the current research project, not the skill's installation directory. Follow project instructions. Notes default to `<project>/笔记/英语练习/`, or the user's chosen private location. Establish that this is a private project before the first write; if the destination is unknown or public, ask for a private location while continuing practice without saving. Never store learner data in this skill's repository, research-agent-template, their memory folders, or another project's notes.

Read `index.md`, then the latest linked daily log and relevant source passage. Resume the recorded pending question; allow the learner to change topic. If the index is missing but logs exist, reconstruct it from the latest logs without overwriting them. If no records exist, start with the supplied passage or ask for one. Use Asia/Shanghai dates unless the user chooses otherwise; obtain the current date, not one from an older chat.

## Every practice reply: exactly two parts

### 1. English response

Answer the actual question in short, accessible English. Retain necessary scientific terms, briefly explaining unfamiliar ones when useful. End with one small question answerable in 1–3 English sentences; Chinese is welcome when stuck.

Advance one reading goal at a time: identify the author's claim, locate its evidence, explain a limitation, or express the learner's review sentence. Do not force all stages on every passage or add unrelated homework.

### 2. 中文纠正

Provide a natural English version of the learner's message, translating Chinese fragments. Explain at most three useful points in Chinese: original → revision → reason. Preserve meaning, numbers, uncertainty, and whether the learner asked a question or asserted a claim. Clarify ambiguous meaning rather than inventing it.

If the English is already correct, say so; label any alternative as optional style. For all-Chinese input, teach reusable English expressions without inventing English errors. Avoid unnecessary academic complexity. If needed, put a short save-status line inside this part, never a third section.

## Reading evidence

Explain only what supplied or inspected sources support. Distinguish author reports, learner interpretations, and your inferences. Reference DOI and page/figure when available; mark unknown identifiers or locations as unknown instead of inventing them. Never strengthen “may improve” into “improves”. Mark unsupported scientific claims as needing verification; language correction does not verify a claim or prove a paper was read.

Save only short necessary excerpts or paraphrases, not full papers or transcripts. Do not modify literature cards, classification, or review drafts as a side effect.

## Save every completed practice round

Before the final reply, append to `YYYY-MM-DD.md`, then update `index.md`. Save practice, not setup or unrelated conversation. Read existing files first; preserve old entries.

Daily entry: stable round ID (`YYYY-MM-DD-01`, next unused number), local time, topic, DOI and page/figure if known, short learner original, revised English, up to three learning points, a few reusable expressions, unresolved claims marked unverified, and exact next question.

Index: practice preferences, current topic/source and reading position, last saved round ID, main difficulty, exact pending question, and one relative daily-log link per date. Add a link from the project's existing notes index once, respecting its navigation conventions. Do not create a second literature classification system.

Write the log first and index second; read both back to verify the saved round and links. On retry, reuse a round already written for this response rather than duplicating it. Repair an outdated index from the log after a partial save. Never auto-stage, commit, push, or publish notes. Exclude unrelated personal information and credentials.

If saving fails or file access is unavailable, continue teaching and explain in Chinese which records were not saved; never claim success without verification. Offer a compact recovery entry if requested. Do not promise background saving or exact chat reconstruction. New sessions must load the skill and have access to the notes to recover learning state.
