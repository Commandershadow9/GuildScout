import React from 'react';
import { motion } from 'framer-motion';

export const TacticalMap = () => {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none perspective-[1000px]">
      {/* 3D Tilted Grid */}
      <div 
        className="absolute inset-[-50%] w-[200%] h-[200%] origin-bottom"
        style={{
            transform: 'rotateX(60deg) translateY(-20%)',
            background: `
                linear-gradient(transparent 0%, rgba(45, 226, 230, 0.1) 1px, transparent 1px),
                linear-gradient(90deg, transparent 0%, rgba(45, 226, 230, 0.1) 1px, transparent 1px)
            `,
            backgroundSize: '60px 60px',
        }}
      >
        <motion.div
            animate={{ y: [0, 60] }}
            transition={{ repeat: Infinity, duration: 3, ease: "linear" }}
            className="w-full h-full"
            style={{
                background: `
                    linear-gradient(transparent 0%, rgba(45, 226, 230, 0.2) 1px, transparent 1px),
                    linear-gradient(90deg, transparent 0%, rgba(45, 226, 230, 0.2) 1px, transparent 1px)
                `,
                backgroundSize: '60px 60px',
            }}
        />
      </div>

      {/* Radial Radar Sweep */}
      <motion.div 
        animate={{ rotate: 360 }}
        transition={{ repeat: Infinity, duration: 10, ease: "linear" }}
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[150vmax] h-[150vmax] origin-center opacity-20"
        style={{
            background: 'conic-gradient(from 0deg, transparent 0deg, rgba(45, 226, 230, 0.5) 20deg, transparent 40deg)'
        }}
      />
      
      {/* Vignette Mask to fade edges */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_0%,#070A12_80%)]" />
    </div>
  );
};
