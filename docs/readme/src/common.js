// Dùng chung cho các trang ảnh README: ngôn ngữ + chủ đề từ URL (?lang=ru&theme=dark), điền chữ, nét tay có seed
// cố định (dựng lại lúc nào cũng ra đúng một hình), vẽ bằng rough.js.
(function () {
  const q = new URLSearchParams(location.search);
  const lang = q.get("lang") || "en";
  const theme = q.get("theme") || "light";
  document.documentElement.dataset.theme = theme;
  document.documentElement.lang = lang;
  const S = window.STRINGS[lang];

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const rnd = mulberry32(1909);   // năm SOS đầu tiên được phát

  function get(path) { return path.split(".").reduce((o, k) => (o == null ? o : o[k]), S); }

  // Điền chữ vào [data-t]; phần tử .hand thì tách từng từ để nghiêng/lệch dòng nhẹ như viết tay thật.
  function fill(root) {
    (root || document).querySelectorAll("[data-t]").forEach((el) => {
      const v = get(el.dataset.t);
      if (v == null) throw new Error("thiếu chuỗi " + lang + ":" + el.dataset.t);
      setText(el, String(v));
    });
  }
  function setText(el, text) {
    el.textContent = "";
    if (!el.classList.contains("hand") && !el.classList.contains("note")) { el.textContent = text; return; }
    const amp = parseFloat(el.dataset.jitter || "1");
    text.split(/(\s+)/).forEach((part) => {
      if (/^\s+$/.test(part)) { el.appendChild(document.createTextNode(part)); return; }
      const s = document.createElement("span");
      s.className = "w";
      s.textContent = part;
      s.style.transform = `translateY(${((rnd() - 0.5) * 2.4 * amp).toFixed(2)}px) rotate(${((rnd() - 0.5) * 2.2 * amp).toFixed(2)}deg)`;
      el.appendChild(s);
    });
  }

  function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

  // Mũi tên vẽ tay: thân cong nhẹ + hai nét đầu mũi.
  function arrow(rc, svg, x1, y1, x2, y2, o) {
    o = Object.assign({ stroke: css("--note"), strokeWidth: 1.8, roughness: 0.9, bow: 0.18, head: 13, seed: 7 }, o || {});
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2, dx = x2 - x1, dy = y2 - y1;
    const cx = mx - dy * o.bow, cy = my + dx * o.bow;
    const path = `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`;
    svg.appendChild(rc.path(path, { stroke: o.stroke, strokeWidth: o.strokeWidth, roughness: o.roughness, seed: o.seed }));
    const ang = Math.atan2(y2 - cy, x2 - cx);
    for (const s of [-1, 1]) {
      const a = ang + Math.PI + s * 0.42;
      svg.appendChild(rc.line(x2, y2, x2 + Math.cos(a) * o.head, y2 + Math.sin(a) * o.head,
        { stroke: o.stroke, strokeWidth: o.strokeWidth, roughness: o.roughness * 0.6, seed: o.seed + 1 + s }));
    }
  }

  // Chấm/gạch Morse của một chuỗi: [{ch, marks:[[x0,x1],...], x0, x1}] theo đơn vị nhịp (chấm 1, gạch 3).
  const MORSE = { A: ".-", B: "-...", C: "-.-.", D: "-..", E: ".", F: "..-.", G: "--.", H: "....", I: "..", J: ".---",
    K: "-.-", L: ".-..", M: "--", N: "-.", O: "---", P: ".--.", Q: "--.-", R: ".-.", S: "...", T: "-", U: "..-",
    V: "...-", W: ".--", X: "-..-", Y: "-.--", Z: "--.." };
  function morseLayout(text) {
    const out = [];
    let t = 0;
    for (const ch of text) {
      const code = MORSE[ch];
      const start = t, marks = [];
      [...code].forEach((e, i) => {
        if (i) t += 1;
        const len = e === "." ? 1 : 3;
        marks.push([t, t + len]);
        t += len;
      });
      out.push({ ch, marks, x0: start, x1: t });
      t += 3;
    }
    return { chars: out, units: t - 3 };
  }

  window.MD = { lang, theme, S, get, fill, setText, css, arrow, rnd, morseLayout,
    ready(draw) {
      // tải font TRƯỚC khi điền chữ: trình duyệt chỉ tải @font-face khi đã có chữ dùng tới nó
      Promise.all([
        document.fonts.load('40px "Hand"', "MorseDesk ӘҚҰ"),
        document.fonts.load('16px "Print"', "Radiogram ӘҚҰ"),
        document.fonts.load('bold 16px "Print"', "Radiogram ӘҚҰ"),
      ]).then(() => document.fonts.ready).then(() => {
        fill();
        draw();
        document.body.dataset.ready = "1";
      });
    } };
})();
