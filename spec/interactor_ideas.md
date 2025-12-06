> \wake (up())

---

\wake ?(..) ---
Functions:
- up(..) --- always true
- sleep(.N*.) --- for timestamp:
--- N --- ticks
--- Ns --- seconds (elapsed)
--- Nu --- unix seconds
--- NZ --- datetime
- from(@#) --- on receive message
- Nbox(.?(@#).) --- on incoming messages > value e.g. Nbox(@alice 5) or Nbox(3)
- published(@#) --- on memory/public write from(@#)

\echo .?($(*)N). ---
Appends your message to \wake for N ticks (contiguous)
$ Queries run each tick
e.g. \echo $(Nspace_since(10 20)) ---
echo can only be used on @me

\spawn @.. .. ---
Spawns and wakes a new named entity @..
with first message after arguments

\name #.. @(..) .. ---
Creates a mind/space with name #.. and entities @(..)
with first message after arguments
e.g. \name #place @(me, mom) Hello World!

\say .@#. ---
Creates messages in spaces #(..) and to entities @(..)
e.g. \say @(me, ace)