"use client";

import { useEffect, useRef, useState } from "react";

interface MatrixRainProps {
  className?: string;
  density?: number;
  speed?: number;
  color?: string;
  chars?: string;
  fadeLength?: number;
}

export function MatrixRain({
  className = "",
  density = 0.05,
  speed = 33,
  color = "#00ff00",
  chars = "01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン",
  fadeLength = 20,
}: MatrixRainProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const updateDimensions = () => {
      const parent = canvas.parentElement;
      if (parent) {
        setDimensions({
          width: parent.clientWidth,
          height: parent.clientHeight,
        });
      }
    };

    updateDimensions();
    window.addEventListener("resize", updateDimensions);

    return () => window.removeEventListener("resize", updateDimensions);
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || dimensions.width === 0) return;

    // Check for reduced motion
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    if (prefersReducedMotion) {
      return;
    }

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = dimensions.width;
    canvas.height = dimensions.height;

    const fontSize = 14;
    const columns = Math.floor(canvas.width / fontSize);

    // Each column has a position (y coordinate)
    const drops: number[] = [];
    for (let i = 0; i < columns; i++) {
      drops[i] = Math.random() * -100;
    }

    const charArray = chars.split("");

    const draw = () => {
      // Semi-transparent black to create fade effect
      ctx.fillStyle = "rgba(10, 10, 10, 0.05)";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.font = `${fontSize}px JetBrains Mono, monospace`;

      for (let i = 0; i < drops.length; i++) {
        // Random character
        const char = charArray[Math.floor(Math.random() * charArray.length)];

        // Calculate opacity based on position for fade effect
        const y = drops[i] * fontSize;
        const opacity = Math.min(1, (canvas.height - y) / (fadeLength * fontSize));

        // Draw character with glow effect
        ctx.fillStyle = color;
        ctx.globalAlpha = opacity * 0.8;
        ctx.fillText(char, i * fontSize, y);

        // Brighter head of the rain
        if (drops[i] > 0) {
          ctx.fillStyle = "#ffffff";
          ctx.globalAlpha = opacity;
          ctx.fillText(char, i * fontSize, y);
        }

        ctx.globalAlpha = 1;

        // Reset drop when it goes below screen, with random chance
        if (y > canvas.height && Math.random() > 1 - density) {
          drops[i] = 0;
        }

        drops[i]++;
      }
    };

    const interval = setInterval(draw, speed);

    return () => clearInterval(interval);
  }, [dimensions, density, speed, color, chars, fadeLength]);

  return (
    <canvas
      ref={canvasRef}
      className={`absolute inset-0 pointer-events-none ${className}`}
      style={{ opacity: 0.15 }}
    />
  );
}
