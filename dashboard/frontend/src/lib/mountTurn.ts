// Heavy parts of the page (a card's charts) mount one at a time, each after the browser has painted, instead of all
// in the same turn as the tap or page load that asked for them.
//
// Building a chart is the most expensive thing the page does, and React does it inside the update that adds the
// card. So a tick under Filters, a tab's first visit or the larger view froze the page until every new chart was
// built (2-4 s at 4x CPU slowdown) before the tick itself even showed. Waiting for a turn here,
// the tap is painted first (the card shows its "Loading graph…" box), then the charts are built one per frame, and a
// touch in between is answered between two of them.

import { useEffect, useState } from "react";

const waiting: Array<() => void> = [];
let running = false;

// Whichever comes first: the frame after next has started (so the last one was painted), or a quarter of a second
// (frames stop in a background tab and in an embedded page scrolled out of view; the charts still get built there)
const afterPaint = (run: () => void) => {
  let done = false;
  const once = () => {
    if (done) return;
    done = true;
    run();
  };
  if (typeof requestAnimationFrame === "function") requestAnimationFrame(() => setTimeout(once, 0));
  setTimeout(once, 250);
};

const next = () => {
  const run = waiting.shift();
  if (!run) {
    running = false;
    return;
  }
  afterPaint(() => {
    run();
    next();
  });
};

/** Calls `run` when its turn comes, in the order asked. Returns the way to give the turn up. */
export function queueMount(run: () => void): () => void {
  waiting.push(run);
  if (!running) {
    running = true;
    next();
  }
  return () => {
    const i = waiting.indexOf(run);
    if (i >= 0) waiting.splice(i, 1);
  };
}

/** False until this component's turn has come: render the placeholder until then, the heavy content after.
 *  It asks for its turn once `ready` (e.g. the chart code has loaded): a turn taken before that would be spent on
 *  nothing, and every card would then build its charts in the same instant, when the code arrives. */
export function useMountTurn(ready = true): boolean {
  const [turn, setTurn] = useState(false);
  useEffect(() => {
    if (ready && !turn) return queueMount(() => setTurn(true));
  }, [ready, turn]);
  return turn;
}
