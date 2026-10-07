# Questions

<!-- top-level bullets are questions: "- <area> asks: ..." — nested bullets are answers -->

- cache asks: the shared bench (sequential) gives p99 ~420ms, fully explained by the 0.5s rebuild stall. Was the reported p99 ~2.4s / median ~80ms measured under concurrent clients (queue pileup through the single-threaded server amplifying the stall), or is it the production framing this demo approximates? If concurrent load is in scope, network — can you measure the queue-depth effect? [source: https://app.devin.ai/sessions/84695ccb45b24afb84c4f72317e5cc29]
