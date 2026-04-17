
import * as THREE from "three";

export function createRenderer() {
  const renderer = new THREE.WebGLRenderer();
  renderer.setSize(window.innerWidth, window.innerHeight);

  const canvas = document.getElementById("game-canvas");
  if (canvas) {
    canvas.replaceWith(renderer.domElement);
  } else {
    document.body.appendChild(renderer.domElement);
  }

  return renderer;
}
