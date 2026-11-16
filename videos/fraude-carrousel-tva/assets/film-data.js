/*
 * Script du film : une seule source pour les sous-titres (compositions/captions.html,
 * généré par tools/build-captions.mjs) et pour le jeu des avatars (bouche, qui parle).
 *
 * Chaque réplique : sp = narrateur (A = Bitmoji 1, B = Bitmoji 2), t0/t1 = fenêtre de parole,
 * g = groupes de sous-titres. *mot* = mot important (orange), *!mot* = mot important (rouge).
 *
 * Tant qu'il n'y a pas de voix enregistrée, les temps des mots sont estimés dans la fenêtre
 * de la réplique. Quand la voix existe : ajouter `w: [[debut, fin], ...]` (un couple par mot,
 * dans l'ordre) à la réplique, puis relancer `node tools/build-captions.mjs`.
 */
(function () {
  var LINES = [
    { sp: "A", t0: 0.25, t1: 4.75, g: ["Un *produit.*", "Plusieurs *sociétés.*", "Et une *TVA* qui *!disparaît.*", "Bienvenue dans la", "*!fraude carrousel.*"] },
    { sp: "B", t0: 5.1, t1: 12.8, g: ["Tu achètes un *produit*", "*120 euros* :", "*100 euros* de produit,", "*20 euros* de *TVA.*", "Cette taxe est destinée", "à *l'État.*"] },
    { sp: "A", t0: 13.1, t1: 22.8, g: ["Dans ce *montage,*", "plusieurs sociétés se *revendent*", "des *marchandises,*", "souvent entre *pays européens.*", "L'une *encaisse* la *TVA…*", "puis *!disparaît*", "sans la *!reverser.*", "L'argent reste", "chez les *!fraudeurs.*"] },
    { sp: "B", t0: 23.1, t1: 26.6, g: ["Mais *attends…*", "l'arnaque ne *!s'arrête*", "*!même pas là !*"] },
    { sp: "A", t0: 27.1, t1: 37.8, g: ["Ailleurs dans le", "*!réseau frauduleux,*", "une autre société *réclame*", "la *déduction*", "ou le *remboursement*", "de cette *TVA.*", "L'État se retrouve", "à déduire ou *rembourser*", "une taxe qu'il n'a", "*!jamais encaissée.*"] },
    { sp: "B", t0: 38.1, t1: 45.8, g: ["Et quand les *marchandises*", "reviennent au", "*point de départ,*", "le circuit peut *recommencer.*", "Voilà pourquoi", "on appelle ça", "un *carrousel !*"] },
    { sp: "A", t0: 46.1, t1: 53.8, g: ["*Résultat :*", "des *!recettes publiques* perdues,", "et des entreprises *honnêtes*", "concurrencées par des", "*!prix* artificiellement *!bas.*", "Les *!dégâts* touchent aussi", "*l'économie réelle.*"] },
    { sp: "B", t0: 54.1, t1: 59.2, g: ["Le *carrousel* tourne,", "les fraudeurs *!encaissent…*", "et à la fin,", "c'est *l'argent public*", "qui *!disparaît.*"] },
  ];

  var words = [];
  var groups = [];
  LINES.forEach(function (line, li) {
    var lineWords = [];
    line.g.forEach(function (gtxt, gi) {
      var emph = 0;
      var gw = [];
      gtxt.split(" ").forEach(function (tok) {
        var e = emph;
        if (tok.charAt(0) === "*") {
          tok = tok.slice(1);
          e = 1;
          if (tok.charAt(0) === "!") {
            tok = tok.slice(1);
            e = 2;
          }
          emph = e;
        }
        if (tok.charAt(tok.length - 1) === "*") {
          tok = tok.slice(0, -1);
          emph = 0;
        }
        if (!tok) return;
        var w = { text: tok, emph: e, line: li, sp: line.sp };
        gw.push(w);
        lineWords.push(w);
      });
      groups.push({ line: li, sp: line.sp, words: gw });
    });
    // Estimated timing: each word weighs its letters, punctuation adds a breath.
    var total = 0;
    var weights = lineWords.map(function (w) {
      var pause = /[.!?…:]$/.test(w.text) ? 5 : /,$/.test(w.text) ? 2.5 : 0;
      var k = w.text.replace(/[^0-9A-Za-zÀ-ÿ]/g, "").length + 2;
      if (/^[0-9]+$/.test(w.text)) k += 5; // "120" is said "cent vingt"
      total += k + pause;
      return [k, pause];
    });
    var t = line.t0;
    var span = line.t1 - line.t0;
    lineWords.forEach(function (w, i) {
      if (line.w && line.w[i]) {
        w.start = line.w[i][0];
        w.end = line.w[i][1];
      } else {
        w.start = t;
        w.end = t + (weights[i][0] / total) * span;
        t = w.end + (weights[i][1] / total) * span;
      }
      words.push(w);
    });
  });
  groups.forEach(function (g, i) {
    g.start = g.words[0].start;
    g.end = g.words[g.words.length - 1].end;
  });
  // A group stays up until the next one of the same line starts (no flicker between groups).
  groups.forEach(function (g, i) {
    var n = groups[i + 1];
    g.show = Math.max(0.12, g.start - 0.06);
    g.hide = n && n.line === g.line ? n.start - 0.06 : g.end + 0.22;
  });

  var FILM = { duration: 60, lines: LINES, words: words, groups: groups };
  if (typeof window !== "undefined") window.__FILM = FILM;
  if (typeof globalThis !== "undefined") globalThis.__FILM = FILM;
})();
