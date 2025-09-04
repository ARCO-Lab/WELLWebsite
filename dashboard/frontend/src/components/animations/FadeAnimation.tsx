// This file defines a FadeAnimation component for animating the appearance of its children with fade and optional blur effects.
// It uses IntersectionObserver to trigger the animation when the component enters the viewport.

import { useRef, useEffect, useState, ReactNode } from "react";

interface FadeAnimationProps {
  children: ReactNode;
  blur?: boolean;
  duration?: number;
  easing?: string;
  delay?: number;
  threshold?: number;
  initialOpacity?: number;
  className?: string;
  resetKey?: any;
}

const FadeAnimation: React.FC<FadeAnimationProps> = ({
  children,
  blur = false,
  duration = 1000,
  easing = "ease-out",
  delay = 0,
  threshold = 0.1,
  initialOpacity = 0,
  className = "",
  resetKey,
}) => {
  // Track if the element is in view
  const [inView, setInView] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  // Reset animation when resetKey changes
  useEffect(() => {
    setInView(false);
  }, [resetKey]);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    // Observe when the element enters the viewport
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          observer.unobserve(element);
          setTimeout(() => {
            setInView(true);
          }, delay);
        }
      },
      { threshold }
    );

    observer.observe(element);

    return () => observer.disconnect();
  }, [threshold, delay, resetKey]); // depend on resetKey

  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: inView ? 1 : initialOpacity,
        transition: `opacity ${duration}ms ${easing}, filter ${duration}ms ${easing}`,
        filter: blur ? (inView ? 'blur(0px)' : 'blur(10px)') : 'none',
      }}
    >
      {children}
    </div>
  );
};

export default FadeAnimation;