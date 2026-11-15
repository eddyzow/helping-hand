// Steady Hand 3D view, version 2: the real SO-101 meshes. The follower (state.robot) is solid, the
// person's hand (state.hand, the leader in the follower's terms) is a translucent rust ghost over it,
// with the two fingertip trails. Falls back to a primitive arm from out_chain when there are no meshes.
// three.js r160 (npm three@0.160.1), vendored from
//   https://cdn.jsdelivr.net/npm/three@0.160.1/build/three.module.min.js
// mount(container) -> { update(state), dispose() }; throws if WebGL is unavailable.
// Units are mm in the robot frame: x forward, y left, z up. Quaternions arrive as [w, x, y, z].
import * as THREE from "./vendor/three.module.min.js";

const MESH_URL = "/meshes/";
const MESH_UNIT_MM = 1000;                 // the SO-101 STL files are in metres
const TRAIL_S = 2.5;                       // seconds of fingertip trail
const TRAIL_MAX = 480;                     // trail points kept (one per frame; 2.5 s at up to ~190 Hz)
const TARGET = new THREE.Vector3(140, 0, 120);  // what the camera looks at: the middle of the reach
const FIT_R = 215;                         // mm of workspace the default view keeps in frame
const AZ0 = -0.95, EL0 = 0.42;             // default three-quarter view, from the robot's front right
const Z = new THREE.Vector3(0, 0, 1), Y = new THREE.Vector3(0, 1, 0);
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

// Joints by the names the controller may use -> index (shoulder turn .. gripper).
const JOINT_NAMES = { shoulderpan: 0, shoulderturn: 0, pan: 0, shoulderlift: 1, shoulder: 1, elbow: 2, elbowflex: 2,
  wristflex: 3, wristbend: 3, wrist: 3, wristroll: 4, roll: 4, gripper: 5, claw: 5 };
// The links each joint moves; motors are told apart by their order in the model (one per joint).
const LINK_JOINT = { rotation_pitch_so101_v1: 0, motor_holder_so101_base_v1: 0, upper_arm_so101_v1: 1,
  under_arm_so101_v1: 2, motor_holder_so101_wrist_v1: 2, wrist_roll_pitch_so101_v2: 3,
  wrist_roll_follower_so101_v1: 4, wrist_roll_follower_so101_camera_mount: 4, moving_jaw_so101_v1: 5 };
const MOTOR_JOINT = [0, 1, 2, 3, 5];       // the sts3215_03a_v1 motors in model order; the no-horn one is the wrist roll

function token(name, fallback) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const c = new THREE.Color(fallback);
  try { if (v) c.setStyle(v); } catch { /* keep the fallback */ }
  return c;
}

// Binary STL -> BufferGeometry with flat normals, in the file's own units.
export function parseSTL(buf) {
  const dv = new DataView(buf);
  const n = buf.byteLength >= 84 ? dv.getUint32(80, true) : 0;
  if (!n || buf.byteLength < 84 + n * 50) throw new Error("not a binary STL");
  const pos = new Float32Array(n * 9);
  for (let i = 0; i < n; i++) {
    const o = 84 + i * 50 + 12;            // skip the stored normal: computed below
    for (let j = 0; j < 9; j++) pos[i * 9 + j] = dv.getFloat32(o + 4 * j, true);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  g.computeVertexNormals();
  g.computeBoundingSphere();
  return g;
}

// Loaded once per page, shared by every mount.
const geoCache = new Map();                // name -> geometry, or null while loading / after a failure
let index = null, indexAt = -1e9;          // Set of served names, "pending", or null (failed; retried every 5 s)
function meshIndex(now) {
  if (index === null && now - indexAt > 5000) {
    indexAt = now;
    index = "pending";
    fetch(MESH_URL + "index.json").then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((a) => { index = new Set(a.map(String)); }).catch(() => { index = null; });
  }
  return index instanceof Set ? index : null;
}
function loadMesh(name) {
  if (geoCache.has(name)) return;
  geoCache.set(name, null);
  fetch(MESH_URL + encodeURIComponent(name)).then((r) => (r.ok ? r.arrayBuffer() : Promise.reject()))
    .then((b) => geoCache.set(name, parseSTL(b))).catch(() => { /* stays null: the fallback keeps drawing */ });
}

function validChain(chain) {
  return Array.isArray(chain) && chain.length >= 7 && chain.slice(0, 7).every(
    (p) => Array.isArray(p) && p.length >= 3 && Number.isFinite(p[0]) && Number.isFinite(p[1]) && Number.isFinite(p[2]));
}
function tipOf(chain) {
  const p = Array.isArray(chain) ? chain[chain.length - 1] : null;
  return Array.isArray(p) && p.length >= 3 && p.slice(0, 3).every(Number.isFinite) ? new THREE.Vector3(p[0], p[1], p[2]) : null;
}
function validEntry(e) {
  return e && typeof e.mesh === "string" && Array.isArray(e.pos) && e.pos.length >= 3 && e.pos.slice(0, 3).every(Number.isFinite)
    && Array.isArray(e.quat) && e.quat.length >= 4 && e.quat.slice(0, 4).every(Number.isFinite);
}

function webgl() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch { return false; }
}

export function mount(container) {
  if (!webgl()) throw new Error("WebGL is not available, so the 3D view cannot start");
  const c = {
    paper: token("--paper", "#f3ede2"), card: token("--card", "#fbf8f2"), ink: token("--ink", "#2a2227"),
    soft: token("--soft", "#6f6468"), line: token("--line", "#e2d9cb"), plum: token("--plum", "#6b2d5c"),
    raw: token("--raw", "#b8552f"),
  };
  const OFF_WHITE = new THREE.Color("#ece6da"), GRAPHITE = new THREE.Color("#3a3735");

  // ---- scene: the solid robot, table and lights. A second scene holds what is drawn over it.
  const scene = new THREE.Scene();
  scene.background = c.paper;
  scene.fog = new THREE.Fog(c.paper, 900, 2600);
  const over = new THREE.Scene();          // trails, hold ring, fallback hand: drawn over the robot after a depth clear
  const camera = new THREE.PerspectiveCamera(35, 1, 10, 6000);
  camera.up.copy(Z);

  scene.add(new THREE.HemisphereLight(c.card, c.line, 1.5));     // a strong ambient keeps shadows soft and grey, not black
  const key = new THREE.DirectionalLight(0xfffaf2, 2.3);       // key: high, front left
  key.position.set(420, 380, 820);
  key.target.position.set(140, 0, 0);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  Object.assign(key.shadow.camera, { left: -420, right: 420, top: 420, bottom: -420, near: 100, far: 2400 });
  key.shadow.bias = -0.0003;
  key.shadow.normalBias = 1.2;
  key.shadow.radius = 4;
  const fill = new THREE.DirectionalLight(0xf2f0ff, 0.7);      // fill: low, front right
  fill.position.set(500, -600, 250);
  const rim = new THREE.DirectionalLight(0xffffff, 1.0);       // rim: behind
  rim.position.set(-600, 100, 500);
  scene.add(key, key.target, fill, rim);

  // The table: opaque, a shade lighter than the page, a faint grid, and the robot's soft shadow.
  const tableGeo = new THREE.CircleGeometry(1400, 96);
  const table = new THREE.Mesh(tableGeo, new THREE.MeshStandardMaterial({ color: c.card, roughness: 0.95 }));
  table.receiveShadow = true;
  const grid = new THREE.GridHelper(800, 16, c.line, c.line);
  grid.rotation.x = Math.PI / 2;
  grid.position.set(120, 0, 0.3);
  // Contact shadow: a soft dark pool under the base (ambient-occlusion feel), from a canvas gradient.
  const blobCanvas = document.createElement("canvas");
  blobCanvas.width = blobCanvas.height = 128;
  const g2 = blobCanvas.getContext("2d"), grad = g2.createRadialGradient(64, 64, 0, 64, 64, 64);
  grad.addColorStop(0, "rgba(40,30,30,0.5)");
  grad.addColorStop(0.55, "rgba(40,30,30,0.18)");
  grad.addColorStop(1, "rgba(40,30,30,0)");
  g2.fillStyle = grad;
  g2.fillRect(0, 0, 128, 128);
  const blobTex = new THREE.CanvasTexture(blobCanvas);
  const blob = new THREE.Mesh(new THREE.PlaneGeometry(190, 170),
    new THREE.MeshBasicMaterial({ map: blobTex, transparent: true, depthWrite: false }));
  blob.position.set(5, 0, 0.2);
  const floor = new THREE.Group();
  floor.add(table, grid, blob);
  scene.add(floor);
  let tableZ = -12;

  // ---- the mesh robot and the ghost hand. The ghost is depth-tested and pushed a hair behind the robot,
  // so where hand and robot agree the solid robot shows, and the shake shows as rust where they differ.
  const offset = { polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 4 };
  const ghostPre = new THREE.MeshBasicMaterial({ colorWrite: false, ...offset });   // depth first: the ghost blends once, not per layer
  const ghostMat = new THREE.MeshLambertMaterial({ color: c.raw, emissive: c.raw, emissiveIntensity: 0.3,
    transparent: true, opacity: 0.5, depthWrite: false, depthFunc: THREE.LessEqualDepth, ...offset });

  function makeBody(ghost) {
    return { ghost, sig: "", parts: [], group: new THREE.Group(), from: 0 };
  }
  const robot = makeBody(false), handBody = makeBody(true);
  scene.add(robot.group, handBody.group);

  function partColour(e) {
    const r = Array.isArray(e.rgba) ? e.rgba : [1, 1, 1, 1];
    const col = new THREE.Color().setRGB(+r[0] || 0, +r[1] || 0, +r[2] || 0, THREE.SRGBColorSpace);
    const hsl = col.getHSL({});
    if (e.mesh.startsWith("sts3215") || hsl.l < 0.2) return { color: GRAPHITE.clone(), motor: true };
    if (hsl.s < 0.12) return { color: OFF_WHITE.clone(), motor: false };      // plain white/grey: warm off-white
    return { color: col.lerp(OFF_WHITE, 0.7), motor: false };                 // the model's colour, matte and muted
  }

  function build(body, list) {
    body.group.clear();
    body.parts.forEach((p) => p.mat?.dispose());
    let motor = 0;
    body.parts = list.map((e) => {
      const name = e.mesh.replace(/\.stl$/i, "");
      const obj = new THREE.Group();
      const joint = name === "sts3215_03a_v1" ? MOTOR_JOINT[motor++] : name === "sts3215_03a_no_horn_v1" ? 4 : LINK_JOINT[name];
      const p = { name: e.mesh, obj, joint: joint ?? -1, mesh: null, mat: null, base: null,
                  fromP: new THREE.Vector3(), toP: new THREE.Vector3(), fromQ: new THREE.Quaternion(), toQ: new THREE.Quaternion(), fresh: true };
      if (!body.ghost) {
        const { color, motor: isMotor } = partColour(e);
        p.base = color;
        p.mat = new THREE.MeshStandardMaterial({ color: color.clone(), roughness: isMotor ? 0.6 : 0.82, metalness: isMotor ? 0.15 : 0 });
      }
      obj.visible = false;
      body.group.add(obj);
      return p;
    });
  }

  // Attach geometry as it arrives; true when every part of the body has its mesh.
  function attach(body) {
    let ready = body.parts.length > 0;
    for (const p of body.parts) {
      if (p.mesh) continue;
      const geo = geoCache.get(p.name);
      if (!geo) { ready = false; continue; }
      if (body.ghost) {
        const pre = new THREE.Mesh(geo, ghostPre), col = new THREE.Mesh(geo, ghostMat);
        pre.renderOrder = 3;
        col.renderOrder = 4;
        p.obj.add(pre, col);
        p.mesh = col;
      } else {
        p.mesh = new THREE.Mesh(geo, p.mat);
        p.mesh.castShadow = p.mesh.receiveShadow = true;
        p.obj.add(p.mesh);
      }
    }
    return ready;
  }

  const _q = new THREE.Quaternion();
  function feedBody(body, list, now) {
    const ok = Array.isArray(list) ? list.filter(validEntry) : [];
    const sig = ok.map((e) => e.mesh).join("|");
    if (sig !== body.sig) { body.sig = sig; build(body, ok); }
    const idx = meshIndex(now);
    ok.forEach((e, i) => {
      const p = body.parts[i];
      if (idx?.has(e.mesh)) loadMesh(e.mesh);
      const s = Array.isArray(e.scale) ? e.scale : [e.scale ?? 1, e.scale ?? 1, e.scale ?? 1];
      p.obj.scale.set(...[0, 1, 2].map((k) => MESH_UNIT_MM * (Number.isFinite(+s[k]) ? +s[k] : 1)));
      _q.set(e.quat[1], e.quat[2], e.quat[3], e.quat[0]).normalize();     // [w,x,y,z] -> three's (x,y,z,w)
      p.fromP.copy(p.fresh ? new THREE.Vector3(...e.pos.slice(0, 3)) : p.obj.position);
      p.fromQ.copy(p.fresh ? _q : p.obj.quaternion);
      p.toP.set(e.pos[0], e.pos[1], e.pos[2]);
      p.toQ.copy(_q);
      p.fresh = false;
    });
    body.from = now;
  }
  function stepBody(body, now, show) {
    const k = clamp((now - body.from) / interval, 0, 1);
    for (const p of body.parts) {
      p.obj.position.lerpVectors(p.fromP, p.toP, k);
      p.obj.quaternion.slerpQuaternions(p.fromQ, p.toQ, k);
      p.obj.visible = show && !!p.mesh;
    }
  }

  // ---- fallback: the version 1 primitive arm from a 7-point chain
  const LINK_R = [19, 16, 15, 13, 11], JOINT_R = [23, 20, 18, 16, 14, 13];
  const cyl = new THREE.CylinderGeometry(1, 1, 1, 28), ball = new THREE.SphereGeometry(1, 28, 18);
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
  function makeArm(link, joint, k, shadows, parent) {
    const group = new THREE.Group();
    const add = (geo, mat) => { const m = new THREE.Mesh(geo, mat); m.castShadow = shadows; group.add(m); return m; };
    const arm = { group, k, links: LINK_R.map(() => add(cyl, link)), joints: JOINT_R.map(() => add(ball, joint)),
                  base: shadows ? add(cyl, joint) : null, fingerA: add(cyl, joint), fingerB: add(cyl, joint),
                  P: Array.from({ length: 7 }, () => new THREE.Vector3()), from: null, to: null, shown: null };
    group.visible = false;
    parent.add(group);
    return arm;
  }
  const v1 = new THREE.Vector3(), v2 = new THREE.Vector3(), side = new THREE.Vector3(), normal = new THREE.Vector3();
  function poseArm(a) {
    const { P, k } = a, s = a.shown;
    for (let i = 0; i < 7; i++) P[i].set(s[3 * i], s[3 * i + 1], s[3 * i + 2]);
    for (let i = 0; i < 5; i++) rod(a.links[i], P[i], P[i + 1], LINK_R[i] * k);
    for (let i = 0; i < 6; i++) { a.joints[i].position.copy(P[i]); a.joints[i].scale.setScalar(JOINT_R[i] * k); }
    if (a.base) rod(a.base, v1.set(P[0].x, P[0].y, tableZ), v2.set(P[0].x, P[0].y, Math.max(P[0].z, tableZ) + 14), 46);
    // Two fingers from the gripper joint to the fingertip, opening in the arm's plane.
    const d = v1.subVectors(P[6], P[5]);
    normal.set(P[6].x - P[0].x, P[6].y - P[0].y, 0).cross(Z);
    if (normal.lengthSq() < 1) normal.set(0, 1, 0);
    side.crossVectors(d, normal);
    if (side.lengthSq() < 1e-6) side.copy(normal);
    side.normalize().multiplyScalar((4 + 0.2 * clamp(s[21], 0, 100)) * k);
    rod(a.fingerA, v2.copy(P[5]).add(side), v2.clone().add(d), 4.5 * k);
    rod(a.fingerB, v2.copy(P[5]).sub(side), v2.clone().add(d), 4.5 * k);
  }
  function feedArm(a, chain, open, now) {
    if (!validChain(chain)) { a.to = a.shown = null; return; }
    const to = chain.slice(0, 7).flatMap((p) => [p[0], p[1], p[2]]);
    to.push(Number.isFinite(open) ? open : a.to ? a.to[21] : 50);
    a.from = a.shown ? a.shown.slice() : to.slice();
    a.shown = a.from.slice();
    a.to = to;
    a.t0 = now;
  }
  function stepArm(a, now, show) {
    a.group.visible = show && !!a.to;
    if (!a.group.visible) return;
    const k = clamp((now - a.t0) / interval, 0, 1);
    for (let j = 0; j < a.to.length; j++) a.shown[j] = a.from[j] + (a.to[j] - a.from[j]) * k;
    poseArm(a);
  }
  const fbLink = new THREE.MeshStandardMaterial({ color: OFF_WHITE, roughness: 0.82 });
  const fbJoint = new THREE.MeshStandardMaterial({ color: GRAPHITE, roughness: 0.6, metalness: 0.15 });
  const fbGhost = new THREE.MeshBasicMaterial({ color: c.raw, transparent: true, opacity: 0.5, depthWrite: false });
  const fbArm = makeArm(fbLink, fbJoint, 1, true, scene);
  const fbHand = makeArm(fbGhost, fbGhost, 0.4, false, over);
  fbHand.group.traverse((o) => { o.renderOrder = 4; });

  // ---- fingertip trails: fading camera-facing ribbons, drawn over everything
  function makeTrail(order) {
    const geo = new THREE.BufferGeometry();
    const pos = new THREE.BufferAttribute(new Float32Array(TRAIL_MAX * 6), 3).setUsage(THREE.DynamicDrawUsage);
    const col = new THREE.BufferAttribute(new Float32Array(TRAIL_MAX * 8), 4).setUsage(THREE.DynamicDrawUsage);
    geo.setAttribute("position", pos);
    geo.setAttribute("color", col);
    const ix = [];
    for (let i = 0; i < TRAIL_MAX - 1; i++) ix.push(2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 1, 2 * i + 3, 2 * i + 2);
    geo.setIndex(ix);
    const mesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({
      vertexColors: true, transparent: true, depthWrite: false, depthTest: false, side: THREE.DoubleSide }));
    mesh.frustumCulled = false;
    mesh.renderOrder = order;
    over.add(mesh);
    return { mesh, pos, col, pts: [], from: null, to: null, tip: new THREE.Vector3() };
  }
  const tan = new THREE.Vector3(), view = new THREE.Vector3(), off = new THREE.Vector3();
  function drawTrail(tr, color, now, width) {
    if (tr.to) {
      tr.tip.lerpVectors(tr.from, tr.to, clamp((now - lastAt) / interval, 0, 1));
      const last = tr.pts[tr.pts.length - 1];
      if (!last || last.p.distanceToSquared(tr.tip) > 0.01 || now - last.t > 50) tr.pts.push({ p: tr.tip.clone(), t: now });
    }
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
  function feedTrail(tr, chain) {
    const tip = tipOf(chain);
    if (!tip) { tr.to = null; tr.pts.length = 0; return; }
    tr.from = tr.to ? tr.tip.clone() : tip;
    tr.to = tip;
  }
  const handTrail = makeTrail(1), robotTrail = makeTrail(2);   // the smooth plum line runs on top of the jagged rust one

  // ---- held: a calm plum ring around the follower's fingertip and its trace on the table, breathing slowly
  const ring = new THREE.Mesh(new THREE.TorusGeometry(30, 1.8, 12, 72),
    new THREE.MeshBasicMaterial({ color: c.plum, transparent: true, opacity: 0, depthWrite: false, depthTest: false }));
  ring.renderOrder = 5;
  over.add(ring);
  const ringShadow = new THREE.Mesh(new THREE.RingGeometry(26, 32, 72),
    new THREE.MeshBasicMaterial({ color: c.plum, transparent: true, opacity: 0, depthWrite: false }));
  scene.add(ringShadow);

  let interval = 100, lastAt = 0, hold = false, calibrating = false, limited = new Set();
  let holdLevel = 0, dimLevel = 0, lastFrame = 0;
  const tint = new THREE.Color();

  // ---- camera: drag to orbit, wheel or pinch to zoom, double-click to reset
  let az = AZ0, el = EL0, zoom = 1, fit = 900;
  const pts = new Map();
  let pinch = 0;
  const pinchDist = () => { const [a, b] = [...pts.values()]; return Math.hypot(a.x - b.x, a.y - b.y); };
  const down = (e) => {
    pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    canvas.setPointerCapture?.(e.pointerId);
    if (pts.size === 2) pinch = pinchDist();
    canvas.style.cursor = "grabbing";
  };
  const move = (e) => {
    const p = pts.get(e.pointerId);
    if (!p) return;
    if (pts.size === 1) {
      az -= (e.clientX - p.x) * 0.008;
      el = clamp(el + (e.clientY - p.y) * 0.006, 0.06, 1.45);
    }
    p.x = e.clientX;
    p.y = e.clientY;
    if (pts.size === 2) { const d = pinchDist(); if (pinch > 0 && d > 0) zoom = clamp(zoom * pinch / d, 0.35, 2.5); pinch = d; }
  };
  const up = (e) => { pts.delete(e.pointerId); pinch = 0; if (!pts.size) canvas.style.cursor = "grab"; };
  const wheel = (e) => { e.preventDefault(); zoom = clamp(zoom * Math.exp(e.deltaY * 0.001), 0.35, 2.5); };
  const reset = () => { az = AZ0; el = EL0; zoom = 1; };

  // ---- renderer; rebuilt from scratch if the WebGL context is lost
  let renderer, canvas, raf = 0, rebuildTimer = 0, disposed = false;
  function makeRenderer() {
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.autoClear = false;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    canvas = renderer.domElement;
    canvas.style.cssText = "display:block;width:100%;height:100%;touch-action:pan-y;cursor:grab";
    canvas.addEventListener("pointerdown", down);
    canvas.addEventListener("pointermove", move);
    canvas.addEventListener("pointerup", up);
    canvas.addEventListener("pointercancel", up);
    canvas.addEventListener("wheel", wheel, { passive: false });
    canvas.addEventListener("dblclick", reset);
    canvas.addEventListener("webglcontextlost", lost);
    container.appendChild(canvas);
    resize();
  }
  function dropRenderer() {
    cancelAnimationFrame(raf);
    canvas.removeEventListener("webglcontextlost", lost);
    renderer.dispose();
    canvas.remove();
  }
  function lost(e) {
    e.preventDefault();
    cancelAnimationFrame(raf);
    clearTimeout(rebuildTimer);
    rebuildTimer = setTimeout(() => {
      if (disposed) return;
      dropRenderer();
      try { makeRenderer(); frame(); } catch (err) { console.warn("3D view: WebGL could not restart", err); }
    }, 300);
  }

  function resize() {
    const w = Math.max(1, container.clientWidth), h = Math.max(1, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    const v = THREE.MathUtils.degToRad(camera.fov) / 2, hz = Math.atan(Math.tan(v) * camera.aspect);
    fit = FIT_R / Math.sin(Math.min(v, hz));
    camera.updateProjectionMatrix();
  }
  const observer = new ResizeObserver(() => resize());
  observer.observe(container);
  makeRenderer();

  function frame() {
    raf = requestAnimationFrame(frame);
    const now = performance.now();
    if (renderer.getPixelRatio() !== Math.min(window.devicePixelRatio || 1, 2)) resize();
    const dist = fit * zoom;
    camera.position.set(Math.cos(el) * Math.cos(az), Math.cos(el) * Math.sin(az), Math.sin(el)).multiplyScalar(dist).add(TARGET);
    camera.lookAt(TARGET);
    scene.fog.near = dist * 0.9;
    scene.fog.far = dist * 2.6;
    floor.position.z = tableZ;

    const meshes = attach(robot);
    attach(handBody);
    stepBody(robot, now, meshes);
    stepBody(handBody, now, meshes);
    stepArm(fbArm, now, !meshes);
    stepArm(fbHand, now, !meshes || !handBody.parts.length);
    const width = dist * 0.0045;
    drawTrail(handTrail, c.raw, now, width);
    drawTrail(robotTrail, c.plum, now, width * 1.15);

    const ease = 1 - Math.exp(-(now - (lastFrame || now)) / 200);   // ~0.2 s fades at any frame rate
    lastFrame = now;
    holdLevel += ((hold ? 1 : 0) - holdLevel) * ease;
    dimLevel += ((calibrating ? 1 : 0) - dimLevel) * ease;
    const tip = robotTrail.to ? robotTrail.tip : null;
    ring.visible = ringShadow.visible = holdLevel > 0.01 && !!tip;
    if (tip) {
      ring.position.copy(tip);
      ring.quaternion.setFromUnitVectors(Z, view.subVectors(camera.position, tip).normalize());   // face the viewer
      ring.scale.setScalar(1 + 0.06 * Math.sin(now / 600));
      ring.material.opacity = 0.8 * holdLevel;
      ringShadow.position.set(tip.x, tip.y, tableZ + 0.6);
      ringShadow.material.opacity = 0.35 * holdLevel;
    }
    // Held: the plastic calms toward plum. Calibrating: everything dims toward the page. Limit: that joint in --raw.
    for (const p of robot.parts) {
      if (!p.mat) continue;
      tint.copy(p.base);
      if (limited.has(p.joint)) tint.lerp(c.raw, 0.7);
      tint.lerp(c.plum, 0.3 * holdLevel).lerp(c.paper, 0.6 * dimLevel);
      p.mat.color.copy(tint);
    }
    fbLink.color.copy(OFF_WHITE).lerp(c.plum, 0.3 * holdLevel).lerp(c.paper, 0.6 * dimLevel);
    ghostMat.opacity = 0.34 * (1 - 0.6 * dimLevel);

    renderer.clear();
    renderer.render(scene, camera);
    renderer.clearDepth();
    renderer.render(over, camera);
  }
  frame();

  return {
    update(state) {
      const now = performance.now();
      if (lastAt) interval = interval * 0.8 + clamp(now - lastAt, 30, 500) * 0.2;
      lastAt = now;
      const s = state || {};
      tableZ = Number.isFinite(s.table_z) ? s.table_z : -12;
      feedBody(robot, s.robot, now);
      feedBody(handBody, s.hand, now);
      feedArm(fbArm, s.out_chain, s.follower?.[5], now);
      feedArm(fbHand, s.raw_chain, s.leader?.[5] ?? s.follower?.[5], now);
      feedTrail(handTrail, s.raw_chain);
      feedTrail(robotTrail, s.out_chain);
      hold = !!s.hold;
      calibrating = s.why_still === "calibrating";
      limited = new Set((Array.isArray(s.limits) ? s.limits : [])
        .map((n) => JOINT_NAMES[String(n).toLowerCase().replace(/[^a-z]/g, "")]).filter((j) => j !== undefined));
    },
    dispose() {
      disposed = true;
      clearTimeout(rebuildTimer);
      observer.disconnect();
      dropRenderer();
      for (const s of [scene, over]) s.traverse((o) => {
        if (o.geometry && ![...geoCache.values()].includes(o.geometry)) o.geometry.dispose();   // cached STL stays for the next mount
        (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => m?.dispose());
      });
      blobTex.dispose();
    },
  };
}
