(() => {
  const { useEffect, useRef } = React;

  const VISUAL_PRESETS = {
    coding: {
      tint: new THREE.Color("#8b5cf6"),
      noise: 0.35,
      wireframe: true,
      flow: 0.4,
    },
    python: {
      tint: new THREE.Color("#22d3ee"),
      noise: 0.5,
      wireframe: false,
      flow: 0.9,
    },
    finance: {
      tint: new THREE.Color("#fbbf24"),
      noise: 0.2,
      wireframe: false,
      flow: 0.2,
    },
    memory: {
      tint: new THREE.Color("#34d399"),
      noise: 0.25,
      wireframe: false,
      flow: 0.1,
    },
  };

  function VictusSphere({ audioActive, visualHint, sphereState }) {
    const mountRef = useRef(null);
    const audioLevelRef = useRef(0);
    const sphereStateRef = useRef(sphereState);
    const visualRef = useRef(visualHint);

    useEffect(() => {
      sphereStateRef.current = sphereState;
    }, [sphereState]);

    useEffect(() => {
      visualRef.current = visualHint;
    }, [visualHint]);

    useEffect(() => {
      const mountNode = mountRef.current;
      if (!mountNode) {
        return undefined;
      }

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 100);
      camera.position.z = 4;

      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setPixelRatio(window.devicePixelRatio || 1);
      renderer.setClearColor(0x000000, 0);
      mountNode.appendChild(renderer.domElement);

      const geometry = new THREE.SphereGeometry(1.1, 64, 64);
      const material = new THREE.ShaderMaterial({
        transparent: true,
        uniforms: {
          uTime: { value: 0 },
          uAudio: { value: 0 },
          uGlow: { value: 0.35 },
          uTint: { value: new THREE.Color("#6366f1") },
          uNoise: { value: 0.25 },
          uFlow: { value: 0.2 },
        },
        vertexShader: `
          varying vec2 vUv;
          void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `,
        fragmentShader: `
          precision mediump float;
          varying vec2 vUv;
          uniform float uTime;
          uniform float uAudio;
          uniform float uGlow;
          uniform vec3 uTint;
          uniform float uNoise;
          uniform float uFlow;

          float noise(vec2 st) {
            return sin((st.x + uTime * uFlow) * 18.0) * sin((st.y - uTime * uFlow) * 18.0);
          }

          void main() {
            float n = noise(vUv);
            float intensity = uNoise * (0.5 + 0.5 * n);
            float glow = uGlow + uAudio * 0.9;
            vec3 color = mix(vec3(0.08, 0.12, 0.2), uTint, glow);
            color += intensity * vec3(0.3, 0.4, 0.8);
            float alpha = 0.85 + uAudio * 0.1;
            gl_FragColor = vec4(color, alpha);
          }
        `,
      });

      const mesh = new THREE.Mesh(geometry, material);
      scene.add(mesh);

      const light = new THREE.PointLight(0xffffff, 1.5, 20);
      light.position.set(4, 4, 4);
      scene.add(light);

      const resize = () => {
        const { clientWidth, clientHeight } = mountNode;
        renderer.setSize(clientWidth, clientHeight);
        camera.aspect = clientWidth / clientHeight;
        camera.updateProjectionMatrix();
      };

      resize();
      window.addEventListener("resize", resize);

      const clock = new THREE.Clock();
      let animationId;

      const animate = () => {
        const elapsed = clock.getElapsedTime();
        const audioLevel = audioLevelRef.current;
        const state = sphereStateRef.current;
        const hint = visualRef.current;
        const preset = hint?.domain ? VISUAL_PRESETS[hint.domain] : null;

        material.uniforms.uTime.value = elapsed;
        material.uniforms.uAudio.value = audioLevel;
        material.uniforms.uGlow.value = 0.35 + audioLevel * 1.4 + (state === "streaming" ? 0.12 : 0);
        material.uniforms.uNoise.value = preset ? preset.noise : 0.25;
        material.uniforms.uFlow.value = preset ? preset.flow : 0.2;
        material.uniforms.uTint.value = preset ? preset.tint : new THREE.Color("#6366f1");
        material.wireframe = Boolean(preset?.wireframe);

        const basePulse = state === "streaming" ? 0.04 : 0.015;
        const breathing = state === "idle" ? 0.03 * Math.sin(elapsed * 0.6) : 0;
        const targetScale = 1 + audioLevel * 0.12 + basePulse * Math.sin(elapsed * 2.4) + breathing;
        mesh.scale.setScalar(targetScale);

        renderer.render(scene, camera);
        animationId = requestAnimationFrame(animate);
      };

      animate();

      return () => {
        cancelAnimationFrame(animationId);
        window.removeEventListener("resize", resize);
        geometry.dispose();
        material.dispose();
        renderer.dispose();
        mountNode.removeChild(renderer.domElement);
      };
    }, []);

    useEffect(() => {
      let animationId;
      const tick = () => {
        if (audioActive) {
          const time = Date.now() / 1000;
          audioLevelRef.current = 0.35 + 0.25 * Math.sin(time * 2.2);
        } else {
          audioLevelRef.current = 0;
        }
        animationId = requestAnimationFrame(tick);
      };

      tick();

      return () => {
        if (animationId) {
          cancelAnimationFrame(animationId);
        }
      };
    }, [audioActive]);

    return React.createElement("div", { className: "sphere-mount", ref: mountRef });
  }

  window.VictusSphere = VictusSphere;
})();
