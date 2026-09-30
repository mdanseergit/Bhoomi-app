"use client";

import React from "react";

export function AnimatedWaveHeader() {
  return (
    <div
      className="pointer-events-none absolute inset-x-0 top-0 overflow-hidden"
      aria-hidden="true"
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        height: "380px",
        overflow: "hidden",
        pointerEvents: "none",
        zIndex: 0,
      }}
    >
      <style>{`
        @keyframes bhoomiWaveForward {
          0% {
            transform: translate3d(0, 0, 0);
          }
          100% {
            transform: translate3d(-50%, 0, 0);
          }
        }
        @keyframes bhoomiWaveReverse {
          0% {
            transform: translate3d(-50%, 0, 0);
          }
          100% {
            transform: translate3d(0, 0, 0);
          }
        }
        .bhoomi-wave-layer-1 {
          animation: bhoomiWaveForward 28s linear infinite;
          will-change: transform;
        }
        .bhoomi-wave-layer-2 {
          animation: bhoomiWaveReverse 21s linear infinite;
          will-change: transform;
        }
        .bhoomi-wave-layer-3 {
          animation: bhoomiWaveForward 15s linear infinite;
          will-change: transform;
        }
        @media (prefers-reduced-motion: reduce) {
          .bhoomi-wave-layer-1,
          .bhoomi-wave-layer-2,
          .bhoomi-wave-layer-3 {
            animation: none !important;
          }
        }
      `}</style>

      {/* Layer 1: Bright fresh leaf green wave (back layer) */}
      <div
        className="bhoomi-wave-layer-1"
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "200%",
          height: "100%",
          zIndex: 1,
        }}
      >
        <svg
          style={{ width: "100%", height: "100%", display: "block" }}
          viewBox="0 0 2880 380"
          preserveAspectRatio="none"
        >
          <path
            fill="#5C9E38"
            d="M 0 0 L 2880 0 L 2880 330.9 C 2820.0 321.8, 2760.0 318.6, 2700.0 319.8 C 2640.0 320.9, 2580.0 325.3, 2520.0 325.8 C 2460.0 326.3, 2400.0 322.4, 2340.0 317.7 C 2280.0 312.9, 2220.0 308.5, 2160.0 311.4 C 2100.0 314.4, 2040.0 325.3, 1980.0 338.6 C 1920.0 351.9, 1860.0 366.2, 1800.0 371.8 C 1740.0 377.4, 1680.0 373.7, 1620.0 364.0 C 1560.0 354.3, 1500.0 340.0, 1440.0 330.9 C 1380.0 321.8, 1320.0 318.6, 1260.0 319.8 C 1200.0 320.9, 1140.0 325.3, 1080.0 325.8 C 1020.0 326.3, 960.0 322.4, 900.0 317.7 C 840.0 312.9, 780.0 308.5, 720.0 311.4 C 660.0 314.4, 600.0 325.3, 540.0 338.6 C 480.0 351.9, 420.0 366.2, 360.0 371.8 C 300.0 377.4, 240.0 373.7, 180.0 364.0 C 120.0 354.3, 60.0 340.0, 0.0 330.9 Z"
          />
        </svg>
      </div>

      {/* Layer 2: Mid forest green wave (middle layer) */}
      <div
        className="bhoomi-wave-layer-2"
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "200%",
          height: "100%",
          zIndex: 2,
        }}
      >
        <svg
          style={{ width: "100%", height: "100%", display: "block" }}
          viewBox="0 0 2880 380"
          preserveAspectRatio="none"
        >
          <path
            fill="#2D5A18"
            d="M 0 0 L 2880 0 L 2880 291.9 C 2820.0 298.8, 2760.0 303.2, 2700.0 300.2 C 2640.0 297.3, 2580.0 286.8, 2520.0 274.1 C 2460.0 261.3, 2400.0 247.3, 2340.0 239.4 C 2280.0 231.6, 2220.0 230.2, 2160.0 233.5 C 2100.0 236.8, 2040.0 243.9, 1980.0 249.3 C 1920.0 254.6, 1860.0 257.9, 1800.0 260.5 C 1740.0 263.0, 1680.0 265.6, 1620.0 271.1 C 1560.0 276.6, 1500.0 285.1, 1440.0 291.9 C 1380.0 298.8, 1320.0 303.2, 1260.0 300.2 C 1200.0 297.3, 1140.0 286.8, 1080.0 274.1 C 1020.0 261.3, 960.0 247.3, 900.0 239.4 C 840.0 231.6, 780.0 230.2, 720.0 233.5 C 660.0 236.8, 600.0 243.9, 540.0 249.3 C 480.0 254.6, 420.0 257.9, 360.0 260.5 C 300.0 263.0, 240.0 265.6, 180.0 271.1 C 120.0 276.6, 60.0 285.1, 0.0 291.9 Z"
          />
        </svg>
      </div>

      {/* Layer 3: Foreground deep agricultural emerald wave (front layer) */}
      <div
        className="bhoomi-wave-layer-3"
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "200%",
          height: "100%",
          zIndex: 3,
        }}
      >
        <svg
          style={{ width: "100%", height: "100%", display: "block" }}
          viewBox="0 0 2880 380"
          preserveAspectRatio="none"
        >
          <path
            fill="#1E3A10"
            d="M 0 0 L 2880 0 L 2880 220.8 C 2820.0 226.4, 2760.0 226.4, 2700.0 224.0 C 2640.0 221.6, 2580.0 218.0, 2520.0 218.0 C 2460.0 217.9, 2400.0 221.5, 2340.0 224.2 C 2280.0 227.0, 2220.0 228.0, 2160.0 223.1 C 2100.0 218.3, 2040.0 207.6, 1980.0 197.4 C 1920.0 187.2, 1860.0 178.7, 1800.0 178.1 C 1740.0 177.4, 1680.0 184.6, 1620.0 194.4 C 1560.0 204.1, 1500.0 215.2, 1440.0 220.8 C 1380.0 226.4, 1320.0 226.4, 1260.0 224.0 C 1200.0 221.6, 1140.0 218.0, 1080.0 218.0 C 1020.0 217.9, 960.0 221.5, 900.0 224.2 C 840.0 227.0, 780.0 228.0, 720.0 223.1 C 660.0 218.3, 600.0 207.6, 540.0 197.4 C 480.0 187.2, 420.0 178.7, 360.0 178.1 C 300.0 177.4, 240.0 184.6, 180.0 194.4 C 120.0 204.1, 60.0 215.2, 0.0 220.8 Z"
          />
        </svg>
      </div>
    </div>
  );
}
