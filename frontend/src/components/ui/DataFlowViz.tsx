"use client";

import { useEffect, useRef, useState } from "react";

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  type: "doc" | "data" | "result";
  status?: "MATCH" | "REVIEW" | "NEW";
  opacity: number;
  char: string;
  size: number;
}

interface DataFlowVizProps {
  className?: string;
}

const DOC_CHARS = ["█", "▓", "▒", "░", "▪", "▫"];
const DATA_CHARS = ["0", "1", "●", "○", "◆", "◇", "■", "□"];
const RESULT_CHARS = ["✓", "?", "+", "→"];

export function DataFlowViz({ className = "" }: DataFlowVizProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const particlesRef = useRef<Particle[]>([]);
  const animationRef = useRef<number>(0);

  useEffect(() => {
    const updateDimensions = () => {
      if (canvasRef.current?.parentElement) {
        setDimensions({
          width: window.innerWidth,
          height: window.innerHeight,
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

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = dimensions.width;
    canvas.height = dimensions.height;

    // Check for reduced motion
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;

    if (prefersReducedMotion) {
      return;
    }

    const centerX = dimensions.width / 2;
    const centerY = dimensions.height / 2;

    // Initialize particles
    const initParticles = () => {
      const particles: Particle[] = [];

      // Document particles (left side, flowing right)
      for (let i = 0; i < 15; i++) {
        particles.push({
          x: Math.random() * (dimensions.width * 0.3),
          y: Math.random() * dimensions.height,
          vx: 0.3 + Math.random() * 0.5,
          vy: (Math.random() - 0.5) * 0.3,
          type: "doc",
          opacity: 0.1 + Math.random() * 0.3,
          char: DOC_CHARS[Math.floor(Math.random() * DOC_CHARS.length)],
          size: 12 + Math.random() * 8,
        });
      }

      // Data particles (middle, swirling)
      for (let i = 0; i < 30; i++) {
        const angle = Math.random() * Math.PI * 2;
        const radius = 50 + Math.random() * 150;
        particles.push({
          x: centerX + Math.cos(angle) * radius,
          y: centerY + Math.sin(angle) * radius,
          vx: Math.cos(angle + Math.PI / 2) * 0.5,
          vy: Math.sin(angle + Math.PI / 2) * 0.5,
          type: "data",
          opacity: 0.1 + Math.random() * 0.4,
          char: DATA_CHARS[Math.floor(Math.random() * DATA_CHARS.length)],
          size: 10 + Math.random() * 6,
        });
      }

      // Result particles (right side, flowing right)
      for (let i = 0; i < 12; i++) {
        const statuses: Array<"MATCH" | "REVIEW" | "NEW"> = ["MATCH", "REVIEW", "NEW"];
        particles.push({
          x: dimensions.width * 0.6 + Math.random() * (dimensions.width * 0.3),
          y: Math.random() * dimensions.height,
          vx: 0.2 + Math.random() * 0.3,
          vy: (Math.random() - 0.5) * 0.2,
          type: "result",
          status: statuses[Math.floor(Math.random() * statuses.length)],
          opacity: 0.2 + Math.random() * 0.3,
          char: RESULT_CHARS[Math.floor(Math.random() * RESULT_CHARS.length)],
          size: 14 + Math.random() * 6,
        });
      }

      return particles;
    };

    particlesRef.current = initParticles();

    const getColor = (particle: Particle): string => {
      if (particle.type === "doc") {
        return `rgba(0, 255, 255, ${particle.opacity})`; // Cyan
      } else if (particle.type === "data") {
        return `rgba(0, 255, 0, ${particle.opacity})`; // Green
      } else {
        // Result colors based on status
        switch (particle.status) {
          case "MATCH":
            return `rgba(0, 255, 0, ${particle.opacity})`; // Green
          case "REVIEW":
            return `rgba(255, 176, 0, ${particle.opacity})`; // Amber
          case "NEW":
            return `rgba(0, 255, 255, ${particle.opacity})`; // Cyan
          default:
            return `rgba(255, 255, 255, ${particle.opacity})`;
        }
      }
    };

    const draw = () => {
      // Clear with fade effect
      ctx.fillStyle = "rgba(10, 10, 10, 0.1)";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Draw connection lines in the center (processing zone)
      ctx.strokeStyle = "rgba(0, 255, 0, 0.03)";
      ctx.lineWidth = 1;
      for (let i = 0; i < 5; i++) {
        ctx.beginPath();
        ctx.arc(centerX, centerY, 80 + i * 40, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Draw and update particles
      particlesRef.current.forEach((p) => {
        // Draw particle
        ctx.font = `${p.size}px "JetBrains Mono", monospace`;
        ctx.fillStyle = getColor(p);
        ctx.fillText(p.char, p.x, p.y);

        // Add glow for result particles
        if (p.type === "result") {
          ctx.shadowColor = getColor(p);
          ctx.shadowBlur = 10;
          ctx.fillText(p.char, p.x, p.y);
          ctx.shadowBlur = 0;
        }

        // Update position
        p.x += p.vx;
        p.y += p.vy;

        // Data particles orbit the center
        if (p.type === "data") {
          const dx = p.x - centerX;
          const dy = p.y - centerY;
          const angle = Math.atan2(dy, dx);
          const dist = Math.sqrt(dx * dx + dy * dy);

          // Gentle orbit
          p.vx = Math.cos(angle + Math.PI / 2) * 0.3;
          p.vy = Math.sin(angle + Math.PI / 2) * 0.3;

          // Keep within orbit range
          if (dist > 200) {
            p.vx -= dx * 0.001;
            p.vy -= dy * 0.001;
          } else if (dist < 50) {
            p.vx += dx * 0.001;
            p.vy += dy * 0.001;
          }
        }

        // Wrap particles
        if (p.x > dimensions.width + 50) {
          p.x = -50;
          p.y = Math.random() * dimensions.height;
        }
        if (p.x < -50) {
          p.x = dimensions.width + 50;
        }
        if (p.y > dimensions.height + 50) {
          p.y = -50;
        }
        if (p.y < -50) {
          p.y = dimensions.height + 50;
        }

        // Randomly change chars for data particles
        if (p.type === "data" && Math.random() < 0.01) {
          p.char = DATA_CHARS[Math.floor(Math.random() * DATA_CHARS.length)];
        }
      });

      // Draw floating metrics
      const time = Date.now() / 1000;
      ctx.font = '12px "JetBrains Mono", monospace';

      // Drift score floating
      ctx.fillStyle = `rgba(0, 255, 0, ${0.2 + Math.sin(time) * 0.1})`;
      ctx.fillText(
        `DRIFT: ${(0.08 + Math.sin(time * 0.5) * 0.04).toFixed(2)}`,
        centerX - 200 + Math.sin(time * 0.3) * 20,
        centerY - 100 + Math.cos(time * 0.4) * 10
      );

      // Reliability floating
      ctx.fillStyle = `rgba(0, 255, 0, ${0.2 + Math.cos(time) * 0.1})`;
      ctx.fillText(
        `RELIABILITY: ${(0.89 + Math.cos(time * 0.3) * 0.05).toFixed(2)}`,
        centerX + 50 + Math.cos(time * 0.2) * 20,
        centerY + 80 + Math.sin(time * 0.5) * 10
      );

      // Processing indicator
      const procChars = ["▓", "▒", "░", "▒"];
      const procChar = procChars[Math.floor(time * 3) % procChars.length];
      ctx.fillStyle = "rgba(255, 176, 0, 0.3)";
      ctx.font = '16px "JetBrains Mono", monospace';
      ctx.fillText(
        `[${procChar}${procChar}${procChar}] PROCESSING`,
        centerX - 80,
        centerY
      );

      animationRef.current = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [dimensions]);

  return (
    <canvas
      ref={canvasRef}
      className={`fixed inset-0 pointer-events-none ${className}`}
      style={{ zIndex: 0 }}
    />
  );
}

// Simpler version for smaller sections
export function DataStreamBg({ className = "" }: { className?: string }) {
  const [chars, setChars] = useState<string[]>([]);

  useEffect(() => {
    const generateChars = () => {
      const newChars = [];
      for (let i = 0; i < 50; i++) {
        newChars.push(DATA_CHARS[Math.floor(Math.random() * DATA_CHARS.length)]);
      }
      setChars(newChars);
    };

    generateChars();
    const interval = setInterval(generateChars, 200);
    return () => clearInterval(interval);
  }, []);

  return (
    <div
      className={`absolute inset-0 overflow-hidden opacity-10 pointer-events-none ${className}`}
    >
      <div className="absolute inset-0 flex flex-wrap justify-center items-center gap-4 text-terminal-green text-xs">
        {chars.map((char, i) => (
          <span
            key={i}
            className="animate-pulse"
            style={{ animationDelay: `${i * 50}ms` }}
          >
            {char}
          </span>
        ))}
      </div>
    </div>
  );
}
