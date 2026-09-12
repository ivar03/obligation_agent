"use client";

import React, { useEffect, useRef } from "react";

interface LandingGridBackgroundProps {
  children?: React.ReactNode;
}

export const LandingGridBackground: React.FC<LandingGridBackgroundProps> = ({ children }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    // Check prefers-reduced-motion & touch devices
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const isTouchDevice =
      typeof window !== "undefined" &&
      ("ontouchstart" in window || navigator.maxTouchPoints > 0 || window.matchMedia("(hover: none)").matches);

    if (prefersReducedMotion || isTouchDevice) {
      el.style.setProperty("--mouse-x", "50vw");
      el.style.setProperty("--mouse-y", "35vh");
      el.style.setProperty("--parallax-x", "0px");
      el.style.setProperty("--parallax-y", "0px");
      return;
    }

    let rafId: number;
    let targetMouseX = window.innerWidth / 2;
    let targetMouseY = window.innerHeight * 0.35;
    let currentMouseX = targetMouseX;
    let currentMouseY = targetMouseY;

    let targetParallaxX = 0;
    let targetParallaxY = 0;
    let currentParallaxX = 0;
    let currentParallaxY = 0;

    let isTicking = false;

    const onMouseMove = (e: MouseEvent) => {
      targetMouseX = e.clientX;
      targetMouseY = e.clientY;

      // Parallax calculation: normalized -1 to +1 from screen center
      const normX = (e.clientX / window.innerWidth - 0.5) * 2;
      const normY = (e.clientY / window.innerHeight - 0.5) * 2;

      // Subtle parallax: 6px-8px max shift
      targetParallaxX = -normX * 8;
      targetParallaxY = -normY * 8;

      if (!isTicking) {
        isTicking = true;
        rafId = requestAnimationFrame(updateFrame);
      }
    };

    const updateFrame = () => {
      // Smooth lerp (linear interpolation) for cursor glow & grid translation
      currentMouseX += (targetMouseX - currentMouseX) * 0.15;
      currentMouseY += (targetMouseY - currentMouseY) * 0.15;

      currentParallaxX += (targetParallaxX - currentParallaxX) * 0.1;
      currentParallaxY += (targetParallaxY - currentParallaxY) * 0.1;

      el.style.setProperty("--mouse-x", `${currentMouseX.toFixed(1)}px`);
      el.style.setProperty("--mouse-y", `${currentMouseY.toFixed(1)}px`);
      el.style.setProperty("--parallax-x", `${currentParallaxX.toFixed(2)}px`);
      el.style.setProperty("--parallax-y", `${currentParallaxY.toFixed(2)}px`);

      const delta =
        Math.abs(targetMouseX - currentMouseX) +
        Math.abs(targetMouseY - currentMouseY) +
        Math.abs(targetParallaxX - currentParallaxX) +
        Math.abs(targetParallaxY - currentParallaxY);

      if (delta > 0.05) {
        rafId = requestAnimationFrame(updateFrame);
      } else {
        isTicking = false;
      }
    };

    window.addEventListener("mousemove", onMouseMove, { passive: true });

    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, []);

  return (
    <div ref={containerRef} className="landing-grid-root relative min-h-screen bg-white">
      {/* Fixed Ambient Orange Intelligence Grid Layers with Border Fade */}
      <div
        className="landing-grid-container fixed inset-0 pointer-events-none z-0 overflow-hidden"
        aria-hidden="true"
      >
        {/* Layer 1: Ambient Floating Base Grid (3cm x 3cm ~ 113.4px) */}
        <div className="landing-grid-base absolute inset-[-30px]" />

        {/* Layer 2: Glowing Orange Grid Lines around cursor position */}
        <div className="landing-grid-highlight absolute inset-[-30px]" />
      </div>

      {/* Foreground Content Stack */}
      <div className="relative z-10">{children}</div>
    </div>
  );
};
