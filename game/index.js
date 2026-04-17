
import { createRenderer } from "./engine/renderer.js";

const renderer = createRenderer();

function animate() {
  requestAnimationFrame(animate);
  renderer.render(new THREE.Scene(), new THREE.PerspectiveCamera());
}

animate();
