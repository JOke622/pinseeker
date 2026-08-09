const dateInput = document.getElementById("date-input");
const holesInput = document.getElementById("holes-input");
const playersInput = document.getElementById("players-input");
const regionInput = document.getElementById("region-input");
const courseInput = document.getElementById("course-input");
const searchBtn = document.getElementById("search-btn");
const statusEl = document.getElementById("status");
const statusText = document.getElementById("status-text");
const statusSpinner = document.getElementById("status-spinner");
const updatedAtEl = document.getElementById("updated-at");
const unavailableToggle = document.getElementById("unavailable-toggle");
const unavailableDetail = document.getElementById("unavailable-detail");
const resultsBody = document.getElementById("results-body");
const resultsTable = document.getElementById("results-table");
const viewTimeBtn = document.getElementById("view-time-btn");
const viewCourseBtn = document.getElementById("view-course-btn");
const favoritesFilterBtn = document.getElementById("favorites-filter-btn");

const timeSlider = document.getElementById("time-slider");
const timeFill = document.getElementById("time-slider-fill");
const handleMin = document.getElementById("time-handle-min");
const handleMax = document.getElementById("time-handle-max");
const labelMin = document.getElementById("time-label-min");
const labelMax = document.getElementById("time-label-max");

const TIME_MIN = 300; // 5:00 AM, in minutes since midnight
const TIME_MAX = 1260; // 9:00 PM
const TIME_STEP = 15;

let timeRange = { min: TIME_MIN, max: TIME_MAX };
let lastResult = null; // most recent /api/tee-times response, re-filtered client-side
let lastUpdated = null; // Date the last successful fetch completed
let currentView = "time"; // "time" (flat, sorted by time) or "course" (grouped by course)
let favoritesOnly = false;

// course_id -> region, read off the Course dropdown's data-region attributes
// (courses.py is the source of truth; the template stamps it onto each option).
// Also stash each option's clean display name so favorite-star prefixes can be
// added/removed without accumulating.
const COURSE_REGIONS = {};
for (const opt of courseInput.options) {
  if (opt.value !== "all") {
    COURSE_REGIONS[opt.value] = opt.dataset.region;
    opt.dataset.name = opt.textContent;
  }
}

const FAVORITES_KEY = "pinseeker-favorite-courses";
let favoriteCourseIds = new Set();
try {
  favoriteCourseIds = new Set(JSON.parse(localStorage.getItem(FAVORITES_KEY) || "[]"));
} catch {
  favoriteCourseIds = new Set();
}

function isFavorite(courseId) {
  return favoriteCourseIds.has(courseId);
}

function updateCourseOptionLabels() {
  for (const opt of courseInput.options) {
    if (opt.value === "all") continue;
    const name = opt.dataset.name;
    opt.textContent = isFavorite(opt.value) ? `★ ${name}` : name;
  }
}

function toggleFavorite(courseId) {
  if (favoriteCourseIds.has(courseId)) {
    favoriteCourseIds.delete(courseId);
  } else {
    favoriteCourseIds.add(courseId);
  }
  localStorage.setItem(FAVORITES_KEY, JSON.stringify([...favoriteCourseIds]));
  updateCourseOptionLabels();
  applyFiltersAndRender();
}

function favoriteStarHtml(courseId) {
  const active = isFavorite(courseId);
  return `<button type="button" class="favorite-star${active ? " active" : ""}" data-course-id="${courseId}" aria-label="${active ? "Remove from" : "Add to"} favorites" aria-pressed="${active}">${active ? "★" : "☆"}</button>`;
}

updateCourseOptionLabels();

// Limits the Course dropdown to courses in the selected region. If the
// currently-selected course falls outside the new region, resets to "all".
function updateCourseOptions() {
  const selectedRegion = regionInput.value;
  let selectedIsHidden = false;
  for (const opt of courseInput.options) {
    if (opt.value === "all") continue;
    const matches = selectedRegion === "all" || opt.dataset.region === selectedRegion;
    opt.hidden = !matches;
    opt.disabled = !matches;
    if (opt.value === courseInput.value && !matches) selectedIsHidden = true;
  }
  if (selectedIsHidden) {
    courseInput.value = "all";
  }
}

function setStatus(text, isError) {
  statusText.textContent = text;
  statusEl.classList.toggle("error", !!isError);
}

function setLoading(isLoading) {
  statusSpinner.classList.toggle("active", isLoading);
}

function todayIso() {
  const d = new Date();
  return d.toISOString().slice(0, 10);
}

function formatMoney(value) {
  if (value === null || value === undefined || value === "") return "-";
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  return n === 0 ? "-" : `$${n.toFixed(0)}`;
}

function minutesToLabel(minutes) {
  const hour24 = Math.floor(minutes / 60);
  const minute = minutes % 60;
  const hour12 = hour24 % 12 || 12;
  const ampm = hour24 < 12 ? "AM" : "PM";
  return `${hour12}:${String(minute).padStart(2, "0")} ${ampm}`;
}

// sort_key is an ISO-ish "...THH:MM:SS..." string; read the clock time directly
// rather than going through Date parsing, which can shift on timezone-less strings.
function minutesFromSortKey(sortKey) {
  const match = /T(\d{2}):(\d{2})/.exec(sortKey || "");
  if (!match) return null;
  return parseInt(match[1], 10) * 60 + parseInt(match[2], 10);
}

function percentForMinutes(minutes) {
  return ((minutes - TIME_MIN) / (TIME_MAX - TIME_MIN)) * 100;
}

function minutesFromClientX(clientX) {
  const rect = timeSlider.getBoundingClientRect();
  const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
  const raw = TIME_MIN + ratio * (TIME_MAX - TIME_MIN);
  return Math.round(raw / TIME_STEP) * TIME_STEP;
}

function updateSliderUI() {
  const minPct = percentForMinutes(timeRange.min);
  const maxPct = percentForMinutes(timeRange.max);
  handleMin.style.left = `${minPct}%`;
  handleMax.style.left = `${maxPct}%`;
  timeFill.style.left = `${minPct}%`;
  timeFill.style.width = `${maxPct - minPct}%`;
  handleMin.setAttribute("aria-valuemin", TIME_MIN);
  handleMin.setAttribute("aria-valuemax", TIME_MAX);
  handleMin.setAttribute("aria-valuenow", timeRange.min);
  handleMax.setAttribute("aria-valuemin", TIME_MIN);
  handleMax.setAttribute("aria-valuemax", TIME_MAX);
  handleMax.setAttribute("aria-valuenow", timeRange.max);
  labelMin.textContent = minutesToLabel(timeRange.min);
  labelMax.textContent = minutesToLabel(timeRange.max);
}

function dragHandle(handleKey) {
  return function onPointerDown(e) {
    e.preventDefault();
    const handleEl = handleKey === "min" ? handleMin : handleMax;
    handleEl.setPointerCapture(e.pointerId);

    function onMove(ev) {
      const minutes = minutesFromClientX(ev.clientX);
      if (handleKey === "min") {
        timeRange.min = Math.min(minutes, timeRange.max);
      } else {
        timeRange.max = Math.max(minutes, timeRange.min);
      }
      updateSliderUI();
      applyFiltersAndRender();
    }
    function onUp() {
      handleEl.releasePointerCapture(e.pointerId);
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
    }
    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onUp);
  };
}

function nudgeHandle(handleKey) {
  return function onKeydown(e) {
    let delta = 0;
    if (e.key === "ArrowLeft" || e.key === "ArrowDown") delta = -TIME_STEP;
    else if (e.key === "ArrowRight" || e.key === "ArrowUp") delta = TIME_STEP;
    else return;
    e.preventDefault();
    if (handleKey === "min") {
      timeRange.min = Math.min(Math.max(TIME_MIN, timeRange.min + delta), timeRange.max);
    } else {
      timeRange.max = Math.max(Math.min(TIME_MAX, timeRange.max + delta), timeRange.min);
    }
    updateSliderUI();
    applyFiltersAndRender();
  };
}

handleMin.addEventListener("pointerdown", dragHandle("min"));
handleMax.addEventListener("pointerdown", dragHandle("max"));
handleMin.addEventListener("keydown", nudgeHandle("min"));
handleMax.addEventListener("keydown", nudgeHandle("max"));

// Clicking/tapping the track jumps the nearer handle to that point.
timeSlider.addEventListener("pointerdown", (e) => {
  if (e.target === handleMin || e.target === handleMax) return;
  const minutes = minutesFromClientX(e.clientX);
  const distMin = Math.abs(minutes - timeRange.min);
  const distMax = Math.abs(minutes - timeRange.max);
  if (distMin <= distMax) {
    timeRange.min = Math.min(minutes, timeRange.max);
  } else {
    timeRange.max = Math.max(minutes, timeRange.min);
  }
  updateSliderUI();
  applyFiltersAndRender();
});

// Prefer the price matching this tee time's own hole count (shown in the Holes
// column); fall back to whichever price is available if that one's missing.
function relevantPrice(tt) {
  if (tt.holes === 9) return tt.price_9 ?? tt.price_18;
  return tt.price_18 ?? tt.price_9;
}

function rowHtml(tt) {
  return `
    <td>${tt.display_time ?? ""}</td>
    <td>${favoriteStarHtml(tt.course_id)} ${tt.course_name ?? ""}</td>
    <td>${tt.holes ?? "-"}</td>
    <td>${tt.available_spots ?? "-"}</td>
    <td>${formatMoney(relevantPrice(tt))}</td>
    <td>${tt.booking_url ? `<a class="book-link" href="${tt.booking_url}" target="_blank" rel="noopener">Book</a>` : ""}</td>
  `;
}

function renderRows(teeTimes) {
  resultsBody.innerHTML = "";
  if (teeTimes.length === 0) {
    resultsBody.innerHTML = `<tr><td colspan="6">No tee times found for these filters.</td></tr>`;
    return;
  }

  for (const tt of teeTimes) {
    const tr = document.createElement("tr");
    tr.innerHTML = rowHtml(tt);
    resultsBody.appendChild(tr);
  }
}

// Which course groups are expanded in the "By Course" view. Collapsed by
// default; persists across re-renders (filter changes) within the session.
const expandedGroups = new Set();

// Same rows, grouped under a collapsible header per course (sorted
// alphabetically), each group internally still ordered by time. The Course
// column is hidden via the "grouped-by-course" class since the header labels it.
function renderGroupedRows(teeTimes) {
  resultsBody.innerHTML = "";
  if (teeTimes.length === 0) {
    resultsBody.innerHTML = `<tr><td colspan="6">No tee times found for these filters.</td></tr>`;
    return;
  }

  const groups = new Map();
  for (const tt of teeTimes) {
    const key = tt.course_name || "Unknown";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(tt);
  }

  const courseNames = [...groups.keys()].sort((a, b) => a.localeCompare(b));
  for (const courseName of courseNames) {
    const times = groups.get(courseName);
    times.sort((a, b) => (a.sort_key || "").localeCompare(b.sort_key || ""));
    const isExpanded = expandedGroups.has(courseName);
    const courseId = times[0].course_id;

    const headerRow = document.createElement("tr");
    headerRow.className = "group-header";
    headerRow.innerHTML = `
      <td colspan="6">
        <button type="button" class="group-toggle" aria-expanded="${isExpanded}">
          <span class="group-toggle-icon">${isExpanded ? "−" : "+"}</span>
          ${courseName} <span class="group-count">(${times.length})</span>
        </button>
        ${favoriteStarHtml(courseId)}
      </td>
    `;
    resultsBody.appendChild(headerRow);

    const rowEls = [];
    for (const tt of times) {
      const tr = document.createElement("tr");
      tr.className = "group-row";
      tr.hidden = !isExpanded;
      tr.innerHTML = rowHtml(tt);
      resultsBody.appendChild(tr);
      rowEls.push(tr);
    }

    const toggleBtn = headerRow.querySelector(".group-toggle");
    toggleBtn.addEventListener("click", () => {
      const nowExpanded = !expandedGroups.has(courseName);
      if (nowExpanded) {
        expandedGroups.add(courseName);
      } else {
        expandedGroups.delete(courseName);
      }
      toggleBtn.setAttribute("aria-expanded", String(nowExpanded));
      toggleBtn.querySelector(".group-toggle-icon").textContent = nowExpanded ? "−" : "+";
      for (const tr of rowEls) tr.hidden = !nowExpanded;
    });
  }
}

function applyFiltersAndRender() {
  if (!lastResult) return;

  const selectedCourse = courseInput.value;
  const selectedRegion = regionInput.value;
  let teeTimes = lastResult.tee_times || [];
  if (selectedCourse !== "all") {
    teeTimes = teeTimes.filter((tt) => tt.course_id === selectedCourse);
  }
  if (selectedRegion !== "all") {
    teeTimes = teeTimes.filter((tt) => COURSE_REGIONS[tt.course_id] === selectedRegion);
  }
  if (favoritesOnly) {
    teeTimes = teeTimes.filter((tt) => isFavorite(tt.course_id));
  }
  teeTimes = teeTimes.filter((tt) => {
    const minutes = minutesFromSortKey(tt.sort_key);
    return minutes === null || (minutes >= timeRange.min && minutes <= timeRange.max);
  });

  setStatus(`Showing ${teeTimes.length} tee times across ${lastResult.courses.length} course(s).`, false);

  const courseErrors = (lastResult.courses || []).filter((c) => c.error);
  if (courseErrors.length > 0) {
    unavailableToggle.hidden = false;
    unavailableToggle.textContent = `${courseErrors.length} course${courseErrors.length === 1 ? "" : "s"} unavailable`;
    unavailableDetail.innerHTML = courseErrors
      .map((c) => `<li>${c.course_name}</li>`)
      .join("");
  } else {
    unavailableToggle.hidden = true;
  }
  unavailableDetail.hidden = true;

  if (lastUpdated) {
    updatedAtEl.textContent = `Updated at ${lastUpdated.toLocaleTimeString()}`;
  }

  if (currentView === "course") {
    renderGroupedRows(teeTimes);
  } else {
    renderRows(teeTimes);
  }
}

function setView(view) {
  currentView = view;
  viewTimeBtn.classList.toggle("active", view === "time");
  viewCourseBtn.classList.toggle("active", view === "course");
  resultsTable.classList.toggle("grouped-by-course", view === "course");
  applyFiltersAndRender();
}

async function search() {
  setStatus("Searching...", false);
  setLoading(true);
  resultsBody.innerHTML = "";

  const params = new URLSearchParams({
    date: dateInput.value || todayIso(),
    holes: holesInput.value,
    players: playersInput.value,
  });

  try {
    const resp = await fetch(`/api/tee-times?${params.toString()}`);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || `Request failed (${resp.status})`);
    lastResult = data;
    lastUpdated = new Date();
  } catch (err) {
    setStatus(`Error: ${err.message}`, true);
    setLoading(false);
    return;
  }

  setLoading(false);
  applyFiltersAndRender();
}

dateInput.value = todayIso();
updateSliderUI();
updateCourseOptions();
searchBtn.addEventListener("click", search);
dateInput.addEventListener("change", search);
holesInput.addEventListener("change", search);
playersInput.addEventListener("change", search);
courseInput.addEventListener("change", applyFiltersAndRender);
regionInput.addEventListener("change", () => {
  updateCourseOptions();
  applyFiltersAndRender();
});
viewTimeBtn.addEventListener("click", () => setView("time"));
viewCourseBtn.addEventListener("click", () => setView("course"));
unavailableToggle.addEventListener("click", () => {
  unavailableDetail.hidden = !unavailableDetail.hidden;
});
favoritesFilterBtn.addEventListener("click", () => {
  favoritesOnly = !favoritesOnly;
  favoritesFilterBtn.classList.toggle("active", favoritesOnly);
  favoritesFilterBtn.setAttribute("aria-pressed", String(favoritesOnly));
  applyFiltersAndRender();
});
// Event delegation: star buttons are re-created on every render, so one
// listener on the (persistent) results body handles all of them.
resultsBody.addEventListener("click", (e) => {
  const btn = e.target.closest(".favorite-star");
  if (!btn) return;
  toggleFavorite(btn.dataset.courseId);
});

search();
