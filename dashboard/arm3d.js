// Steady Hand 3D view: the follower arm (solid plum) and the person's hand (rust ghost), with fingertip trails.
// three.js r160 (npm three@0.160.1), vendored from
//   https://cdn.jsdelivr.net/npm/three@0.160.1/build/three.module.min.js
// mount(container) -> { update(state), dispose() }. Units are mm in the robot frame: x forward, y left, z up.
import * as THREE from "./vendor/three.module.min.js";

const TRAIL_S = 2.5;                       // seconds of fingertip trail
const TRAIL_MAX = 480;                     // trail points kept (one per frame; 2.5 s at up to ~190 Hz)
const LINK_R = [19, 16, 15, 13, 11];       // mm: base-shoulder, shoulder-upper, upper arm, forearm, wrist
const JOINT_R = [23, 20, 18, 16, 14, 13];  // mm: at base, shoulder, upper arm, forearm, wrist, gripper
const TARGET = new THREE.Vector3(100, 0, 115);  // what the camera looks at
const FIT_R = 185;                         // mm of workspace the default view keeps in frame
const Z = new THREE.Vector3(0, 0, 1), Y = new THREE.Vector3(0, 1, 0);
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

function token(name, fallback) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const c = new THREE.Color(fallback);
  try { if (v) c.setStyle(v); } catch { /* keep the fallback */ }
  return c;
}

// A unit-geometry mesh stretched as a rod of radius r from a to b.
const _d = new THREE.Vector3();
function rod(mesh, a, b, r) {
  _d.subVectors(b, a);
  const len = _d.length();
  mesh.visible = len > 0.5;
  if (!mesh.visible) return;
  mesh.position.addVectors(a, b).multiplyScalar(0.5);
  mesh.quaternion.setFromUnitVectors(Y, _d.divideScalar(len));
  mesh.scale.set(r, len, r);
}

function validChain(chain) {
  return Array.isArray(chain) && chain.length >= 7 && chain.slice(0, 7).every(
    (p) => Array.isArray(p) && p.length >= 3 && Number.isFinite(p[0]) && Number.isFinite(p[1]) && Number.isFinite(p[2]));
}

export function mount(container) {
  const c = {
    paper: token("--paper", "#f3ede2"), card: token("--card", "#fbf8f2"), ink: token("--ink", "#2a2227"),
    soft: token("--soft", "#6f6468"), line: token("--line", "#e2d9cb"), plum: token("--plum", "#6b2d5c"),
    raw: token("--raw", "#b8552f"),
  };

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const canvas = renderer.domElement;
  canvas.style.cssText = "display:block;width:100%;height:100%;touch-action:pan-y;cursor:grab";
  container.appendChild(canvas);

  const scene = new THREE.Scene();
  scene.background = c.paper;
  scene.fog = new THREE.Fog(c.paper, 900, 2600);
  const camera = new THREE.PerspectiveCamera(35, 1, 10, 6000);
  camera.up.copy(Z);

  scene.add(new THREE.HemisphereLight(c.card, c.line, 2.0));
  const sun = new THREE.DirectionalLight(0xffffff, 1.6);
  sun.position.set(260, -320, 900);
  sun.target.position.set(110, 0, 0);
  sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  Object.assign(sun.shadow.camera, { left: -400, right: 400, top: 400, bottom: -400, near: 100, far: 2000 });
  sun.shadow.bias = -0.0004;
  sun.shadow.normalBias = 1.5;
  scene.add(sun, sun.target);

  // The table: a disc a shade lighter than the page, a faint grid, and the arms' soft shadow.
  const table = new THREE.Mesh(new THREE.CircleGeometry(1400, 96), new THREE.MeshLambertMaterial({ color: c.card }));
  table.receiveShadow = true;
  scene.add(table);
  const grid = new THREE.GridHelper(800, 16, c.line, c.line);
  grid.rotation.x = Math.PI / 2;
  grid.position.set(110, 0, 0.3);
  grid.material.transparent = true;
  grid.material.opacity = 0.9;
  scene.add(grid);

  const cyl = new THREE.CylinderGeometry(1, 1, 1, 28);
  const ball = new THREE.SphereGeometry(1, 28, 18);

  function makeArm(link, joint, claw, k, shadows) {
    const group = new THREE.Group();
    const mesh = (mat) => {
      const m = new THREE.Mesh(cyl, mat);
      m.castShadow = shadows;
      group.add(m);
      return m;
    };
    const links = LINK_R.map(() => mesh(link));
    const joints = JOINT_R.map(() => {
      const m = new THREE.Mesh(ball, joint);
      m.castShadow = shadows;
      group.add(m);
      return m;
    });
    const base = shadows ? mesh(joint) : null, palm = mesh(claw), bar = mesh(claw), fingerA = mesh(claw), fingerB = mesh(claw);
    group.visible = false;
    scene.add(group);
    const P = Array.from({ length: 7 }, () => new THREE.Vector3());
    return { group, links, joints, base, palm, bar, fingerA, fingerB, k, P, from: null, to: null, shown: null, t0: 0,
             trail: makeTrail(), tip: new THREE.Vector3() };
  }

  const v1 = new THREE.Vector3(), v2 = new THREE.Vector3(), v3 = new THREE.Vector3(), v4 = new THREE.Vector3();
  const side = new THREE.Vector3(), normal = new THREE.Vector3();
  function pose(a) {
    const { P, k } = a, s = a.shown;
    for (let i = 0; i < 7; i++) P[i].set(s[3 * i], s[3 * i + 1], s[3 * i + 2]);
    for (let i = 0; i < 5; i++) rod(a.links[i], P[i], P[i + 1], LINK_R[i] * k);
    for (let i = 0; i < 6; i++) { a.joints[i].position.copy(P[i]); a.joints[i].scale.setScalar(JOINT_R[i] * k); }
    if (a.base) rod(a.base, v1.set(P[0].x, P[0].y, 0), v2.set(P[0].x, P[0].y, Math.max(P[0].z, 0) + 14), 46);
    // The claw: a short palm from the gripper joint, then two fingers to the fingertip that open in the arm's plane.
    const d = v1.subVectors(P[6], P[5]);
    normal.set(P[6].x - P[0].x, P[6].y - P[0].y, 0).cross(Z);
    if (normal.lengthSq() < 1) normal.set(0, 1, 0);
    side.crossVectors(d, normal);
    if (side.lengthSq() < 1e-6) side.copy(normal);
    side.normalize();
    const palmEnd = v2.copy(P[5]).addScaledVector(d, 0.35);
    rod(a.palm, P[5], palmEnd, 12 * k);
    const gap = (4 + 0.2 * clamp(s[21], 0, 100)) * k;   // half the jaw opening, mm
    v3.copy(palmEnd).addScaledVector(side, gap);
    v4.copy(palmEnd).addScaledVector(side, -gap);
    rod(a.bar, v3, v4, 5 * k);
    rod(a.fingerA, v3, v3.clone().addScaledVector(d, 0.65), 4.5 * k);
    rod(a.fingerB, v4, v4.clone().addScaledVector(d, 0.65), 4.5 * k);
    a.tip.copy(P[6]);
  }

  // A fading camera-facing ribbon through the last TRAIL_S seconds of one fingertip.
  function makeTrail() {
    const geo = new THREE.BufferGeometry();
    const pos = new THREE.BufferAttribute(new Float32Array(TRAIL_MAX * 6), 3).setUsage(THREE.DynamicDrawUsage);
    const col = new THREE.BufferAttribute(new Float32Array(TRAIL_MAX * 8), 4).setUsage(THREE.DynamicDrawUsage);
    geo.setAttribute("position", pos);
    geo.setAttribute("color", col);
    const index = [];
    for (let i = 0; i < TRAIL_MAX - 1; i++) index.push(2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 1, 2 * i + 3, 2 * i + 2);
    geo.setIndex(index);
    const mesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({
      vertexColors: true, transparent: true, depthWrite: false, side: THREE.DoubleSide }));
    mesh.frustumCulled = false;
    scene.add(mesh);
    return { mesh, pos, col, pts: [] };
  }
  const tan = new THREE.Vector3(), view = new THREE.Vector3(), off = new THREE.Vector3();
  function drawTrail(tr, color, now, width) {
    while (tr.pts.length && (now - tr.pts[0].t > TRAIL_S * 1000 || tr.pts.length > TRAIL_MAX)) tr.pts.shift();
    const n = tr.pts.length, p = tr.pos.array, q = tr.col.array;
    for (let i = 0; i < n; i++) {
      const pt = tr.pts[i].p, age = (now - tr.pts[i].t) / (TRAIL_S * 1000);
      tan.subVectors(tr.pts[Math.min(i + 1, n - 1)].p, tr.pts[Math.max(i - 1, 0)].p);
      view.subVectors(camera.position, pt);
      off.crossVectors(tan, view);
      if (off.lengthSq() < 1e-9) off.set(0, 0, 1);
      off.normalize().multiplyScalar(width * (0.35 + 0.65 * (1 - age)));
      p.set([pt.x + off.x, pt.y + off.y, pt.z + off.z, pt.x - off.x, pt.y - off.y, pt.z - off.z], 6 * i);
      const alpha = 0.9 * (1 - age) ** 1.3;
      q.set([color.r, color.g, color.b, alpha, color.r, color.g, color.b, alpha], 8 * i);
    }
    tr.pos.needsUpdate = tr.col.needsUpdate = true;
    tr.mesh.geometry.setDrawRange(0, Math.max(0, n - 1) * 6);
  }

  const solid = new THREE.MeshStandardMaterial({ color: c.plum, roughness: 0.42, metalness: 0.08 });
  const solidJoint = new THREE.MeshStandardMaterial({ color: c.ink, roughness: 0.55, metalness: 0.1 });
  // The hand is an x-ray: a thin rust skeleton drawn over everything, so its shake shows even inside the solid arm.
  const ghostMat = new THREE.MeshBasicMaterial({ color: c.raw, transparent: true, opacity: 0.55, depthTest: false, depthWrite: false });
  const arm = makeArm(solid, solidJoint, solidJoint, 1, true);
  const hand = makeArm(ghostMat, ghostMat, ghostMat, 0.4, false);
  hand.trail.mesh.renderOrder = 1;
  arm.trail.mesh.renderOrder = 3;   // the smooth plum line runs on top of the jagged rust one
  hand.group.traverse((o) => { o.renderOrder = 2; });

  // Held: a calm plum ring around the follower's fingertip that breathes slowly.
  const ring = new THREE.Mesh(new THREE.TorusGeometry(30, 1.8, 12, 72),
    new THREE.MeshBasicMaterial({ color: c.plum, transparent: true, opacity: 0, depthWrite: false }));
  scene.add(ring);
  const ringShadow = new THREE.Mesh(new THREE.RingGeometry(26, 32, 72),
    new THREE.MeshBasicMaterial({ color: c.plum, transparent: true, opacity: 0, depthWrite: false }));
  scene.add(ringShadow);
  let holdLevel = 0, hold = false;

  // Interpolation: each update starts a glide from what is on screen now to the new pose over one update interval.
  let interval = 100, lastAt = 0;
  function feed(a, chain, open, now) {
    if (!validChain(chain)) {
      a.to = a.shown = null;
      a.group.visible = false;
      a.trail.pts.length = 0;
      return;
    }
    const to = chain.slice(0, 7).flatMap((p) => [p[0], p[1], p[2]]);
    to.push(Number.isFinite(open) ? open : a.to ? a.to[21] : 50);
    a.from = a.shown ? a.shown.slice() : to.slice();
    a.shown = a.from.slice();
    a.to = to;
    a.t0 = now;
    a.group.visible = true;
  }
  function step(a, now) {
    if (!a.to) return;
    const k = clamp((now - a.t0) / interval, 0, 1);
    for (let j = 0; j < a.to.length; j++) a.shown[j] = a.from[j] + (a.to[j] - a.from[j]) * k;
    pose(a);
    const last = a.trail.pts[a.trail.pts.length - 1];
    if (!last || last.p.distanceToSquared(a.tip) > 0.01 || now - last.t > 50) a.trail.pts.push({ p: a.tip.clone(), t: now });
  }

  // Drag to orbit, wheel to zoom. Touch: horizontal drag orbits, vertical drag still scrolls the page.
  let az = -1.2, el = 0.36, zoom = 1, drag = null, fit = 900;
  const down = (e) => { drag = { id: e.pointerId, x: e.clientX, y: e.clientY }; canvas.setPointerCapture(e.pointerId); canvas.style.cursor = "grabbing"; };
  const move = (e) => {
    if (!drag || e.pointerId !== drag.id) return;
    az -= (e.clientX - drag.x) * 0.008;
    el = clamp(el + (e.clientY - drag.y) * 0.006, 0.04, 1.45);
    drag.x = e.clientX;
    drag.y = e.clientY;
  };
  const up = () => { drag = null; canvas.style.cursor = "grab"; };
  const wheel = (e) => { e.preventDefault(); zoom = clamp(zoom * Math.exp(e.deltaY * 0.001), 0.35, 2.5); };
  canvas.addEventListener("pointerdown", down);
  canvas.addEventListener("pointermove", move);
  canvas.addEventListener("pointerup", up);
  canvas.addEventListener("pointercancel", up);
  canvas.addEventListener("wheel", wheel, { passive: false });

  function resize() {
    const w = Math.max(1, container.clientWidth), h = Math.max(1, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    const v = THREE.MathUtils.degToRad(camera.fov) / 2, hz = Math.atan(Math.tan(v) * camera.aspect);
    fit = FIT_R / Math.sin(Math.min(v, hz));
    camera.updateProjectionMatrix();
  }
  const observer = new ResizeObserver(resize);
  observer.observe(container);
  resize();

  let raf = 0;
  function frame() {
    raf = requestAnimationFrame(frame);
    const now = performance.now();
    if (renderer.getPixelRatio() !== Math.min(window.devicePixelRatio || 1, 2)) resize();
    const dist = fit * zoom;
    camera.position.set(Math.cos(el) * Math.cos(az), Math.cos(el) * Math.sin(az), Math.sin(el)).multiplyScalar(dist).add(TARGET);
    camera.lookAt(TARGET);
    scene.fog.near = dist * 0.9;
    scene.fog.far = dist * 2.6;
    step(arm, now);
    step(hand, now);
    const width = dist * 0.0045;
    drawTrail(hand.trail, c.raw, now, width);
    drawTrail(arm.trail, c.plum, now, width * 1.15);

    holdLevel += ((hold && arm.to ? 1 : 0) - holdLevel) * 0.08;
    const breathe = 1 + 0.06 * Math.sin(now / 600);
    ring.visible = ringShadow.visible = holdLevel > 0.01 && !!arm.to;
    ring.position.copy(arm.tip);
    ring.scale.setScalar(breathe);
    ring.material.opacity = 0.75 * holdLevel;
    ringShadow.position.set(arm.tip.x, arm.tip.y, 0.6);
    ringShadow.material.opacity = 0.35 * holdLevel;
    solid.color.copy(c.plum).lerp(c.soft, 0.25 * holdLevel);   // held: the arm calms to a dustier plum
    renderer.render(scene, camera);
  }
  frame();

  return {
    update(state) {
      const now = performance.now();
      if (lastAt) interval = interval * 0.8 + clamp(now - lastAt, 30, 500) * 0.2;
      lastAt = now;
      const s = state || {};
      feed(arm, s.out_chain, s.follower?.[5], now);
      feed(hand, s.raw_chain, s.leader?.[5] ?? s.follower?.[5], now);
      hold = !!s.hold;
    },
    dispose() {
      cancelAnimationFrame(raf);
      observer.disconnect();
      canvas.removeEventListener("pointerdown", down);
      canvas.removeEventListener("pointermove", move);
      canvas.removeEventListener("pointerup", up);
      canvas.removeEventListener("pointercancel", up);
      canvas.removeEventListener("wheel", wheel);
      scene.traverse((o) => {
        o.geometry?.dispose();
        (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => m?.dispose());
      });
      renderer.dispose();
      canvas.remove();
    },
  };
}
