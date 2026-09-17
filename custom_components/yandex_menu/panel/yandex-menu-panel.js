/* Панель «Яндекс меню» для Home Assistant.
   Ванильный веб-компонент: HA не отдаёт custom-панелям свой lit, а тянуть
   библиотеку с CDN в домашнюю систему не хочется. */

const LIMIT_FALLBACK = 5;

/* Состояния сущностей HA, при которых значок устройства светится. */
const ON_STATES = new Set([
  "on", "open", "opening", "closing", "playing", "cleaning", "returning",
  "heat", "cool", "heat_cool", "auto", "dry", "fan_only",
]);

const ICONS = {
  light:
    "M12,2A7,7 0 0,0 5,9C5,11.38 6.19,13.47 8,14.74V17A1,1 0 0,0 9,18H15A1,1 0 0,0 16,17V14.74C17.81,13.47 19,11.38 19,9A7,7 0 0,0 12,2M9,21A1,1 0 0,0 10,22H14A1,1 0 0,0 15,21V20H9V21Z",
  switch:
    "M16,7V3H14V7H10V3H8V7C7,7 6,8 6,9V14.5L9.5,18V21H14.5V18L18,14.5V9C18,8 17,7 16,7Z",
  socket:
    "M16,7V3H14V7H10V3H8V7C7,7 6,8 6,9V14.5L9.5,18V21H14.5V18L18,14.5V9C18,8 17,7 16,7Z",
  curtain: "M3,3H21V5H3V3M5,7H19V9H5V7M5,11H19V13H5V11M3,15H21V17H3V15M8,19H16V21H8V19Z",
  speaker:
    "M7,2H17A2,2 0 0,1 19,4V20A2,2 0 0,1 17,22H7A2,2 0 0,1 5,20V4A2,2 0 0,1 7,2M12,10A3,3 0 0,0 9,13A3,3 0 0,0 12,16A3,3 0 0,0 15,13A3,3 0 0,0 12,10M12,5A1.5,1.5 0 0,0 10.5,6.5A1.5,1.5 0 0,0 12,8A1.5,1.5 0 0,0 13.5,6.5A1.5,1.5 0 0,0 12,5Z",
  vacuum:
    "M12,2A10,10 0 0,1 22,12A10,10 0 0,1 12,22A10,10 0 0,1 2,12A10,10 0 0,1 12,2M12,8A4,4 0 0,0 8,12A4,4 0 0,0 12,16A4,4 0 0,0 16,12A4,4 0 0,0 12,8Z",
  script:
    "M14,10H19.5L14,4.5V10M5,3H15L21,9V19A2,2 0 0,1 19,21H5A2,2 0 0,1 3,19V5A2,2 0 0,1 5,3M9,13V17H11V13H9M13,13V17H15V13H13Z",
  sensor:
    "M12,2A3,3 0 0,1 15,5V11A3,3 0 0,1 12,14A3,3 0 0,1 9,11V5A3,3 0 0,1 12,2M19,11C19,14.53 16.39,17.44 13,17.93V21H11V17.93C7.61,17.44 5,14.53 5,11H7A5,5 0 0,0 12,16A5,5 0 0,0 17,11H19Z",
  meter:
    "M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4M12,6V12L16,14L15,15.75L11,13.5V6H12Z",
  other:
    "M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4Z",
};

const STYLES = `
  :host {
    display: block;
    height: 100vh;
    background: var(--primary-background-color, #f5f6f8);
    color: var(--primary-text-color, #212121);
    font-family: var(--paper-font-body1_-_font-family, Roboto, system-ui, sans-serif);
    font-size: 14px;
    line-height: 1.45;
    --gap: 16px;
    --line: var(--divider-color, rgba(127,127,127,.28));
    --surface: var(--card-background-color, #fff);
    --surface-2: var(--secondary-background-color, rgba(127,127,127,.08));
    --muted: var(--secondary-text-color, #727272);
    --accent: var(--primary-color, #03a9f4);
    --danger: var(--error-color, #db4437);
    --warn: var(--warning-color, #ffa600);
    --ok: var(--success-color, #43a047);
    --lit: var(--state-light-active-color, var(--state-active-color, #ff9800));
    --mono: ui-monospace, SFMono-Regular, "Roboto Mono", Menlo, monospace;
  }
  * { box-sizing: border-box; }
  button { font: inherit; color: inherit; cursor: pointer; }
  input, select { font: inherit; color: inherit; }
  :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 6px; }

  .layout { display: flex; flex-direction: column; height: 100%; }
  header.bar {
    display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
    padding: 10px 16px;
    background: var(--app-header-background-color, var(--surface));
    color: var(--app-header-text-color, var(--primary-text-color));
    border-bottom: 1px solid var(--line);
  }
  header.bar h1 { margin: 0; font-size: 20px; font-weight: 400; }
  .grow { flex: 1 1 40px; }
  .search {
    display: flex; align-items: center; gap: 8px;
    background: var(--surface-2); border-radius: 999px; padding: 6px 14px; min-width: 190px;
  }
  .search input { border: 0; background: transparent; outline: none; width: 100%; }
  .icon-only { border: 0; background: transparent; padding: 8px; border-radius: 50%; display: grid; place-items: center; }
  .icon-only:hover { background: var(--surface-2); }

  .btn {
    display: inline-flex; align-items: center; gap: 8px;
    border: 1px solid var(--line); background: var(--surface);
    border-radius: 999px; padding: 7px 15px; font-size: 13.5px; white-space: nowrap;
  }
  .btn:hover:not([disabled]) { border-color: var(--accent); color: var(--accent); }
  .btn-primary { background: var(--accent); border-color: var(--accent); color: var(--text-primary-color, #fff); }
  .btn-primary:hover:not([disabled]) { filter: brightness(1.08); color: var(--text-primary-color, #fff); }
  .btn-quiet { background: var(--surface-2); border-color: transparent; }
  .btn-danger { border-color: transparent; background: rgba(219,68,55,.12); color: var(--danger); }
  .btn[disabled] { opacity: .45; cursor: default; }

  .body { flex: 1; display: flex; min-height: 0; }
  .list { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 22px; }
  .room-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 8px; }
  .room-head h2 {
    margin: 0; font-size: 13px; font-weight: 500; letter-spacing: .4px;
    text-transform: uppercase; color: var(--muted);
  }
  .room-head .count { font-size: 12px; color: var(--muted); }
  .card { background: var(--surface); border-radius: 12px; box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,.12)); overflow: hidden; }
  .row {
    display: grid;
    grid-template-columns: 36px minmax(150px, 1.4fr) minmax(140px, 1.6fr) 120px;
    gap: 14px; align-items: center; width: 100%; text-align: left;
    padding: 10px 14px; background: transparent; border: 0;
    border-top: 1px solid var(--line);
  }
  .row.offer { grid-template-columns: 36px minmax(150px, 1.4fr) minmax(140px, 1.6fr) auto; }
  .row:first-child { border-top: 0; }
  .row:hover { background: var(--surface-2); }
  .row.selected { background: rgba(3,169,244,.12); }
  .avatar {
    width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center; flex: none;
    background: var(--surface-2); color: var(--muted); transition: background .25s, color .25s, box-shadow .25s;
  }
  .row.lit .avatar, .avatar.lit {
    background: color-mix(in srgb, var(--lit) 22%, transparent); color: var(--lit);
    box-shadow: 0 0 12px color-mix(in srgb, var(--lit) 55%, transparent);
  }
  .title { font-weight: 500; }
  .entity { font-family: var(--mono); font-size: 11.5px; color: var(--muted); word-break: break-all; }
  .chips { display: flex; flex-wrap: wrap; gap: 5px; }
  .chip { font-size: 11.5px; padding: 2px 9px; border-radius: 999px; background: var(--surface-2); color: var(--muted); }
  .chip.primary { background: rgba(3,169,244,.16); color: var(--accent); font-weight: 500; }
  .role { font-size: 11.5px; color: var(--muted); }
  .role b { color: var(--primary-text-color); font-weight: 500; }

  .panel {
    width: 420px; flex: none; border-left: 1px solid var(--line);
    background: var(--surface); display: flex; flex-direction: column;
  }
  .panel[hidden] { display: none; }
  .panel-head { padding: 14px 16px; border-bottom: 1px solid var(--line); display: flex; gap: 12px; align-items: flex-start; }
  .panel-head h3 { margin: 0 0 2px; font-size: 17px; font-weight: 500; }
  .panel-body { flex: 1; overflow-y: auto; padding: 0 16px 16px; }
  .panel-foot { border-top: 1px solid var(--line); padding: 12px 16px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }

  .section { padding: 16px 0; border-top: 1px solid var(--line); }
  .section:first-child { border-top: 0; }
  .section-head { display: flex; align-items: baseline; gap: 8px; }
  .section-head h4 { margin: 0; font-size: 12.5px; font-weight: 500; letter-spacing: .4px; text-transform: uppercase; color: var(--muted); }
  .section-head .counter { margin-left: auto; font-size: 12px; color: var(--muted); font-variant-numeric: tabular-nums; }
  .hint { margin: 4px 0 12px; font-size: 12.5px; color: var(--muted); }

  .names { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
  .name {
    display: flex; align-items: center; gap: 8px;
    padding: 8px 8px 8px 12px; border-radius: 10px;
    background: var(--surface-2);
  }
  .name.primary { background: rgba(3,169,244,.14); box-shadow: inset 0 0 0 1px var(--accent); }
  .name .value { flex: 1; font-weight: 500; word-break: break-word; }
  .name .tag { font-size: 10.5px; text-transform: uppercase; letter-spacing: .4px; color: var(--accent); }
  .mini { border: 0; background: transparent; color: var(--muted); padding: 4px; border-radius: 6px; display: grid; place-items: center; }
  .mini:hover:not([disabled]) { color: var(--accent); background: rgba(3,169,244,.14); }
  .mini.danger:hover:not([disabled]) { color: var(--danger); background: rgba(219,68,55,.12); }
  .mini[disabled] { opacity: .4; cursor: default; }

  .add { display: flex; gap: 8px; }
  .add input {
    flex: 1; padding: 9px 12px; border-radius: 10px;
    border: 1px solid var(--line); background: var(--surface);
  }
  .msg { margin-top: 10px; padding: 9px 12px; border-radius: 10px; font-size: 12.5px; }
  .msg.error { background: rgba(219,68,55,.12); color: var(--danger); }
  .msg.warn { background: rgba(255,167,38,.16); color: var(--warn); }
  .msg.info { background: var(--surface-2); color: var(--muted); }

  .seg { display: flex; border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
  .seg button { flex: 1; border: 0; background: var(--surface); padding: 9px 8px; font-size: 13px; }
  .seg button + button { border-left: 1px solid var(--line); }
  .seg button.on { background: var(--accent); color: var(--text-primary-color, #fff); font-weight: 500; }

  select.field, input.field {
    width: 100%; padding: 9px 12px; border-radius: 10px;
    border: 1px solid var(--line); background: var(--surface);
  }

  .empty { padding: 40px 16px; text-align: center; color: var(--muted); }
  .loader { padding: 40px 16px; text-align: center; color: var(--muted); }
  .fatal { margin: 16px; padding: 16px; border-radius: 12px; background: rgba(219,68,55,.1); color: var(--danger); }

  .toast {
    position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%);
    background: var(--primary-text-color); color: var(--primary-background-color);
    padding: 10px 18px; border-radius: 999px; font-size: 13px; z-index: 9;
    max-width: 90vw;
  }
  .toast[hidden] { display: none; }
  .busy { opacity: .55; pointer-events: none; }

  @media (max-width: 900px) {
    .panel { position: fixed; inset: 0; width: auto; z-index: 8; border-left: 0; }
    .row { grid-template-columns: 36px 1fr; row-gap: 6px; }
    .row .chips, .row .role { grid-column: 2; }
    .row.offer { grid-template-columns: 36px 1fr auto; }
    .row.offer .role { grid-column: 2; grid-row: 2; }
    .row.offer .btn { grid-column: 3; grid-row: 1 / 3; }
  }
`;

class YandexMenuPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = null;
    this._error = null;
    this._selected = null;
    this._query = "";
    this._message = null;
    this._busy = false;
    this._loaded = false;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._loaded) {
      this._loaded = true;
      this._render();
      this._load(true);
      return;
    }
    this._refreshLit();
  }

  set narrow(value) {
    this._narrow = value;
  }

  connectedCallback() {
    if (!this.shadowRoot.firstChild) this._render();
  }

  /* ------------------------------------------------------------- транспорт */

  async _call(type, payload = {}) {
    return this._hass.connection.sendMessagePromise({ type, ...payload });
  }

  async _load(force = false) {
    try {
      this._data = await this._call("yandex_menu/list", { force });
      this._error = null;
    } catch (err) {
      this._error = err && err.message ? err.message : String(err);
    }
    this._render();
  }

  async _act(type, payload, successText) {
    this._busy = true;
    this._render();
    try {
      this._data = await this._call(type, payload);
      this._message = null;
      const notice = this._data && this._data.notice;
      if (notice) this._toast(notice);
      else if (successText) this._toast(successText);
    } catch (err) {
      const text = err && err.message ? err.message : String(err);
      this._message = { level: "error", text };
    } finally {
      this._busy = false;
      this._render();
    }
  }

  _toast(text) {
    const toast = this.shadowRoot.getElementById("toast");
    if (!toast) return;
    toast.textContent = text;
    toast.hidden = false;
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      toast.hidden = true;
    }, 3200);
  }

  /* ---------------------------------------------------------------- данные */

  get _devices() {
    return (this._data && this._data.devices) || [];
  }

  _device(id) {
    return this._devices.find((item) => item.id === id) || null;
  }

  _iconFor(device) {
    const type = device.current_type || device.type || "";
    if (type.includes("light")) return ICONS.light;
    if (type.includes("socket")) return ICONS.socket;
    if (type.includes("switch")) return ICONS.switch;
    if (type.includes("curtain") || type.includes("openable")) return ICONS.curtain;
    if (type.includes("speaker")) return ICONS.speaker;
    if (type.includes("vacuum")) return ICONS.vacuum;
    if (type.includes("smart_meter")) return ICONS.meter;
    if (type.includes("sensor")) return ICONS.sensor;
    if (device.external_id && device.external_id.startsWith("script.")) return ICONS.script;
    return ICONS.other;
  }

  /** Включено ли устройство: у сущностей HA — по живому состоянию, у остальных — по Яндексу. */
  _isOn(device) {
    if (!device.switchable) return false; // датчики не «включаются»: открытая дверь не должна светиться
    const states = (this._hass && this._hass.states) || {};
    const entity = device.external_id ? states[device.external_id] : null;
    if (entity) return ON_STATES.has(entity.state);
    return device.on === true;
  }

  /** Состояния в HA меняются постоянно — обновляем только подсветку, без перерисовки. */
  _refreshLit() {
    const root = this.shadowRoot;
    if (!root || !this._data) return;
    for (const row of root.querySelectorAll(".row[data-id]")) {
      const device = this._device(row.getAttribute("data-id"));
      if (device) row.classList.toggle("lit", this._isOn(device));
    }
    const head = root.querySelector(".panel-head .avatar");
    const selected = this._device(this._selected);
    if (head && selected) head.classList.toggle("lit", this._isOn(selected));
  }

  _roleWord(device) {
    if (!device.role) return "";
    return device.role.endsWith("main") ? "основной свет" : "дополнительный";
  }

  /** Проверка имени до отправки: дубли, предел, пересечения с чужими именами. */
  _checkName(value, device) {
    const limit = (this._data && this._data.max_names) || LIMIT_FALLBACK;
    const name = value.trim();
    if (!name) return { level: "error", text: "Введите название." };
    if (device.names.length >= limit)
      return {
        level: "error",
        text: `Больше ${limit} имён Яндекс не принимает — сначала удалите лишнее.`,
      };
    const lower = name.toLowerCase();
    if (device.names.some((item) => item.toLowerCase() === lower))
      return { level: "error", text: "Такое имя у устройства уже есть." };

    for (const other of this._devices) {
      if (other.id === device.id) continue;
      for (const otherName of other.names) {
        const on = String(otherName).toLowerCase();
        if (on === lower)
          return {
            level: "warn",
            text: `«${otherName}» уже занято устройством в комнате ${other.room || "без комнаты"}.`,
          };
        if (on.includes(lower) || lower.includes(on)) {
          const shorter = on.length < lower.length ? otherName : name;
          return {
            level: "warn",
            text: `«${otherName}» и «${name}» пересекаются — Алиса выберет короткое, то есть «${shorter}».`,
          };
        }
      }
    }
    return null;
  }

  _snapshotDiffers(device) {
    const snapshots = (this._data && this._data.snapshots) || {};
    const snapshot = device.external_id ? snapshots[device.external_id] : null;
    if (!snapshot || !snapshot.names || !snapshot.names.length) return false;
    const same =
      snapshot.names.length === device.names.length &&
      snapshot.names.every((name, index) => name === device.names[index]) &&
      (snapshot.role || null) === (device.role || null);
    return !same;
  }

  /* ----------------------------------------------------------------- вёрстка */

  _render() {
    const root = this.shadowRoot;
    if (!root.firstChild) {
      const style = document.createElement("style");
      style.textContent = STYLES;
      root.appendChild(style);
      const layout = document.createElement("div");
      layout.className = "layout";
      layout.innerHTML = `
        <header class="bar">
          <button class="icon-only" id="menu" title="Меню">${this._svg(
            "M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z"
          )}</button>
          <h1>Яндекс меню</h1>
          <div class="grow"></div>
          <label class="search">
            ${this._svg(
              "M9.5,3A6.5,6.5 0 0,1 16,9.5C16,11.11 15.41,12.59 14.44,13.73L14.71,14H15.5L20.5,19L19,20.5L14,15.5V14.71L13.73,14.44C12.59,15.41 11.11,16 9.5,16A6.5,6.5 0 0,1 3,9.5A6.5,6.5 0 0,1 9.5,3M9.5,5C7,5 5,7 5,9.5C5,12 7,14 9.5,14C12,14 14,12 14,9.5C14,7 12,5 9.5,5Z",
              16
            )}
            <input id="q" type="search" placeholder="Поиск" autocomplete="off">
          </label>
          <button class="btn" id="discover">Обновить список</button>
        </header>
        <div class="body">
          <div class="list" id="list"></div>
          <aside class="panel" id="panel" hidden></aside>
        </div>
        <div class="toast" id="toast" hidden></div>
      `;
      root.appendChild(layout);
      this._bind();
    }
    this._renderList();
    this._renderPanel();
    const layout = root.querySelector(".layout");
    if (layout) layout.classList.toggle("busy", this._busy);
  }

  _svg(path, size = 20) {
    return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="${path}"/></svg>`;
  }

  _esc(value) {
    return String(value === null || value === undefined ? "" : value).replace(
      /[&<>"]/g,
      (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])
    );
  }

  _renderList() {
    const host = this.shadowRoot.getElementById("list");
    if (!host) return;

    if (this._error) {
      host.innerHTML = `<div class="fatal">${this._esc(this._error)}</div>`;
      return;
    }
    if (!this._data) {
      host.innerHTML = `<div class="loader">Читаю Яндекс-дом…</div>`;
      return;
    }

    const query = this._query.trim().toLowerCase();
    const match = (device) =>
      !query ||
      (device.names.join(" ") + " " + (device.external_id || "")).toLowerCase().includes(query);

    const rooms = [];
    const seen = new Set();
    for (const device of this._devices) {
      const room = device.room || "Без комнаты";
      if (!seen.has(room)) {
        seen.add(room);
        rooms.push(room);
      }
    }

    let html = "";
    for (const room of rooms) {
      const items = this._devices.filter(
        (device) => (device.room || "Без комнаты") === room && match(device)
      );
      if (!items.length) continue;
      html += `<section><div class="room-head"><h2>${this._esc(room)}</h2><span class="count">${
        items.length
      }</span></div><div class="card">`;
      for (const device of items) {
        const chips = device.names
          .map(
            (name, index) =>
              `<span class="chip${index === 0 ? " primary" : ""}">${this._esc(name)}</span>`
          )
          .join("");
        const classes = ["row"];
        if (device.id === this._selected) classes.push("selected");
        if (this._isOn(device)) classes.push("lit");
        html += `<button class="${classes.join(" ")}" data-id="${device.id}">
          <span class="avatar">${this._svg(this._iconFor(device), 18)}</span>
          <span><span class="title">${this._esc(device.names[0])}</span><br>
            <span class="entity">${this._esc(device.external_id || "устройство Яндекса")}</span></span>
          <span class="chips">${chips}</span>
          <span class="role">${this._roleWord(device) ? `<b>${this._roleWord(device)}</b>` : ""}</span>
        </button>`;
      }
      html += `</div></section>`;
    }

    const unexposed = (this._data.unexposed || []).filter(
      (item) => !query || (item.name + " " + item.entity_id).toLowerCase().includes(query)
    );
    if (query && unexposed.length) {
      html += `<section><div class="room-head"><h2>Есть в Home Assistant, но не отдано в Алису</h2><span class="count">${unexposed.length}</span></div><div class="card">`;
      for (const item of unexposed.slice(0, 40)) {
        html += `<div class="row offer">
          <span class="avatar">${this._svg(ICONS.other, 18)}</span>
          <span><span class="title">${this._esc(item.name)}</span><br>
            <span class="entity">${this._esc(item.entity_id)}</span></span>
          <span class="role">${item.area ? "зона " + this._esc(item.area) : ""}${
          item.available === false ? ` <b style="color:var(--warn)">недоступна</b>` : ""
        }</span>
          <button class="btn btn-quiet" data-expose="${this._esc(item.entity_id)}">Отдать в Алису</button>
        </div>`;
      }
      html += `</div></section>`;
    } else if (!query) {
      html += `<section><div class="room-head"><h2>Отдать в Алису</h2></div><div class="card"><div class="empty">
        Начните вводить название или сущность в поиске — сущности Home Assistant, которых ещё нет в Алисе, появятся здесь.
        ${
          this._data.label && !this._data.label.supported
            ? `<div class="msg warn" style="margin-top:12px;text-align:left">${this._esc(
                this._data.label.reason
              )}</div>`
            : ""
        }
      </div></div></section>`;
    }

    host.innerHTML = html || `<div class="empty">Ничего не нашлось.</div>`;
  }

  _renderPanel() {
    const host = this.shadowRoot.getElementById("panel");
    if (!host) return;
    const device = this._device(this._selected);
    if (!device) {
      host.hidden = true;
      host.innerHTML = "";
      return;
    }
    host.hidden = false;

    const limit = (this._data && this._data.max_names) || LIMIT_FALLBACK;
    const full = device.names.length >= limit;
    const isLight = (device.current_type || "").includes("light") && device.role_switchable;

    const names = device.names
      .map(
        (name, index) => `
        <div class="name${index === 0 ? " primary" : ""}">
          <span class="value">${this._esc(name)}</span>
          ${
            index === 0
              ? `<span class="tag">основное</span>`
              : `<button class="mini" data-primary="${this._esc(name)}" title="Сделать основным">${this._svg(
                  "M12,17.27L18.18,21L16.54,13.97L22,9.24L14.81,8.62L12,2L9.19,8.62L2,9.24L7.45,13.97L5.82,21L12,17.27Z",
                  16
                )}</button>`
          }
          ${
            device.names.length > 1
              ? `<button class="mini danger" data-remove="${this._esc(name)}" title="Удалить имя">${this._svg(
                  "M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z",
                  16
                )}</button>`
              : ""
          }
        </div>`
      )
      .join("");

    const message = this._message
      ? `<div class="msg ${this._message.level}">${this._esc(this._message.text)}</div>`
      : full
      ? `<div class="msg info">Занято ${limit} имён из ${limit} — это потолок Яндекса.</div>`
      : "";

    const rooms = (this._data.rooms || [])
      .map(
        (room) =>
          `<option value="${this._esc(room.id)}"${room.id === device.room_id ? " selected" : ""}>${this._esc(
            room.name
          )}</option>`
      )
      .join("");

    host.innerHTML = `
      <div class="panel-head">
        <span class="avatar${this._isOn(device) ? " lit" : ""}">${this._svg(this._iconFor(device), 20)}</span>
        <div>
          <h3>${this._esc(device.names[0])}</h3>
          <div class="entity">${this._esc(device.external_id || "устройство Яндекса")}</div>
        </div>
        <button class="icon-only" id="close" title="Закрыть" style="margin-left:auto">${this._svg(
          "M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z",
          20
        )}</button>
      </div>
      <div class="panel-body">
        <div class="section">
          <div class="section-head"><h4>Имена для голоса</h4><span class="counter">${
            device.names.length
          } / ${limit}</span></div>
          <p class="hint">Первое имя — основное, его видно в приложении «Дом с Алисой». Остальные работают как синонимы.</p>
          <div class="names">${names}</div>
          <div class="add">
            <input id="newname" type="text" ${full ? "disabled" : ""} placeholder="${
      full ? "Достигнут предел имён" : "Ещё одно имя, например «люстра»"
    }" autocomplete="off">
            <button class="btn btn-primary" id="add" ${full ? "disabled" : ""}>Добавить</button>
          </div>
          ${message}
        </div>

        ${
          isLight
            ? `<div class="section">
                <div class="section-head"><h4>Роль в комнате</h4></div>
                <p class="hint">«Алиса, включи свет» зажигает только основной свет комнаты. Дополнительный включается по имени.</p>
                <div class="seg">
                  <button data-role="main" class="${
                    device.role && device.role.endsWith("main") ? "on" : ""
                  }">Основной свет</button>
                  <button data-role="secondary" class="${
                    device.role && device.role.endsWith("secondary") ? "on" : ""
                  }">Дополнительный</button>
                </div>
              </div>`
            : ""
        }

        <div class="section">
          <div class="section-head"><h4>Комната</h4></div>
          <p class="hint">Комнату Алиса использует в командах вроде «включи свет в зале».</p>
          <select class="field" id="room">${rooms}</select>
        </div>

        ${
          this._snapshotDiffers(device)
            ? `<div class="section">
                <div class="section-head"><h4>Слепок</h4></div>
                <p class="hint">Сохранённый набор имён и роль отличаются от нынешних — так бывает после пересоздания устройства.</p>
                <button class="btn" id="restore">Вернуть имена и роль из слепка</button>
              </div>`
            : ""
        }
      </div>
      <div class="panel-foot">
        ${
          device.switchable && /light|socket|switch/.test(device.current_type || "")
            ? `<button class="btn btn-quiet" id="blink">Проверить: мигнуть</button>`
            : ""
        }
        <div class="grow"></div>
        ${
          device.from_ha
            ? `<button class="btn btn-danger" id="unexpose">Убрать из Алисы</button>`
            : `<button class="btn btn-danger" id="delete">Удалить</button>`
        }
      </div>
    `;
  }

  /* ---------------------------------------------------------------- события */

  _bind() {
    const root = this.shadowRoot;

    root.getElementById("menu").addEventListener("click", () => {
      this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
    });

    root.getElementById("q").addEventListener("input", (event) => {
      this._query = event.target.value;
      this._renderList();
    });

    root.getElementById("discover").addEventListener("click", () => {
      this._act("yandex_menu/discovery", {}, "Яндекс перечитывает список устройств");
    });

    root.getElementById("list").addEventListener("click", (event) => {
      const row = event.target.closest("[data-id]");
      if (row) {
        this._selected = row.getAttribute("data-id");
        this._message = null;
        this._render();
        return;
      }
      const expose = event.target.closest("[data-expose]");
      if (expose) {
        this._act(
          "yandex_menu/expose",
          { entity_id: expose.getAttribute("data-expose"), expose: true },
          "Отдал в Алису и обновил список устройств"
        );
      }
    });

    const panel = root.getElementById("panel");

    panel.addEventListener("click", (event) => {
      const device = this._device(this._selected);
      if (!device) return;

      if (event.target.closest("#close")) {
        this._selected = null;
        this._message = null;
        this._render();
        return;
      }

      const remove = event.target.closest("[data-remove]");
      if (remove) {
        this._act(
          "yandex_menu/name_delete",
          { device_id: device.id, name: remove.getAttribute("data-remove") },
          "Имя удалено"
        );
        return;
      }

      const primary = event.target.closest("[data-primary]");
      if (primary) {
        this._act(
          "yandex_menu/name_primary",
          { device_id: device.id, name: primary.getAttribute("data-primary") },
          "Основное имя изменено"
        );
        return;
      }

      const role = event.target.closest("[data-role]");
      if (role) {
        this._act(
          "yandex_menu/set_role",
          { device_id: device.id, role: role.getAttribute("data-role") },
          "Роль изменена"
        );
        return;
      }

      if (event.target.closest("#add")) {
        const input = panel.querySelector("#newname");
        const value = input.value.trim();
        const verdict = this._checkName(value, device);
        if (verdict && verdict.level === "error") {
          this._message = verdict;
          this._renderPanel();
          return;
        }
        this._message = verdict;
        this._act("yandex_menu/name_add", { device_id: device.id, name: value }, "Имя добавлено");
        return;
      }

      if (event.target.closest("#blink")) {
        this._call("yandex_menu/blink", { device_id: device.id });
        this._toast("Включаю на три секунды");
        return;
      }

      if (event.target.closest("#restore")) {
        this._act("yandex_menu/restore", { device_id: device.id }, "Вернул имена из слепка");
        return;
      }

      if (event.target.closest("#unexpose")) {
        if (
          !confirm(
            `Убрать «${device.names[0]}» из Алисы?\n\nСнимем метку и удалим устройство в Яндексе. ` +
              `Сущность в Home Assistant останется на месте.`
          )
        )
          return;
        this._selected = null;
        this._act("yandex_menu/withdraw", { device_id: device.id });
        return;
      }

      if (event.target.closest("#delete")) {
        if (!confirm(`Удалить «${device.names[0]}» из Яндекс-дома? Это необратимо.`)) return;
        this._selected = null;
        this._act("yandex_menu/delete_device", { device_id: device.id }, "Устройство удалено");
      }
    });

    panel.addEventListener("change", (event) => {
      const device = this._device(this._selected);
      if (!device) return;
      if (event.target.id === "room") {
        this._act(
          "yandex_menu/set_room",
          { device_id: device.id, room_id: event.target.value },
          "Комната изменена"
        );
      }
    });

    panel.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && event.target.id === "newname") {
        event.preventDefault();
        panel.querySelector("#add").click();
      }
    });
  }
}

customElements.define("yandex-menu-panel", YandexMenuPanel);
