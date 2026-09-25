/* ---------- Helpers ---------- */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function moeda(v) {
  return (Number(v) || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}
function dataHoraBr(iso) {
  if (!iso) return "";
  const [d, h] = iso.split(" ");
  const [ano, mes, dia] = d.split("-");
  return `${dia}/${mes} ${h ? h.slice(0, 5) : ""}`;
}
function msg(texto, tipo = "ok") {
  const el = $("#msg");
  el.textContent = texto;
  el.className = tipo;
  el.style.opacity = 1;
  clearTimeout(msg._t);
  msg._t = setTimeout(() => (el.style.opacity = 0), 3000);
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let data = null;
  try {
    data = await res.json();
  } catch (e) {}
  if (!res.ok) {
    throw new Error((data && data.erro) || "Erro na requisição.");
  }
  return data;
}

/* ---------- Navegação entre abas ---------- */
$$("nav button").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$("nav button").forEach((b) => b.classList.remove("on"));
    btn.classList.add("on");
    const alvo = btn.dataset.t;
    $$("main > section").forEach((s) => (s.hidden = s.id !== alvo));
    carregarTudo();
  });
});

/* ---------- Painel ---------- */
async function carregarPainel() {
  const p = await api("/api/painel");
  $("#sDentro").textContent = p.dentro;
  $("#sHoje").textContent = moeda(p.recebido_hoje);

  const abertas = await api("/api/estadias/abertas");
  const div = $("#abertas");
  if (!abertas.length) {
    div.innerHTML = "<p>Estacionamento vazio.</p>";
  } else {
    div.innerHTML = abertas
      .map(
        (e) => `
      <div class="linha">
        <div>
          <b>${e.Placa}</b> ${e.Modelo || ""} — ${e.Nome}<br>
          <small>entrou ${dataHoraBr(e.Horario_Entrada)}</small>
        </div>
        <button class="sec" data-saida="${e.Placa}">Registrar saída</button>
      </div>`
      )
      .join("");
    div.querySelectorAll("[data-saida]").forEach((b) =>
      b.addEventListener("click", () => abrirDialogoSaida(b.dataset.saida))
    );
  }
}

/* ---------- Entrada ---------- */
$("#fEntrada").addEventListener("submit", async (e) => {
  e.preventDefault();
  const placa = $("#placaEntrada").value.trim().toUpperCase();
  try {
    await api("/api/entrada", { method: "POST", body: JSON.stringify({ placa }) });
    $("#placaEntrada").value = "";
    msg("Entrada registrada!");
    carregarTudo();
  } catch (err) {
    msg(err.message, "erro");
  }
});

/* ---------- Saída / pagamento ---------- */
let estadiaAtual = null;
async function abrirDialogoSaida(placa) {
  try {
    const info = await api("/api/saida/consultar?placa=" + encodeURIComponent(placa));
    estadiaAtual = info.estadia_id;
    $("#dInfo").innerHTML = `
      <p><b>Placa:</b> ${info.placa}</p>
      <p><b>Entrada:</b> ${dataHoraBr(info.entrada)}</p>
      <p><b>Saída:</b> ${dataHoraBr(info.saida)}</p>
      <p><b>Total a pagar:</b> ${moeda(info.total)}</p>`;
    $("#dSaida").showModal();
  } catch (err) {
    msg(err.message, "erro");
  }
}
$("#cancelSaida").addEventListener("click", () => $("#dSaida").close());
$("#okSaida").addEventListener("click", async () => {
  try {
    await api("/api/saida/confirmar", {
      method: "POST",
      body: JSON.stringify({ estadia_id: estadiaAtual, forma: $("#dForma").value }),
    });
    $("#dSaida").close();
    msg("Pagamento registrado. Saída liberada!");
    carregarTudo();
  } catch (err) {
    msg(err.message, "erro");
  }
});

/* ---------- Clientes ---------- */
$("#fCliente").addEventListener("submit", async (e) => {
  e.preventDefault();
  const nome = $("#cNome").value.trim();
  const fone = $("#cFone").value.trim();
  const cpf = $("#cCpf").value.replace(/\D/g, "");
  try {
    await api("/api/clientes", { method: "POST", body: JSON.stringify({ nome, fone, cpf }) });
    e.target.reset();
    msg("Cliente cadastrado!");
    carregarTudo();
  } catch (err) {
    msg(err.message, "erro");
  }
});

async function carregarClientes() {
  const lista = await api("/api/clientes");
  $("#tClientes").innerHTML = lista.length
    ? lista
        .map(
          (c) =>
            `<div class="linha"><div><b>${c.Nome}</b> — ${c.Fone || "sem fone"}<br><small>CPF: ${c.CPF}</small></div></div>`
        )
        .join("")
    : "<p>Nenhum cliente cadastrado.</p>";

  const sel = $("#vCliente");
  sel.innerHTML = lista.map((c) => `<option value="${c.ID}">${c.Nome}</option>`).join("");
}

/* ---------- Preços ---------- */
$("#fPreco").addEventListener("submit", async (e) => {
  e.preventDefault();
  const tipo = $("#pTipo").value.trim();
  const hora = $("#pHora").value;
  const diaria = $("#pDiaria").value;
  try {
    await api("/api/precos", { method: "POST", body: JSON.stringify({ tipo, hora, diaria }) });
    e.target.reset();
    msg("Tipo de preço cadastrado!");
    carregarTudo();
  } catch (err) {
    msg(err.message, "erro");
  }
});

async function carregarPrecos() {
  const lista = await api("/api/precos");
  $("#tPrecos").innerHTML = lista
    .map(
      (p) =>
        `<div class="linha"><div><b>${p.Tipo_Veiculo}</b><br><small>Hora: ${moeda(p.Valor_Hora)} | Diária: ${moeda(p.Valor_Diaria)}</small></div></div>`
    )
    .join("");

  const sel = $("#vPreco");
  sel.innerHTML = lista.map((p) => `<option value="${p.ID}">${p.Tipo_Veiculo}</option>`).join("");
}

/* ---------- Veículos ---------- */
$("#fVeiculo").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    placa: $("#vPlaca").value.trim().toUpperCase(),
    modelo: $("#vModelo").value.trim(),
    marca: $("#vMarca").value.trim(),
    cor: $("#vCor").value.trim(),
    cliente_id: $("#vCliente").value,
    preco_id: $("#vPreco").value,
  };
  try {
    await api("/api/veiculos", { method: "POST", body: JSON.stringify(body) });
    e.target.reset();
    msg("Veículo cadastrado!");
    carregarTudo();
  } catch (err) {
    msg(err.message, "erro");
  }
});

async function carregarVeiculos() {
  const lista = await api("/api/veiculos");
  $("#tVeiculos").innerHTML = lista.length
    ? lista
        .map(
          (v) =>
            `<div class="linha"><div><b>${v.Placa}</b> — ${v.Marca || ""} ${v.Modelo || ""} (${v.Cor || "-"})<br>
        <small>${v.Tipo_Veiculo} | Dono: ${v.Cliente_Nome}</small></div></div>`
        )
        .join("")
    : "<p>Nenhum veículo cadastrado.</p>";

  const datalist = $("#placas");
  datalist.innerHTML = lista.map((v) => `<option value="${v.Placa}">`).join("");
}

/* ---------- Pagamentos ---------- */
async function carregarPagamentos() {
  const lista = await api("/api/pagamentos");
  let total = 0;
  $("#tPag").innerHTML = lista.length
    ? lista
        .map((p) => {
          total += p.Valor_Pago;
          return `<div class="linha"><div>${dataHoraBr(p.Data_Pago)} — <b>${p.Placa}</b> | ${p.Forma_Pagamento}</div><div>${moeda(p.Valor_Pago)}</div></div>`;
        })
        .join("")
    : "<p>Nenhum pagamento registrado.</p>";
  $("#totalPag").textContent = moeda(total);
}

/* ---------- Carregar tudo ---------- */
async function carregarTudo() {
  try {
    await Promise.all([
      carregarPainel(),
      carregarClientes(),
      carregarPrecos(),
      carregarVeiculos(),
      carregarPagamentos(),
    ]);
  } catch (err) {
    msg(err.message, "erro");
  }
}

carregarTudo();