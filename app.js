const state = {
  data: null,
  category: "all",
  region: "all",
  query: "",
  sort: "relevance",
  visible: 7,
  watchlist: JSON.parse(localStorage.getItem("signal-brief-watchlist-v2") || "null") || ["BAE Systems", "ChapsVision", "Elbit Systems", "Rheinmetall", "Hanwha Aerospace", "Lockheed Martin"],
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const escapeHtml = (value = "") => String(value).replace(/[&<>'"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
const cleanUrl = (url = "") => /^https?:\/\//i.test(url) ? url : "#";
const relativeTime = date => {
  const value = new Date(date);
  if (Number.isNaN(value.getTime())) return "Recent";
  const hours = Math.max(0, Math.floor((Date.now() - value.getTime()) / 36e5));
  if (hours < 1) return "Just now";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return days === 1 ? "1 day ago" : `${days} days ago`;
};
const money = (value, currency = "USD") => {
  const amount = Number(value) || 0;
  try {
    return new Intl.NumberFormat("en", { style: "currency", currency, notation: "compact", maximumFractionDigits: 1 }).format(amount);
  } catch (_) {
    return `${currency} ${amount.toLocaleString()}`;
  }
};

function filteredArticles() {
  if (!state.data) return [];
  const query = state.query.toLowerCase().trim();
  return state.data.articles
    .filter(article => state.category === "all" || article.category === state.category)
    .filter(article => state.region === "all" || (article.region || "Global") === state.region)
    .filter(article => !query || [article.title, article.summary, article.source, article.region, ...(article.tags || [])].join(" ").toLowerCase().includes(query))
    .sort((a, b) => state.sort === "newest" ? new Date(b.published) - new Date(a.published) : b.score - a.score);
}

function renderArticles() {
  const articles = filteredArticles();
  const shown = articles.slice(0, state.visible);
  $("#results-count").textContent = articles.length;
  $("#article-grid").innerHTML = shown.length ? shown.map((article, index) => `
    <article class="article-card ${index === 0 && state.category === "all" && !state.query ? "featured" : ""}">
      <div class="article-card-top">
        <span class="article-category"><span class="market">${escapeHtml(article.region || "Global")}</span> / ${escapeHtml(article.category)}</span>
        <span class="score" style="--score:${Math.min(article.score, 100)}%">${article.score}% relevant</span>
      </div>
      <h3><a href="${cleanUrl(article.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(article.title)}</a></h3>
      <p>${escapeHtml(article.summary || "Open the source to read the full report and underlying details.")}</p>
      <div class="article-meta"><span class="source">${escapeHtml(article.source)}</span><span class="divider"></span><time datetime="${escapeHtml(article.published)}">${relativeTime(article.published)}</time></div>
      <div class="article-tags">${(article.tags || []).slice(0, 3).map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}</div>
    </article>
  `).join("") : `<div class="empty-state"><strong>No signals found.</strong><p>Try a broader category or clear your search.</p></div>`;
  $("#load-more").hidden = shown.length >= articles.length;
}

function renderBrief() {
  const distinct = [];
  const regions = new Set();
  for (const article of state.data.articles) {
    if (!regions.has(article.region)) {
      distinct.push(article);
      regions.add(article.region);
    }
    if (distinct.length === 3) break;
  }
  if (distinct.length < 3) {
    for (const article of state.data.articles) {
      if (!distinct.includes(article)) distinct.push(article);
      if (distinct.length === 3) break;
    }
  }
  $("#brief-list").innerHTML = distinct.map((article, index) => `
    <article class="brief-item">
      <span class="brief-number">0${index + 1}</span>
      <a href="${cleanUrl(article.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(article.title)}</a>
      <time datetime="${escapeHtml(article.published)}">${relativeTime(article.published)}</time>
    </article>
  `).join("");
}

function renderCompanies() {
  const panel = $("#company-list");
  panel.innerHTML = state.watchlist.length ? state.watchlist.map(name => {
    const count = state.data.articles.filter(article => (article.tags || []).some(tag => tag.toLowerCase() === name.toLowerCase()) || article.title.toLowerCase().includes(name.toLowerCase())).length;
    const initials = name.split(/\s+/).map(word => word[0]).slice(0, 2).join("");
    return `<div class="company-item"><span class="company-logo">${escapeHtml(initials)}</span><span><strong>${escapeHtml(name)}</strong><small>${count ? "Active coverage" : "Quiet period"}</small></span><span class="company-signal ${count ? "" : "zero"}">${count}</span><button class="company-remove" type="button" data-company="${escapeHtml(name)}" aria-label="Remove ${escapeHtml(name)}">×</button></div>`;
  }).join("") : `<div class="empty-state"><strong>Watchlist empty.</strong><p>Reload to restore the default companies.</p></div>`;
  $$(".company-remove", panel).forEach(button => button.addEventListener("click", () => {
    state.watchlist = state.watchlist.filter(name => name !== button.dataset.company);
    localStorage.setItem("signal-brief-watchlist-v2", JSON.stringify(state.watchlist));
    renderCompanies();
  }));
}

function renderContracts() {
  const contracts = state.data.contracts || [];
  $("#contract-rows").innerHTML = contracts.length ? contracts.slice(0, 8).map(contract => `
    <tr>
      <td>${escapeHtml(contract.recipient)}</td>
      <td>${escapeHtml(contract.description)}</td>
      <td>${money(contract.amount, contract.currency)}</td>
      <td>${escapeHtml(contract.jurisdiction || "United States")}</td>
      <td>${escapeHtml(contract.agency || "Public buyer")}</td>
      <td><a href="${cleanUrl(contract.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(contract.record_source || contract.award_id)} ↗</a></td>
    </tr>
  `).join("") : `<tr><td colspan="6">Contract records are temporarily unavailable. The news stream is still current.</td></tr>`;
}

function renderMeta() {
  const updated = new Date(state.data.meta.updated_at);
  $("#brief-date").textContent = updated.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
  $("#updated-time").textContent = Number.isNaN(updated.getTime()) ? "Recently" : `${updated.toLocaleDateString("en-US", { month: "short", day: "numeric" })} · ${updated.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}`;
  $("#stat-articles").textContent = state.data.articles.length;
  $("#stat-contracts").textContent = state.data.contracts.length;
  $("#stat-regions").textContent = new Set(state.data.articles.map(item => item.region || "Global")).size;
}

function bindInteractions() {
  $$(".filter-chip").forEach(button => button.addEventListener("click", () => {
    $$(".filter-chip").forEach(item => item.classList.toggle("active", item === button));
    state.category = button.dataset.category;
    state.visible = 7;
    renderArticles();
  }));
  $$(".region-chip").forEach(button => button.addEventListener("click", () => {
    $$(".region-chip").forEach(item => item.classList.toggle("active", item === button));
    state.region = button.dataset.region;
    state.visible = 7;
    renderArticles();
  }));
  $("#sort-select").addEventListener("change", event => { state.sort = event.target.value; renderArticles(); });
  $("#load-more").addEventListener("click", () => { state.visible += 6; renderArticles(); });

  const panel = $("#search-panel");
  const toggle = $("#search-toggle");
  const closeSearch = () => { panel.hidden = true; toggle.setAttribute("aria-expanded", "false"); };
  toggle.addEventListener("click", () => {
    panel.hidden = !panel.hidden;
    toggle.setAttribute("aria-expanded", String(!panel.hidden));
    if (!panel.hidden) $("#global-search").focus();
  });
  $("#global-search").addEventListener("input", event => { state.query = event.target.value; state.visible = 7; renderArticles(); });
  document.addEventListener("keydown", event => { if (event.key === "Escape") closeSearch(); });

  $("#edit-watchlist").addEventListener("click", event => {
    const parent = $(".watchlist-panel");
    parent.classList.toggle("editing");
    event.target.textContent = parent.classList.contains("editing") ? "Done" : "Edit";
  });
  $("#watchlist-add").addEventListener("submit", event => {
    event.preventDefault();
    const input = $("#company-input");
    const name = input.value.trim();
    if (name && !state.watchlist.some(item => item.toLowerCase() === name.toLowerCase())) {
      state.watchlist.push(name);
      localStorage.setItem("signal-brief-watchlist-v2", JSON.stringify(state.watchlist));
      input.value = "";
      renderCompanies();
    }
  });

  const dialog = $("#methodology-dialog");
  [$("#open-methodology"), $("#footer-methodology"), $("#header-methodology")].forEach(button => button.addEventListener("click", () => dialog.showModal()));
  $(".dialog-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", event => { if (event.target === dialog) dialog.close(); });
}

async function init() {
  bindInteractions();
  try {
    const response = await fetch("data/news.json", { cache: "no-store" });
    if (!response.ok) throw new Error("Data unavailable");
    state.data = await response.json();
    renderMeta();
    renderBrief();
    renderArticles();
    renderCompanies();
    renderContracts();
  } catch (error) {
    $("#article-grid").innerHTML = `<div class="empty-state"><strong>The signal feed is offline.</strong><p>Refresh shortly; the public-source collector may be updating.</p></div>`;
    $("#brief-list").innerHTML = `<p>Latest briefing unavailable.</p>`;
    $("#updated-time").textContent = "Synchronization pending";
  }
}

init();
