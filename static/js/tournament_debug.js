(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value == null ? "" : value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const fmt = value => Number(value).toFixed(3).replace(".", ",");
  let participants = [];
  let tournament = null;
  let busy = false;
  let initialized = false;

  const css = document.createElement("style");
  css.textContent = [
    "#bracketsView > .mgmt-stats,#bracketsView > .mgmt-brackets,#bracketsView > .mgmt-grid,#bracketsView > .mgmt-panel{display:none!important}",
    "#tournamentDebug{margin:16px 0 22px;color:#eaf4ff;font-family:Arial,Helvetica,sans-serif}",
    "#tournamentDebug .td-panel{background:#071323ed;border:1px solid #31516c;border-radius:14px;padding:16px;margin-bottom:14px;box-shadow:0 8px 26px #0004}",
    "#tournamentDebug .td-head{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:12px}",
    "#tournamentDebug h2,#tournamentDebug h3{margin:0;color:#70eaff;letter-spacing:.5px}",
    "#tournamentDebug .td-muted{color:#a8bbcf;font-size:13px}",
    "#tournamentDebug .td-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:14px}",
    "#tournamentDebug .td-stat{background:#0c2035;border:1px solid #294862;border-radius:10px;padding:12px}",
    "#tournamentDebug .td-stat small{display:block;color:#a8bbcf;margin-bottom:5px}",
    "#tournamentDebug .td-stat strong{font-size:24px;color:#fff}",
    "#tournamentDebug .td-current{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center;text-align:center}",
    "#tournamentDebug .td-robot{background:#0a1b2d;border:1px solid #31516c;border-radius:12px;padding:15px 8px;min-width:0}",
    "#tournamentDebug .td-robot strong{display:block;font-size:clamp(18px,2.2vw,28px);overflow-wrap:anywhere}",
    "#tournamentDebug .td-robot small{display:block;color:#a8bbcf;margin-top:6px}",
    "#tournamentDebug .td-vs{font-weight:900;color:#ffe66d;font-size:20px}",
    "#tournamentDebug .td-actions{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:14px}",
    "#tournamentDebug button{border:0;border-radius:8px;padding:11px 18px;font-weight:800;cursor:pointer}",
    "#tournamentDebug button:disabled{opacity:.45;cursor:not-allowed}",
    "#tdWin1{background:#16854f;color:#fff}#tdWin2{background:#2469bc;color:#fff}#tdStart{background:#ffe66d;color:#18202a}#tdReset{background:#25394d;color:#fff;border:1px solid #526c82}",
    "#tournamentDebug .td-tables{display:grid;grid-template-columns:1fr 1fr;gap:14px}",
    "#tournamentDebug .td-table h3{margin-bottom:10px}",
    "#tournamentDebug .td-entry{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:8px;background:#0a1b2d;margin:6px 0}",
    "#tournamentDebug .td-index{min-width:68px;font:700 13px ui-monospace,monospace;color:#ffe66d}",
    "#tournamentDebug .td-entry strong{flex:1;overflow-wrap:anywhere}",
    "#tournamentDebug .td-empty{color:#92a7bb;padding:12px 0}",
    "#tournamentDebug .td-history{max-height:220px;overflow:auto}",
    "#tournamentDebug .td-history-row{display:grid;grid-template-columns:44px 1fr auto;gap:10px;border-bottom:1px solid #20384d;padding:8px 0;font-size:13px}",
    "#tournamentDebug .td-note{color:#a8bbcf;font-size:13px;line-height:1.45;margin:10px 0 0}",
    "#tournamentDebug .td-badge{display:inline-block;border-radius:99px;padding:5px 9px;background:#17344b;color:#70eaff;font-size:12px;font-weight:800}",
    "@media(max-width:700px){#tournamentDebug .td-stats{grid-template-columns:repeat(2,minmax(0,1fr))}#tournamentDebug .td-tables{grid-template-columns:1fr}#tournamentDebug .td-current{gap:5px}#tournamentDebug .td-robot{padding:12px 4px}#tournamentDebug .td-actions button{width:100%}}"
  ].join("\n");
  document.head.appendChild(css);

  function ensurePanel() {
    const view = $("bracketsView");
    if (!view || $("tournamentDebug")) return;
    const panel = document.createElement("section");
    panel.id = "tournamentDebug";
    panel.innerHTML =
      '<div class="td-panel"><div class="td-head"><div><h2>PRUEBA DE TORNEO · DOBLE ELIMINACIÓN</h2><div class="td-muted">Modo provisional: selecciona quién gana para comprobar el avance de los robots.</div></div><span class="td-badge" id="tdStatus">SIN INICIAR</span></div>' +
      '<div class="td-stats"><div class="td-stat"><small>Ronda actual</small><strong id="tdRound">—</strong></div><div class="td-stat"><small>Combates acumulados</small><strong id="tdCount">0</strong></div><div class="td-stat"><small>Participantes válidos</small><strong id="tdValid">0</strong></div><div class="td-stat"><small>Byes de esta ronda</small><strong id="tdBye">—</strong></div></div>' +
      '<div class="td-panel"><div class="td-head"><h3>ENFRENTAMIENTO ACTUAL</h3><span class="td-muted" id="tdDirection">Esperando inicio</span></div><div id="tdMatch"><div class="td-empty">Pulsa “Iniciar torneo” para preparar la primera ronda.</div></div><div class="td-actions"><button id="tdWin1" disabled>Gana R1</button><button id="tdWin2" disabled>Gana R2</button></div></div>' +
      '<div class="td-tables"><div class="td-panel td-table"><div class="td-head"><h3>WINNERS</h3><span class="td-badge" id="tdWCount">0</span></div><div id="tdWinners"></div></div><div class="td-panel td-table"><div class="td-head"><h3>LOSSERS</h3><span class="td-badge" id="tdLCount">0</span></div><div id="tdLosers"></div></div></div>' +
      '<div class="td-panel"><div class="td-head"><h3>REGISTRO DE PRUEBA</h3><span class="td-muted">Índices provisionales con 3 decimales</span></div><div id="tdHistory" class="td-history"><div class="td-empty">Todavía no hay combates registrados.</div></div><div class="td-actions"><button id="tdStart">Iniciar torneo</button><button id="tdReset">Reiniciar prueba</button></div><p class="td-note">Al iniciar se activa la bandera de torneo iniciado. Agregar, editar o eliminar participantes deberá pedir confirmación para reiniciar la competencia. Estos botones registran resultados de prueba; no inician el ESP32.</p></div></div>';
    const description = view.querySelector(".mgmt-description");
    if (description) description.insertAdjacentElement("afterend", panel);
    else view.prepend(panel);
    $("tdStart").addEventListener("click", startTournament);
    $("tdReset").addEventListener("click", resetTournament);
    $("tdWin1").addEventListener("click", () => recordWinner(1));
    $("tdWin2").addEventListener("click", () => recordWinner(2));
  }

  function valid(p) {
    return Number(p.weight) > 0 && Number(p.weight) <= 500 && Array.isArray(p.checks) && p.checks.every(Boolean);
  }
  function player(id) { return tournament.players.find(p => p.id === id); }
  function activePlayers() { return tournament.players.filter(p => !tournament.eliminated.includes(p.id)); }
  function fmtIndex(n) { return Number(n).toFixed(3).replace(".", ","); }

  function uniqueIndex(value, excludingIds) {
    value = Math.round(value * 1000) / 1000;
    const excluded = new Set(excludingIds);
    while (activePlayers().some(p => !excluded.has(p.id) && Math.round(p.index * 1000) === Math.round(value * 1000))) {
      value = Math.round((value - 0.010) * 1000) / 1000;
    }
    return value;
  }

  function preparePairs(ids, direction, byeSide, initial) {
    const sorted = ids.map(player).filter(Boolean).sort((a,b) => a.index-b.index);
    if (initial) {
      const n = sorted.length;
      let capacity = 1;
      while (capacity < n) capacity *= 2;
      const byes = capacity - n;
      const matchCount = Math.floor((n - byes) / 2);
      const pool = sorted.slice(0, matchCount * 2);
      return {
        pairs: Array.from({length:matchCount}, (_,i) => [pool[i*2].id,pool[i*2+1].id]),
        byeIds: sorted.slice(matchCount*2).map(p=>p.id),
        byeOccurred: byes > 0
      };
    }
    let pool = sorted.slice();
    let byeIds = [];
    if (pool.length % 2) {
      const bye = byeSide === "high" ? pool.pop() : pool.shift();
      byeIds = bye ? [bye.id] : [];
    }
    if (direction === "desc") pool.reverse();
    const pairs = [];
    for (let i=0;i+1<pool.length;i+=2) pairs.push([pool[i].id,pool[i+1].id]);
    return {pairs,byeIds,byeOccurred:byeIds.length>0};
  }

  function beginRound(type, initial) {
    const ids = type === "W" ? tournament.winners : tournament.losers;
    const prepared = preparePairs(ids, tournament.direction, tournament.byeSide, !!initial);
    tournament.roundType = type;
    if (type === "W") tournament.wRound += 1;
    else tournament.lRound += 1;
    tournament.round = {
      type:type, number:type === "W" ? tournament.wRound : tournament.lRound,
      pairs:prepared.pairs, byeIds:prepared.byeIds, position:0, initial:!!initial
    };
    tournament.current = null;
    if (initial) tournament.byeSide = "low";
    else if (prepared.byeOccurred) tournament.byeSide = tournament.byeSide === "high" ? "low" : "high";
    tournament.current = nextPair();
    if (!tournament.current) afterRound();
  }

  function nextPair() {
    if (!tournament.round) return null;
    while (tournament.round.position < tournament.round.pairs.length) {
      const pair = tournament.round.pairs[tournament.round.position];
      const a = player(pair[0]), b = player(pair[1]);
      if (a && b && !tournament.eliminated.includes(a.id) && !tournament.eliminated.includes(b.id)) return {a:a.id,b:b.id,type:"match"};
      tournament.round.position += 1;
    }
    return null;
  }

  function startFinal() {
    if (tournament.winners.length === 1 && tournament.losers.length === 1) {
      tournament.phase = "final";
      tournament.finalNo = 1;
      tournament.current = {a:tournament.winners[0],b:tournament.losers[0],type:"final"};
    } else if (tournament.winners.length === 1 && tournament.losers.length > 1) {
      beginRound("L", false);
    } else if (tournament.winners.length > 1) {
      beginRound("W", false);
    } else if (tournament.losers.length > 1) {
      beginRound("L", false);
    } else {
      finishIfPossible();
    }
  }

  function finishIfPossible() {
    if (tournament.winners.length === 1 && tournament.losers.length === 1) {
      startFinal();
      return true;
    }
    if (tournament.winners.length === 1 && tournament.losers.length === 0) {
      tournament.champion = tournament.winners[0];
      tournament.phase = "finished";
      tournament.current = null;
      return true;
    }
    if (tournament.winners.length === 0 && tournament.losers.length === 1) {
      tournament.champion = tournament.losers[0];
      tournament.phase = "finished";
      tournament.current = null;
      return true;
    }
    return false;
  }

  function afterRound() {
    if (finishIfPossible()) return;
    if (tournament.winners.length <= 1) {
      if (tournament.losers.length > 1) beginRound("L", false);
      else startFinal();
      return;
    }
    if (tournament.round.type === "W") {
      if (tournament.round.number === 1) beginRound("W", false);
      else if (tournament.losers.length > 1) beginRound("L", false);
      else beginRound("W", false);
    } else {
      beginRound("W", false);
    }
  }

  function render() {
    ensurePanel();
    if (!tournament || !$("tournamentDebug")) return;
    const round = tournament.round;
    const current = tournament.current;
    $("tdStatus").textContent = tournament.phase === "finished" ? "TORNEO FINALIZADO" : tournament.started ? "TORNEO INICIADO" : "SIN INICIAR";
    $("tdRound").textContent = tournament.phase === "final" ? (tournament.finalNo === 1 ? "Final 1" : "Final decisiva") : round ? (round.type === "W" ? "Winners " : "Lossers ") + round.number : "—";
    $("tdCount").textContent = tournament.matches;
    $("tdValid").textContent = tournament.players.length;
    $("tdBye").textContent = round && round.byeIds.length ? round.byeIds.map(id => player(id)?.robot || "").join(", ") : "—";
    $("tdDirection").textContent = round ? "Recorrido: " + (tournament.direction === "asc" ? "índice menor → mayor" : "índice mayor → menor") : "Esperando inicio";
    const a = current && player(current.a), b = current && player(current.b);
    if (a && b) {
      $("tdMatch").innerHTML = '<div class="td-current"><div class="td-robot"><strong>R1 · ' + esc(a.robot) + '</strong><small>' + esc(a.pilot) + ' · índice ' + fmtIndex(a.index) + '</small></div><div class="td-vs">VS</div><div class="td-robot"><strong>R2 · ' + esc(b.robot) + '</strong><small>' + esc(b.pilot) + ' · índice ' + fmtIndex(b.index) + '</small></div></div>';
    } else if (tournament.champion) {
      const champ = player(tournament.champion);
      $("tdMatch").innerHTML = '<div class="td-empty">🏆 Campeón: <strong>' + esc(champ ? champ.robot : "—") + '</strong> · índice ' + (champ ? fmtIndex(champ.index) : "—") + '</div>';
    } else if (tournament.phase === "ready") {
      $("tdMatch").innerHTML = '<div class="td-empty">Pulsa “Iniciar torneo” para preparar la primera ronda.</div>';
    } else {
      $("tdMatch").innerHTML = '<div class="td-empty">No hay enfrentamiento preparado.</div>';
    }
    $("tdWin1").disabled = !tournament.started || !current || busy || tournament.phase === "finished";
    $("tdWin2").disabled = !tournament.started || !current || busy || tournament.phase === "finished";
    $("tdStart").textContent = tournament.started ? "Torneo iniciado" : "Iniciar torneo";
    $("tdStart").disabled = tournament.started && tournament.phase !== "finished";
    const renderList = ids => ids.map(player).filter(Boolean).sort((a,b)=>a.index-b.index).map(p =>
      '<div class="td-entry"><span class="td-index">' + fmtIndex(p.index) + '</span><strong>' + esc(p.robot) + '</strong><span class="td-muted">' + esc(p.pilot) + '</span></div>'
    ).join("") || '<div class="td-empty">Vacío</div>';
    $("tdWCount").textContent = tournament.winners.length;
    $("tdLCount").textContent = tournament.losers.length;
    $("tdWinners").innerHTML = renderList(tournament.winners);
    $("tdLosers").innerHTML = renderList(tournament.losers);
    $("tdHistory").innerHTML = tournament.history.slice().reverse().map((h,i) =>
      '<div class="td-history-row"><strong>' + (tournament.history.length-i) + '</strong><span>' + esc(h.round) + ' · ' + esc(h.a) + ' vs ' + esc(h.b) + '<br><span class="td-muted">Ganó ' + esc(h.winner) + ' · índices ' + fmtIndex(h.indexA) + ' / ' + fmtIndex(h.indexB) + '</span></span><strong>' + h.total + '</strong></div>'
    ).join("") || '<div class="td-empty">Todavía no hay combates registrados.</div>';
  }

  async function persist() {
    const response = await fetch("/api/tournament/debug-state", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({state:tournament})
    });
    const data = await response.json().catch(()=>({}));
    if (!response.ok) throw new Error(data.error || "No se pudo guardar el estado del torneo.");
    tournament = data.state || tournament;
  }

  async function refreshParticipants() {
    const response = await fetch("/api/participants");
    if (!response.ok) throw new Error("No se pudieron consultar los participantes.");
    participants = (await response.json()).filter(valid).sort((a,b)=>a.id-b.id);
  }

  function freshState() {
    const players = participants.map((p,i)=>({id:p.id,pilot:p.pilot,robot:p.robot,index:i+1}));
    return {
      started:false,phase:"ready",players:players,winners:players.map(p=>p.id),losers:[],eliminated:[],
      round:null,current:null,wRound:0,lRound:0,roundType:"W",direction:"asc",byeSide:"high",
      matches:0,history:[],champion:null,finalNo:0
    };
  }

  async function loadState() {
    const response = await fetch("/api/tournament/debug-state");
    if (!response.ok) throw new Error("No se pudo consultar el estado del torneo.");
    const data = await response.json();
    tournament = data.state;
    if (!tournament || !Array.isArray(tournament.players)) tournament = freshState();
    render();
  }

  async function startTournament() {
    if (busy || (tournament && tournament.started && tournament.phase !== "finished")) return;
    busy = true;
    try {
      await refreshParticipants();
      if (participants.length < 2) {
        alert("Se necesitan al menos dos participantes válidos para iniciar el torneo.");
        return;
      }
      tournament = freshState();
      tournament.started = true;
      tournament.phase = "running";
      beginRound("W", true);
      await persist();
      render();
    } catch (error) { alert(error.message); }
    finally { busy = false; render(); }
  }

  async function resetTournament() {
    if (busy) return;
    if (tournament && tournament.started && !confirm("¿Reiniciar la prueba? Se borrarán los resultados provisionales y se desactivará la bandera de torneo iniciado.")) return;
    busy = true;
    try {
      const response = await fetch("/api/tournament/debug-state", {
        method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({reset:true})
      });
      const data = await response.json().catch(()=>({}));
      if (!response.ok) throw new Error(data.error || "No se pudo reiniciar la prueba.");
      await refreshParticipants();
      tournament = freshState();
      render();
    } catch (error) { alert(error.message); }
    finally { busy = false; render(); }
  }

  async function recordWinner(side) {
    if (busy || !tournament || !tournament.current) return;
    busy = true;
    try {
      const match = tournament.current;
      const a = player(match.a), b = player(match.b);
      if (!a || !b) throw new Error("No se encontraron los participantes del combate.");
      const winner = side === 1 ? a : b;
      const loser = side === 1 ? b : a;
      const oldA = a.index, oldB = b.index;
      const roundLabel = tournament.phase === "final" ? (tournament.finalNo === 1 ? "Final 1" : "Final decisiva") : (tournament.round.type === "W" ? "Winners " : "Lossers ") + tournament.round.number;
      tournament.matches += 1;
      tournament.history.push({round:roundLabel,a:a.robot,b:b.robot,winner:winner.robot,indexA:oldA,indexB:oldB,total:tournament.matches});
      if (match.type === "final") {
        if (tournament.finalNo === 1 && winner.id === tournament.winners[0]) {
          tournament.champion = winner.id;
          tournament.winners = [winner.id];
          tournament.losers = [];
          tournament.eliminated.push(loser.id);
          tournament.phase = "finished";
          tournament.current = null;
        } else if (tournament.finalNo === 1) {
          tournament.winners = [];
          tournament.losers = [winner.id, loser.id];
          tournament.phase = "final";
          tournament.finalNo = 2;
          tournament.current = {a:winner.id,b:loser.id,type:"final"};
        } else {
          tournament.champion = winner.id;
          tournament.winners = [];
          tournament.losers = [winner.id];
          tournament.eliminated.push(loser.id);
          tournament.phase = "finished";
          tournament.current = null;
        }
      } else {
        const table = tournament.round.type;
        const newIndex = uniqueIndex((oldA + oldB) / 2, [a.id,b.id]);
        winner.index = newIndex;
        const activeOthers = activePlayers().filter(p=>p.id!==a.id && p.id!==b.id);
        let loserIndex = loser.id === a.id ? oldA : oldB;
        while (activeOthers.some(p=>Math.round(p.index*1000)===Math.round(loserIndex*1000)) || Math.round(loserIndex*1000)===Math.round(winner.index*1000)) {
          loserIndex = Math.round((loserIndex - 0.010)*1000)/1000;
        }
        loser.index = loserIndex;
        if (table === "W") {
          tournament.winners = tournament.winners.filter(id=>id!==a.id && id!==b.id);
          tournament.winners.push(winner.id);
          tournament.losers.push(loser.id);
        } else {
          tournament.losers = tournament.losers.filter(id=>id!==a.id && id!==b.id);
          tournament.losers.push(winner.id);
          tournament.eliminated.push(loser.id);
        }
        tournament.round.position += 1;
        tournament.current = nextPair();
        if (!tournament.current) {
          tournament.direction = tournament.direction === "asc" ? "desc" : "asc";
          afterRound();
        }
      }
      await persist();
      render();
    } catch (error) { alert(error.message); }
    finally { busy = false; render(); }
  }

  async function init() {
    if (initialized) return;
    initialized = true;
    ensurePanel();
    try { await refreshParticipants(); await loadState(); }
    catch (error) { if ($("tdMatch")) $("tdMatch").textContent = error.message; }
  }
  document.addEventListener("DOMContentLoaded", init);
  if (document.readyState !== "loading") init();
  window.setInterval(async () => {
    if (!tournament || !tournament.started) return;
    try {
      const response = await fetch("/api/tournament/debug-state");
      if (!response.ok) return;
      const data = await response.json();
      if (!data.started) {
        await refreshParticipants();
        tournament = freshState();
        render();
      }
    } catch (_) {}
  }, 1500);
})();