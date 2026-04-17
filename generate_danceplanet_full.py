#!/usr/bin/env python3

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from textwrap import dedent

REQUIRED_PACKAGES = ["numpy", "pillow"]


def install_missing_packages():
    for pkg in REQUIRED_PACKAGES:
        try:
            __import__(pkg)
        except ImportError:
            print(f"[Auto-Installer] Missing package '{pkg}', installing...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
            print(f"[Auto-Installer] Installed '{pkg}' successfully.")


install_missing_packages()

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(".")
SRC_PUBLIC = ROOT / "public"
SRC_PAGES = ROOT / "pages"
DIST = ROOT / "vercel_dist"

FFMPEG_DIR = ROOT / "ffmpeg_bin"
FFMPEG_EXE = FFMPEG_DIR / "ffmpeg.exe"


def ensure_ffmpeg():
    if FFMPEG_EXE.exists():
        print(f"[FFmpeg] Using local ffmpeg at {FFMPEG_EXE}")
        return str(FFMPEG_EXE)

    if shutil.which("ffmpeg"):
        print("[FFmpeg] Found ffmpeg on PATH.")
        return "ffmpeg"

    print("[FFmpeg] Not found. Auto-downloading Windows 64-bit build from gyan.dev...")
    FFMPEG_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = FFMPEG_DIR / "ffmpeg.zip"
    url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

    try:
        import urllib.request

        print(f"[FFmpeg] Downloading from {url} ...")
        with urllib.request.urlopen(url) as resp, open(zip_path, "wb") as out:
            out.write(resp.read())
        print("[FFmpeg] Download complete. Extracting...")

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(FFMPEG_DIR)

        exe_candidate = None
        for root, dirs, files in os.walk(FFMPEG_DIR):
            if "ffmpeg.exe" in files:
                exe_candidate = Path(root) / "ffmpeg.exe"
                break

        if not exe_candidate or not exe_candidate.exists():
            raise RuntimeError("ffmpeg.exe not found after extraction.")

        shutil.copy2(exe_candidate, FFMPEG_EXE)
        print(f"[FFmpeg] Installed ffmpeg to {FFMPEG_EXE}")
        return str(FFMPEG_EXE)

    except Exception as e:
        print("[FFmpeg] Auto-download failed.")
        print("Error:", e)
        print("Please install FFmpeg manually and ensure 'ffmpeg' is on PATH.")
        sys.exit(1)


def ensure_dirs():
    (SRC_PUBLIC / "models" / "fighters").mkdir(parents=True, exist_ok=True)
    (SRC_PUBLIC / "sounds").mkdir(parents=True, exist_ok=True)
    (SRC_PUBLIC / "video").mkdir(parents=True, exist_ok=True)
    SRC_PAGES.mkdir(parents=True, exist_ok=True)


def synth_tone(freq, duration, sr=44100, volume=0.3, wave_type="sine"):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    if wave_type == "sine":
        wave = np.sin(2 * np.pi * freq * t)
    elif wave_type == "square":
        wave = np.sign(np.sin(2 * np.pi * freq * t))
    elif wave_type == "saw":
        wave = 2 * (t * freq - np.floor(0.5 + t * freq))
    else:
        wave = np.sin(2 * np.pi * freq * t)
    return (wave * volume).astype(np.float32)


def save_wav(path, data, sr=44100):
    import wave

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        int_data = np.clip(data * 32767, -32768, 32767).astype(np.int16)
        wf.writeframes(int_data.tobytes())


def make_music_tracks(fast=False):
    sr = 44100
    base_dur = 10 if fast else 20
    long_dur = 15 if fast else 30

    dur = base_dur
    base = synth_tone(80, dur, sr, 0.25, "sine")
    arp = synth_tone(440, dur, sr, 0.15, "saw")
    pad = synth_tone(220, dur, sr, 0.1, "sine")
    synthwave = base + arp + pad
    save_wav(SRC_PUBLIC / "sounds" / "music_synthwave.wav", synthwave, sr)

    dur = base_dur
    kick = synth_tone(60, dur, sr, 0.4, "sine")
    saw = synth_tone(220, dur, sr, 0.2, "saw")
    lead = synth_tone(660, dur, sr, 0.15, "square")
    edm = kick + saw + lead
    save_wav(SRC_PUBLIC / "sounds" / "music_edm.wav", edm, sr)

    dur = base_dur
    bass = synth_tone(100, dur, sr, 0.3, "sine")
    chord = synth_tone(300, dur, sr, 0.15, "saw")
    hat = synth_tone(8000, dur, sr, 0.05, "square")
    disco = bass + chord + hat
    save_wav(SRC_PUBLIC / "sounds" / "music_disco.wav", disco, sr)

    dur = base_dur
    kick = synth_tone(50, dur, sr, 0.5, "sine")
    noise = np.random.randn(int(sr * dur)).astype(np.float32) * 0.05
    techno = kick + noise
    save_wav(SRC_PUBLIC / "sounds" / "music_techno.wav", techno, sr)

    dur = long_dur
    pad1 = synth_tone(110, dur, sr, 0.2, "sine")
    pad2 = synth_tone(220, dur, sr, 0.15, "sine")
    pad3 = synth_tone(330, dur, sr, 0.1, "sine")
    ambient = pad1 + pad2 + pad3
    save_wav(SRC_PUBLIC / "sounds" / "music_ambient.wav", ambient, sr)

    click = synth_tone(1000, 0.1, sr, 0.4, "square")
    save_wav(SRC_PUBLIC / "sounds" / "select.wav", click, sr)
    switch = synth_tone(600, 0.08, sr, 0.3, "sine")
    save_wav(SRC_PUBLIC / "sounds" / "switch.wav", switch, sr)


def encode_video_from_frames(ffmpeg_path, frames_dir, output_path, fps=30):
    frames_dir = Path(frames_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg_path,
        "-y",
        "-framerate",
        str(fps),
        "-i",
        str(frames_dir / "frame_%05d.png"),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    print("[FFmpeg] Encoding video:", output_path)
    subprocess.run(cmd, check=True)


def make_neon_tunnel_video(ffmpeg_path, duration=5, fps=30, size=(1280, 720)):
    w, h = size
    frames_dir = ROOT / "frames" / "intro_tunnel"
    frames_dir.mkdir(parents=True, exist_ok=True)

    total_frames = duration * fps
    for i in range(total_frames):
        t = i / fps
        img = Image.new("RGB", size, (0, 0, 0))
        draw = ImageDraw.Draw(img)
        depth = 20
        for j in range(depth):
            f = (j + t * 10) % depth
            margin = int(f / depth * min(w, h) / 2)
            color = (0, int(255 * (1 - f / depth)), 255)
            draw.rectangle(
                [margin, margin, w - margin, h - margin],
                outline=color,
                width=2,
            )
        frame_path = frames_dir / f"frame_{i+1:05d}.png"
        img.save(frame_path, "PNG")

    encode_video_from_frames(
        ffmpeg_path,
        frames_dir,
        SRC_PUBLIC / "video" / "intro_tunnel.mp4",
        fps=fps,
    )


def make_grid_flyin_video(ffmpeg_path, duration=5, fps=30, size=(1280, 720)):
    w, h = size
    frames_dir = ROOT / "frames" / "intro_grid"
    frames_dir.mkdir(parents=True, exist_ok=True)

    total_frames = duration * fps
    for i in range(total_frames):
        t = i / fps
        img = Image.new("RGB", size, (5, 5, 20))
        draw = ImageDraw.Draw(img)
        spacing = 40
        offset = int(t * 80)
        for x in range(0, w, spacing):
            draw.line([(x, 0), (x, h)], fill=(0, 80, 255), width=1)
        for y in range(-offset % spacing, h, spacing):
            draw.line([(0, y), (w, y)], fill=(0, 80, 255), width=1)
        draw.rectangle([0, h // 2, w, h], fill=(0, 0, 0))
        draw.rectangle([0, h // 2 - 20, w, h // 2 + 20], fill=(0, 0, 80))
        frame_path = frames_dir / f"frame_{i+1:05d}.png"
        img.save(frame_path, "PNG")

    encode_video_from_frames(
        ffmpeg_path,
        frames_dir,
        SRC_PUBLIC / "video" / "intro_grid.mp4",
        fps=fps,
    )


def make_particles_video(ffmpeg_path, duration=4, fps=30, size=(1280, 720)):
    w, h = size
    frames_dir = ROOT / "frames" / "intro_particles"
    frames_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(42)
    particles = rng.random((200, 2))

    total_frames = duration * fps
    for i in range(total_frames):
        t = i / fps
        img = Image.new("RGB", size, (0, 0, 0))
        draw = ImageDraw.Draw(img)
        for j in range(len(particles)):
            x = int(particles[j, 0] * w)
            y = int(particles[j, 1] * h)
            r = 2
            color = (255, 255, 255)
            draw.ellipse([x - r, y - r, x + r, y + r], fill=color)
        alpha = min(1.0, t / 2.0)
        text = "DancePlanet"
        font_size = 80
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx, ty = (w - tw) // 2, (h - th) // 2
        draw.text(
            (tx, ty),
            text,
            fill=(
                int(255 * alpha),
                int(255 * alpha),
                int(255 * alpha),
            ),
            font=font,
        )
        frame_path = frames_dir / f"frame_{i+1:05d}.png"
        img.save(frame_path, "PNG")

    encode_video_from_frames(
        ffmpeg_path,
        frames_dir,
        SRC_PUBLIC / "video" / "intro_particles.mp4",
        fps=fps,
    )


def make_sunset_video(ffmpeg_path, duration=5, fps=30, size=(1280, 720)):
    w, h = size
    frames_dir = ROOT / "frames" / "intro_sunset"
    frames_dir.mkdir(parents=True, exist_ok=True)

    total_frames = duration * fps
    for i in range(total_frames):
        t = i / fps
        img = Image.new("RGB", size, (10, 0, 30))
        draw = ImageDraw.Draw(img)
        sun_y = int(h * 0.4 + math.sin(t) * 20)
        sun_r = 120
        draw.ellipse(
            [w // 2 - sun_r, sun_y - sun_r, w // 2 + sun_r, sun_y + sun_r],
            fill=(255, 120, 0),
        )
        spacing = 40
        for x in range(0, w, spacing):
            draw.line([(x, h // 2), (x, h)], fill=(200, 0, 200), width=1)
        for j in range(0, h // 2, spacing):
            y = h - j
            draw.line([(0, y), (w, y)], fill=(200, 0, 200), width=1)
        frame_path = frames_dir / f"frame_{i+1:05d}.png"
        img.save(frame_path, "PNG")

    encode_video_from_frames(
        ffmpeg_path,
        frames_dir,
        SRC_PUBLIC / "video" / "intro_sunset.mp4",
        fps=fps,
    )


def make_videos(ffmpeg_path, fast=False):
    base_dur = 3 if fast else 5
    short_dur = 3 if fast else 4
    make_neon_tunnel_video(ffmpeg_path, duration=base_dur)
    make_grid_flyin_video(ffmpeg_path, duration=base_dur)
    make_particles_video(ffmpeg_path, duration=short_dur)
    make_sunset_video(ffmpeg_path, duration=base_dur)


GAME_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>DancePlanet – Fighter Select</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="description" content="DancePlanet – 3D fighter select with music-reactive intros and arena transitions." />
  <style>
    body {
      margin: 0;
      background: #050509;
      color: #f0f0f0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    #ui {
      margin-top: 10px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
    }
    #viewer {
      width: 100%;
      max-width: 960px;
      height: 600px;
      border: 1px solid #333;
      margin-top: 10px;
      position: relative;
      overflow: hidden;
    }
    .btn-row {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: center;
    }
    button {
      padding: 6px 14px;
      border-radius: 4px;
      border: 1px solid #555;
      background: #111;
      color: #f0f0f0;
      cursor: pointer;
    }
    button:hover {
      background: #222;
    }
    #fighter-name {
      font-size: 1.1rem;
      font-weight: 600;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }
    #status {
      font-size: 0.8rem;
      color: #aaa;
    }
    #stats-panel {
      margin-top: 6px;
      font-size: 0.85rem;
      background: #111;
      padding: 6px 10px;
      border-radius: 4px;
      border: 1px solid #333;
      min-width: 260px;
    }
    #stats-panel h3 {
      margin: 0 0 4px 0;
      font-size: 0.9rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #ffd966;
    }
    #stats-panel ul {
      list-style: none;
      padding: 0;
      margin: 0;
    }
    #stats-panel li {
      margin: 2px 0;
    }
    #spinner {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      width: 60px;
      height: 60px;
      border-radius: 50%;
      border: 6px solid #333;
      border-top: 6px solid #0ff;
      animation: spin 0.8s linear infinite, pulse 1.2s ease-in-out infinite;
      display: none;
      z-index: 10;
    }
    @keyframes spin {
      0% { transform: translate(-50%, -50%) rotate(0deg); }
      100% { transform: translate(-50%, -50%) rotate(360deg); }
    }
    @keyframes pulse {
      0% { transform: translate(-50%, -50%) scale(1); }
      50% { transform: translate(-50%, -50%) scale(1.15); }
      100% { transform: translate(-50%, -50%) scale(1); }
    }
    #model-error {
      display: none;
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      background: #220000;
      padding: 12px 18px;
      border: 1px solid #aa0000;
      border-radius: 6px;
      color: #ffaaaa;
      font-size: 0.9rem;
      text-align: center;
      z-index: 20;
    }
    #arena-transition {
      display: none;
      position: fixed;
      top: 0; left: 0;
      width: 100%; height: 100%;
      background: black;
      color: white;
      font-size: 2rem;
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 9999;
      opacity: 0;
      transition: opacity 1s ease;
    }
    #compare-panel {
      margin-top: 10px;
      background: #111;
      border: 1px solid #333;
      border-radius: 4px;
      padding: 6px 10px;
      font-size: 0.8rem;
      max-width: 960px;
    }
    #compare-panel h3 {
      margin: 0 0 4px 0;
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #9ad0ff;
    }
    #compare-list {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .compare-item {
      border: 1px solid #444;
      border-radius: 4px;
      padding: 4px 6px;
      min-width: 150px;
    }
    .locked {
      opacity: 0.4;
    }
  </style>
</head>
<body>
  <audio id="select-sound" src="/sounds/select.wav"></audio>
  <audio id="switch-sound" src="/sounds/switch.wav"></audio>
  <audio id="arena-music" loop></audio>

  <div id="ui">
    <div id="fighter-name">Loading...</div>
    <div class="btn-row">
      <button id="prev-btn">&larr; Prev</button>
      <button id="next-btn">Next &rarr;</button>
      <button id="select-btn">Select Fighter</button>
      <button id="play-btn">Play Game</button>
      <button id="music-mode-btn">Music: Auto (Groove)</button>
    </div>
    <div id="status">Use mouse to orbit. Model auto-rotates.</div>
    <div id="stats-panel">
      <h3>Fighter Stats</h3>
      <ul>
        <li><strong>Style:</strong> <span id="stat-style">-</span></li>
        <li><strong>Power:</strong> <span id="stat-power">-</span></li>
        <li><strong>Speed:</strong> <span id="stat-speed">-</span></li>
        <li><strong>Groove:</strong> <span id="stat-groove">-</span></li>
      </ul>
    </div>
  </div>

  <div id="viewer">
    <div id="spinner"></div>
    <div id="model-error">⚠️ Model not found</div>
  </div>

  <div id="compare-panel">
    <h3>Fighter Comparison</h3>
    <div id="compare-list"></div>
  </div>

  <div id="arena-transition">Entering Arena...</div>

  <script type="module">
    import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';
    import { GLTFLoader } from 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/loaders/GLTFLoader.js';
    import { OrbitControls } from 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/controls/OrbitControls.js';

    const fighters = [
      { id: 'cyber_dance_warrior', name: 'Cyber Dance Warrior', path: '/models/fighters/cyber_dance_warrior.glb',
        style: 'Cyber Rave Warrior', power: 8, speed: 7, groove: 10, unlockCost: 0 },
      { id: 'street_dance_brawler', name: 'Street Dance Brawler', path: '/models/fighters/street_dance_brawler.glb',
        style: 'Urban Brawler', power: 9, speed: 6, groove: 7, unlockCost: 100 },
      { id: 'electro_samurai', name: 'Electro Samurai', path: '/models/fighters/electro_samurai.glb',
        style: 'Techno Samurai', power: 8, speed: 8, groove: 8, unlockCost: 200 },
      { id: 'pop_idol_fighter', name: 'Pop Idol Fighter', path: '/models/fighters/pop_idol_fighter.glb',
        style: 'Stage Performer', power: 6, speed: 9, groove: 10, unlockCost: 300 },
      { id: 'robot_groove_unit', name: 'Robot Groove Unit', path: '/models/fighters/robot_groove_unit.glb',
        style: 'Mech Groove', power: 7, speed: 7, groove: 9, unlockCost: 400 }
    ];

    function pickMusicForGroove(groove) {
      if (groove >= 9) {
        const choices = ['/sounds/music_edm.wav', '/sounds/music_techno.wav'];
        return choices[Math.floor(Math.random() * choices.length)];
      } else if (groove >= 7) {
        const choices = ['/sounds/music_synthwave.wav', '/sounds/music_disco.wav'];
        return choices[Math.floor(Math.random() * choices.length)];
      } else if (groove >= 5) {
        const choices = ['/sounds/music_synthwave.wav', '/sounds/music_ambient.wav'];
        return choices[Math.floor(Math.random() * choices.length)];
      } else {
        return '/sounds/music_ambient.wav';
      }
    }

    function pickIntroForGroove(groove) {
      if (groove >= 9) {
        const choices = ['/video/intro_tunnel.mp4', '/video/intro_particles.mp4'];
        return choices[Math.floor(Math.random() * choices.length)];
      } else if (groove >= 7) {
        const choices = ['/video/intro_grid.mp4', '/video/intro_tunnel.mp4'];
        return choices[Math.floor(Math.random() * choices.length)];
      } else if (groove >= 5) {
        const choices = ['/video/intro_sunset.mp4', '/video/intro_grid.mp4'];
        return choices[Math.floor(Math.random() * choices.length)];
      } else {
        return '/video/intro_sunset.mp4';
      }
    }

    let currentIndex = 0;
    const container = document.getElementById('viewer');
    const nameLabel = document.getElementById('fighter-name');
    const statusLabel = document.getElementById('status');
    const spinner = document.getElementById('spinner');
    const errorBox = document.getElementById('model-error');
    const compareList = document.getElementById('compare-list');

    const selectSound = document.getElementById('select-sound');
    const switchSound = document.getElementById('switch-sound');
    const arenaMusic = document.getElementById('arena-music');

    const statStyle = document.getElementById('stat-style');
    const statPower = document.getElementById('stat-power');
    const statSpeed = document.getElementById('stat-speed');
    const statGroove = document.getElementById('stat-groove');

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x050509);

    const camera = new THREE.PerspectiveCamera(
      60,
      container.clientWidth / container.clientHeight,
      0.1,
      100
    );
    camera.position.set(2.5, 2.2, 3.2);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x222233, 0.8);
    scene.add(hemiLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 1.5);
    dirLight.position.set(5, 10, 7);
    scene.add(dirLight);

    const loader = new GLTFLoader();
    let currentModel = null;
    let mixer = null;
    const clock = new THREE.Clock();

    function getUnlocked() {
      const raw = localStorage.getItem('danceplanet_unlocked_fighters');
      if (!raw) return ['cyber_dance_warrior'];
      try { return JSON.parse(raw); } catch { return ['cyber_dance_warrior']; }
    }
    function setUnlocked(list) {
      localStorage.setItem('danceplanet_unlocked_fighters', JSON.stringify(list));
    }
    function isUnlocked(id) {
      return getUnlocked().includes(id);
    }

    function showError(msg) {
      errorBox.innerHTML = "⚠️ " + msg;
      errorBox.style.display = "block";
    }
    function hideError() {
      errorBox.style.display = "none";
    }

    function fadeInModel(model) {
      model.traverse(obj => {
        if (obj.material && obj.material.opacity !== undefined) {
          obj.material.transparent = true;
          obj.material.opacity = 0;
        }
      });
      let fade = 0;
      const fadeInterval = setInterval(() => {
        fade += 0.05;
        model.traverse(obj => {
          if (obj.material && obj.material.opacity !== undefined) {
            obj.material.opacity = Math.min(fade, 1);
          }
        });
        if (fade >= 1) clearInterval(fadeInterval);
      }, 30);
    }

    function fighterIntro(model) {
      model.scale.set(0.1, 0.1, 0.1);
      model.position.y = -1;
      let t = 0;
      const intro = setInterval(() => {
        t += 0.05;
        model.scale.set(t, t, t);
        model.position.y = -1 + t;
        if (t >= 1.2) clearInterval(intro);
      }, 16);
    }

    function startArenaTransition() {
      const overlay = document.getElementById('arena-transition');
      overlay.style.display = 'flex';
      setTimeout(() => { overlay.style.opacity = 1; }, 50);

      const fighter = fighters[currentIndex];
      const groove = fighter.groove || 5;
      const volume = Math.min(1, Math.max(0.2, groove / 10));
      arenaMusic.volume = volume;
      arenaMusic.play().catch(() => {});

      setTimeout(() => {
        window.location.href = '/pages/arena.html';
      }, 2000);
    }

    function setFighterName() {
      const f = fighters[currentIndex];
      const locked = !isUnlocked(f.id);
      nameLabel.textContent = f.name + (locked ? " (Locked)" : "");
    }

    function updateStats() {
      const f = fighters[currentIndex];
      statStyle.textContent = f.style;
      statPower.textContent = f.power;
      statSpeed.textContent = f.speed;
      statGroove.textContent = f.groove;
    }

    function showSpinner(show) {
      spinner.style.display = show ? 'block' : 'none';
    }

    function clearModel() {
      if (currentModel) {
        scene.remove(currentModel);
        currentModel.traverse(obj => {
          if (obj.geometry) obj.geometry.dispose();
          if (obj.material) {
            if (Array.isArray(obj.material)) {
              obj.material.forEach(m => m.dispose && m.dispose());
            } else {
              obj.material.dispose && obj.material.dispose();
            }
          }
        });
        currentModel = null;
      }
      mixer = null;
    }

    function applyCyberGlow(model) {
      model.traverse(obj => {
        if (obj.isMesh && obj.material && obj.material.emissive) {
          obj.material.emissive.setHex(0x00ffff);
          obj.material.emissiveIntensity = 1.2;
        }
      });
    }

    function loadCurrentFighter() {
      clearModel();
      hideError();
      const fighter = fighters[currentIndex];
      if (!isUnlocked(fighter.id)) {
        statusLabel.textContent = 'Locked fighter. Unlock in game.';
        return;
      }
      statusLabel.textContent = 'Loading ' + fighter.name + '...';
      showSpinner(true);
      loader.load(
        fighter.path,
        gltf => {
          currentModel = gltf.scene;
          currentModel.position.set(0, 0, 0);
          currentModel.scale.set(1.2, 1.2, 1.2);
          if (fighter.id === 'cyber_dance_warrior') {
            applyCyberGlow(currentModel);
          }
          if (gltf.animations && gltf.animations.length > 0) {
            mixer = new THREE.AnimationMixer(currentModel);
            mixer.clipAction(gltf.animations[0]).play();
          }
          scene.add(currentModel);
          fadeInModel(currentModel);
          fighterIntro(currentModel);
          statusLabel.textContent = 'Loaded ' + fighter.name + '.';
          showSpinner(false);
        },
        undefined,
        err => {
          console.error(err);
          showSpinner(false);
          showError("Model not found: " + fighter.path);
          statusLabel.textContent = 'Error loading model.';
        }
      );
    }

    function renderComparison() {
      compareList.innerHTML = "";
      const unlocked = getUnlocked();
      fighters.forEach(f => {
        const div = document.createElement('div');
        div.className = 'compare-item' + (unlocked.includes(f.id) ? '' : ' locked');
        div.innerHTML = `
          <strong>${f.name}</strong><br>
          Style: ${f.style}<br>
          Power: ${f.power} | Speed: ${f.speed} | Groove: ${f.groove}<br>
          ${unlocked.includes(f.id) ? 'Unlocked' : 'Locked (Cost: ' + f.unlockCost + ')'}
        `;
        compareList.appendChild(div);
      });
    }

    document.getElementById('prev-btn').addEventListener('click', () => {
      switchSound.play();
      currentIndex = (currentIndex - 1 + fighters.length) % fighters.length;
      setFighterName();
      updateStats();
      loadCurrentFighter();
    });

    document.getElementById('next-btn').addEventListener('click', () => {
      switchSound.play();
      currentIndex = (currentIndex + 1) % fighters.length;
      setFighterName();
      updateStats();
      loadCurrentFighter();
    });

    document.getElementById('select-btn').addEventListener('click', () => {
      selectSound.play();
      const fighter = fighters[currentIndex];
      if (!isUnlocked(fighter.id)) {
        statusLabel.textContent = 'Cannot select locked fighter.';
        return;
      }
      localStorage.setItem('danceplanet_selected_fighter', fighter.id);
      statusLabel.textContent = 'Selected: ' + fighter.name + ' (saved).';
    });

    let musicMode = 'auto';
    const musicModeBtn = document.getElementById('music-mode-btn');
    musicModeBtn.addEventListener('click', () => {
      musicMode = musicMode === 'auto' ? 'manual' : 'auto';
      musicModeBtn.textContent = musicMode === 'auto'
        ? 'Music: Auto (Groove)'
        : 'Music: Manual (Random)';
    });

    document.getElementById('play-btn').addEventListener('click', () => {
      selectSound.play();
      const fighter = fighters[currentIndex];
      if (!isUnlocked(fighter.id)) {
        statusLabel.textContent = 'Unlock this fighter in game first.';
        return;
      }
      localStorage.setItem('danceplanet_selected_fighter', fighter.id);

      const groove = fighter.groove || 5;
      let musicSrc;
      if (musicMode === 'auto') {
        musicSrc = pickMusicForGroove(groove);
      } else {
        const allTracks = [
          '/sounds/music_synthwave.wav',
          '/sounds/music_edm.wav',
          '/sounds/music_disco.wav',
          '/sounds/music_techno.wav',
          '/sounds/music_ambient.wav'
        ];
        musicSrc = allTracks[Math.floor(Math.random() * allTracks.length)];
      }
      const introSrc = pickIntroForGroove(groove);

      localStorage.setItem('danceplanet_selected_music', musicSrc);
      localStorage.setItem('danceplanet_selected_intro', introSrc);

      arenaMusic.src = musicSrc;

      startArenaTransition();
    });

    function animate() {
      requestAnimationFrame(animate);
      const delta = clock.getDelta();
      controls.update();
      if (mixer) mixer.update(delta);
      if (currentModel) currentModel.rotation.y += 0.01;
      renderer.render(scene, camera);
    }

    window.addEventListener('resize', () => {
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    });

    if (!localStorage.getItem('danceplanet_unlocked_fighters')) {
      setUnlocked(['cyber_dance_warrior', 'street_dance_brawler']);
    }

    setFighterName();
    updateStats();
    renderComparison();
    loadCurrentFighter();
    animate();
  </script>
</body>
</html>
"""

ARENA_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>DancePlanet – Arena</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="description" content="DancePlanet – Neon arena with music-reactive intro and camera fly-in." />
  <style>
    body {
      margin: 0;
      background: black;
      color: #f0f0f0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      overflow: hidden;
    }
    #overlay {
      position: fixed;
      top: 0; left: 0;
      width: 100%; height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      background: radial-gradient(circle at center, rgba(255,255,255,0.1), rgba(0,0,0,0.9));
      z-index: 10;
      opacity: 1;
      transition: opacity 1s ease;
    }
    #overlay h1 {
      font-size: 2.5rem;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }
    #intro-video {
      position: fixed;
      top: 0; left: 0;
      width: 100%; height: 100%;
      object-fit: cover;
      z-index: 5;
      opacity: 0;
      transition: opacity 1s ease;
    }
    canvas {
      display: block;
    }
  </style>
</head>
<body>
  <audio id="arena-music" loop></audio>
  <video id="intro-video"></video>
  <div id="overlay"><h1>Welcome to the Arena</h1></div>
  <canvas id="arena-canvas"></canvas>

  <script type="module">
    import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';

    const canvas = document.getElementById('arena-canvas');
    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x050509);

    const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 200);
    camera.position.set(0, 10, 40);

    const light = new THREE.DirectionalLight(0xffffff, 2);
    light.position.set(10, 20, 10);
    scene.add(light);

    const floorGeo = new THREE.CircleGeometry(20, 64);
    const floorMat = new THREE.MeshStandardMaterial({ color: 0x111133, metalness: 0.6, roughness: 0.3 });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.rotation.x = -Math.PI / 2;
    scene.add(floor);

    const ringGeo = new THREE.TorusGeometry(18, 0.4, 16, 100);
    const ringMat = new THREE.MeshStandardMaterial({ color: 0x00ffff, emissive: 0x003366, emissiveIntensity: 1.5 });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.position.y = 0.2;
    scene.add(ring);

    const clock = new THREE.Clock();

    function resize() {
      const w = window.innerWidth;
      const h = window.innerHeight;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }
    window.addEventListener('resize', resize);
    resize();

    function cameraFlyIn() {
      const duration = 3;
      let t = 0;
      const startPos = new THREE.Vector3(0, 30, 80);
      const endPos = new THREE.Vector3(0, 8, 25);
      function step() {
        const dt = clock.getDelta();
        t += dt;
        const alpha = Math.min(1, t / duration);
        camera.position.lerpVectors(startPos, endPos, alpha);
        camera.lookAt(0, 0, 0);
        if (alpha < 1) requestAnimationFrame(step);
      }
      step();
    }

    function animate() {
      requestAnimationFrame(animate);
      const dt = clock.getDelta();
      ring.rotation.y += dt * 0.8;
      renderer.render(scene, camera);
    }

    const overlay = document.getElementById('overlay');
    const introVideo = document.getElementById('intro-video');
    const arenaMusic = document.getElementById('arena-music');

    const savedIntro = localStorage.getItem('danceplanet_selected_intro');
    if (savedIntro) {
      introVideo.src = savedIntro;
    } else {
      introVideo.src = '/video/intro_grid.mp4';
    }

    const savedMusic = localStorage.getItem('danceplanet_selected_music');
    if (savedMusic) {
      arenaMusic.src = savedMusic;
      arenaMusic.volume = 0.8;
      arenaMusic.play().catch(() => {});
    }

    function startIntro() {
      introVideo.style.opacity = 1;
      introVideo.play().catch(() => {});
      setTimeout(() => { overlay.style.opacity = 0; }, 1000);
      setTimeout(() => { introVideo.style.opacity = 0; }, 3500);
      cameraFlyIn();
    }

    startIntro();
    animate();
  </script>
</body>
</html>
"""


def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")


def write_vercel_json():
    config = {
        "version": 2,
        "routes": [
            {"src": "/sounds/(.*)", "dest": "/sounds/$1"},
            {"src": "/video/(.*)", "dest": "/video/$1"},
            {"src": "/models/(.*)", "dest": "/models/$1"},
            {"src": "/pages/(.*)", "dest": "/pages/$1"},
        ],
    }
    DIST.mkdir(parents=True, exist_ok=True)
    with open(DIST / "vercel.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def copy_tree(src: Path, dst: Path):
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True)


def build_vercel_dist():
    print("[Vercel] Rebuilding vercel_dist/ ...")
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True, exist_ok=True)

    copy_tree(SRC_PAGES, DIST / "pages")
    copy_tree(SRC_PUBLIC / "sounds", DIST / "sounds")
    copy_tree(SRC_PUBLIC / "video", DIST / "video")
    copy_tree(SRC_PUBLIC / "models", DIST / "models")

    write_vercel_json()
    print("[Vercel] vercel_dist/ ready at:", DIST.resolve())


def parse_args():
    p = argparse.ArgumentParser(description="DancePlanet full generator + Vercel package")
    p.add_argument("--fast", action="store_true", help="Fast build (shorter audio/video)")
    p.add_argument("--skip-audio", action="store_true", help="Skip audio generation")
    p.add_argument("--skip-video", action="store_true", help="Skip video generation")
    p.add_argument("--skip-html", action="store_true", help="Skip HTML generation")
    return p.parse_args()


def main():
    args = parse_args()
    print("=== DancePlanet Full Generator + Vercel Package ===")
    ensure_dirs()
    ffmpeg_path = ensure_ffmpeg()

    if not args.skip_audio:
        print("\n[Step 1] Generating audio tracks...")
        make_music_tracks(fast=args.fast)
    else:
        print("\n[Step 1] Skipping audio generation (--skip-audio).")

    if not args.skip_video:
        print("\n[Step 2] Generating videos (this may take a bit)...")
        make_videos(ffmpeg_path, fast=args.fast)
    else:
        print("\n[Step 2] Skipping video generation (--skip-video).")

    if not args.skip_html:
        print("\n[Step 3] Writing HTML pages...")
        write_file(SRC_PAGES / "game.html", GAME_HTML)
        write_file(SRC_PAGES / "arena.html", ARENA_HTML)
    else:
        print("\n[Step 3] Skipping HTML generation (--skip-html).")

    print("\n[Step 4] Building Vercel deployment folder...")
    build_vercel_dist()

    print("\n=== Build Complete ===")
    print("Project root:      ", ROOT.resolve())
    print("Vercel package:    ", DIST.resolve())
    print("\nDeploy via Vercel with Root Directory = 'vercel_dist'.")


if __name__ == "__main__":
    main()
