"use strict";

// Keep these rules in step with game.py, including Renju's recursive three test.
const axes = [[1, 0], [0, 1], [1, 1], [1, -1]];
const stepFrom = ([x, y], [dx, dy], step) => [x + dx * step, y + dy * step];

class PeerGame {
  constructor(size, renju, foulLoss = false) {
    this.size = size;
    this.renju = renju;
    this.foulLoss = foulLoss;
    this.moves = [];
    this.board = new Map();
    this.result = {winner: 0, line: [], foul: ""};
  }

  get turn() { return 1 + this.moves.length % 2; }
  get ended() { return Boolean(this.result.winner) || this.moves.length === this.size ** 2; }
  stone(point) { return this.board.get(String(point)); }
  empty(point) { return point.every(n => n >= 0 && n < this.size) && !this.stone(point); }

  line(point, axis, color) {
    let start = 0, end = 0;
    while (this.stone(stepFrom(point, axis, start - 1)) === color) start--;
    while (this.stone(stepFrom(point, axis, end + 1)) === color) end++;
    return Array.from({length: end - start + 1}, (_, index) => stepFrom(point, axis, start + index));
  }

  doubleThreat(point, length) {
    const found = new Set();
    for (const axis of axes) {
      for (let start = 1 - length; start <= 0; start++) {
        const cells = Array.from({length}, (_, index) => stepFrom(point, axis, start + index));
        const stones = cells.filter(cell => this.stone(cell) === 1);
        if (stones.length !== length - 1) continue;
        const id = stones.map(String).sort().join(";");
        if (found.has(id)) continue;
        const gap = cells.find(cell => this.stone(cell) !== 1);
        if (!this.empty(gap)) continue;
        const three = length === 4;
        if (three && ![start - 1, start + length].every(i => this.empty(stepFrom(point, axis, i)))) continue;
        if ([start - (three ? 2 : 1), start + length + (three ? 1 : 0)]
          .some(i => this.stone(stepFrom(point, axis, i)) === 1)) continue;
        if (three) {
          const result = this.inspect(gap, 1);
          if (result.foul || result.winner) continue;
        }
        found.add(id);
        if (found.size === 2) return true;
      }
    }
    return false;
  }

  inspect(point, color) {
    this.board.set(String(point), color);
    try {
      const lines = axes.map(axis => this.line(point, axis, color));
      const longest = lines.reduce((a, b) => a.length >= b.length ? a : b);
      if (color === 2 || !this.renju) {
        if (longest.length >= 5) return {winner: color, line: longest, foul: ""};
      } else {
        const five = lines.find(line => line.length === 5);
        if (five) return {winner: color, line: five, foul: ""};
        for (const [foul, check] of [["overline", () => longest.length > 5],
          ["four", () => this.doubleThreat(point, 5)], ["three", () => this.doubleThreat(point, 4)]]) {
          if (check()) return {winner: 2, line: [], foul};
        }
      }
      return {winner: 0, line: [], foul: ""};
    } finally {
      this.board.delete(String(point));
    }
  }

  play(point) {
    if (this.ended || !point.every(Number.isInteger) || !this.empty(point)) return false;
    const result = this.inspect(point, this.turn);
    if (result.foul && !this.foulLoss) throw new Error("forbidden");
    this.result = result;
    this.board.set(String(point), this.turn);
    this.moves.push(point);
    return true;
  }

  undo() {
    for (const move of this.moves.splice(-2)) this.board.delete(String(move));
    this.result = {winner: 0, line: [], foul: ""};
  }
}

class PeerMatch {
  constructor(options) {
    this.game = new PeerGame(options.size, options.renju, options.foul_loss);
    this.hostColor = options.host_first ? 1 : 2;
    this.undo = options.undo;
    this.revision = 0;
    this.round = 1;
    this.rematch = null;
    this.ready = false;
    this.closed = false;
  }

  state() {
    const game = this.game;
    return {size: game.size, renju: game.renju, foul_loss: game.foulLoss, moves: game.moves.slice(), undo: this.undo,
      ready: this.ready, turn: game.turn, ended: game.ended, revision: this.revision,
      round: this.round, rematch: this.rematch ? [...this.rematch] : null, ...game.result};
  }

  call(action, data, color) {
    const game = this.game;
    if (this.closed) throw new Error("room_closed");
    if (action === "join") {
      if (color !== this.hostColor && data.rematch === true && !this.rematch) this.rematch = new Set();
      return {color, state: this.state()};
    }
    if (action === "leave") {
      this.closed = true;
      return {};
    }
    if (action === "state") return this.state();
    if (action === "rematch") {
      if (!this.rematch || !this.ready || !game.ended) throw new Error("not_turn");
      if (data.revision !== this.revision) throw new Error("stale_move");
      this.rematch.add(color);
      if (this.rematch.size === 2) {
        this.game = new PeerGame(game.size, game.renju, game.foulLoss);
        this.rematch.clear();
        this.round++;
        this.revision++;
      }
      return this.state();
    }
    if (!["move", "undo"].includes(action)) throw new Error("invalid_request");
    if (!this.ready || game.turn !== color || game.ended) throw new Error("not_turn");
    if (data.revision !== this.revision) throw new Error("stale_move");
    if (action === "undo") {
      if (!this.undo || game.moves.length < 2) throw new Error("cannot_undo");
      game.undo();
    } else {
      if (data.ply !== game.moves.length) throw new Error("stale_move");
      if (!game.play([data.x, data.y])) throw new Error("occupied");
    }
    this.revision++;
    return this.state();
  }
}

const SIGNAL_URL = "https://wmoaxlrncbfcsyqtfbku.supabase.co/functions/v1/five-pair";
const delay = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

async function signalRoom(action, data) {
  const response = await fetch(SIGNAL_URL, {method: "POST", credentials: "omit", redirect: "error",
    headers: {"Content-Type": "application/json"}, body: JSON.stringify({action, ...data}),
    signal: AbortSignal.timeout(10000)});
  const reply = await response.json();
  if (!response.ok) throw new Error(reply.error || "pair_unavailable");
  return reply;
}

function gatherIce(pc) {
  return new Promise(resolve => {
    const done = () => {
      clearTimeout(timer);
      pc.removeEventListener("icegatheringstatechange", check);
      resolve();
    };
    const check = () => { if (pc.iceGatheringState === "complete") done(); };
    const timer = setTimeout(done, 4000);
    pc.addEventListener("icegatheringstatechange", check);
    check();
  });
}

class BrowserPeer {
  constructor(match = null) {
    // Host ICE candidates only. The signaling endpoint does not relay moves.
    this.pc = new RTCPeerConnection({iceServers: []});
    this.match = match;
    this.pending = new Map();
    this.sequence = 0;
    this.closed = false;
    this.error = "";
    this.receipt = null;
    this.pc.addEventListener("connectionstatechange", () => {
      if (this.pc.connectionState === "failed" && !this.closed) this.close("pair_failed");
    });
  }

  attach(channel) {
    this.channel = channel;
    channel.onopen = () => { if (this.match) this.match.ready = true; };
    channel.onclose = () => { if (!this.closed) this.close("room_closed"); };
    channel.onmessage = event => {
      if (typeof event.data !== "string" || event.data.length > 8192) return;
      let data;
      try { data = JSON.parse(event.data); } catch { return; }
      if (!data || typeof data !== "object") return;
      if (data.closed && !this.match) {
        this.close("room_closed");
      } else if (this.match && Number.isSafeInteger(data.id)) {
        const reply = {id: data.id};
        try { reply.result = this.match.call(data.action, data.body || {}, 3 - this.match.hostColor); }
        catch (error) { reply.error = error.message; }
        channel.send(JSON.stringify(reply));
      } else if (!this.match && this.pending.has(data.id)) {
        const request = this.pending.get(data.id);
        this.pending.delete(data.id);
        clearTimeout(request.timer);
        if (data.error) request.reject(new Error(data.error));
        else request.resolve(data.result);
      }
    };
  }

  async host() {
    this.attach(this.pc.createDataChannel("five"));
    await this.pc.setLocalDescription(await this.pc.createOffer());
    await gatherIce(this.pc);
    this.receipt = await signalRoom("offer", {sdp: this.pc.localDescription.sdp});
    this.waitForAnswer().catch(() => this.close("pair_failed"));
    return {code: this.receipt.code, color: this.match.hostColor, state: this.match.state()};
  }

  async waitForAnswer() {
    const started = Date.now();
    while (!this.closed) {
      let sdp;
      try {
        ({sdp} = await signalRoom("status", this.receipt));
      } catch (error) {
        if (this.closed) return;
        if (error.message === "room_closed") {
          this.close("pair_expired");
          return;
        }
        if (Date.now() - started >= 300000) {
          this.close("pair_expired");
          return;
        }
      }
      if (this.closed) return;
      if (sdp) {
        await this.pc.setRemoteDescription({type: "answer", sdp});
        await this.waitForChannel();
        this.clearReceipt();
        return;
      }
      await delay(Date.now() - started < 30000 ? 1500 : 3500);
    }
  }

  async join(code) {
    this.pc.ondatachannel = event => this.attach(event.channel);
    const {sdp} = await signalRoom("lookup", {code});
    await this.pc.setRemoteDescription({type: "offer", sdp});
    await this.pc.setLocalDescription(await this.pc.createAnswer());
    await gatherIce(this.pc);
    await signalRoom("answer", {code, key: crypto.randomUUID(), sdp: this.pc.localDescription.sdp});
    await this.waitForChannel();
    return this.call("join", {rematch: true});
  }

  async waitForChannel() {
    const deadline = Date.now() + 15000;
    while (!this.closed && Date.now() < deadline) {
      if (this.channel?.readyState === "open") return;
      await delay(100);
    }
    throw new Error("pair_failed");
  }

  async call(action, body) {
    if (this.closed) throw new Error(this.error || "room_closed");
    if (this.match) return this.match.call(action, body, this.match.hostColor);
    if (this.channel?.readyState !== "open") throw new Error("pair_unavailable");
    return await new Promise((resolve, reject) => {
      const id = ++this.sequence;
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error("pair_unavailable"));
      }, 2500);
      this.pending.set(id, {resolve, reject, timer});
      this.channel.send(JSON.stringify({id, action, body}));
    });
  }

  clearReceipt() {
    if (this.receipt) signalRoom("close", this.receipt).catch(() => {});
    this.receipt = null;
  }

  close(error = "") {
    if (this.closed) return;
    this.closed = true;
    this.error = error;
    this.clearReceipt();
    if (this.match && this.channel?.readyState === "open") this.channel.send(JSON.stringify({closed: true}));
    this.pc.close();
    for (const request of this.pending.values()) {
      clearTimeout(request.timer);
      request.reject(new Error(error || "room_closed"));
    }
    this.pending.clear();
  }
}
