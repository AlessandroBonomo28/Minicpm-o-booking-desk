# Steering a full-duplex speech model at inference time

What worked, what failed, with numbers. Companion to the [README](../README.md). Dates are September 2026; every
run is a live conversation on one RTX 5090 with a headset, recorded in the gateway's run registry
(`logs_demo/hud_runs/<session>.log`), and every change was preceded by a written prediction and checked against it.

## 1. The problem

MiniCPM-o 4.5 in duplex mode is a good listener and a fluent talker, and it is impossible to steer with the tools a
turn-based stack gives you. Three walls, hit in the first days:

1. **You cannot tell it when to speak.** Every second the model decides `<|listen|>` or `<|speak|>` from the audio it
   hears. A change in the world (a calendar lookup came back, a booking was written) is not audio, so nothing happens.
2. **You cannot hand it a fact without it becoming its own words.** Anything put in the text stream is either read out
   as its own sentence or treated as background.
3. **The session dies after a few minutes.** The KV cache grows at ~18 tokens/s (3.5k tokens in 3 minutes); past a
   point the model listens forever or degrades.

The goal was a desk that books, checks and cancels appointments against a database, stays full-duplex (interruptions,
overlap, no turn boundaries), and never claims something the database does not say. On vanilla weights: no
fine-tuning of the speech model at any point.

## 2. Method

- One variable per experiment, prediction written before the run, run recorded, prediction confronted.
- Benches first, live second: an extractor regression (58 cases), a dialogue-context set (28), a normaliser battery
  (40), a state-machine replay of recorded sessions (76), judge probes (20). Benches verify; they do not discover.
- Live test is the gate: a change that passes the benches and makes the conversation worse is dropped, whatever the
  benches say. Two such changes are in section 5.

## 3. What worked

### 3.1 The screen as state, through the vision input

An **operator screen** of two or three lines, rendered as a 448×448 frame and sent with every one-second chunk, is
how the system talks to the model. It is state, not a message: the state machine rewrites it whenever the record or
the database changes, and the model reads whatever is on it when it decides to speak.

The rule that made it work (7 Sep): **every line must be a sentence the operator can say to the customer as it is.**
`BOOK: APRIL` / `WHICH DAY?`; `APRIL 20, ALL DAY` / `FREE, EXCEPT 3 PM, 6 PM` / `WHAT TIME?`; `APRIL 20, 2 PM` /
`FREE` / `SHALL I BOOK IT?`; `BOOKED` / `ANYTHING ELSE?`. No instructions to the operator, no act labels, no lists
the customer did not ask for. Times in spoken form (`6 PM`), busy days only when the question is about the month.

On the `text-booking` branch the same lines go in as plain text tokens in the vision slot of the unit (after
`<unit>`, before the audio), with no image encoding. Behaviour is the same, and the frame pipeline is gone. That is the
evidence that the channel matters, not the pixels: a per-second perception slot the model was trained to follow.

### 3.2 `force_speak`: the "when"

Upstream exposes `force_listen` (the client can silence the model for a chunk). We added its exact mirror in
`MiniCPMO45/modeling_minicpmo_unified.py`: at the first decision step of a unit, with the turn closed, a sampled
`<|listen|>` becomes `<|speak|>` and decoding continues as in any natural onset. The sequence of tokens is the one the
model produces on its own; only the decision is overridden.

Measured 7 Sep: the turn opens within 1 s in 8 of 9 forces; on the reference sessions 0.5-1.2 s in 11 of 12.

### 3.3 The judge (σ) decides, code verifies

Who decides when to force? Not a timer (section 5, item 3). A background LLM call, at the end of every model turn and 3 s
after a customer line left unanswered, receives the whole conversation, the screen, the machine state, the timings and
the desk's contract, and returns:

- `status`: `ok` or `stuck`, with a `kind` (silent, off context, repeating, ignores screen, false claim, cannot do);
- `help`: the sentence to say, in the first person, which goes on the screen with a forced turn;
- `claim`: what the model asserted (slot free, slot taken, booking confirmed, booking cancelled) with day and time;
- `readback`: the values the model repeated, used to fill missing fields as tentative values;
- `screen_said`: whether the model actually spoke the screen's result (from 13 Sep; a regex on the words gave 5
  false forces out of 7 in one session).

**Claims are never trusted.** Code checks each one on the database: "I've booked it" before the customer's yes → red
`NOTHING BOOKED YET`; "3 pm is free" when it is taken → red `3 PM IS TAKEN`; "the whole day is free" on a partially
booked day → "Sorry, April 28th is free except 3 PM and 6 PM. What time?". Red lines are sentences too: labels such
as `CHECK THE SCREEN` were read 0 times out of 5.

Guards, each one the answer to a loop seen live: one help between two customer lines; at most two per state, reds
included; at least 6 s between forces; a verdict is dropped if the machine changed while it was being computed; never a
force in the first three chunks or while a turn is open; a stale help line is cleared as soon as the machine changes
with a customer line (measured: flash-lite gives precedence to a stale help over the screen, and a prompt sentence
saying "the screen wins" did not fix it; not sending stale help did).

**Mid-turn judge** (8 Sep): a turn that runs past 10 s is judged on its partial text, then every 8 s. A turn that
lists days or repeats itself is cut with `force_listen` (the model closes it cleanly with `<|turn_eos|>`), the audio
stops, and the help line follows with the usual guards; at most three cuts per customer line. Trigger: session
`sess_f229adaaa73a`, a 46-second turn ("the 16th is available. Okay, let me check again...") with `<|speak|>` at
every second and nothing to stop it. Probes: listing → stuck, repeating → stuck, reading the screen line once → ok,
a normal answer → ok (4/4). Live: a healthy 12-second reading of a month was left alone.

### 3.4 The extractor and the state machine

MiniCPM-o 4.5 has the Qwen3 `<tool_call>` template in its tokenizer, and with the exact `<tools>` block it invents the
answer instead of calling the function (3 probes, 3 Sep). So the tools are called by a separate model that reads the
**customer's words** (browser VAD, 300 ms of silence, then Whisper large-v3-turbo on the last seconds of microphone)
and emits one event for a deterministic machine.

What the extractor learned to be, measured:

- Three separate tools (book / check / cancel) made a local Qwen3-1.7B fill fields by force. One tool
  `request(intent, month|null, day|null, time|null)` fed only the customer's lines stopped it (4 Sep).
- The contract that held: `set` (values said, never writes, merges and never forgets), `yes` (the only event that
  writes; it must quote the customer's accepting words as an argument, which removed the questions mistaken for a yes),
  `no`, `cancel` (give up the request in progress). Later `unbook` (cancel a written booking, with its own confirmation).
- Harness v3 (6 Sep): the open question quoted with its values, an explicit TAKEN state, values only from the
  customer's line. flash-lite 52 → 58/58 on the regression, minimax-m3 21 → 28/28 on the dialogue set.
- Constrained decoding on the local model: 44/55 against 47/55 free (it invents values to fill the JSON). Dropped.
- Cloud vs local: 53/55 and 23/24 against 48/55 and 18/24. Nemotron 3 Nano: 48/58 at 1.2 s against 52/58 at 0.9 s.
  Claude Sonnet 5: +3 points, 2.5 s per call, too slow. In production: `google/gemini-3.5-flash-lite`, ~1 s.

The machine (`gateway.py`): IDLE → COLLECTING (merge, validate, show rejected values) → CONFIRM (the slot checked on
the DB, `SHALL I BOOK IT?`) → DONE (BOOKED / TAKEN / CANCELLED). Idempotent: the same record is a null event. "You
pick" is a machine capability (8 Sep): it proposes the first free day, then the first free hour between 9 and 18; `no`
moves to the next, the customer's own value or "any" closes the delegation. A proposal made by the model itself ("How
about April 15th?") is a `slot_free` claim, verified on the DB, and enters as a tentative value with a question mark
(`BOOK: APRIL 15?` / `DOES THAT WORK?`), so the customer's yes has somewhere to land; before that rule the yes fell
into nothing and the model announced a booking three times (session `sess_41c874e48161`).

### 3.5 Sessions that do not die

Per-session KV sliding window (`set_sliding_window`, mode `basic`, prune from 4000 down to 3500 tokens, system prompt
preserved). Measured 4 Sep: a 6.5-minute coherent session with 4 prunes and no degradation once the text repetition
penalty was set to 1.0 (the penalty, not the window, was causing the rambling: with the upstream sign convention a
negative logit divided by the penalty makes the repeated token *more* likely). A jury of replays put the KV cut at
chance level as a cause of errors; it is not.

### 3.6 Reference sessions

`sess_20257233a096` (8 Sep, 4 min 13 s), the run the author called perfect:

| t (s) | customer | machine / screen | model |
|---|---|---|---|
| 16.5 | "I don't know, what can you do?" | judge: stuck, off context → help | "I can help you book your tickets or hotel room" → forced: "I can only book a time slot. Which day would you like?" (+2.0 s) |
| 41-48 | "I'd like to book... in April" | `BOOK: APRIL` / `WHICH DAY?` | "April. Which day?" |
| 56.2 | "I don't know which ones are available" | pick → `BOOK: APRIL 4?` / `DOES THAT WORK?` | "Okay. April 4th. Does that work?" |
| 68.2 | "What are all the days available in April?" | `FREE: APRIL` / `FREE, EXCEPT 1, 2, 3, 15, 20, 25, 28` / `WHICH DAY?` | reads the line once, 8 s, no cut |
| 85-121 | "Pick one" … "At 15" … "Um, okay, yes" | `APRIL 4, 3 PM` / `FREE` / `SHALL I BOOK IT?` → `BOOKED` | "April 4th, 3 p.m. free. Shall I book it?" → "booked. Anything else?" |
| 143 | "No, actually... for November" (said over the model's turn about March) | `FREE: NOVEMBER` / `ALL DAYS FREE` | judge: ignores screen → forced: "Free for November, all days free. Which day?" (+0.8 s) |
| 165 | silence | judge: silent → force | repeats the day question |
| 181-211 | "the 15" … "yeah at 18" … "uh yes yes" | `NOVEMBER 15, 6 PM` → `BOOKED` | "6 p.m. free. Shall I book it?" → "booked. Anything else?" |

Two bookings written, zero wrong writes, four forces all justified, zero reds, no turn over 12 s.

`sess_f0ab8867fc79` (7 Sep, 2 min 43 s): 12 judgements, 3 stuck (all justified), 0 false alarms on fillers
("Um..."), 0 wrong writes, one red ("Okay, I'll book it for you" before the yes → `NOTHING BOOKED YET`) corrected by
voice within 1 s. Latencies: extractor 1.0-1.4 s, judge 0.8-1.2 s, force → turn 0.6-0.7 s.

## 4. Numbers

| what | how | result |
|---|---|---|
| force_speak opens the turn | live, 7-8 Sep | 8/9 within 1 s; 11/12 in 0.5-1.2 s |
| judge probes | `tools/sigma_probe.py`, cloud | 20/20 (mid-turn 4/4, pick 4/4) |
| state-machine replay | `tools/fsm_replay_test.py`, no services | 76/76 (`vision-booking`), 72/72 (`text-booking`) |
| extractor regression | `tools/tool_agent_eval.py` | 58/58 (flash-lite, harness v3) |
| extractor, dialogue context | `tools/tool_agent_eval_dialog.py` | 28/28 |
| normaliser | `tools/test_norm.py` | 40/40 |
| screen_said by the judge vs regex | probe on `sess_8166a18771e5` | 13/13 vs 5 false forces out of 7 |
| KV window | live, 4 Sep | 6.5 min, 4 prunes, no degradation |

## 5. What failed

1. **Frames alone never woke the model** (every session up to 6 Sep). The model reacts to a frame only inside a turn
   it was already going to take. A jury over 13 frames with no pending turn: 0 spoke. Prompts ("ALWAYS SPEAK, read the
   screen"), a blinking banner and a two-halves screen did not change that. `force_speak` did.
2. **Injected text becomes the model's own words.** Text fed in the output slot of the unit before the decision:
   "do you like cats" → the model says "I like cats". Text in the protected system region (a sticky context rebuilt
   into the cache): background, no effect on behaviour. Both hooks are still in the model code; neither is used.
3. **A timed turn policy** (force on every event frame, a latch while a turn is open, a 3.5 s watchdog): the model
   talked too much and answered twice. Replaced by the judge.
4. **Operator instructions on the screen** (`SAY: AVAILABLE`, `ASK: DAY`, `WAIT`): read literally in forced turns
   ("I'm going to ask the day"). Gone; only customer-facing sentences.
5. **Two-line partial results** (`18 TAKEN` / `OTHER HOURS FREE`): the model inverted the polarity. One line:
   `YES, EXCEPT 6 PM`.
6. **Readback values recycled into the record**: a value the model invented in a forced turn became a field. Now
   readbacks are accepted only from turns that follow a customer line.
7. **An explicit STUCK state in the machine** (13 Sep, with memory of the previous state and the problem on the
   screen): the forces defeated the caps, the model talked on its own and role-flipped on the text channel. Dropped
   the same day; the judge's help line plus the guards is the working shape.
8. **Native tool calling** on the speech model: invents the answer (3/3). Separate extractor instead.
9. **A server-side echo canceller** for a loudspeaker setup (the model hears its own voice through a Wi-Fi
   speaker/microphone pair and answers itself): NLMS/partitioned-block adaptive filter plus spectral suppression,
   aligned on the client clock. Ineffective on that path, and measurably so: two lossy codecs and a small speaker left
   a waveform coherence of ~0.02 with 1-2% clipping, which no linear canceller recovers. Decision: cancel echo at the
   capture device, headset for the demo. Removed from the code.

## 6. Open

- The decision granularity is one second: every correction lands in the next unit.
- After `DOES THAT WORK?` the model sometimes asks its own question on top (a double question, not a loop).
- A readback of `time = any` ("all day") against the record's `all-day` gives a harmless false yellow.
- The cloud extractor has latency spikes; the local fallback is at 4 s and scores lower.
- Occasional non-English phonemes after fillers on very short turns: the speech decoder, accepted.
- The text channel (`text-booking`) needs the same number of live sessions as the frame channel before it replaces
  it; `tools/hud_run_compare.py` exists for that A/B.

## 7. Next

Port the front model. A stronger duplex base with real-time thinking inside (DuplexOmni, arXiv:2606.09186) should
need less of the judge and none of the frame rendering; the screen-through-perception channel, the state machine and
the claim verification do not depend on which model listens.
