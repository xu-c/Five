"use strict";

const strings = {
  zh: {
    language: "English", lan: "局域网联机", code: "房间码", join: "加入房间", back: "返回",
    wait: "等待对手加入", joining: "正在加入房间…", reconnect: "连接中断，正在重连…",
    black: "执黑", white: "执白", free: "自由", renju: "连珠禁手", position: "第 {n} 手",
    yours: ["", "你执黑，请落子", "你执白，请落子"], theirs: ["", "黑棋落子", "白棋落子"],
    result: ["和棋", "黑棋胜", "白棋胜"], place: "落子", leave: "退出房间",
    leaving: "正在退出房间…", on: "音效开启", off: "音效关闭", rules: "规则说明", board: "五子棋棋盘",
    freestyle: "自由。黑白连成五颗或更多即胜。",
    renjuRule: "连珠禁手。黑棋恰好五连获胜，白棋五连或更长即胜。黑棋三三、四四或长连判白胜，恰好五连优先。",
    wrong_code: "房间码错误", room_full: "房间已满", room_closed: "房间已结束",
    not_turn: "还不能落子", stale_move: "棋局已更新", occupied: "该点不能落子",
    connection_error: "连接失败，请重试", confirmLeave: "离开会结束这间房。确定离开？",
    three: "三三", four: "四四", overline: "长连",
    try_later: "配对服务繁忙，请稍后重试。",
    create: "创建房间", creating: "正在创建房间…",
    roomGuide: "Zero 和网页可以互相加入。双方请连接同一局域网，配对时需要联网。",
    webJoin: "输入对手分享的 10 位房间码。",
    webCreate: "创建后把 10 位房间码发给对手。双方请连接同一局域网。",
    webWait: "请保持此标签页打开，配对码 5 分钟内有效。",
    pair_failed: "配对中断。请确认双方在同一局域网，然后重新创建或加入。",
    pair_expired: "房间码已过期，请重新创建。",
    pair_unavailable: "暂时无法连接配对服务，请稍后重试。",
    first: "先手", firstHost: "房主", firstGuest: "加入方", rule: "规则", size: "棋盘",
    allowUndo: "允许悔棋", undo: "悔棋", cannot_undo: "当前无法悔棋",
  },
  en: {
    language: "简体中文", lan: "LAN play", code: "Room code", join: "Join room", back: "Back",
    wait: "Waiting for opponent", joining: "Joining room…", reconnect: "Connection lost. Reconnecting…",
    black: "Black", white: "White", free: "Freestyle", renju: "Renju fouls", position: "Move {n}",
    yours: ["", "Your turn (Black)", "Your turn (White)"], theirs: ["", "Black to move", "White to move"],
    result: ["Draw", "Black wins", "White wins"], place: "Place", leave: "Leave room",
    leaving: "Leaving room…", on: "Sound on", off: "Sound off", rules: "Rules guide", board: "Gomoku board",
    freestyle: "Freestyle. Either side wins with five or more in a row.",
    renjuRule: "Renju fouls. Black wins with exactly five. White wins with five or more. Black loses on double three, double four or overline unless the move also makes exactly five.",
    wrong_code: "Wrong room code", room_full: "Room is full", room_closed: "Room closed",
    not_turn: "Cannot play now", stale_move: "Board updated", occupied: "Point unavailable",
    connection_error: "Connection failed. Try again", confirmLeave: "Leaving closes the room. Leave now?",
    three: "Double three", four: "Double four", overline: "Overline",
    try_later: "Pairing service is busy. Try again shortly.",
    create: "Create room", creating: "Creating room…",
    roomGuide: "Play across Zero devices and browsers. Use the same LAN. Pairing needs internet access.",
    webJoin: "Enter the 10-digit code from your opponent.",
    webCreate: "Share the 10-digit code after creating the room. Both players must be on the same LAN.",
    webWait: "Keep this tab open. The pairing code expires in five minutes.",
    pair_failed: "Pairing was interrupted. Check that both players are on the same LAN, then try again.",
    pair_expired: "The room code expired. Create a new room.",
    pair_unavailable: "The pairing service is temporarily unavailable. Try again shortly.",
    first: "First move", firstHost: "Host", firstGuest: "Guest", rule: "Rules", size: "Board",
    allowUndo: "Allow undo", undo: "Undo", cannot_undo: "Cannot undo now",
  },
};

const byId = id => document.getElementById(id);
const canvas = byId("board");
const ctx = canvas.getContext("2d");
const directions = {arrowup:[0,-1], f:[0,-1], arrowdown:[0,1], x:[0,1],
                    arrowleft:[-1,0], z:[-1,0], arrowright:[1,0], c:[1,0]};
let seat = null;
let lang = localStorage.getItem("five-language") === "en" ? "en" : "zh";
let sound = localStorage.getItem("five-sound") !== "off";
let state = null, cursor = [7, 7], message = "", disconnected = false;
let busy = false, pendingAction = null, pollTimer = null, mode = "", peer = null;

function clearSeat() {
  peer?.close();
  peer = null;
  seat = null;
  state = null;
  pendingAction = null;
  disconnected = false;
}

function accept(next) {
  if (!state) cursor = [Math.floor(next.size / 2), Math.floor(next.size / 2)];
  if (state && next.moves.length < state.moves.length && next.turn === seat.color) {
    cursor = state.moves[next.moves.length];
  }
  if (sound && state && next.moves.length > state.moves.length) {
    const audio = byId("stone");
    audio.currentTime = 0;
    audio.play().catch(() => {});
  }
  state = next;
  disconnected = false;
}

function canPlay() {
  return state && state.ready && !state.ended && !disconnected && state.turn === seat.color;
}

function canUndo() {
  return canPlay() && state.undo && state.moves.length >= 2 && !pendingAction;
}

function queuePoll(delay = 350) {
  clearTimeout(pollTimer);
  if (seat) pollTimer = setTimeout(poll, delay);
}

async function poll() {
  if (!seat || busy) return;
  const action = pendingAction;
  pendingAction = null;
  busy = true;
  try {
    accept(await peer.call(action?.name || "state", action?.body || {}));
    if (action) message = "";
  } catch (error) {
    if (["room_closed", "pair_failed", "pair_expired"].includes(error.message)) {
      clearSeat();
      mode = "";
      message = error.message;
    } else if (["not_turn", "stale_move", "occupied", "cannot_undo"].includes(error.message)) {
      message = error.message;
    } else {
      disconnected = true;
    }
  } finally {
    busy = false;
    render();
    queuePoll(pendingAction ? 0 : disconnected ? 1000 : 350);
  }
}

function selectMode(value) {
  mode = value;
  message = "";
  byId("room-form").reset();
  render();
  if (mode === "join") byId("code").focus();
}

byId("create-mode").onclick = () => selectMode("create");
byId("join-mode").onclick = () => selectMode("join");
byId("back").onclick = () => selectMode("");

byId("room-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (!busy && mode) await enterRoom();
});

async function enterRoom() {
  const creating = mode === "create";
  busy = true;
  message = creating ? "creating" : "joining";
  render();
  try {
    const options = {size: Number(byId("size").value), renju: byId("rule").value === "renju",
      host_first: byId("first").value === "host", undo: byId("allow-undo").checked};
    peer = new BrowserPeer(creating ? new PeerMatch(options) : null);
    const reply = creating ? await peer.host() : await peer.join(byId("code").value);
    seat = {color: reply.color, code: reply.code};
    accept(reply.state);
    message = "";
  } catch (error) {
    clearSeat();
    message = ["wrong_code", "room_full", "try_later", "pair_unavailable"].includes(error.message)
      ? error.message : "pair_failed";
  } finally {
    busy = false;
    render();
    if (seat) canvas.focus();
    queuePoll();
  }
}

byId("leave").onclick = async () => {
  if (busy || !seat || !confirm(strings[lang].confirmLeave)) return;
  clearTimeout(pollTimer);
  busy = true;
  message = "leaving";
  render();
  try {
    await peer.call("leave", {});
    clearSeat();
    mode = "";
    message = "room_closed";
  } catch (error) {
    clearSeat();
    mode = "";
    message = "room_closed";
  } finally {
    busy = false;
    render();
    queuePoll();
  }
};

byId("language").onclick = () => {
  lang = lang === "zh" ? "en" : "zh";
  localStorage.setItem("five-language", lang);
  render();
};

byId("sound").onclick = () => {
  sound = !sound;
  localStorage.setItem("five-sound", sound ? "on" : "off");
  render();
};

function place() {
  if (!canPlay() || pendingAction) return;
  pendingAction = {name: "move", body: {x: cursor[0], y: cursor[1], ply: state.moves.length,
                                         revision: state.revision}};
  if (!busy) queuePoll(0);
}

function undo() {
  if (!canUndo()) return;
  pendingAction = {name: "undo", body: {revision: state.revision}};
  if (!busy) queuePoll(0);
}

byId("undo").onclick = () => { undo(); canvas.focus(); };

document.addEventListener("keydown", event => {
  if (!state || !seat || /^(INPUT|BUTTON|SUMMARY)$/.test(event.target.tagName)) return;
  const direction = directions[event.key.toLowerCase()];
  if (direction) {
    event.preventDefault();
    cursor = cursor.map((value, i) => (value + direction[i] + state.size) % state.size);
    render();
  } else if (event.key === "Enter" && !event.repeat) {
    event.preventDefault();
    place();
  } else if (event.key.toLowerCase() === "u" && !event.repeat) {
    undo();
  }
});

canvas.addEventListener("click", event => {
  if (!state || state.ended) return;
  const rect = canvas.getBoundingClientRect();
  const {margin, step} = geometry();
  cursor = [event.clientX - rect.left, event.clientY - rect.top].map((value, i) =>
    Math.max(0, Math.min(state.size - 1,
      Math.round((value * canvas.width / (i ? rect.height : rect.width) - margin) / step))));
  render();
  place();
});

function geometry() {
  const margin = 28;
  return {margin, step: (canvas.width - 2 * margin) / (state.size - 1)};
}

function drawBoard() {
  const {margin, step} = geometry();
  const pixel = point => point.map(value => margin + value * step);
  const radius = step * .39;
  const end = canvas.width - margin;
  ctx.fillStyle = "#d8af75";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.beginPath();
  ctx.strokeStyle = "#78542f";
  ctx.lineWidth = 2;
  for (let i = 0; i < state.size; i++) {
    const p = margin + i * step;
    ctx.moveTo(p, margin); ctx.lineTo(p, end);
    ctx.moveTo(margin, p); ctx.lineTo(end, p);
  }
  ctx.stroke();
  const dot = (point, r, fill) => {
    ctx.beginPath();
    ctx.arc(...pixel(point), r, 0, Math.PI * 2);
    ctx.fillStyle = fill;
    ctx.fill();
  };
  const center = Math.floor(state.size / 2), edge = state.size - 4;
  for (const point of [[center,center],[3,3],[3,edge],[edge,3],[edge,edge]]) dot(point, 4, "#78542f");
  state.moves.forEach((point, i) => {
    dot(point, radius, "#4f3623");
    dot(point, radius - 1.5, i % 2 ? "#fffdf7" : "#16191b");
  });
  if (state.line.length) {
    ctx.beginPath();
    ctx.moveTo(...pixel(state.line[0]));
    ctx.lineTo(...pixel(state.line[state.line.length - 1]));
    ctx.strokeStyle = "#e98743";
    ctx.lineWidth = 4;
    ctx.stroke();
  }
  if (state.moves.length) dot(state.moves[state.moves.length - 1], 4, state.foul ? "#e26047" : "#4db99d");
  if (!state.ended) {
    const [x,y] = pixel(cursor), r = radius + 4;
    ctx.beginPath();
    for (const dx of [-1,1]) for (const dy of [-1,1]) {
      ctx.moveTo(x + dx * (r - 9), y + dy * r);
      ctx.lineTo(x + dx * r, y + dy * r);
      ctx.lineTo(x + dx * r, y + dy * (r - 9));
    }
    ctx.strokeStyle = "#134d3d";
    ctx.lineWidth = 4;
    ctx.stroke();
  }
}

function render() {
  const t = strings[lang];
  const creating = mode === "create";
  document.documentElement.lang = lang === "zh" ? "zh-Hans" : "en";
  for (const [id, key] of Object.entries({
    language:"language", "place-label":"place",
    "create-mode":"create", "join-mode":"join", back:"back", "code-label":"code", "peer-wait":"webWait",
    "first-label":"first", "first-host":"firstHost", "first-guest":"firstGuest",
    "rule-label":"rule", "rule-free":"free", "rule-renju":"renju", "size-label":"size",
    "undo-label":"allowUndo", undo:"undo",
    leave:"leave", rules:"rules", "freestyle-rule":"freestyle", "renju-rule":"renjuRule",
  })) byId(id).textContent = t[key];
  byId("subtitle").textContent = seat && state ?
    `${t.lan} · ${seat.color === 1 ? t.black : t.white} · ${state.renju ? t.renju : t.free}` : t.lan;
  byId("room-menu").hidden = Boolean(seat) || Boolean(mode);
  byId("room-form").hidden = Boolean(seat) || !mode;
  byId("back").disabled = busy;
  byId("room-submit").textContent = creating ? t.create : t.join;
  byId("room-submit").disabled = busy;
  byId("create-options").hidden = !creating;
  byId("code-fields").hidden = mode !== "join";
  byId("code").required = mode === "join";
  byId("playing").hidden = !seat;
  byId("room-info").hidden = !seat?.code || Boolean(state?.ready);
  byId("room-info").textContent = seat?.code ? `${t.code} ${seat.code}` : "";
  byId("peer-wait").hidden = !peer || !seat?.code || Boolean(state?.ready);
  byId("undo").hidden = !state?.undo;
  byId("undo").disabled = !canUndo();
  byId("board-panel").hidden = !state;
  byId("sound").textContent = sound ? t.on : t.off;
  byId("sound").setAttribute("aria-pressed", String(sound));
  canvas.setAttribute("aria-label", t.board);
  const status = byId("status");
  status.removeAttribute("data-color");
  if (disconnected) status.textContent = t.reconnect;
  else if (message) status.textContent = t[message] || t.connection_error;
  else if (!seat) status.textContent = creating ? t.webCreate : mode === "join" ? t.webJoin : t.roomGuide;
  else if (!state || !state.ready) status.textContent = t.wait;
  else {
    const color = state.ended ? state.winner : state.turn;
    if (color) status.dataset.color = color;
    status.textContent = state.ended ? t.result[state.winner] :
      (state.turn === seat.color ? t.yours : t.theirs)[state.turn];
  }
  if (state) {
    byId("coordinates").textContent = state.foul ? t[state.foul] :
      t.position.replace("{n}", state.moves.length + (state.ended ? 0 : 1)) +
      (state.ended ? "" : ` · ${String.fromCharCode(65 + cursor[0])}${cursor[1] + 1}`);
    drawBoard();
  }
}

render();
