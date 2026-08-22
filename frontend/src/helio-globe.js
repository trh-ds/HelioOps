/* <helio-globe> — Earth + magnetosphere under solar-wind load.
   Ported from the Claude Design project verbatim; only the THREE import at the
   top is new (the original pulled r134 off a CDN into window.THREE).
   Attributes: industry(aviation|grid|maritime|telecom) g-scale(1..5) mode(hero|right|ambient) */
import * as THREE_NS from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
window.THREE = window.THREE || THREE_NS

// Served from public/, not bundled — it is 8.4MB and must not block first paint.
var EARTH_GLB = import.meta.env.BASE_URL + 'models/earth.glb'

;(function () {
  var ACCENT = {
    aviation: [0.94, 0.64, 0.29],
    grid: [1.0, 0.42, 0.29],
    maritime: [0.29, 0.84, 1.0],
    telecom: [0.62, 0.48, 1.0]
  };
  var MODES = {
    hero:    { cam: [3.3, 0.95, 5.65], off: [0, 0, 0], dim: 1.0, fov: 34 },
    right:   { cam: [4.0, 0.8, 5.2], off: [1.35, -0.1, 0], dim: 0.78, fov: 36 },
    ambient: { cam: [3.8, 0.7, 7.4], off: [2.7, 0.45, 0], dim: 0.85, fov: 34 }
  };

  function whenTHREE(cb) {
    if (window.THREE) return cb(window.THREE);
    var t = setInterval(function () { if (window.THREE) { clearInterval(t); cb(window.THREE); } }, 40);
  }

  // Shue-like magnetopause standoff, theta measured from the sunward (+X) axis
  function mp(theta, r0) { return r0 * Math.pow(2 / (1 + Math.cos(Math.min(theta, 3.0))), 0.62); }

  function lerp(a, b, t) { return a + (b - a) * t; }

  function Globe(THREE, host) {
    var self = this;
    this.THREE = THREE;
    this.host = host;
    this.t = 0;
    this.state = { industry: 'aviation', g: 4, mode: 'hero' };
    this.cur = { g: 4, ax: ACCENT.aviation.slice(), dim: 1, camx: 3.3, camy: 0.95, camz: 5.65, offx: 0 };

    var scene = this.scene = new THREE.Scene();
    var cam = this.cam = new THREE.PerspectiveCamera(34, 1, 0.1, 260);
    cam.position.set(3.3, 0.95, 5.65);
    var renderer = this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x000000, 0);
    host.appendChild(renderer.domElement);
    renderer.domElement.style.cssText = 'display:block;width:100%;height:100%';

    this.uni = {
      time: { value: 0 },
      psz: { value: 1 },
      accent: { value: new THREE.Vector3(0.94, 0.64, 0.29) },
      gnorm: { value: 0.75 },
      dim: { value: 1 },
      sun: { value: new THREE.Vector3(1, 0.06, 0.12).normalize() }
    };
    var U = this.uni;

    var root = this.root = new THREE.Group();
    scene.add(root);

    /* ---------- starfield ---------- */
    function stars(count, radius, size, base) {
      var pos = new Float32Array(count * 3), sz = new Float32Array(count), ph = new Float32Array(count);
      for (var i = 0; i < count; i++) {
        var u = Math.random() * 2 - 1, a = Math.random() * Math.PI * 2, s = Math.sqrt(1 - u * u);
        var r = radius * (0.75 + Math.random() * 0.5);
        pos[i * 3] = r * s * Math.cos(a); pos[i * 3 + 1] = r * u; pos[i * 3 + 2] = r * s * Math.sin(a);
        sz[i] = size * (0.35 + Math.pow(Math.random(), 3) * 1.9);
        ph[i] = Math.random() * 6.283;
      }
      var g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      g.setAttribute('sz', new THREE.BufferAttribute(sz, 1));
      g.setAttribute('ph', new THREE.BufferAttribute(ph, 1));
      return new THREE.Points(g, new THREE.ShaderMaterial({
        uniforms: U, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
        vertexShader: 'attribute float sz;attribute float ph;uniform float time;uniform float psz;varying float v;' +
          'void main(){v=0.55+0.45*sin(time*0.7+ph);vec4 mv=modelViewMatrix*vec4(position,1.0);' +
          'gl_Position=projectionMatrix*mv;gl_PointSize=sz*psz*(160.0/-mv.z);}',
        fragmentShader: 'uniform float dim;varying float v;void main(){vec2 c=gl_PointCoord-0.5;' +
          'float d=1.0-smoothstep(0.06,0.5,length(c));if(d<=0.001)discard;' +
          'gl_FragColor=vec4(' + base + ',d*v*dim);}'
      }));
    }
    scene.add(stars(2200, 90, 2.4, 'vec3(0.86,0.88,1.0)'));
    scene.add(stars(520, 55, 3.0, 'vec3(0.72,0.66,1.0)'));

    /* ---------- earth ---------- */
    var earth = this.earth = new THREE.Group();
    earth.rotation.z = -0.409;
    root.add(earth);

    var body = new THREE.Mesh(new THREE.SphereGeometry(1, 72, 54), new THREE.ShaderMaterial({
      uniforms: U,
      vertexShader: 'varying vec3 vn;varying vec3 vw;varying vec3 vp;' +
        'void main(){vn=normalize(mat3(modelMatrix)*normal);vp=position;' +
        'vec4 w=modelMatrix*vec4(position,1.0);vw=w.xyz;gl_Position=projectionMatrix*viewMatrix*w;}',
      fragmentShader: 'uniform vec3 sun;uniform vec3 accent;uniform float dim;uniform float gnorm;' +
        'varying vec3 vn;varying vec3 vw;varying vec3 vp;' +
        'float h(vec3 p){return fract(sin(dot(p,vec3(17.3,113.7,49.1)))*43758.5453);}' +
        'float n3(vec3 p){vec3 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);' +
        'float a=mix(mix(mix(h(i),h(i+vec3(1,0,0)),f.x),mix(h(i+vec3(0,1,0)),h(i+vec3(1,1,0)),f.x),f.y),' +
        'mix(mix(h(i+vec3(0,0,1)),h(i+vec3(1,0,1)),f.x),mix(h(i+vec3(0,1,1)),h(i+vec3(1,1,1)),f.x),f.y),f.z);return a;}' +
        'void main(){vec3 V=normalize(cameraPosition-vw);float lam=dot(vn,sun);' +
        'float day=smoothstep(-0.20,0.45,lam);' +
        'float m=n3(vp*3.1)*0.6+n3(vp*7.7)*0.3+n3(vp*17.0)*0.1;' +
        'vec3 col;' +
        'vec3 sea=vec3(0.085,0.105,0.225);vec3 land=vec3(0.165,0.180,0.315);' +
        'vec3 base=mix(sea,land,smoothstep(0.45,0.60,m));' +
        'col=base*(0.17+day*1.45);' +
        'float fres=pow(1.0-max(dot(V,vn),0.0),3.2);' +
        'col+=accent*fres*(0.30+0.55*gnorm)*(0.35+0.65*day);' +
        'col+=vec3(0.34,0.40,0.95)*fres*0.30;' +
        'float night=1.0-day;col+=vec3(0.95,0.72,0.32)*night*step(0.80,m)*0.16;' +
        'gl_FragColor=vec4(col*dim,1.0);}'
    }));
    earth.add(body);

    /* ---------- realistic earth (GLB) ----------
       Swapped in for the procedural `body` above once it loads. The shader
       sphere stays until then and stays for good if the file is missing, so a
       failed fetch degrades to the old globe instead of an empty scene.

       The model is the only thing here with PBR materials — everything else is
       a ShaderMaterial lit by the `sun` uniform — so these two lights exist
       purely for it, aimed down the same sun vector. */
    var sunLight = this.sunLight = new THREE.DirectionalLight(0xfff4e6, 3.2);
    sunLight.position.copy(U.sun.value).multiplyScalar(12);
    scene.add(sunLight);
    scene.add(new THREE.AmbientLight(0x2b3157, 0.6));

    new GLTFLoader().load(EARTH_GLB, function (gltf) {
      var m = gltf.scene;

      /* The rest of the scene renders raw linear values with the renderer left
         on the default LinearEncoding. GLTFLoader tags colour maps as sRGB,
         which would then be decoded and never re-encoded — the model would come
         out muddy. Tagging them linear keeps it consistent with everything
         around it; brightness is trimmed on the light instead. */
      m.traverse(function (o) {
        if (!o.material) return;
        [o.material.map, o.material.emissiveMap].forEach(function (tex) {
          if (tex) { tex.encoding = THREE.LinearEncoding; }
        });
        o.material.needsUpdate = true;
      });

      // Normalise to the unit radius the scene is built around: graticule at
      // 1.008, atmosphere shell at 1.085, aurora ovals offset off 1.0.
      var box = new THREE.Box3().setFromObject(m);
      var size = box.getSize(new THREE.Vector3());
      var mid = box.getCenter(new THREE.Vector3());
      var k = 2 / Math.max(size.x, size.y, size.z);
      m.scale.setScalar(k);
      m.position.set(-mid.x * k, -mid.y * k, -mid.z * k);

      earth.remove(body);
      body.geometry.dispose();
      body.material.dispose();
      earth.add(m);
      self.model = m;
    }, undefined, function () { /* keep the procedural sphere */ });

    // surface dots
    (function () {
      var n = 11000, pos = new Float32Array(n * 3);
      for (var i = 0; i < n; i++) {
        var y = 1 - (i / (n - 1)) * 2, r = Math.sqrt(Math.max(0, 1 - y * y)), th = i * 2.39996;
        pos[i * 3] = Math.cos(th) * r * 1.004; pos[i * 3 + 1] = y * 1.004; pos[i * 3 + 2] = Math.sin(th) * r * 1.004;
      }
      var g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      earth.add(new THREE.Points(g, new THREE.ShaderMaterial({
        uniforms: U, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
        vertexShader: 'uniform vec3 sun;uniform float psz;varying float d;void main(){d=max(dot(normalize(mat3(modelMatrix)*position),sun),0.0);' +
          'vec4 mv=modelViewMatrix*vec4(position,1.0);gl_Position=projectionMatrix*mv;gl_PointSize=psz*(9.5/-mv.z);}',
        fragmentShader: 'uniform float dim;varying float d;void main(){vec2 c=gl_PointCoord-0.5;' +
          'if(length(c)>0.5)discard;gl_FragColor=vec4(vec3(0.62,0.70,0.95),(0.06+d*0.40)*dim);}'
      })));
    })();

    // graticule
    (function () {
      var pts = [], i, j, a, b, la;
      for (i = 0; i < 12; i++) {
        var lo = i / 12 * Math.PI * 2;
        for (j = 0; j < 72; j++) {
          a = -Math.PI / 2 + j / 72 * Math.PI; b = -Math.PI / 2 + (j + 1) / 72 * Math.PI;
          pts.push(Math.cos(a) * Math.cos(lo) * 1.008, Math.sin(a) * 1.008, Math.cos(a) * Math.sin(lo) * 1.008);
          pts.push(Math.cos(b) * Math.cos(lo) * 1.008, Math.sin(b) * 1.008, Math.cos(b) * Math.sin(lo) * 1.008);
        }
      }
      for (i = 1; i < 6; i++) {
        la = -Math.PI / 2 + i / 6 * Math.PI;
        var rr = Math.cos(la) * 1.008, yy = Math.sin(la) * 1.008;
        for (j = 0; j < 96; j++) {
          a = j / 96 * Math.PI * 2; b = (j + 1) / 96 * Math.PI * 2;
          pts.push(Math.cos(a) * rr, yy, Math.sin(a) * rr, Math.cos(b) * rr, yy, Math.sin(b) * rr);
        }
      }
      var g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(pts), 3));
      earth.add(new THREE.LineSegments(g, new THREE.ShaderMaterial({
        uniforms: U, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
        vertexShader: 'uniform vec3 sun;varying float d;void main(){d=max(dot(normalize(mat3(modelMatrix)*position),sun),0.0);' +
          'gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
        fragmentShader: 'uniform float dim;varying float d;void main(){gl_FragColor=vec4(vec3(0.45,0.55,0.92),(0.035+d*0.075)*dim);}'
      })));
    })();

    // atmosphere
    var atmo = new THREE.Mesh(new THREE.SphereGeometry(1.085, 64, 48), new THREE.ShaderMaterial({
      uniforms: U, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.BackSide,
      vertexShader: 'varying vec3 vn;varying vec3 vw;void main(){vn=normalize(mat3(modelMatrix)*normal);' +
        'vec4 w=modelMatrix*vec4(position,1.0);vw=w.xyz;gl_Position=projectionMatrix*viewMatrix*w;}',
      fragmentShader: 'uniform vec3 sun;uniform vec3 accent;uniform float dim;uniform float gnorm;uniform float time;' +
        'varying vec3 vn;varying vec3 vw;void main(){vec3 V=normalize(cameraPosition-vw);' +
        'float f=pow(1.0-max(dot(V,-vn),0.0),2.6);float lam=max(dot(-vn,sun),0.0);' +
        'vec3 c=mix(vec3(0.25,0.34,0.85),accent,0.35+0.45*gnorm);' +
        'float comp=pow(lam,3.0)*(0.35+0.9*gnorm)*(0.85+0.15*sin(time*1.6));' +
        'gl_FragColor=vec4(c*(f*0.55+comp*0.7),(f*0.30+comp*0.34)*dim);}'
    }));
    earth.add(atmo);

    // aurora ovals
    this.aurora = [];
    [1, -1].forEach(function (s) {
      var m = new THREE.Mesh(new THREE.TorusGeometry(0.42, 0.075, 8, 110), new THREE.ShaderMaterial({
        uniforms: U, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
        vertexShader: 'varying vec2 vu;void main(){vu=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
        fragmentShader: 'uniform float dim;uniform float gnorm;uniform float time;uniform vec3 accent;varying vec2 vu;' +
          'void main(){float band=sin(vu.y*6.283)*0.5+0.5;' +
          'float w=0.55+0.45*sin(vu.x*38.0+time*1.1)*sin(vu.x*13.0-time*0.6);' +
          'vec3 c=mix(vec3(0.20,0.95,0.62),accent,0.45);' +
          'gl_FragColor=vec4(c,band*w*(0.14+0.55*gnorm)*dim);}'
      }));
      m.rotation.x = Math.PI / 2; m.position.y = s * 0.90; m.scale.set(1, 1, 1);
      earth.add(m); self.aurora.push(m);
    });

    /* ---------- magnetopause shell + bow shock ---------- */
    function shellGeo(scale, nT, nP, thetaMax) {
      var pos = new Float32Array(nT * nP * 3), idx = [], uvs = new Float32Array(nT * nP * 2), k = 0;
      for (var i = 0; i < nT; i++) {
        var th = i / (nT - 1) * thetaMax;
        for (var j = 0; j < nP; j++) {
          var ph = j / (nP - 1) * Math.PI * 2, r = mp(th, 1) * scale, s = Math.sin(th);
          pos[k * 3] = r * Math.cos(th); pos[k * 3 + 1] = r * s * Math.cos(ph); pos[k * 3 + 2] = r * s * Math.sin(ph);
          uvs[k * 2] = i / (nT - 1); uvs[k * 2 + 1] = j / (nP - 1); k++;
        }
      }
      for (i = 0; i < nT - 1; i++) for (j = 0; j < nP - 1; j++) {
        var a = i * nP + j, b = a + 1, c = a + nP, d = c + 1;
        idx.push(a, c, b, b, c, d);
      }
      var g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      g.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
      g.setIndex(idx); g.computeVertexNormals();
      return g;
    }

    var shell = this.shell = new THREE.Mesh(shellGeo(1, 44, 72, 2.55), new THREE.ShaderMaterial({
      uniforms: U, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
      vertexShader: 'varying vec3 vn;varying vec3 vw;varying vec2 vu;' +
        'void main(){vn=normalize(mat3(modelMatrix)*normal);vu=uv;vec4 w=modelMatrix*vec4(position,1.0);' +
        'vw=w.xyz;gl_Position=projectionMatrix*viewMatrix*w;}',
      fragmentShader: 'uniform vec3 accent;uniform float time;uniform float dim;uniform float gnorm;' +
        'varying vec3 vn;varying vec3 vw;varying vec2 vu;' +
        'void main(){vec3 V=normalize(cameraPosition-vw);float f=pow(1.0-abs(dot(V,vn)),3.4);' +
        'float ripple=0.55+0.45*sin(vu.x*22.0-time*2.4+sin(vu.y*9.0)*1.4);' +
        'float nose=smoothstep(0.48,0.0,vu.x);' +
        'vec3 c=mix(vec3(0.30,0.38,0.95),accent,0.30+nose*0.55*gnorm);' +
        'float a=f*(0.05+0.30*nose*(0.4+0.6*gnorm))*(0.55+0.45*ripple);' +
        'float grid=step(0.965,fract(vu.y*36.0))+step(0.972,fract(vu.x*22.0));' +
        'a+=grid*f*0.16;gl_FragColor=vec4(c*(1.0+nose*gnorm*0.8),a*dim);}'
    }));
    root.add(shell);

    var shock = this.shock = new THREE.Mesh(shellGeo(1.42, 26, 52, 2.2), new THREE.ShaderMaterial({
      uniforms: U, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
      vertexShader: 'varying vec3 vn;varying vec3 vw;varying vec2 vu;' +
        'void main(){vn=normalize(mat3(modelMatrix)*normal);vu=uv;vec4 w=modelMatrix*vec4(position,1.0);' +
        'vw=w.xyz;gl_Position=projectionMatrix*viewMatrix*w;}',
      fragmentShader: 'uniform vec3 accent;uniform float time;uniform float dim;uniform float gnorm;' +
        'varying vec3 vn;varying vec3 vw;varying vec2 vu;' +
        'void main(){vec3 V=normalize(cameraPosition-vw);float f=pow(1.0-abs(dot(V,vn)),4.0);' +
        'float p=0.5+0.5*sin(vu.x*10.0-time*3.0);float nose=smoothstep(0.55,0.0,vu.x);' +
        'gl_FragColor=vec4(mix(vec3(0.55,0.60,1.0),accent,0.5),f*nose*(0.02+0.09*gnorm)*p*dim);}'
    }));
    root.add(shock);

    /* ---------- dipole field lines ---------- */
    (function () {
      var pos = [], us = [], lines = [[1.72, 14], [2.45, 10], [3.35, 6]];
      lines.forEach(function (cfg) {
        var L = cfg[0], count = cfg[1];
        for (var n = 0; n < count; n++) {
          var lon = n / count * Math.PI * 2 + (L * 0.7);
          var lamMax = Math.acos(Math.sqrt(1 / L)), N = 70, prev = null;
          for (var i = 0; i <= N; i++) {
            var lam = -lamMax + (i / N) * 2 * lamMax, cl = Math.cos(lam), r = L * cl * cl;
            var x = r * cl * Math.cos(lon), y = r * Math.sin(lam), z = r * cl * Math.sin(lon);
            // tail stretch + dayside clamp against the magnetopause
            var th = Math.acos(Math.max(-1, Math.min(1, x / Math.max(r, 1e-4))));
            var lim = mp(th, 3.05) * 0.94;
            if (r > lim) { var k2 = lim / r; x *= k2; y *= k2; z *= k2; }
            if (x < 0) x *= 1.5;
            var p = [x, y, z];
            if (prev) { pos.push(prev[0], prev[1], prev[2], p[0], p[1], p[2]); us.push(i / N, (i + 1) / N); }
            prev = p;
          }
        }
      });
      var g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(pos), 3));
      g.setAttribute('u', new THREE.BufferAttribute(new Float32Array(us), 1));
      var m = new THREE.LineSegments(g, new THREE.ShaderMaterial({
        uniforms: U, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
        vertexShader: 'attribute float u;varying float vu;varying float vx;' +
          'void main(){vu=u;vx=position.x;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
        fragmentShader: 'uniform float time;uniform float dim;uniform float gnorm;uniform vec3 accent;' +
          'varying float vu;varying float vx;void main(){' +
          'float flow=fract(vu*2.0-time*0.10);float d=pow(flow,2.4);' +
          'vec3 c=mix(vec3(0.36,0.45,0.98),accent,smoothstep(0.0,4.0,vx)*0.7);' +
          'gl_FragColor=vec4(c,(0.05+0.17*d)*(0.5+0.5*gnorm)*dim);}'
      }));
      earth.add(m); self.field = m;
    })();

    /* ---------- solar wind ---------- */
    (function () {
      var n = self.windN = 900;
      self.wind = new Float32Array(n * 3);
      var life = self.windLife = new Float32Array(n);
      for (var i = 0; i < n; i++) {
        self.wind[i * 3] = 1 + Math.random() * 7;
        var a = Math.random() * Math.PI * 2, rr = Math.sqrt(Math.random()) * 2.7;
        self.wind[i * 3 + 1] = Math.cos(a) * rr; self.wind[i * 3 + 2] = Math.sin(a) * rr;
        life[i] = Math.random();
      }
      var g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(self.wind, 3));
      g.setAttribute('life', new THREE.BufferAttribute(life, 1));
      self.windGeo = g;
      root.add(new THREE.Points(g, new THREE.ShaderMaterial({
        uniforms: U, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
        vertexShader: 'attribute float life;uniform float psz;varying float vl;varying float vx;' +
          'void main(){vl=life;vx=position.x;vec4 mv=modelViewMatrix*vec4(position,1.0);' +
          'gl_Position=projectionMatrix*mv;gl_PointSize=(1.0+life*2.6)*psz*(8.0/-mv.z);}',
        fragmentShader: 'uniform vec3 accent;uniform float dim;uniform float gnorm;varying float vl;varying float vx;' +
          'void main(){vec2 c=gl_PointCoord-0.5;float d=1.0-smoothstep(0.05,0.5,length(c));if(d<=0.001)discard;' +
          'float fade=smoothstep(-6.5,-1.0,vx)*0.6+0.4;' +
          'gl_FragColor=vec4(mix(accent,vec3(1.0,0.93,0.82),0.35),d*(0.16+0.62*gnorm)*fade*dim);}'
      })));
    })();

    /* ---------- industry overlays ---------- */
    function greatArc(latA, lonA, latB, lonB, bulge, seg) {
      var A = ll(latA, lonA), B = ll(latB, lonB), out = [];
      for (var i = 0; i <= seg; i++) {
        var t = i / seg, d = Math.acos(Math.max(-1, Math.min(1, A.dot(B))));
        var s = Math.sin(d) || 1e-4;
        var v = A.clone().multiplyScalar(Math.sin((1 - t) * d) / s).add(B.clone().multiplyScalar(Math.sin(t * d) / s));
        v.normalize().multiplyScalar(1 + bulge * Math.sin(Math.PI * t) + 0.012);
        out.push(v);
      }
      return out;
    }
    function ll(lat, lon) {
      var a = lat * Math.PI / 180, b = lon * Math.PI / 180;
      return new THREE.Vector3(Math.cos(a) * Math.cos(b), Math.sin(a), Math.cos(a) * Math.sin(b));
    }
    function pathLines(paths, color, weight) {
      var pos = [], us = [];
      paths.forEach(function (p) {
        for (var i = 0; i < p.length - 1; i++) {
          pos.push(p[i].x, p[i].y, p[i].z, p[i + 1].x, p[i + 1].y, p[i + 1].z);
          us.push(i / (p.length - 1), (i + 1) / (p.length - 1));
        }
      });
      var g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(pos), 3));
      g.setAttribute('u', new THREE.BufferAttribute(new Float32Array(us), 1));
      var m = new THREE.ShaderMaterial({
        uniforms: THREE.UniformsUtils.merge([{ op: { value: 0 } }]), transparent: true,
        depthWrite: false, blending: THREE.AdditiveBlending,
        vertexShader: 'attribute float u;varying float vu;void main(){vu=u;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}',
        fragmentShader: 'uniform float op;uniform float time;varying float vu;void main(){' +
          'float f=pow(fract(vu*1.6-time*0.28),3.0);' +
          'gl_FragColor=vec4(' + color + ',op*(' + weight + '+0.85*f));}'
      });
      m.uniforms.time = U.time; m.uniforms.dim = U.dim;
      return new THREE.LineSegments(g, m);
    }
    function ring(lat, color, weight) {
      var p = [], i;
      for (i = 0; i <= 128; i++) p.push(ll(lat, i / 128 * 360));
      return pathLines([p], color, weight);
    }
    function pins(list, color) {
      var pos = new Float32Array(list.length * 3), ph = new Float32Array(list.length);
      list.forEach(function (c, i) {
        var v = ll(c[0], c[1]).multiplyScalar(1.02);
        pos[i * 3] = v.x; pos[i * 3 + 1] = v.y; pos[i * 3 + 2] = v.z; ph[i] = Math.random() * 6.283;
      });
      var g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      g.setAttribute('ph', new THREE.BufferAttribute(ph, 1));
      var m = new THREE.ShaderMaterial({
        uniforms: { op: { value: 0 }, time: U.time, dim: U.dim, psz: U.psz }, transparent: true,
        depthWrite: false, blending: THREE.AdditiveBlending,
        vertexShader: 'attribute float ph;uniform float time;uniform float psz;varying float vp;' +
          'void main(){vp=0.5+0.5*sin(time*2.2+ph);vec4 mv=modelViewMatrix*vec4(position,1.0);' +
          'gl_Position=projectionMatrix*mv;gl_PointSize=(3.0+vp*3.0)*psz*(2.6/-mv.z);}',
        fragmentShader: 'uniform float op;uniform float dim;varying float vp;void main(){vec2 c=gl_PointCoord-0.5;' +
          'float l=length(c);float core=1.0-smoothstep(0.10,0.28,l);float halo=1.0-smoothstep(0.2,0.5,l);' +
          'gl_FragColor=vec4(' + color + ',op*(core*0.9+halo*0.30*vp));}'
      });
      return new THREE.Points(g, m);
    }

    this.overlays = {};
    var ov;

    // AVIATION — polar tracks + the G4 reroute latitude (70°N)
    ov = new THREE.Group();
    ov.add(pathLines([
      greatArc(51, -0.5, 40, -74, 0.16, 60), greatArc(53, -2, 35, -118, 0.20, 70),
      greatArc(60, 11, 45, -123, 0.20, 70), greatArc(50, 8, 43, -79, 0.15, 60)
    ], 'vec3(0.96,0.70,0.36)', 0.30));
    ov.add(ring(70, 'vec3(1.0,0.55,0.30)', 0.28));
    ov.add(ring(78, 'vec3(0.98,0.78,0.45)', 0.12));
    ov.add(pins([[51, -0.5], [40, -74], [35, -118], [60, 11], [64, -22]], 'vec3(1.0,0.78,0.42)'));
    earth.add(ov); this.overlays.aviation = ov;

    // GRID — mid-latitude GIC corridor
    ov = new THREE.Group();
    ov.add(ring(55, 'vec3(1.0,0.45,0.32)', 0.30));
    ov.add(ring(45, 'vec3(1.0,0.55,0.40)', 0.12));
    ov.add(pathLines([
      greatArc(55, -95, 50, -75, 0.02, 30), greatArc(58, 12, 55, 28, 0.02, 30),
      greatArc(52, -110, 56, -130, 0.02, 24)
    ], 'vec3(1.0,0.62,0.42)', 0.45));
    ov.add(pins([[55, -95], [50, -75], [58, 12], [55, 28], [52, -110], [56, -130], [60, 25]], 'vec3(1.0,0.60,0.40)'));
    earth.add(ov); this.overlays.grid = ov;

    // MARITIME — high-latitude sea lanes + GMDSS
    ov = new THREE.Group();
    ov.add(pathLines([
      greatArc(66, -50, 70, 30, 0.05, 60), greatArc(60, -140, 66, 170, 0.05, 50),
      greatArc(72, 60, 74, 120, 0.05, 40)
    ], 'vec3(0.36,0.86,1.0)', 0.32));
    ov.add(ring(66.5, 'vec3(0.42,0.80,1.0)', 0.14));
    ov.add(pins([[66, -50], [70, 30], [66, 170], [72, 60], [74, 120], [60, -140]], 'vec3(0.50,0.90,1.0)'));
    earth.add(ov); this.overlays.maritime = ov;

    // TELECOM — orbital link + ground stations
    ov = new THREE.Group();
    (function () {
      var p = [], i;
      for (i = 0; i <= 128; i++) {
        var a = i / 128 * Math.PI * 2;
        p.push(new THREE.Vector3(Math.cos(a) * 1.62, Math.sin(a) * 0.30, Math.sin(a) * 1.58));
      }
      ov.add(pathLines([p], 'vec3(0.66,0.54,1.0)', 0.22));
    })();
    ov.add(pathLines([
      greatArc(30, -100, 55, 20, 0.42, 50), greatArc(-10, 60, 35, 140, 0.38, 50),
      greatArc(20, -60, -25, -50, 0.30, 40)
    ], 'vec3(0.70,0.58,1.0)', 0.34));
    ov.add(pins([[30, -100], [55, 20], [-10, 60], [35, 140], [20, -60], [-25, -50]], 'vec3(0.76,0.64,1.0)'));
    earth.add(ov); this.overlays.telecom = ov;

    Object.keys(this.overlays).forEach(function (k) {
      self.overlays[k].traverse(function (o) { if (o.material) o.material.uniforms.op.value = 0; });
    });

    /* ---------- loop ---------- */
    var clock = new THREE.Clock();
    this.resize();
    if (window.ResizeObserver) {
      this.ro = new ResizeObserver(function () { self.resize(); });
      this.ro.observe(host);
    }
    (function tick() {
      self.raf = requestAnimationFrame(tick);
      var dt = Math.min(clock.getDelta(), 0.05);
      self.update(dt);
      renderer.render(scene, cam);
    })();
  }

  Globe.prototype.resize = function () {
    var w = this.host.clientWidth || 800, h = this.host.clientHeight || 600;
    this.renderer.setSize(w, h, false);
    this.uni.psz.value = this.renderer.getPixelRatio() * (h / 900);
    this.cam.aspect = w / h; this.cam.updateProjectionMatrix();
  };

  Globe.prototype.update = function (dt) {
    var s = this.state, c = this.cur, U = this.uni, k = Math.min(dt * 2.2, 1), self = this;
    this.t += dt; U.time.value = this.t;

    var tgt = ACCENT[s.industry] || ACCENT.aviation;
    c.ax[0] = lerp(c.ax[0], tgt[0], k); c.ax[1] = lerp(c.ax[1], tgt[1], k); c.ax[2] = lerp(c.ax[2], tgt[2], k);
    U.accent.value.set(c.ax[0], c.ax[1], c.ax[2]);

    c.g = lerp(c.g, s.g, k);
    var gn = (c.g - 1) / 4;
    U.gnorm.value = gn;

    var m = MODES[s.mode] || MODES.hero;
    c.dim = lerp(c.dim, m.dim, k * 0.6); U.dim.value = c.dim;
    // The model is lit, not shaded by `dim`, so it has to be dimmed by hand.
    this.sunLight.intensity = 3.2 * c.dim;
    c.camx = lerp(c.camx, m.cam[0], k * 0.5); c.camy = lerp(c.camy, m.cam[1], k * 0.5); c.camz = lerp(c.camz, m.cam[2], k * 0.5);
    c.offx = lerp(c.offx, m.off[0], k * 0.5);
    this.cam.position.set(c.camx + Math.sin(this.t * 0.11) * 0.10, c.camy + Math.sin(this.t * 0.08) * 0.06, c.camz);
    this.cam.lookAt(c.offx * -1.0, m.off[1], 0);
    if (Math.abs(this.cam.fov - m.fov) > 0.01) { this.cam.fov = lerp(this.cam.fov, m.fov, k * 0.5); this.cam.updateProjectionMatrix(); }

    this.earth.rotation.y += dt * 0.045;

    // magnetopause compression: standoff shrinks as the storm strengthens
    var r0 = 2.75 - gn * 0.55;
    this.shell.scale.set(r0, r0, r0);
    this.shock.scale.set(r0, r0, r0);
    this.shell.rotation.z = -0.05 * gn;

    this.aurora.forEach(function (a, i) {
      var sc = 1 + gn * 0.48, rr = 0.42 * sc;
      a.scale.set(sc, sc, 1);
      a.position.y = (i === 0 ? 1 : -1) * Math.sqrt(Math.max(0.04, 1 - rr * rr)) * 1.004;
    });

    // solar wind advection + deflection around the magnetopause
    var arr = this.wind, n = this.windN, sp = (0.9 + gn * 2.2) * dt, lim = r0 * 1.02;
    for (var i = 0; i < n; i++) {
      var x = arr[i * 3] - sp, y = arr[i * 3 + 1], z = arr[i * 3 + 2];
      if (x < -6.5) {
        x = 5 + Math.random() * 3.5;
        var a2 = Math.random() * Math.PI * 2, rr = Math.sqrt(Math.random()) * 2.7;
        y = Math.cos(a2) * rr; z = Math.sin(a2) * rr;
      }
      var r = Math.sqrt(x * x + y * y + z * z);
      if (r > 0.001) {
        var th = Math.acos(Math.max(-1, Math.min(1, x / r))), rmp = mp(th, lim);
        if (r < rmp) { var f = rmp / r; x *= f; y *= f; z *= f; }
      }
      arr[i * 3] = x; arr[i * 3 + 1] = y; arr[i * 3 + 2] = z;
    }
    this.windGeo.attributes.position.needsUpdate = true;

    Object.keys(this.overlays).forEach(function (key) {
      var want = key === s.industry ? 1 : 0;
      self.overlays[key].traverse(function (o) {
        if (!o.material || !o.material.uniforms.op) return;
        var u = o.material.uniforms.op;
        u.value = lerp(u.value, want, k * 0.7);
        o.visible = u.value > 0.004;
      });
    });
  };

  Globe.prototype.dispose = function () {
    cancelAnimationFrame(this.raf);
    if (this.ro) this.ro.disconnect();
    this.renderer.dispose();
    if (this.renderer.domElement.parentNode) this.renderer.domElement.parentNode.removeChild(this.renderer.domElement);
  };

  var HelioGlobe = function () { return Reflect.construct(HTMLElement, [], HelioGlobe); };
  HelioGlobe.prototype = Object.create(HTMLElement.prototype);
  HelioGlobe.prototype.constructor = HelioGlobe;
  Object.setPrototypeOf(HelioGlobe, HTMLElement);

  HelioGlobe.observedAttributes = ['industry', 'g-scale', 'gscale', 'mode'];
  Object.defineProperty(HelioGlobe.prototype, 'gScale', {
    set: function (v) { this._gScale = v; this.sync(); },
    get: function () { return this._gScale; }
  });
  Object.defineProperty(HelioGlobe.prototype, 'industryProp', {
    set: function (v) { this._ind = v; this.sync(); },
    get: function () { return this._ind; }
  });
  HelioGlobe.prototype.connectedCallback = function () {
    var self = this;
    this.style.cssText = 'display:block;width:100%;height:100%';
    if (this._g) return;
    whenTHREE(function (THREE) {
      if (self._g || !self.isConnected) return;
      self._g = new Globe(THREE, self);
      self.sync();
    });
  };
  HelioGlobe.prototype.disconnectedCallback = function () { if (this._g) { this._g.dispose(); this._g = null; } };
  HelioGlobe.prototype.attributeChangedCallback = function () { this.sync(); };
  HelioGlobe.prototype.sync = function () {
    if (!this._g) return;
    var ind = this.getAttribute('industry') || this._ind;
    var raw = this.getAttribute('g-scale') || this.getAttribute('gscale');
    var g = parseFloat(raw != null ? raw : this._gScale);
    var md = this.getAttribute('mode');
    if (ACCENT[ind]) this._g.state.industry = ind;
    if (!isNaN(g)) this._g.state.g = Math.max(1, Math.min(5, g));
    if (MODES[md]) this._g.state.mode = md;
  };
  if (!window.customElements.get('helio-globe')) window.customElements.define('helio-globe', HelioGlobe);
})();
