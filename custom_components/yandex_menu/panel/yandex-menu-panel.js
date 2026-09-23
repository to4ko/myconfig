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
  play: "M8,5.14V19.14L19,12.14L8,5.14Z",
  sync:
    "M12,18A6,6 0 0,1 6,12C6,11 6.25,10.03 6.7,9.2L5.24,7.74C4.46,8.97 4,10.43 4,12A8,8 0 0,0 12,20V23L16,19L12,15M12,4V1L8,5L12,9V6A6,6 0 0,1 18,12C18,13 17.75,13.97 17.3,14.8L18.76,16.26C19.54,15.03 20,13.57 20,12A8,8 0 0,0 12,4Z",
  syncAlert:
    "M11,13H13V7H11M21,4H15V10L17.24,7.76C18.32,8.85 19,10.34 19,12C19,14.61 17.33,16.83 15,17.65V19.74C18.45,18.85 21,15.73 21,12C21,9.79 20.09,7.8 18.64,6.36M11,17H13V15H11M3,12C3,14.21 3.91,16.2 5.36,17.64L3,20H9V14L6.76,16.24C5.68,15.15 5,13.66 5,12C5,9.39 6.67,7.17 9,6.35V4.26C5.55,5.15 3,8.27 3,12Z",
  voice:
    "M9,5A4,4 0 0,1 13,9A4,4 0 0,1 9,13A4,4 0 0,1 5,9A4,4 0 0,1 9,5M9,15C11.67,15 17,16.34 17,19V21H1V19C1,16.34 6.33,15 9,15M16.76,5.36C18.78,7.56 18.78,10.61 16.76,12.63L15.08,10.94C15.92,9.76 15.92,8.23 15.08,7.05L16.76,5.36M20.07,2C24,6.05 23.97,12.11 20.07,16L18.44,14.37C21.21,11.19 21.21,6.65 18.44,3.63L20.07,2Z",
  scenario:
    "M9 14H14V15.7C13.9 15.8 13.9 15.9 13.8 16H9V14M9 12H14V10H9V12M9 8H14V6H9V8M7 5C7 4.4 7.4 4 8 4H16V13.8C16.6 13.4 17.3 13.2 18 13.1V5C18 4.4 18.4 4 19 4S20 4.4 20 5V6H22V5C22 3.3 20.7 2 19 2H8C6.3 2 5 3.3 5 5V16H7V5M13 19V18.4 18H2V19C2 20.7 3.3 22 5 22H13.8C13.3 21.1 13 20.1 13 19M17 16V22L22 19L17 16Z",
};

/* Значки умений в списке: вид умения → [подпись, иконка]. Порядок = порядок показа. */
const SKILL_ICONS = {
  on_off: [
    "включение",
    "M16.56,5.44L15.11,6.89C16.84,7.94 18,9.83 18,12A6,6 0 0,1 12,18A6,6 0 0,1 6,12C6,9.83 7.16,7.94 8.88,6.88L7.44,5.44C5.36,6.88 4,9.28 4,12A8,8 0 0,0 12,20A8,8 0 0,0 20,12C20,9.28 18.64,6.88 16.56,5.44M13,3H11V13H13",
  ],
  brightness: [
    "яркость",
    "M12,18V6A6,6 0 0,1 18,12A6,6 0 0,1 12,18M20,15.31L23.31,12L20,8.69V4H15.31L12,0.69L8.69,4H4V8.69L0.69,12L4,15.31V20H8.69L12,23.31L15.31,20H20V15.31Z",
  ],
  color: [
    "цвет",
    "M17.5,12A1.5,1.5 0 0,1 16,10.5A1.5,1.5 0 0,1 17.5,9A1.5,1.5 0 0,1 19,10.5A1.5,1.5 0 0,1 17.5,12M14.5,8A1.5,1.5 0 0,1 13,6.5A1.5,1.5 0 0,1 14.5,5A1.5,1.5 0 0,1 16,6.5A1.5,1.5 0 0,1 14.5,8M9.5,8A1.5,1.5 0 0,1 8,6.5A1.5,1.5 0 0,1 9.5,5A1.5,1.5 0 0,1 11,6.5A1.5,1.5 0 0,1 9.5,8M6.5,12A1.5,1.5 0 0,1 5,10.5A1.5,1.5 0 0,1 6.5,9A1.5,1.5 0 0,1 8,10.5A1.5,1.5 0 0,1 6.5,12M12,3A9,9 0 0,0 3,12A9,9 0 0,0 12,21A1.5,1.5 0 0,0 13.5,19.5C13.5,19.11 13.35,18.76 13.11,18.5C12.88,18.23 12.73,17.88 12.73,17.5A1.5,1.5 0 0,1 14.23,16H16A5,5 0 0,0 21,11C21,6.58 16.97,3 12,3Z",
  ],
  white: [
    "оттенок белого",
    "M3.55 19.09L4.96 20.5L6.76 18.71L5.34 17.29M12 6C8.69 6 6 8.69 6 12S8.69 18 12 18 18 15.31 18 12C18 8.68 15.31 6 12 6M20 13H23V11H20M17.24 18.71L19.04 20.5L20.45 19.09L18.66 17.29M20.45 5L19.04 3.6L17.24 5.39L18.66 6.81M13 1H11V4H13M6.76 5.39L4.96 3.6L3.55 5L5.34 6.81L6.76 5.39M1 13H4V11H1M13 20H11V23H13",
  ],
  scenes: [
    "режимы света",
    "M7.5,5.6L5,7L6.4,4.5L5,2L7.5,3.4L10,2L8.6,4.5L10,7L7.5,5.6M19.5,15.4L22,14L20.6,16.5L22,19L19.5,17.6L17,19L18.4,16.5L17,14L19.5,15.4M22,2L20.6,4.5L22,7L19.5,5.6L17,7L18.4,4.5L17,2L19.5,3.4L22,2M13.34,12.78L15.78,10.34L13.66,8.22L11.22,10.66L13.34,12.78M14.37,7.29L16.71,9.63C17.1,10 17.1,10.65 16.71,11.04L5.04,22.71C4.65,23.1 4,23.1 3.63,22.71L1.29,20.37C0.9,20 0.9,19.35 1.29,18.96L12.96,7.29C13.35,6.9 14,6.9 14.37,7.29Z",
  ],
  mode: [
    "режимы",
    "M8 13C6.14 13 4.59 14.28 4.14 16H2V18H4.14C4.59 19.72 6.14 21 8 21S11.41 19.72 11.86 18H22V16H11.86C11.41 14.28 9.86 13 8 13M8 19C6.9 19 6 18.1 6 17C6 15.9 6.9 15 8 15S10 15.9 10 17C10 18.1 9.1 19 8 19M19.86 6C19.41 4.28 17.86 3 16 3S12.59 4.28 12.14 6H2V8H12.14C12.59 9.72 14.14 11 16 11S19.41 9.72 19.86 8H22V6H19.86M16 9C14.9 9 14 8.1 14 7C14 5.9 14.9 5 16 5S18 5.9 18 7C18 8.1 17.1 9 16 9Z",
  ],
  open: [
    "открытие",
    "M18,16V13H15V22H13V2H15V11H18V8L22,12L18,16M2,12L6,16V13H9V22H11V2H9V11H6V8L2,12Z",
  ],
  temperature: [
    "температура",
    "M15 13V5A3 3 0 0 0 9 5V13A5 5 0 1 0 15 13M12 4A1 1 0 0 1 13 5V8H11V5A1 1 0 0 1 12 4Z",
  ],
  volume: [
    "громкость",
    "M14,3.23V5.29C16.89,6.15 19,8.83 19,12C19,15.17 16.89,17.84 14,18.7V20.77C18,19.86 21,16.28 21,12C21,7.72 18,4.14 14,3.23M16.5,12C16.5,10.23 15.5,8.71 14,7.97V16C15.5,15.29 16.5,13.76 16.5,12M3,9V15H7L12,20V4L7,9H3Z",
  ],
  channel: [
    "каналы",
    "M9,2C7.89,2 7,2.89 7,4V20C7,21.11 7.89,22 9,22H15C16.11,22 17,21.11 17,20V4C17,2.89 16.11,2 15,2H13V4H11V2H9M11,6H13V8H15V10H13V12H11V10H9V8H11V6M9,14H11V16H9V14M13,14H15V16H13V14M9,18H11V20H9V18M13,18H15V20H13V18Z",
  ],
  humidity: [
    "влажность",
    "M12,3.25C12,3.25 6,10 6,14C6,17.32 8.69,20 12,20A6,6 0 0,0 18,14C18,10 12,3.25 12,3.25M14.47,9.97L15.53,11.03L9.53,17.03L8.47,15.97M9.75,10A1.25,1.25 0 0,1 11,11.25A1.25,1.25 0 0,1 9.75,12.5A1.25,1.25 0 0,1 8.5,11.25A1.25,1.25 0 0,1 9.75,10M14.25,14.5A1.25,1.25 0 0,1 15.5,15.75A1.25,1.25 0 0,1 14.25,17A1.25,1.25 0 0,1 13,15.75A1.25,1.25 0 0,1 14.25,14.5Z",
  ],
  toggle: [
    "переключатели",
    "M17 6H7C3.69 6 1 8.69 1 12S3.69 18 7 18H17C20.31 18 23 15.31 23 12S20.31 6 17 6M17 16H7C4.79 16 3 14.21 3 12S4.79 8 7 8H17C19.21 8 21 9.79 21 12S19.21 16 17 16M17 9C15.34 9 14 10.34 14 12S15.34 15 17 15 20 13.66 20 12 18.66 9 17 9Z",
  ],
  video_stream: [
    "видео",
    "M6.03 12.03L8.03 15.5L5.5 18.68L2 12.62L6.03 12.03M17 18V15.29C17.88 14.9 18.5 14.03 18.5 13C18.5 12.43 18.3 11.9 17.97 11.5L19.94 10.35C20.95 9.76 21.3 8.47 20.71 7.46L19.33 5.06C18.74 4.05 17.45 3.7 16.44 4.28L8.31 9C7.36 9.53 7.03 10.75 7.58 11.71L9.08 14.31C9.63 15.26 10.86 15.59 11.81 15.04L13.69 13.96C13.94 14.55 14.41 15.03 15 15.29V18C15 19.1 15.9 20 17 20H22V18H17Z",
  ],
  sensor: [
    "показания",
    "M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,4A8,8 0 0,1 20,12C20,14.4 19,16.5 17.3,18C15.9,16.7 14,16 12,16C10,16 8.2,16.7 6.7,18C5,16.5 4,14.4 4,12A8,8 0 0,1 12,4M14,5.89C13.62,5.9 13.26,6.15 13.1,6.54L11.81,9.77L11.71,10C11,10.13 10.41,10.6 10.14,11.26C9.73,12.29 10.23,13.45 11.26,13.86C12.29,14.27 13.45,13.77 13.86,12.74C14.12,12.08 14,11.32 13.57,10.76L13.67,10.5L14.96,7.29L14.97,7.26C15.17,6.75 14.92,6.17 14.41,5.96C14.28,5.91 14.15,5.89 14,5.89M10,6A1,1 0 0,0 9,7A1,1 0 0,0 10,8A1,1 0 0,0 11,7A1,1 0 0,0 10,6M7,9A1,1 0 0,0 6,10A1,1 0 0,0 7,11A1,1 0 0,0 8,10A1,1 0 0,0 7,9M17,9A1,1 0 0,0 16,10A1,1 0 0,0 17,11A1,1 0 0,0 18,10A1,1 0 0,0 17,9Z",
  ],
  event: [
    "события",
    "M10 21H14C14 22.1 13.1 23 12 23S10 22.1 10 21M21 19V20H3V19L5 17V11C5 7.9 7 5.2 10 4.3V4C10 2.9 10.9 2 12 2S14 2.9 14 4V4.3C17 5.2 19 7.9 19 11V17L21 19M17 11C17 8.2 14.8 6 12 6S7 8.2 7 11V18H17V11Z",
  ],
};
const SKILL_FALLBACK = ["умение", "M3,17V19H9V17H3M3,5V7H13V5H3M13,21V19H21V17H13V15H11V21H13M7,9V11H3V13H7V15H9V9H7M21,13V11H11V13H21M15,9H17V7H21V5H17V3H15V9Z"];
const SKILLS_SHOWN = 5;

/* Слова для Алисы. Во фразах {name} — имя устройства, {room} — комната,
   {value} — выбранное значение. Склонять имена панель не умеет, поэтому
   перед проверкой фразу можно поправить. */
const RANGE_WORDS = {
  brightness: ["Яркость", [
    ["ярче", "сделай {name} ярче"],
    ["темнее", "сделай {name} темнее"],
    ["на 50%", "установи яркость {name} на 50 процентов"],
  ]],
  open: ["Открыть частично", [["на 50%", "открой {name} на 50 процентов"]]],
  temperature: ["Температура", [
    ["выше", "повысь температуру {name}"],
    ["ниже", "понизь температуру {name}"],
  ]],
  volume: ["Громкость", [
    ["громче", "сделай {name} громче"],
    ["тише", "сделай {name} тише"],
  ]],
  channel: ["Каналы", [
    ["следующий канал", "следующий канал на {name}"],
    ["предыдущий канал", "предыдущий канал на {name}"],
  ]],
  humidity: ["Влажность", [["на 50%", "установи влажность {name} на 50 процентов"]]],
};

const MODE_WORDS = {
  cleanup_mode: ["Уборка", "включи {value} на {name}"],
  work_speed: ["Скорость", "поставь скорость {value} на {name}"],
  fan_speed: ["Скорость вентилятора", "поставь скорость {value} на {name}"],
  thermostat: ["Режим", "включи режим {value} на {name}"],
  swing: ["Направление воздуха", "включи {value} на {name}"],
  program: ["Программа", "включи программу {value} на {name}"],
  input_source: ["Источник", "переключи {name} на {value}"],
};

const TOGGLE_WORDS = {
  pause: ["Пауза", [["пауза", "поставь {name} на паузу"], ["продолжи", "продолжи {name}"]]],
  mute: ["Звук", [["выключи звук", "выключи звук на {name}"], ["включи звук", "включи звук на {name}"]]],
  backlight: ["Подсветка", [["включи подсветку", "включи подсветку на {name}"], ["выключи подсветку", "выключи подсветку на {name}"]]],
  controls_locked: ["Блокировка кнопок", [["заблокируй", "заблокируй {name}"], ["разблокируй", "разблокируй {name}"]]],
  oscillation: ["Вращение", [["включи вращение", "включи вращение на {name}"], ["выключи вращение", "выключи вращение на {name}"]]],
  ionization: ["Ионизация", [["включи ионизацию", "включи ионизацию на {name}"], ["выключи ионизацию", "выключи ионизацию на {name}"]]],
  keep_warm: ["Поддержание тепла", [["включи подогрев", "включи поддержание тепла на {name}"], ["выключи подогрев", "выключи поддержание тепла на {name}"]]],
};

/* Вопросы к датчикам. true — спрашивают про комнату, false — про само устройство. */
const ASK_WORDS = {
  temperature: ["какая температура", true],
  humidity: ["какая влажность", true],
  co2_level: ["какой уровень углекислого газа", true],
  "pm1_density": ["какое качество воздуха", true],
  "pm2.5_density": ["какое качество воздуха", true],
  "pm10_density": ["какое качество воздуха", true],
  tvoc: ["какое качество воздуха", true],
  illumination: ["какая освещённость", true],
  pressure: ["какое давление", true],
  battery_level: ["какой заряд", false],
  water_level: ["какой уровень воды", false],
  food_level: ["сколько корма", false],
  power: ["какая мощность", false],
  voltage: ["какое напряжение", false],
  amperage: ["какой ток", false],
  electricity_meter: ["какие показания", false],
  gas_meter: ["какие показания", false],
  water_meter: ["какие показания", false],
  heat_meter: ["какие показания", false],
};

const CHIPS_COLLAPSED = 6;
const STATION_KEY = "yandex_menu.station";
const HOUSE_KEY = "yandex_menu.house";

const STYLES = `
  :host {
    display: block;
    box-sizing: border-box;
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
    /* Вырезы экрана: часы и «чёлка» сверху, полоска «домой» снизу. Home Assistant
       отдаёт их своими переменными (приложение подставляет свои значения), без
       них берём у браузера. */
    --safe-top: var(--safe-area-inset-top, env(safe-area-inset-top, 0px));
    --safe-bottom: var(--safe-area-inset-bottom, env(safe-area-inset-bottom, 0px));
    --safe-left: var(--safe-area-inset-left, env(safe-area-inset-left, 0px));
    --safe-right: var(--safe-area-inset-right, env(safe-area-inset-right, 0px));
    /* Сверху отступ берёт шапка, снизу — список и карточка: так их цвет доходит
       до края экрана. Сбоку вырез может уже прикрывать боковое меню HA — тогда
       он не наш. */
    padding: 0 var(--safe-area-content-inset-right, var(--safe-right)) 0
      var(--safe-area-content-inset-left, var(--safe-left));
  }
  * { box-sizing: border-box; }
  button { font: inherit; color: inherit; cursor: pointer; }
  input, select { font: inherit; color: inherit; }
  :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 6px; }

  .layout { display: flex; flex-direction: column; height: 100%; }
  header.bar {
    display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
    padding: calc(10px + var(--safe-top)) 16px 10px;
    background: var(--app-header-background-color, var(--surface));
    color: var(--app-header-text-color, var(--primary-text-color));
    border-bottom: 1px solid var(--line);
  }
  header.bar h1 { margin: 0; font-size: 20px; font-weight: 400; }
  .account { font-size: 12.5px; color: var(--muted); background: var(--surface-2); padding: 3px 10px; border-radius: 999px; }
  .houses { display: flex; flex-wrap: wrap; gap: 2px; padding: 3px; border-radius: 999px; background: var(--surface-2); }
  .houses[hidden] { display: none; }
  .houses button {
    border: 0; background: transparent; padding: 4px 12px; border-radius: 999px;
    font-size: 13px; color: var(--muted); display: inline-flex; align-items: baseline; gap: 6px;
  }
  .houses button:hover { color: var(--primary-text-color); }
  .houses button.on { background: var(--surface); color: var(--accent); font-weight: 500; box-shadow: 0 1px 2px rgba(0,0,0,.14); }
  .houses .n { font-size: 11.5px; font-weight: 400; color: var(--muted); font-variant-numeric: tabular-nums; }
  .elsewhere { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: 12.5px; color: var(--muted); }
  .elsewhere .chip { font-size: 12.5px; padding: 3px 11px; }
  .grow { flex: 1 1 40px; }
  .search {
    display: flex; align-items: center; gap: 8px;
    background: var(--surface-2); border-radius: 999px; padding: 6px 14px; min-width: 190px;
  }
  .search input { border: 0; background: transparent; outline: none; width: 100%; }
  .icon-only { border: 0; background: transparent; padding: 8px; border-radius: 50%; display: grid; place-items: center; }
  .icon-only:hover { background: var(--surface-2); }
  .icon-only[hidden] { display: none; }
  .sync { color: var(--muted); }
  .sync[disabled] { cursor: default; }
  .sync[disabled]:hover { background: transparent; }
  .sync.spin svg { animation: spin 1.2s linear infinite; }
  .sync.warn { color: var(--warn); }
  @keyframes spin { to { transform: rotate(-360deg); } }
  @media (prefers-reduced-motion: reduce) { .sync.spin svg { animation-duration: 4s; } }

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
  .list {
    flex: 1; overflow-y: auto; padding: 16px 16px calc(16px + var(--safe-bottom));
    display: flex; flex-direction: column; gap: 22px;
  }
  .room-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 8px; }
  .room-head h2 {
    margin: 0; font-size: 13px; font-weight: 500; letter-spacing: .4px;
    text-transform: uppercase; color: var(--muted);
  }
  .room-head .count { font-size: 12px; color: var(--muted); }
  .room-cmd {
    margin-left: auto; align-self: center; border: 0; background: transparent; color: var(--muted);
    display: inline-flex; align-items: center; gap: 5px; padding: 3px 9px; border-radius: 999px; font-size: 12px;
  }
  .room-cmd:hover, .room-cmd.on { color: var(--accent); background: rgba(3,169,244,.12); }
  .card { background: var(--surface); border-radius: 12px; box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,.12)); overflow: hidden; }
  .row {
    display: grid;
    grid-template-columns: 36px minmax(150px, 1.4fr) minmax(120px, 1.6fr) 124px;
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
  .meta { display: flex; align-items: center; gap: 8px; min-width: 0; }
  .skills { display: flex; align-items: center; gap: 3px; width: 94px; flex: none; color: var(--muted); }
  .skills > span { display: grid; place-items: center; }
  .skills .more { font-size: 11px; padding-left: 2px; }
  .row:hover .skills { color: var(--accent); }
  .row.scenario .meta { justify-content: flex-end; }

  .panel {
    width: 420px; flex: none; border-left: 1px solid var(--line);
    background: var(--surface); display: flex; flex-direction: column;
    padding-bottom: var(--safe-bottom);
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

  button.chip { border: 0; cursor: pointer; }
  .pick:hover { color: var(--accent); }
  .pick.on { background: rgba(3,169,244,.16); color: var(--accent); font-weight: 500; }
  .chip.more { background: transparent; color: var(--accent); }
  button.chip.go:hover { color: var(--accent); background: rgba(3,169,244,.14); }
  .say-row {
    display: grid; grid-template-columns: 1fr auto; gap: 5px 10px; align-items: center;
    padding: 10px 0; border-top: 1px solid var(--line);
  }
  .say-row:first-of-type { border-top: 0; }
  .say-label { font-size: 12.5px; color: var(--muted); }
  .say-row .chips { grid-column: 1; }
  .say-row .chip { font-size: 12.5px; padding: 4px 11px; }
  .say-row .play { grid-column: 2; grid-row: 1 / 3; }
  .play {
    width: 34px; height: 34px; padding: 0; border-radius: 50%; flex: none;
    border: 1px solid var(--line); background: var(--surface); color: var(--accent);
    display: grid; place-items: center;
  }
  .play:hover { border-color: var(--accent); background: rgba(3,169,244,.1); }
  .station { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 0 0 6px; font-size: 12.5px; color: var(--muted); }
  .station select { width: auto; flex: 1; min-width: 150px; padding: 6px 10px; }
  .who { font-size: 13px; margin: 6px 0 4px; }
  .who + .chips { margin-bottom: 8px; }

  select.field, input.field {
    width: 100%; padding: 9px 12px; border-radius: 10px;
    border: 1px solid var(--line); background: var(--surface);
  }

  .empty { padding: 40px 16px; text-align: center; color: var(--muted); }
  .loader { padding: 40px 16px; text-align: center; color: var(--muted); }
  .loader .what { color: var(--primary-text-color); }
  .loader .left { margin-top: 4px; font-size: 13px; }
  .loader .bar { width: min(320px, 100%); height: 4px; margin: 14px auto 0; border-radius: 2px; background: var(--surface-2); overflow: hidden; }
  .loader .bar i { display: block; height: 100%; background: var(--accent); transition: width .4s ease; }
  .loader .hint { max-width: 420px; margin: 16px auto 0; font-size: 13px; line-height: 1.45; }
  .sync-note { font-size: 12px; color: var(--muted); white-space: nowrap; margin-left: -4px; }
  .sync-note[hidden] { display: none; }
  .fatal { margin: 16px; padding: 16px; border-radius: 12px; background: rgba(219,68,55,.1); color: var(--danger); }

  .toast {
    position: fixed; left: 50%; bottom: calc(24px + var(--safe-bottom)); transform: translateX(-50%);
    background: var(--primary-text-color); color: var(--primary-background-color);
    padding: 10px 18px; border-radius: 999px; font-size: 13px; z-index: 9;
    max-width: 90vw;
  }
  .toast[hidden] { display: none; }
  .busy { opacity: .55; pointer-events: none; }

  @media (max-width: 900px) {
    /* карточка открыта поверх всего экрана — вырезы она обходит сама */
    .panel {
      position: fixed; inset: 0; width: auto; z-index: 8; border-left: 0;
      padding: var(--safe-top) var(--safe-right) var(--safe-bottom) var(--safe-left);
    }
    .row { grid-template-columns: 36px 1fr; row-gap: 6px; }
    .row .chips, .row .role, .row .meta { grid-column: 2; }
    .row.scenario { grid-template-columns: 36px 1fr auto; }
    .row.scenario .chips { grid-column: 2; grid-row: 2; }
    .row.scenario .meta { grid-column: 3; grid-row: 1 / 3; }
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
    // Список приходит из трёх мест: сохранённый, свежий и ответ на действие.
    // Каждый запрос получает номер, и на экране остаётся ответ самого позднего.
    this._seq = 0; // номер последнего запроса за списком
    this._shown = 0; // номер запроса, чей список сейчас на экране
    this._loading = 0; // сколько обновлений списка сейчас в пути
    this._savedAt = null; // на экране сохранённый список — когда его прочитали
    this._progress = null; // как далеко зашла сборка списка: дом, сколько прочитано
    this._unsubProgress = null;
    this._room = null; // открыта карточка комнаты вместо устройства
    // Карточка открывалась сменой поля и следа в истории браузера не оставляла:
    // аппаратная «назад» на телефоне снимала запись входа в панель и уносила на
    // дашборд. Теперь под открытой карточкой лежит своя запись: первый «назад»
    // съедает её и возвращает к списку, второй уводит с панели.
    this._histCard = false; // наша запись в истории есть
    this._backRoom = null; // в устройство провалились из комнаты — туда и вернёмся
    this._listShape = null; // дом и поиск прошлой отрисовки: сменились — прокрутка наверх
    this._onPop = this._onPop.bind(this); // ссылка одна: по ней же отписываемся
    this._picked = {}; // выбранный чип в строке фраз
    this._expanded = {}; // строки, где показаны все значения
    this._sayRows = {}; // строки фраз последней отрисовки, для кнопки «проверить»
    this._scrollToSkills = false;
    // Выбранная Станция — своя в каждом доме. Раньше хранилась одной строкой.
    this._stationByHouse = {};
    this._house = null;
    try {
      const saved = localStorage.getItem(STATION_KEY);
      if (saved) this._stationByHouse = saved.startsWith("{") ? JSON.parse(saved) : { "": saved };
    } catch (err) {
      this._stationByHouse = {};
    }
    try {
      this._house = localStorage.getItem(HOUSE_KEY);
    } catch (err) {
      this._house = null;
    }
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._loaded) {
      this._loaded = true;
      this._render();
      // Яндекс отвечает секунды: пока идёт свежий список, показываем прошлый
      this._watchProgress();
      this._loadSaved();
      this._load(true);
      return;
    }
    this._syncMenu();
    this._refreshLit();
  }

  set narrow(value) {
    this._narrow = value;
    this._syncMenu();
  }

  connectedCallback() {
    // Ушли с панели и вернулись «назад»: элемент Home Assistant пересоздаёт, а
    // наша запись в истории цела. Восстанавливаем по ней, что было открыто, —
    // иначе на экране список, в истории карточка, и «назад» тратится впустую.
    const card = history.state && history.state.ymCard;
    this._histCard = Boolean(card);
    if (card) {
      this._selected = card.device || null;
      this._room = card.room || null;
      this._backRoom = card.fromRoom || null;
    }
    if (!this.shadowRoot.firstChild) this._render();
    else if (card) this._render();
    window.addEventListener("popstate", this._onPop);
    if (this._loaded) this._watchProgress();
  }

  disconnectedCallback() {
    window.removeEventListener("popstate", this._onPop);
    if (this._unsubProgress) {
      this._unsubProgress.then((unsub) => unsub()).catch(() => {});
      this._unsubProgress = null;
    }
    clearTimeout(this._toastTimer);
    // Свою запись здесь не снимаем: history.back() посреди чужой навигации
    // отменил бы переход, который пользователь только что сделал.
  }

  /* ---------------------------------------------------------------- история */

  /** Открытая карточка = одна запись в истории браузера.

      Адрес не меняем: роутер Home Assistant сверяет путь и запись с тем же путём
      пропускает мимо себя — так же устроены его собственные диалоги. Ключи dialog,
      opensDialog и dialogData заняты его диалог-менеджером, поэтому своё кладём
      под ymCard; from — то, чем он отличает «есть куда вернуться» от «некуда». */
  _openCard() {
    const card = this._room
      ? { room: this._room }
      : { device: this._selected, fromRoom: this._backRoom || null };
    // Вторая проверка — на случай, когда крестик уже отправил history.back(), а
    // ответ ещё не пришёл: запись пока наша, и второй класть нельзя.
    if (this._histCard || (history.state && history.state.ymCard)) {
      // карточка сменилась — правим свою запись, второй не кладём
      if (history.state && history.state.ymCard)
        history.replaceState({ ...history.state, ymCard: card }, "");
      this._histCard = true;
      return;
    }
    history.pushState({ from: location.pathname, ymCard: card }, "");
    this._histCard = true;
  }

  /** Закрытие не кнопкой «назад»: крестик, смена дома, удаление устройства. */
  _closeCard() {
    this._selected = null;
    this._room = null;
    this._backRoom = null;
    this._message = null;
    this._dropCardHistory();
  }

  _dropCardHistory() {
    if (!this._histCard) return;
    this._histCard = false; // метку снимаем до back(): свой же popstate тогда ничего не делает
    // Снимаем только свою запись и только пока панель на экране: наверху может
    // лежать чужая (диалог HA поверх панели), а уйти с панели человек мог сам.
    // Оставшаяся под чужой записью наша — не беда: вернувшись на неё, панель
    // поднимет карточку из состояния, а _dropGoneCard закроет, если та мертва.
    if (this.isConnected && history.state && history.state.ymCard) history.back();
  }

  /** Карточка открыта, а устройства или комнаты уже нет: их могли удалить в
      приложении Яндекса, пока карточка висела. Запись снимаем здесь, иначе
      «назад» потратится на экран, которого не видно. */
  _dropGoneCard() {
    if (!this._data) return;
    if (this._selected) {
      const device = this._device(this._selected);
      // тот же тест, что и в _renderDevicePanel: карточка из чужого дома не показывается
      if (!device || !this._inHouse(device)) this._closeCard();
      return;
    }
    if (this._room && !this._houseDevices.some((device) => device.room === this._room))
      this._closeCard();
  }

  /** «Назад». Чужую запись не трогаем — это уход с панели, им занимается HA. */
  _onPop() {
    // Приземлились на свою же запись — значит закрывали не карточку. Так Home
    // Assistant снимает свои диалоги: он тоже делает history.back(), и без этой
    // проверки его крестик схлопывал бы заодно и нашу карточку. Заодно сюда
    // приходит кнопка «вперёд» — возвращаем то, что в записи и записано.
    // До HA 2025.2 его диалог затирал чужое состояние целиком, поэтому там
    // закрытие диалога заодно закроет и карточку — неприятно, но не страшно.
    if (history.state && history.state.ymCard) {
      const card = history.state.ymCard;
      const device = card.device || null;
      const room = card.room || null;
      this._histCard = true;
      this._backRoom = card.fromRoom || null;
      if (device !== this._selected || room !== this._room) {
        this._selected = device;
        this._room = room;
        this._dropGoneCard(); // пока запись лежала, устройство могли удалить
        this._render();
      }
      return;
    }
    if (!this._histCard) return; // ушли с чужой записи — это уход с панели
    this._histCard = false;
    this._message = null;
    if (this._backRoom) {
      // в устройство провалились из карточки комнаты: возвращаемся в неё, и под
      // ней снова нужна запись, иначе следующий «назад» уйдёт мимо списка
      this._selected = null;
      this._room = this._backRoom;
      this._backRoom = null;
      this._openCard();
    } else {
      this._selected = null;
      this._room = null;
    }
    this._render();
  }

  /* ------------------------------------------------------------- транспорт */

  async _call(type, payload = {}) {
    return this._hass.connection.sendMessagePromise({ type, ...payload });
  }

  /** Можно ли показать ответ запроса номер seq.

      Нельзя, если на экране уже ответ более позднего: свежий список, запрошенный
      до переименования, приходит после ответа на него и откатил бы имя назад. */
  _take(seq) {
    if (seq < this._shown) return false;
    this._shown = seq;
    return true;
  }

  /** Ход сборки списка. В большом доме первая сборка идёт минутами: Яндекс
      отдаёт настройки каждого устройства отдельно, и видно должно быть, что
      работа идёт, а не зависла. */
  _watchProgress() {
    if (this._unsubProgress || !this._hass) return;
    this._unsubProgress = this._hass.connection.subscribeMessage(
      (state) => {
        this._progress = state || null;
        this._renderStatus();
        if (!this._data && !this._error) this._renderList();
      },
      { type: "yandex_menu/progress" }
    );
    const mine = this._unsubProgress;
    mine.catch(() => {
      // без прогресса панель работает как раньше
      if (this._unsubProgress === mine) this._unsubProgress = null;
    });
  }

  /** «около 3 минут» по оценке сервера. */
  _leftText(seconds) {
    if (seconds === null || seconds === undefined) return "";
    if (seconds < 15) return "ещё несколько секунд";
    if (seconds < 60) return "осталось меньше минуты";
    if (seconds < 90) return "осталось около минуты";
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) return `осталось около ${minutes} ${this._plural(minutes, "минуты", "минут", "минут")}`;
    const hours = Math.round(minutes / 60);
    return `осталось около ${hours} ${this._plural(hours, "часа", "часов", "часов")}`;
  }

  /** «Читаю дом «Дача»: 124 из 380» — или null, когда читать по одному нечего. */
  _progressText() {
    const state = this._progress;
    if (!state || !state.total) return null;
    const done = Math.min(state.done, state.total);
    const where = state.house ? `дом «${state.house}»` : "Яндекс-дом";
    return { what: `Читаю ${where}: ${done} из ${state.total}`, left: this._leftText(state.left), done, total: state.total };
  }

  /** Список, прочитанный в прошлый раз, — Home Assistant отдаёт его сразу. */
  async _loadSaved() {
    const seq = ++this._seq;
    let saved = null;
    try {
      saved = await this._call("yandex_menu/list_saved");
    } catch (err) {
      return; // не беда: свежий список уже в пути
    }
    if (!saved || !this._take(seq)) return;
    this._data = saved;
    this._savedAt = saved.saved_at || null;
    this._syncHouse();
    this._dropGoneCard();
    this._render();
  }

  async _load(force = false) {
    const seq = ++this._seq;
    this._loading += 1;
    this._renderStatus();
    try {
      const data = await this._call("yandex_menu/list", { force });
      if (this._take(seq)) {
        this._data = data;
        this._savedAt = null;
        this._error = null;
        this._syncHouse();
        this._dropGoneCard();
      }
    } catch (err) {
      // На экране список новее этого запроса — ошибка к нему уже не относится.
      // Иначе она видна: без списка — во весь экран, при старом — значком в шапке.
      if (seq >= this._shown) this._error = err && err.message ? err.message : String(err);
    } finally {
      this._loading -= 1;
    }
    this._render();
  }

  async _act(type, payload, successText) {
    const seq = ++this._seq;
    this._busy = true;
    this._render();
    try {
      const data = await this._call(type, payload);
      if (this._take(seq)) {
        this._data = data;
        this._savedAt = null;
        this._error = null;
      }
      this._syncHouse();
      this._dropGoneCard();
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

  get _houses() {
    return (this._data && this._data.households) || [];
  }

  /** Открытый дом. null — дом один, делить нечего, и панель выглядит как раньше. */
  get _houseId() {
    const houses = this._houses;
    if (houses.length < 2) return null;
    const open =
      houses.find((house) => house.id === this._house) ||
      houses.find((house) => house.current) ||
      houses[0];
    return open.id;
  }

  /** Закрепляем открытый дом после каждой загрузки.

      Иначе смена основного дома в приложении Яндекса молча перекинула бы панель
      в другой дом, а открытая карточка проверяла бы фразы чужой Станцией. */
  _syncHouse() {
    const houses = this._houses;
    if (houses.length < 2 || houses.some((house) => house.id === this._house)) return;
    if (this._house && (this._selected || this._room)) {
      // дом, который был открыт, пропал — его карточки больше не к месту
      this._closeCard();
    }
    this._house = (houses.find((house) => house.current) || houses[0]).id;
  }

  _inHouse(item, houseId = this._houseId) {
    return !houseId || !item.household_id || item.household_id === houseId;
  }

  /** Устройства открытого дома. */
  get _houseDevices() {
    return this._devices.filter((device) => this._inHouse(device));
  }

  _openHouse(id) {
    if (id === this._houseId) return;
    this._house = id;
    this._closeCard(); // карточка была из прежнего дома — и запись под ней тоже
    try {
      localStorage.setItem(HOUSE_KEY, id);
    } catch (err) {
      // без localStorage выбор проживёт до перезагрузки страницы
    }
    this._render();
    const list = this.shadowRoot.getElementById("list");
    if (list) list.scrollTop = 0;
  }

  /** Блок «Отдать в Алису» — там, куда навык Home Assistant кладёт устройства. */
  _offerHere(houseId = this._houseId) {
    if (!houseId) return true;
    const withHa = new Set(
      this._devices.filter((device) => device.from_ha).map((device) => device.household_id)
    );
    if (withHa.size) return withHa.has(houseId);
    const current = this._houses.find((house) => house.current) || this._houses[0];
    return current.id === houseId;
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
    return device.role.endsWith("main") ? "основной свет" : "дополнительный свет";
  }

  _roleShort(device) {
    if (!device.role) return "";
    return device.role.endsWith("main") ? "осн" : "доп";
  }

  _plural(count, one, few, many) {
    const tens = count % 100;
    const units = count % 10;
    if (units === 1 && tens !== 11) return one;
    if (units >= 2 && units <= 4 && (tens < 12 || tens > 14)) return few;
    return many;
  }

  _skillIcons(device) {
    const order = Object.keys(SKILL_ICONS);
    const rank = (kind) => (order.includes(kind) ? order.indexOf(kind) : order.length);
    const kinds = [...(device.skills || [])].sort((left, right) => rank(left) - rank(right));
    const fits = kinds.length > SKILLS_SHOWN ? SKILLS_SHOWN - 1 : kinds.length;
    let html = kinds
      .slice(0, fits)
      .map((kind) => {
        const [title, path] = SKILL_ICONS[kind] || SKILL_FALLBACK;
        return `<span title="${this._esc(title)}">${this._svg(path, 16)}</span>`;
      })
      .join("");
    if (kinds.length > fits) {
      const rest = kinds.slice(fits).map((kind) => (SKILL_ICONS[kind] || SKILL_FALLBACK)[0]);
      html += `<span class="more" title="${this._esc(rest.join(", "))}">+${kinds.length - fits}</span>`;
    }
    return html;
  }

  /* ------------------------------------------------------ фразы для Алисы */

  /** Строки «что сказать» для устройства: подпись и чипы [слово, фраза]. */
  _deviceWords(device, skills) {
    const name = String(device.names[0] || "").toLowerCase();
    const room = device.room ? device.room.toLowerCase() : "";
    const type = device.current_type || device.type || "";
    const external = device.external_id || "";
    const fill = (template, value = "") =>
      template.replace("{name}", name).replace("{room}", room).replace("{value}", value);
    const chips = (pairs) => pairs.map(([word, template]) => [word, fill(template)]);
    const values = (items, template) =>
      items.map((item) => {
        const word = String(item).toLowerCase();
        return [word, fill(template, word)];
      });
    const rows = [];

    for (const cap of skills.capabilities || []) {
      if (cap.kind === "on_off") {
        let pairs = [["включи", "включи {name}"], ["выключи", "выключи {name}"]];
        if (/^(script|scene|button)\./.test(external)) pairs = [["включи", "включи {name}"]];
        else if (/openable|curtain/.test(type))
          pairs = [["открой", "открой {name}"], ["закрой", "закрой {name}"]];
        rows.push({ id: "on_off", label: "Включение", chips: chips(pairs) });
      } else if (cap.kind === "range") {
        const known = RANGE_WORDS[cap.instance];
        if (known) rows.push({ id: `range-${cap.instance}`, label: known[0], chips: chips(known[1]) });
      } else if (cap.kind === "color_setting") {
        const palette = cap.palette || [];
        if (cap.color && palette.length)
          rows.push({ id: "color", label: "Цвет", chips: values(palette, "включи {value} цвет на {name}") });
        if (cap.white)
          rows.push({
            id: "white",
            label: "Оттенок белого",
            chips: chips([["теплее", "сделай {name} теплее"], ["холоднее", "сделай {name} холоднее"]]),
          });
        const scenes = cap.scenes || [];
        if (scenes.length)
          rows.push({ id: "scenes", label: "Режимы света", chips: values(scenes, "включи режим {value} на {name}") });
      } else if (cap.kind === "mode") {
        const modes = cap.modes || [];
        if (!modes.length) continue;
        const [label, template] = MODE_WORDS[cap.instance] || [
          cap.name ? cap.name[0].toUpperCase() + cap.name.slice(1) : "Режим",
          "включи режим {value} на {name}",
        ];
        rows.push({ id: `mode-${cap.instance}`, label, chips: values(modes, template) });
      } else if (cap.kind === "toggle") {
        const known = TOGGLE_WORDS[cap.instance];
        const what = cap.name || cap.instance;
        const [label, pairs] = known || [
          what[0].toUpperCase() + what.slice(1),
          [[`включи ${what}`, `включи ${what} на {name}`], [`выключи ${what}`, `выключи ${what} на {name}`]],
        ];
        rows.push({ id: `toggle-${cap.instance}`, label, chips: chips(pairs) });
      } else if (cap.kind === "video_stream") {
        rows.push({ id: "video", label: "Видео", chips: chips([["покажи", "покажи {name}"]]) });
      }
    }

    const asks = [];
    const events = [];
    for (const prop of skills.properties || []) {
      if (prop.kind === "float") {
        const [question, aboutRoom] = ASK_WORDS[prop.instance] || [`какой ${prop.name || prop.instance}`, false];
        const phrase = aboutRoom && room ? `${question} в ${room}` : `${question} у ${name}`;
        if (!asks.some(([word]) => word === question)) asks.push([question, phrase]);
      } else if (prop.kind === "event") {
        for (const event of prop.events || []) if (!events.includes(event)) events.push(event);
      }
    }
    if (asks.length) rows.push({ id: "ask", label: "Спросить", chips: asks });
    if (events.length) rows.push({ id: "events", label: "События для сценариев", info: events });

    const order = ["on_off", "range-brightness", "color", "white", "scenes", "mode", "range", "toggle", "video", "ask", "events"];
    const rank = (row) => {
      const index = order.findIndex((prefix) => row.id === prefix || row.id.startsWith(`${prefix}-`));
      return index === -1 ? order.length : index;
    };
    return rows.sort((left, right) => rank(left) - rank(right));
  }

  /** Команды на комнату: свет по ролям и весь дом. */
  _roomWords(room, devices) {
    const where = room.toLowerCase();
    const lights = devices.filter((device) => /light/.test(device.current_type || device.type || ""));
    const main = lights.filter((device) => !device.role || device.role.endsWith("main"));
    const rows = [];
    if (lights.length) {
      rows.push({
        id: "room-light",
        label: "Свет в комнате",
        chips: [
          ["включи свет", `включи свет в ${where}`],
          ["выключи свет", `выключи свет в ${where}`],
        ],
      });
    }
    if (main.some((device) => (device.skills || []).includes("brightness"))) {
      rows.push({
        id: "room-brightness",
        label: "Яркость в комнате",
        chips: [
          ["ярче", `сделай свет в ${where} ярче`],
          ["темнее", `сделай свет в ${where} темнее`],
        ],
      });
    }
    rows.push({
      id: "house-light",
      label: "Во всём доме",
      chips: [
        ["выключи весь свет", "выключи весь свет"],
        ["включи весь свет", "включи весь свет"],
      ],
    });
    return rows;
  }

  /** Станции открытого дома: Станция выполняет фразу у себя дома, чужой дом не тронет. */
  get _stations() {
    return ((this._data && this._data.stations) || []).filter((item) => this._inHouse(item));
  }

  _stationFor(room) {
    const stations = this._stations;
    if (!stations.length) return null;
    const chosen = this._stationByHouse[this._houseId || ""] || this._stationByHouse[""];
    return (
      stations.find((item) => item.entity_id === chosen) ||
      stations.find((item) => room && item.room === room) ||
      stations[0]
    );
  }

  _stationPicker(room) {
    const stations = this._stations;
    const current = this._stationFor(room);
    if (!current)
      return `<div class="msg info">${
        this._houseId
          ? "Чтобы проверять фразы, нужна Яндекс.Станция из этого дома в Home Assistant."
          : "Чтобы проверять фразы, нужна Яндекс.Станция в Home Assistant."
      }</div>`;
    if (stations.length === 1)
      return `<div class="station">Проверка через ${this._esc(current.name)}</div>`;
    const options = stations
      .map(
        (item) =>
          `<option value="${this._esc(item.entity_id)}"${
            item.entity_id === current.entity_id ? " selected" : ""
          }>${this._esc(item.name)}</option>`
      )
      .join("");
    return `<label class="station">Проверять через <select class="field" id="station">${options}</select></label>`;
  }

  _chipsHtml(key, pairs) {
    const picked = this._picked[key] || 0;
    const collapse = pairs.length > CHIPS_COLLAPSED + 2 && !this._expanded[key];
    const shown = collapse ? pairs.slice(0, CHIPS_COLLAPSED) : pairs;
    let html = shown
      .map(
        ([word], index) =>
          `<button class="chip pick${index === picked ? " on" : ""}" data-pick="${this._esc(
            key
          )}" data-index="${index}">${this._esc(word)}</button>`
      )
      .join("");
    if (collapse)
      html += `<button class="chip more" data-expand="${this._esc(key)}">ещё ${
        pairs.length - CHIPS_COLLAPSED
      }</button>`;
    return html;
  }

  /** Раздел «Что сказать Алисе»: подсказка, выбор станции и строки чипов. */
  _saySection(owner, rows, room) {
    const station = this._stationFor(room);
    const body = rows
      .map((row) => {
        if (row.info)
          return `<div class="say-row"><div class="say-label">${this._esc(row.label)}</div>
            <div class="chips">${row.info
              .map((word) => `<span class="chip">${this._esc(word)}</span>`)
              .join("")}</div></div>`;
        const key = `${owner}|${row.id}`;
        this._sayRows[key] = row.chips;
        return `<div class="say-row">
          <div class="say-label">${this._esc(row.label)}</div>
          <div class="chips">${this._chipsHtml(key, row.chips)}</div>
          ${
            station
              ? `<button class="play" data-say="${this._esc(key)}" title="Проверить через Станцию">${this._svg(
                  ICONS.play,
                  18
                )}</button>`
              : ""
          }
        </div>`;
      })
      .join("");
    const count = rows.filter((row) => !row.info).length;
    return `<div class="section" id="skills">
      <div class="section-head"><h4>Что сказать Алисе</h4>${
        count ? `<span class="counter">${count} ${this._plural(count, "умение", "умения", "умений")}</span>` : ""
      }</div>
      <p class="hint">Нажмите на слово, чтобы выбрать его. Кнопка ▶ отправит фразу на Станцию, и устройство сработает по-настоящему.</p>
      ${this._stationPicker(room)}
      <div class="say">${body}</div>
    </div>`;
  }

  _deviceSkillsSection(device) {
    if (/smart_speaker/.test(device.current_type || device.type || ""))
      return `<div class="section" id="skills"><div class="section-head"><h4>Что сказать Алисе</h4></div>
        <p class="hint">Это колонка с Алисой. Её команды общие для Алисы и к умному дому не относятся.</p></div>`;
    const rows = this._deviceWords(device, device.abilities || {});
    if (!rows.length)
      return `<div class="section" id="skills"><div class="section-head"><h4>Что сказать Алисе</h4></div>
        <p class="hint">Яндекс не сообщил ни одного умения этого устройства.</p></div>`;
    return this._saySection(device.id, rows, device.room);
  }

  async _say(key) {
    const pairs = this._sayRows[key];
    if (!pairs) return;
    const room = key.startsWith("sc|")
      ? null
      : this._room || (this._device(this._selected) || {}).room || null;
    const station = this._stationFor(room);
    if (!station) return;
    const pair = pairs[this._picked[key] || 0] || pairs[0];
    const text = prompt(
      `${station.name} выполнит эту фразу по-настоящему, будто её сказали вслух.\nФразу можно поправить:`,
      pair[1]
    );
    if (text === null || !text.trim()) return;
    try {
      await this._call("yandex_menu/say", { entity_id: station.entity_id, text: text.trim() });
      this._toast(`${station.name}: ${text.trim()}`);
    } catch (err) {
      this._toast(err && err.message ? err.message : String(err));
    }
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

    // Алиса путает имена только внутри одного дома
    for (const other of this._devices) {
      if (other.id === device.id || !this._inHouse(other, device.household_id)) continue;
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
          <button class="icon-only" id="menu" title="Меню" hidden>${this._svg(
            "M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z"
          )}</button>
          <h1>Яндекс меню</h1>
          <button class="icon-only sync" id="sync" hidden></button>
          <span class="sync-note" id="syncnote" hidden></span>
          <span class="account" id="account" title="Аккаунт Яндекса. Сменить: настройки интеграции" hidden></span>
          <nav class="houses" id="houses" aria-label="Дома" hidden></nav>
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
    // Аккаунт показываем, только когда их несколько, — иначе это лишний шум
    const account = root.getElementById("account");
    const info = this._data && this._data.account;
    if (account) {
      account.hidden = !(info && info.several && info.name);
      account.textContent = info && info.name ? info.name : "";
    }
    this._renderHouses();
    this._renderStatus();
    this._syncMenu();
    const layout = root.querySelector(".layout");
    if (layout) layout.classList.toggle("busy", this._busy);
  }

  /** Кнопка «меню» нужна, только когда боковое меню Home Assistant не на экране:
      на телефоне и когда его спрятали совсем. На широком экране она повторяла бы
      кнопку в самом меню — по этому же правилу Home Assistant показывает свою.
      Кнопка рисуется скрытой, поэтому до первого hass она не мелькает. */
  _syncMenu() {
    const button = this.shadowRoot.getElementById("menu");
    if (!button) return;
    const hass = this._hass;
    const needed = this._narrow || (hass && hass.dockedSidebar === "always_hidden");
    button.hidden = !needed || Boolean(hass && hass.kioskMode);
  }

  /** Значок в шапке: крутится, пока список обновляется, и желтеет, если не вышло.
      Жёлтый нажимается — это повтор, в том числе когда списка нет совсем. */
  _renderStatus() {
    const sync = this.shadowRoot.getElementById("sync");
    if (!sync) return;
    const loading = this._loading > 0;
    const failed = !loading && Boolean(this._error);
    const shown = this._savedAt ? ` Сейчас показан сохранённый список — ${this._when(this._savedAt)}.` : "";
    // «Обновить список» в большом доме тоже идёт минутами — счётчик нужен и там
    const progress = loading || this._busy ? this._progressText() : null;
    let title = "";
    if (progress) title = `${progress.what}, ${progress.left}.${shown}`;
    else if (loading) title = `Обновляю список.${shown}`;
    else if (failed) title = `Список не обновился: ${this._error}.${shown} Нажмите, чтобы попробовать ещё раз.`;
    sync.hidden = !title;
    sync.disabled = loading || Boolean(progress);
    sync.title = title;
    sync.setAttribute("aria-label", title);
    sync.classList.toggle("spin", loading || Boolean(progress));
    sync.classList.toggle("warn", failed);
    // Поверх списка — только счётчик: подробности в подсказке значка
    const note = this.shadowRoot.getElementById("syncnote");
    if (note) {
      const text = progress && this._data ? `${progress.done} из ${progress.total}` : "";
      note.hidden = !text;
      if (note.textContent !== text) note.textContent = text;
    }
    // Значок меняем, только когда он другой: перерисовка сбила бы вращение
    const icon = failed ? "syncAlert" : "sync";
    if (sync.dataset.icon !== icon) {
      sync.dataset.icon = icon;
      sync.innerHTML = this._svg(ICONS[icon], 20);
    }
  }

  _when(seconds) {
    return new Date(seconds * 1000).toLocaleString("ru-RU", {
      day: "numeric",
      month: "long",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  /** Вкладки домов — только когда на аккаунте их несколько. */
  _renderHouses() {
    const host = this.shadowRoot.getElementById("houses");
    if (!host) return;
    const houseId = this._houseId;
    host.hidden = !houseId;
    if (!houseId) {
      host.innerHTML = "";
      return;
    }
    host.innerHTML = this._houses
      .map((house) => {
        const count = this._devices.filter((device) => device.household_id === house.id).length;
        const title = house.shared ? "Дом, которым с вами поделились" : "";
        return `<button data-house="${this._esc(house.id)}" class="${house.id === houseId ? "on" : ""}"${
          title ? ` title="${title}"` : ""
        } aria-pressed="${house.id === houseId}">${this._esc(house.name)}${
          house.shared ? " · общий" : ""
        }<span class="n">${count}</span></button>`;
      })
      .join("");
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

  _loaderHtml() {
    const progress = this._progressText();
    if (!progress) return `<div class="loader"><div class="what">Читаю Яндекс-дом…</div></div>`;
    const percent = Math.round((progress.done / progress.total) * 100);
    // Предупреждаем, только когда ждать и правда долго: 30 ламп читаются за секунды
    const hint =
      progress.total > 100
        ? `<div class="hint">Устройств много, а Яндекс отдаёт настройки каждого по отдельности,
           поэтому первая загрузка идёт долго. Дальше панель будет открываться сразу.</div>`
        : "";
    return `<div class="loader" role="status">
      <div class="what">${this._esc(progress.what)}</div>
      <div class="left">${this._esc(progress.left)}</div>
      <div class="bar"><i style="width:${percent}%"></i></div>
      ${hint}
    </div>`;
  }

  _renderList() {
    const host = this.shadowRoot.getElementById("list");
    if (!host) return;
    // Список переписывается целиком, поэтому прокрутку держим руками: закрыв
    // карточку, человек должен оказаться там, где нажал на лампу. А вот при
    // смене дома или поиска список уже другой — его правильно показать сверху.
    const shape = `${this._houseId || ""}|${this._query}`;
    const keepScroll = shape === this._listShape ? host.scrollTop : 0;

    if (!this._data) {
      host.innerHTML = this._error
        ? `<div class="fatal">${this._esc(this._error)}</div>`
        : this._loaderHtml();
      return;
    }

    const query = this._query.trim().toLowerCase();
    const match = (device) =>
      !query ||
      (device.names.join(" ") + " " + (device.external_id || "")).toLowerCase().includes(query);

    const houseId = this._houseId;
    const devices = this._houseDevices;
    const rooms = [];
    const seen = new Set();
    for (const device of devices) {
      const room = device.room || "Без комнаты";
      if (!seen.has(room)) {
        seen.add(room);
        rooms.push(room);
      }
    }

    let html = "";
    if (query && houseId) {
      // поиск идёт по открытому дому, но находки в других домах не прячем
      const elsewhere = this._houses
        .filter((house) => house.id !== houseId)
        .map((house) => [
          house,
          this._devices.filter((device) => device.household_id === house.id && match(device)).length,
        ])
        .filter(([, count]) => count);
      if (elsewhere.length)
        html += `<div class="elsewhere">Нашлось и в других домах:${elsewhere
          .map(
            ([house, count]) =>
              `<button class="chip go" data-house="${this._esc(house.id)}">${this._esc(house.name)} · ${count}</button>`
          )
          .join("")}</div>`;
    }
    if (!devices.length && houseId && !query) {
      const house = this._houses.find((item) => item.id === houseId);
      html += `<div class="empty">В доме «${this._esc(house.name)}» пока нет устройств.</div>`;
    }
    for (const room of rooms) {
      const items = devices.filter(
        (device) => (device.room || "Без комнаты") === room && match(device)
      );
      if (!items.length) continue;
      const roomButton =
        room === "Без комнаты"
          ? ""
          : `<button class="room-cmd${this._room === room ? " on" : ""}" data-room="${this._esc(
              room
            )}" title="Команды на всю комнату">${this._svg(ICONS.voice, 14)}команды</button>`;
      html += `<section><div class="room-head"><h2>${this._esc(room)}</h2><span class="count">${
        items.length
      }</span>${roomButton}</div><div class="card">`;
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
          <span class="meta">
            <span class="skills">${this._skillIcons(device)}</span>
            <span class="role" title="${this._roleWord(device)}">${
              this._roleShort(device) ? `<b>${this._roleShort(device)}</b>` : ""
            }</span>
          </span>
        </button>`;
      }
      html += `</div></section>`;
    }

    const scenarios = (this._data.scenarios || []).filter(
      (item) =>
        (!houseId || !(item.households || []).length || item.households.includes(houseId)) &&
        (!query || (item.name + " " + item.phrases.join(" ")).toLowerCase().includes(query))
    );
    if (scenarios.length) {
      const station = this._stationFor(null);
      html += `<section><div class="room-head"><h2>Сценарии</h2><span class="count">${scenarios.length}</span></div><div class="card">`;
      for (const item of scenarios) {
        const key = `sc|${item.id}`;
        const pairs = item.phrases.map((phrase) => [phrase, phrase]);
        this._sayRows[key] = pairs;
        html += `<div class="row scenario">
          <span class="avatar">${this._svg(ICONS.scenario, 18)}</span>
          <span><span class="title">${this._esc(item.name)}</span>${
            item.active === false ? `<br><span class="entity">выключен</span>` : ""
          }</span>
          <span class="chips">${
            pairs.length
              ? this._chipsHtml(key, pairs)
              : `<span class="role">запускается не голосом</span>`
          }</span>
          <span class="meta">${
            pairs.length && station
              ? `<button class="play" data-say="${this._esc(key)}" title="Проверить через Станцию">${this._svg(
                  ICONS.play,
                  18
                )}</button>`
              : ""
          }</span>
        </div>`;
      }
      html += `</div></section>`;
    }

    const offer = this._offerHere();
    const matching = (this._data.unexposed || []).filter(
      (item) => !query || (item.name + " " + item.entity_id).toLowerCase().includes(query)
    );
    const unexposed = offer ? matching : [];
    // Сущности Home Assistant приезжают в один дом — тот, где живёт навык. В остальных
    // домах раздел просто пропадал бы, и было бы непонятно, куда за ним идти.
    const elsewhere = offer || !matching.length ? null : this._houses.find((house) => this._offerHere(house.id));
    if (elsewhere && query)
      html += `<div class="elsewhere">Отдать в Алису из Home Assistant можно в доме:<button class="chip go" data-house="${this._esc(
        elsewhere.id
      )}">${this._esc(elsewhere.name)} · ${matching.length}</button></div>`;
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
    } else if (!query && elsewhere) {
      // тот же заголовок, что и в доме, где раздел работает: иначе строка висит без подписи
      html += `<section><div class="room-head"><h2>Отдать в Алису</h2></div><div class="card"><div class="empty">
        Сущности Home Assistant приезжают в дом «${this._esc(elsewhere.name)}» — откройте его, чтобы отдать.
        <div class="elsewhere" style="margin-top:10px;justify-content:center"><button class="chip go" data-house="${this._esc(
          elsewhere.id
        )}">${this._esc(elsewhere.name)} · ${matching.length}</button></div>
      </div></div></section>`;
    } else if (!query && offer) {
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
    host.scrollTop = keepScroll;
    this._listShape = shape;
  }

  _renderPanel() {
    const host = this.shadowRoot.getElementById("panel");
    if (!host) return;
    // Карточку восстановили из истории, а список ещё в пути: Яндекс отвечает
    // секунды. Без заглушки человек видел бы пустой экран и не понимал, что
    // «назад» ему закрывать.
    if (!this._data && (this._selected || this._room)) {
      if (this._error) {
        // список не пришёл вовсе — ошибку видно в самом списке, карточке нечего показать
        host.hidden = true;
        host.innerHTML = "";
        host.dataset.owner = "";
        return;
      }
      host.hidden = false;
      host.dataset.owner = "";
      host.innerHTML = `
        <div class="panel-head">
          <div>
            <h3>Читаю Яндекс-дом…</h3>
            <div class="entity">карточка откроется, как придёт список</div>
          </div>
          <button class="icon-only" id="close" title="Закрыть" style="margin-left:auto">${this._svg(
            "M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z",
            20
          )}</button>
        </div>`;
      return;
    }
    // Перерисовка той же карточки не должна сбрасывать прокрутку
    const owner = this._room ? `room:${this._room}` : this._selected || "";
    const body = host.querySelector(".panel-body");
    const keepScroll = body && host.dataset.owner === owner ? body.scrollTop : 0;
    host.dataset.owner = owner;

    if (this._room) this._renderRoomPanel(host);
    else this._renderDevicePanel(host);

    const fresh = host.querySelector(".panel-body");
    if (!fresh) return;
    fresh.scrollTop = keepScroll;
    const section = host.querySelector("#skills");
    if (this._scrollToSkills && section) {
      fresh.scrollTop += section.getBoundingClientRect().top - fresh.getBoundingClientRect().top;
    }
    this._scrollToSkills = false;
  }

  _renderRoomPanel(host) {
    const room = this._room;
    const devices = this._houseDevices.filter((device) => device.room === room);
    if (!devices.length) {
      // Список ещё не пришёл — карточку восстановили из истории, ей просто нечего
      // показать; закрывать её здесь значило бы стереть то, что человек открывал.
      if (this._data) {
        this._room = null;
        this._dropCardHistory(); // карточка ушла без клика — запись под ней тоже
      }
      host.hidden = true;
      host.innerHTML = "";
      return;
    }
    host.hidden = false;

    const lights = devices.filter((device) => /light/.test(device.current_type || device.type || ""));
    const main = lights.filter((device) => !device.role || device.role.endsWith("main"));
    const secondary = lights.filter((device) => device.role && device.role.endsWith("secondary"));
    const openChips = (items) =>
      items
        .map((device) => `<button class="chip" data-open="${device.id}">${this._esc(device.names[0])}</button>`)
        .join("");
    const who = lights.length
      ? `<p class="who">На «включи свет» откликнется основной свет:</p>
         <div class="chips">${
           main.length ? openChips(main) : `<span class="role">никто, у всего света роль «доп»</span>`
         }</div>
         ${
           secondary.length
             ? `<p class="who">Дополнительный включается только по имени:</p>
                <div class="chips">${openChips(secondary)}</div>`
             : ""
         }`
      : `<p class="hint">Света в этой комнате нет.</p>`;

    host.innerHTML = `
      <div class="panel-head">
        <span class="avatar">${this._svg(ICONS.voice, 20)}</span>
        <div>
          <h3>${this._esc(room)}</h3>
          <div class="entity">команды на комнату</div>
        </div>
        <button class="icon-only" id="close" title="Закрыть" style="margin-left:auto">${this._svg(
          "M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z",
          20
        )}</button>
      </div>
      <div class="panel-body">
        ${this._saySection(`room:${room}`, this._roomWords(room, devices), room)}
        <div class="section">
          <div class="section-head"><h4>Кто отзовётся</h4></div>
          ${who}
        </div>
      </div>
    `;
  }

  _renderDevicePanel(host) {
    const found = this._device(this._selected);
    // карточка из другого дома не показывается: Станции и комнаты в ней были бы чужие
    const device = found && this._inHouse(found) ? found : null;
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

    // Переносить можно только в комнату своего дома
    const rooms = (this._data.rooms || [])
      .filter((room) => this._inHouse(room, device.household_id))
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

        ${this._deviceSkillsSection(device)}

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

  /** Чипы и кнопка «проверить» — одинаково в списке и в карточке. */
  _handleSayClick(event) {
    const pick = event.target.closest("[data-pick]");
    if (pick) {
      const key = pick.getAttribute("data-pick");
      this._picked[key] = Number(pick.getAttribute("data-index"));
      for (const chip of pick.parentElement.querySelectorAll("[data-pick]"))
        chip.classList.toggle("on", chip === pick);
      return true;
    }
    const expand = event.target.closest("[data-expand]");
    if (expand) {
      const key = expand.getAttribute("data-expand");
      this._expanded[key] = true;
      expand.parentElement.innerHTML = this._chipsHtml(key, this._sayRows[key] || []);
      return true;
    }
    const say = event.target.closest("[data-say]");
    if (say) {
      this._say(say.getAttribute("data-say"));
      return true;
    }
    return false;
  }

  _bind() {
    const root = this.shadowRoot;

    root.getElementById("menu").addEventListener("click", () => {
      this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
    });

    root.getElementById("sync").addEventListener("click", () => {
      if (this._loading) return;
      // без списка ошибка и так во весь экран, а поверх списка её иначе не видно
      if (this._error && this._data) this._toast(`Список не обновился: ${this._error}. Пробую ещё раз`);
      this._load(true);
    });

    root.getElementById("houses").addEventListener("click", (event) => {
      const house = event.target.closest("[data-house]");
      if (house) this._openHouse(house.getAttribute("data-house"));
    });

    root.getElementById("q").addEventListener("input", (event) => {
      this._query = event.target.value;
      this._renderList();
    });

    root.getElementById("discover").addEventListener("click", () => {
      this._act("yandex_menu/discovery", {}, "Яндекс перечитывает список устройств");
    });

    root.getElementById("list").addEventListener("click", (event) => {
      if (this._handleSayClick(event)) return;
      const house = event.target.closest("[data-house]");
      if (house) {
        this._openHouse(house.getAttribute("data-house"));
        return;
      }
      const roomButton = event.target.closest("[data-room]");
      if (roomButton) {
        const room = roomButton.getAttribute("data-room");
        if (this._room === room) {
          this._closeCard(); // повторный клик закрывает — парных записей не копим
        } else {
          this._room = room;
          this._selected = null;
          this._backRoom = null;
          this._message = null;
          this._openCard();
        }
        this._render();
        return;
      }
      const row = event.target.closest("[data-id]");
      if (row) {
        this._selected = row.getAttribute("data-id");
        this._room = null;
        this._backRoom = null;
        this._scrollToSkills = Boolean(event.target.closest(".skills"));
        this._message = null;
        this._openCard();
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
      if (event.target.closest("#close")) {
        this._closeCard();
        this._render();
        return;
      }

      if (this._handleSayClick(event)) return;

      const open = event.target.closest("[data-open]");
      if (open) {
        this._backRoom = this._room; // пришли из комнаты — «назад» вернёт в неё
        this._selected = open.getAttribute("data-open");
        this._room = null;
        this._message = null;
        this._openCard();
        this._render();
        return;
      }

      const device = this._device(this._selected);
      if (!device) return;

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
        this._closeCard();
        this._act("yandex_menu/withdraw", { device_id: device.id });
        return;
      }

      if (event.target.closest("#delete")) {
        if (!confirm(`Удалить «${device.names[0]}» из Яндекс-дома? Это необратимо.`)) return;
        this._closeCard();
        this._act("yandex_menu/delete_device", { device_id: device.id }, "Устройство удалено");
      }
    });

    panel.addEventListener("change", (event) => {
      if (event.target.id === "station") {
        this._stationByHouse[this._houseId || ""] = event.target.value;
        try {
          localStorage.setItem(STATION_KEY, JSON.stringify(this._stationByHouse));
        } catch (err) {
          // без localStorage выбор проживёт до перезагрузки страницы
        }
        return;
      }
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
