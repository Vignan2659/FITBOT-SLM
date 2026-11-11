import { useCallback, useEffect, useRef, useState } from "react";

// Plays a few photos as a short motion while the cursor (or keyboard focus, or a tap) is on a picture, like a
// flip book: frame 0, 1, ... and round again. When it stops, the picture goes back to its resting frame.
export default function useMotion(frames, { rest = 0, interval = 750 } = {}) {
  const count = frames.length;
  const restIndex = Math.min(Math.max(rest, 0), Math.max(count - 1, 0));
  const [index, setIndex] = useState(restIndex);
  const [playing, setPlaying] = useState(false);
  const timer = useRef(null);

  const stop = useCallback(() => {
    clearInterval(timer.current);
    timer.current = null;
    setPlaying(false);
    setIndex(restIndex);
  }, [restIndex]);

  const start = useCallback(() => {
    if (count < 2 || timer.current) return;
    frames.forEach((src) => { const im = new Image(); im.src = src; });   // preload so the frames don't flicker
    setPlaying(true);
    setIndex(0);
    timer.current = setInterval(() => setIndex((i) => (i + 1) % count), interval);
  }, [frames, count, interval]);

  useEffect(() => () => clearInterval(timer.current), []);
  useEffect(() => { clearInterval(timer.current); timer.current = null; setPlaying(false); setIndex(restIndex); }, [restIndex, count]);

  const toggle = useCallback(() => (timer.current ? stop() : start()), [start, stop]);
  const bind = { onMouseEnter: start, onMouseLeave: stop, onFocus: start, onBlur: stop, onTouchStart: toggle };
  return { index: Math.min(index, Math.max(count - 1, 0)), playing, start, stop, toggle, bind };
}
