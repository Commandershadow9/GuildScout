import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Points, PointMaterial, Float, Stars } from '@react-three/drei';
import * as THREE from 'three';

// 1. Runic / Tactical Rings
const TacticalRing = ({ radius, speed, color, dashArray }: { radius: number; speed: number; color: string; dashArray: number }) => {
  const meshRef = useRef<THREE.Mesh>(null);
  
  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.z += speed * 0.001;
      meshRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.1) * 0.1;
    }
  });

  return (
    <mesh ref={meshRef} rotation={[-Math.PI / 2, 0, 0]}>
      <ringGeometry args={[radius, radius + 0.05, 128]} />
      <meshBasicMaterial 
        color={color} 
        transparent 
        opacity={0.3} 
        side={THREE.DoubleSide}
        blending={THREE.AdditiveBlending}
      />
    </mesh>
  );
};

// 2. Floating Embers / Magic Dust
const Embers = () => {
  const ref = useRef<THREE.Points>(null);
  
  const [positions, opacity] = useMemo(() => {
    const count = 300;
    const positions = new Float32Array(count * 3);
    const opacity = new Float32Array(count);
    
    for (let i = 0; i < count; i++) {
      const r = Math.random() * 15 + 5; // Radius distribution
      const theta = Math.random() * Math.PI * 2;
      positions[i * 3] = r * Math.cos(theta); // x
      positions[i * 3 + 1] = (Math.random() - 0.5) * 5; // y (height spread)
      positions[i * 3 + 2] = r * Math.sin(theta); // z
      opacity[i] = Math.random();
    }
    return [positions, opacity];
  }, []);

  useFrame((state) => {
    if (ref.current) {
      ref.current.rotation.y = state.clock.elapsedTime * 0.02;
    }
  });

  return (
    <group rotation={[0, 0, Math.PI / 4]}>
      <Points ref={ref} positions={positions} stride={3} frustumCulled={false}>
        <PointMaterial
          transparent
          color="#2DE2E6"
          size={0.05}
          sizeAttenuation={true}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          opacity={0.6}
        />
      </Points>
    </group>
  );
};

// 3. Central Core Glow
const CoreGlow = () => {
  return (
    <mesh position={[0, -2, 0]}>
      <sphereGeometry args={[2, 32, 32]} />
      <meshBasicMaterial color="#0B1224" transparent opacity={0.9} />
    </mesh>
  );
};

const Scene = () => {
  return (
    <>
      <color attach="background" args={['#050812']} />
      <fog attach="fog" args={['#050812', 5, 25]} />
      
      <ambientLight intensity={0.5} />
      
      {/* Tactical Rings (The "Table" Feel) */}
      <group position={[0, -1, 0]} rotation={[Math.PI / 3, 0, 0]}>
        <TacticalRing radius={3} speed={1} color="#2DE2E6" dashArray={0.5} />
        <TacticalRing radius={4.5} speed={-0.5} color="#5865F2" dashArray={0.2} />
        <TacticalRing radius={6} speed={0.2} color="#2DE2E6" dashArray={0.8} />
      </group>

      {/* Floating Particles */}
      <Float speed={1} rotationIntensity={0.5} floatIntensity={0.5}>
        <Embers />
      </Float>

      {/* Distant Stars for depth */}
      <Stars radius={100} depth={50} count={5000} factor={4} saturation={0} fade speed={1} />
      
      {/* Subtle Blue Pulse Light */}
      <pointLight position={[0, 0, 5]} distance={10} intensity={2} color="#2DE2E6" />
    </>
  );
};

const ThreeBackground = () => {
  return (
    <div className="fixed inset-0 z-[-10]">
      <Canvas camera={{ position: [0, 2, 10], fov: 45 }}>
        <Scene />
      </Canvas>
      {/* Overlay to ensure text readability over 3D scene */}
      <div className="absolute inset-0 bg-gradient-to-t from-[#050812] via-transparent to-[#050812]/50 pointer-events-none" />
      <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-[0.03] pointer-events-none mix-blend-overlay" />
    </div>
  );
};

export default ThreeBackground;
