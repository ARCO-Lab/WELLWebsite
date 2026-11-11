// This file defines a FadeAnimation component that fades its children in (optionally from a blur) when they appear.
// Content that is there when the page first renders is shown as is: only what appears later (e.g. the rows of a
// filter group being opened) fades in, and right away rather than once scrolled into view, so nothing below the
// fold waits half-hidden. With reduced motion, everything shows at once.

import { useEffect, useRef, useState, ReactNode } from "react";

interface FadeAnimationProps {
  children: ReactNode;
  blur?: boolean;
  duration?: number;
  easing?: string;
  delay?: number;
  initialOpacity?: number;
  className?: string;
  resetKey?: any; // fade in again when this changes
}

// Set once the page's first render has committed: anything mounted before that is part of the initial layout.
let pageRendered = false;

const prefersReducedMotion = () =>
  typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

const FadeAnimation: React.FC<FadeAnimationProps> = ({
  children,
  blur = false,
  duration = 1000,
  easing = "ease-out",
  delay = 0,
  initialOpacity = 0,
  className = "",
  resetKey,
}) => {
  // Part of the first render (the server's HTML included): shown from the start.
  const [shown, setShown] = useState(() => !pageRendered || prefersReducedMotion());
  const [animating, setAnimating] = useState(false);
  const initiallyShown = useRef(shown);
  const mounted = useRef(false);

  useEffect(() => {
    pageRendered = true;
  }, []);

  // On mounting later, and whenever resetKey changes after that: hide, then fade in.
  useEffect(() => {
    const isMount = !mounted.current;
    mounted.current = true;
    if (prefersReducedMotion() || (isMount && initiallyShown.current)) {
      setShown(true);
      return;
    }
    setAnimating(true);
    setShown(false);
    // Two frames, so the hidden state is painted before the transition to shown starts
    let frame = requestAnimationFrame(() => {
      frame = requestAnimationFrame(() => setShown(true));
    });
    return () => cancelAnimationFrame(frame);
  }, [resetKey]);

  const transition = `${duration}ms ${easing} ${delay}ms`;
  return (
    <div
      className={className}
      style={{
        opacity: shown ? 1 : initialOpacity,
        transition: animating ? `opacity ${transition}, filter ${transition}` : undefined,
        filter: blur ? (shown ? "blur(0px)" : "blur(10px)") : undefined,
      }}
    >
      {children}
    </div>
  );
};

export default FadeAnimation;
